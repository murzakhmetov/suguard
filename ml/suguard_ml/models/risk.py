"""Diabetes risk screening: probabilities of elevated HbA1c (+ optional glucose evidence).

1. **Profile model** (trained on NHANES 2017-2018, laboratory HbA1c labels):
   P(HbA1c >= 5.7 %) and P(HbA1c >= 6.5 %) for an adult *without* a diabetes
   diagnosis, from age, sex, BMI, resting heart rate (measured by the
   bracelet), physical activity and ancestry (Asian, with an ancestry x BMI
   term, since Asian adults reach high HbA1c at a lower BMI; European).
   Without ancestry the model under-predicts for Asian and over-predicts for
   European participants; both groups matter for Kazakhstan. Logistic regression on a few
   transformed inputs: transparent, portable to Dart/JS, and calibrated in
   the pooled (unweighted) NHANES sample; per-subgroup calibration is in
   models/metrics/risk_cv.json. It estimates whether HbA1c is elevated *now*
   (cross-sectional), not future incidence.

2. **Glucose evidence** (off unless the caller states the glucose error is
   validated): the mean of >= 7 days of glucose estimates maps to an HbA1c
   estimate with the ADAG relation, HbA1c = (mean_mg/dL + 46.7) / 28.7
   (Nathan et al., Diabetes Care 2008; fitted on people with and without
   diabetes, unlike GMI, which reads ~0.5 % high in normoglycaemia). Bayes'
   rule combines it with the profile prior:

       P(class | x, a) ~ P(class | x) * integral p(a1c | class) N(a; a1c, s^2)

   with p(a1c | class) the NHANES HbA1c distributions inside each class and
   s^2 = (ADAG scatter)^2 + (mean error / 28.7)^2.

Missing optional inputs are marginalised: binary ones by averaging over both
values with population shares, resting HR by imputing it from age/sex/BMI.
Inputs the model does not use (waist, smoking) are reported back as unused.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

ADAG_INTERCEPT, ADAG_SLOPE = 46.7, 28.7     # eAG(mg/dL) = 28.7 * HbA1c - 46.7
ADAG_A1C_SD = 0.45                          # scatter of HbA1c around the ADAG line (%)
A1C_GRID = np.round(np.arange(4.0, 15.0 + 1e-9, 0.05), 2)


def design_row(age, male, bmi, waist_cm, pulse_bpm, active, smoker, asian=0.0, european=0.0) -> np.ndarray:
    """Model inputs. Kept in one place so training and inference agree."""
    lb = np.log(bmi / 28.0)
    return np.array([
        (age - 45.0) / 15.0,
        ((age - 45.0) / 15.0) ** 2,
        male,
        lb,
        (waist_cm - 98.0) / 15.0,
        (pulse_bpm - 72.0) / 12.0,
        active,
        smoker,
        asian,
        asian * lb,
        european,
    ], dtype=np.float64)


DESIGN_NAMES = ["age_z", "age_z2", "male", "log_bmi", "waist_z", "pulse_z", "active", "smoker",
                "asian", "asian_log_bmi", "european"]
ANCESTRIES = ("asian", "european", "other")
FACTOR_COLUMNS = {"age": ["age_z", "age_z2"], "sex": ["male"], "bmi": ["log_bmi", "asian_log_bmi"],
                  "waist": ["waist_z"], "resting_hr": ["pulse_z"], "activity": ["active"],
                  "smoking": ["smoker"], "ancestry": ["asian", "european"]}
INPUT_COLUMNS = {"waist_cm": "waist_z", "smoker": "smoker", "resting_hr_bpm": "pulse_z",
                 "physically_active": "active", "male": "male", "ancestry": "asian"}


@dataclass
class RiskInput:
    age: float
    bmi: float | None = None
    height_cm: float | None = None
    weight_kg: float | None = None
    male: bool | None = None
    waist_cm: float | None = None
    resting_hr_bpm: float | None = None
    physically_active: bool | None = None
    smoker: bool | None = None
    ancestry: str | None = None              # "asian" (East/South/Southeast/Central Asian), "european", "other"
    diagnosed_diabetes: bool = False

    def bmi_value(self) -> float:
        if self.bmi is not None:
            return float(self.bmi)
        if self.height_cm and self.weight_kg:
            return float(self.weight_kg / (self.height_cm / 100.0) ** 2)
        raise ValueError("need bmi or height_cm + weight_kg")


@dataclass
class GlucoseEvidence:
    mean_mgdl: float          # mean of the bracelet's glucose estimates
    error_sd_mgdl: float      # validated SD of the error of that mean (bias + noise)
    days: float               # wear time covered


class RiskModel:
    def __init__(self, spec: dict):
        self.spec = spec
        names = spec.get("design", DESIGN_NAMES)
        if names != DESIGN_NAMES:
            raise ValueError("risk_model.json was built for a different design; retrain it")
        self.coef = {k: np.asarray(v["coef"], dtype=np.float64) for k, v in spec["models"].items()}
        self.intercept = {k: float(v["intercept"]) for k, v in spec["models"].items()}
        self.used = set(spec.get("features_used", DESIGN_NAMES))
        self.imputers = spec["imputers"]
        self.prevalence = spec["binary_prevalence"]
        self.age_min, self.age_max = spec.get("age_range", [18.0, 80.0])
        self.a1c_density = {k: np.asarray(v, dtype=np.float64) for k, v in spec["a1c_density"].items()}

    @classmethod
    def load(cls, path: str | Path | None = None) -> "RiskModel":
        p = Path(path) if path else Path(__file__).resolve().parents[2] / "models" / "risk_model.json"
        return cls(json.loads(Path(p).read_text()))

    # --- helpers ------------------------------------------------------------
    def _impute(self, name: str, age: float, male: float, bmi: float) -> float:
        m = self.imputers[name]
        return float(m["intercept"] + m["age"] * age + m["male"] * male + m["bmi"] * bmi)

    def _prob(self, target: str, x: np.ndarray) -> float:
        z = self.intercept[target] + float(self.coef[target] @ x)
        return float(1.0 / (1.0 + np.exp(-z)))

    def _options(self, value, key: str, col: str) -> list[tuple[float, float]]:
        """(value, weight) pairs: the given value, or both values weighted by
        population share when unknown; a constant if the model ignores it."""
        if col not in self.used:
            return [(0.0, 1.0)]
        if value is not None:
            return [(float(value), 1.0)]
        p = self.prevalence[key]
        return [(1.0, p), (0.0, 1.0 - p)]

    def _ancestry_options(self, ancestry: str | None) -> list[tuple[float, float, float]]:
        """(asian, european, weight) triples; population shares if unanswered."""
        if "asian" not in self.used and "european" not in self.used:
            return [(0.0, 0.0, 1.0)]
        if ancestry is not None:
            if ancestry not in ANCESTRIES:
                raise ValueError(f"ancestry must be one of {ANCESTRIES}")
            return [(float(ancestry == "asian"), float(ancestry == "european"), 1.0)]
        pa, pe = self.prevalence["asian"], self.prevalence["european"]
        return [(1.0, 0.0, pa), (0.0, 1.0, pe), (0.0, 0.0, 1.0 - pa - pe)]

    def _clip(self, inp: RiskInput) -> tuple[float, float]:
        return float(np.clip(inp.age, self.age_min, self.age_max)), float(np.clip(inp.bmi_value(), 14, 70))

    # --- profile layer --------------------------------------------------------
    def profile_probs(self, inp: RiskInput) -> dict[str, float]:
        """P(HbA1c >= 5.7) and P(HbA1c >= 6.5), marginalising missing inputs."""
        age, bmi = self._clip(inp)
        out = {"dysglycemia": 0.0, "diabetes": 0.0}
        for male, w_s in self._options(inp.male, "male", "male"):
            pulse = inp.resting_hr_bpm if inp.resting_hr_bpm is not None else self._impute("pulse_bpm", age, male, bmi)
            pulse = float(np.clip(pulse, 40, 130))
            waist = inp.waist_cm if (inp.waist_cm is not None and "waist_z" in self.used) else 98.0
            for act, w_a in self._options(inp.physically_active, "active", "active"):
                for smk, w_k in self._options(inp.smoker, "smoker", "smoker"):
                    for asn, eur, w_n in self._ancestry_options(inp.ancestry):
                        x = design_row(age, male, bmi, float(waist), pulse, act, smk, asn, eur)
                        w = w_s * w_a * w_k * w_n
                        for t in out:
                            out[t] += w * self._prob(t, x)
        out["diabetes"] = min(out["diabetes"], out["dysglycemia"])
        return out

    # --- glucose evidence layer ------------------------------------------------
    def class_likelihoods(self, a1c_hat: float, sd: float) -> np.ndarray:
        """p(a1c_hat | normal), p(... | prediabetes), p(... | diabetes)."""
        kern = np.exp(-0.5 * ((a1c_hat - A1C_GRID) / sd) ** 2) / (sd * np.sqrt(2 * np.pi))
        return np.array([float(np.sum(self.a1c_density[c] * kern) * 0.05)
                         for c in ("normal", "prediabetes", "diabetes")])

    def predict(self, inp: RiskInput, glucose: GlucoseEvidence | None = None,
                glucose_validated: bool = False) -> dict:
        """``glucose`` is used only if ``glucose_validated`` (the caller owns a
        glucose model validated on this device and supplies its error)."""
        if inp.diagnosed_diabetes:
            return {"applicable": False, "reason": "diagnosed_diabetes",
                    "message": "Risk screening is for people without a diagnosis; use glucose monitoring instead."}
        prof = self.profile_probs(inp)
        prior = np.array([1 - prof["dysglycemia"], prof["dysglycemia"] - prof["diabetes"], prof["diabetes"]])
        post, used, a1c_hat, ignored = prior.copy(), False, None, None
        if glucose is not None:
            if not glucose_validated:
                ignored = "no glucose model validated on this device"
            elif not (glucose.days >= 7 and glucose.error_sd_mgdl and glucose.error_sd_mgdl > 0):
                ignored = "needs >= 7 days and a positive validated error SD"
            else:
                a1c_hat = (glucose.mean_mgdl + ADAG_INTERCEPT) / ADAG_SLOPE
                sd = float(np.hypot(ADAG_A1C_SD, glucose.error_sd_mgdl / ADAG_SLOPE))
                post = prior * self.class_likelihoods(a1c_hat, sd)
                post = post / post.sum() if post.sum() > 0 else prior
                used = True
        p_dys, p_dm = float(post[1] + post[2]), float(post[2])
        cat = category(p_dys, p_dm)
        not_used = [k for k, col in INPUT_COLUMNS.items()
                    if getattr(inp, k) is not None and col not in self.used]
        # Unanswered questions the model does use: the estimate is then the average over the
        # reference population (US adults, NHANES), which is not the user's own group. For
        # ancestry this matters: an Asian adult is underestimated by about a third.
        averaged = [k for k, col in (("male", "male"), ("physically_active", "active"), ("ancestry", "asian"))
                    if getattr(inp, k) is None and col in self.used]
        return {
            "applicable": True,
            "p_prediabetes_or_diabetes": p_dys,
            "p_diabetes": p_dm,
            "p_prediabetes": float(post[1]),
            "profile_only": {"p_prediabetes_or_diabetes": prof["dysglycemia"], "p_diabetes": prof["diabetes"]},
            "risk_score": round(100 * p_dys, 1),
            "risk_score_meaning": "estimated probability (%) that HbA1c is >= 5.7 % (prediabetes or diabetes) "
                                  "in an adult without a diagnosis; a screening estimate, not a diagnosis",
            "category": cat,
            "glucose_evidence_used": used,
            "glucose_evidence_ignored": ignored,
            "a1c_from_glucose_pct": None if a1c_hat is None else round(a1c_hat, 2),
            "inputs_not_used": not_used,
            "inputs_averaged_over_reference_population": averaged,
            "age_clipped": bool(inp.age > self.age_max or inp.age < self.age_min),
            "factors": self.explain(inp, target="diabetes" if (p_dm >= 0.10 and p_dys < 0.60) else "dysglycemia"),
        }

    def explain(self, inp: RiskInput, target: str = "dysglycemia") -> list[dict]:
        """Contribution of each *provided* input to the log-odds of ``target``,
        relative to a reference adult (45 y, BMI 25, HR 70, active, non-smoker,
        ancestry "other"), with the same clipping as the prediction. Unanswered
        inputs are not reported as factors."""
        age, bmi = self._clip(inp)
        ref = design_row(45, 0.5, 25.0, 98.0, 70.0, 1.0, 0.0, 0.0, 0.0)
        male = 0.5 if inp.male is None else float(inp.male)
        pulse = 70.0 if inp.resting_hr_bpm is None else float(np.clip(inp.resting_hr_bpm, 40, 130))
        act = 1.0 if inp.physically_active is None else float(inp.physically_active)
        smk = 0.0 if inp.smoker is None else float(inp.smoker)
        asn = float(inp.ancestry == "asian")
        eur = float(inp.ancestry == "european")
        waist = 98.0 if inp.waist_cm is None else float(inp.waist_cm)
        c = self.coef[target] * (design_row(age, male, bmi, waist, pulse, act, smk, asn, eur) - ref)
        idx = {n: i for i, n in enumerate(DESIGN_NAMES)}
        provided = {"age": True, "bmi": True, "sex": inp.male is not None, "waist": inp.waist_cm is not None,
                    "resting_hr": inp.resting_hr_bpm is not None, "activity": inp.physically_active is not None,
                    "smoking": inp.smoker is not None, "ancestry": inp.ancestry is not None}
        out = []
        for factor, cols in FACTOR_COLUMNS.items():
            if not provided[factor] or not any(col in self.used for col in cols):
                continue
            out.append({"factor": factor, "log_odds": round(float(sum(c[idx[col]] for col in cols)), 3),
                        "target": target})
        return sorted(out, key=lambda d: -abs(d["log_odds"]))


def category(p_dys: float, p_dm: float) -> str:
    """Coarse category for the app, from fixed probability cut-points.

    The observed HbA1c rates inside each category (out-of-fold on NHANES)
    are stored in models/metrics/risk_cv.json -> categories_oof.
    """
    if p_dys >= 0.60 or p_dm >= 0.10:
        return "high"
    if p_dys >= 0.40:
        return "elevated"
    if p_dys >= 0.20:
        return "moderate"
    return "low"
