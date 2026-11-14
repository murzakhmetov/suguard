"""Diabetes risk: calibrated screening probabilities plus glucose evidence.

Two layers:

1. **Profile model** (trained on NHANES, laboratory HbA1c labels):
   P(HbA1c >= 5.7 %) and P(HbA1c >= 6.5 %) for an adult without a diabetes
   diagnosis, from age, sex, BMI, waist, resting heart rate (measured by the
   bracelet) and two lifestyle answers. Logistic regression on a small set
   of transformed inputs, so it is transparent, calibrated and trivially
   portable to Dart/JS (the exported JSON holds everything needed).

2. **Glucose evidence** (optional): if the bracelet's glucose estimates have
   a *validated* error, their mean over >= 7 days gives the Glucose
   Management Indicator GMI = 3.31 + 0.02392 * mean_mg/dL (Bergenstal 2018),
   an estimate of HbA1c. Bayes' rule combines it with the profile prior:

       P(class | x, gmi) ~ P(class | x) * integral p(a1c | class) N(gmi; a1c, s^2)

   where p(a1c | class) are the NHANES HbA1c distributions inside each
   class and s^2 = (GMI-HbA1c discordance)^2 + (0.02392 * mean error)^2.
   Unvalidated glucose (no error estimate) is ignored, so a poor glucose
   model cannot inflate the risk.

Missing optional inputs are marginalised: binary ones by averaging over both
values with NHANES prevalences, waist and pulse by imputing them from the
rest (linear models fitted on NHANES).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

GMI_INTERCEPT, GMI_SLOPE = 3.31, 0.02392
GMI_A1C_SD = 0.45   # SD of HbA1c - GMI between individuals (Bergenstal et al., Diabetes Care 2018)
A1C_GRID = np.round(np.arange(4.0, 15.0 + 1e-9, 0.05), 2)


def design_row(age, male, bmi, waist_cm, pulse_bpm, active, smoker) -> np.ndarray:
    """Model inputs. Kept in one place so training and inference agree."""
    return np.array([
        (age - 45.0) / 15.0,
        ((age - 45.0) / 15.0) ** 2,
        male,
        np.log(bmi / 28.0),
        (waist_cm - 98.0) / 15.0,
        (pulse_bpm - 72.0) / 12.0,
        active,
        smoker,
    ], dtype=np.float64)


DESIGN_NAMES = ["age_z", "age_z2", "male", "log_bmi", "waist_z", "pulse_z", "active", "smoker"]


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
        self.coef = {k: np.asarray(v["coef"], dtype=np.float64) for k, v in spec["models"].items()}
        self.intercept = {k: float(v["intercept"]) for k, v in spec["models"].items()}
        self.imputers = spec["imputers"]
        self.prevalence = spec["binary_prevalence"]
        self.a1c_density = {k: np.asarray(v, dtype=np.float64) for k, v in spec["a1c_density"].items()}

    @classmethod
    def load(cls, path: str | Path | None = None) -> "RiskModel":
        p = Path(path) if path else Path(__file__).resolve().parents[2] / "models" / "risk_model.json"
        return cls(json.loads(Path(p).read_text()))

    # --- profile layer -------------------------------------------------
    def _impute(self, name: str, age: float, male: float, bmi: float) -> float:
        m = self.imputers[name]
        return float(m["intercept"] + m["age"] * age + m["male"] * male + m["bmi"] * bmi)

    def _prob(self, target: str, x: np.ndarray) -> float:
        z = self.intercept[target] + float(self.coef[target] @ x)
        return float(1.0 / (1.0 + np.exp(-z)))

    def profile_probs(self, inp: RiskInput) -> dict[str, float]:
        """P(HbA1c >= 5.7) and P(HbA1c >= 6.5), marginalising missing inputs."""
        age = float(np.clip(inp.age, 18, 90))
        bmi = float(np.clip(inp.bmi_value(), 14, 70))
        sexes = [(float(inp.male), 1.0)] if inp.male is not None else \
            [(1.0, self.prevalence["male"]), (0.0, 1 - self.prevalence["male"])]
        acts = [(float(inp.physically_active), 1.0)] if inp.physically_active is not None else \
            [(1.0, self.prevalence["active"]), (0.0, 1 - self.prevalence["active"])]
        smks = [(float(inp.smoker), 1.0)] if inp.smoker is not None else \
            [(1.0, self.prevalence["smoker"]), (0.0, 1 - self.prevalence["smoker"])]
        out = {"dysglycemia": 0.0, "diabetes": 0.0}
        for male, w_s in sexes:
            waist = inp.waist_cm if inp.waist_cm is not None else self._impute("waist_cm", age, male, bmi)
            pulse = inp.resting_hr_bpm if inp.resting_hr_bpm is not None else self._impute("pulse_bpm", age, male, bmi)
            pulse = float(np.clip(pulse, 40, 130))
            for act, w_a in acts:
                for smk, w_k in smks:
                    x = design_row(age, male, bmi, float(waist), pulse, act, smk)
                    w = w_s * w_a * w_k
                    for t in out:
                        out[t] += w * self._prob(t, x)
        out["diabetes"] = min(out["diabetes"], out["dysglycemia"])
        return out

    # --- glucose evidence layer -----------------------------------------
    def class_likelihoods(self, gmi: float, sd: float) -> np.ndarray:
        """p(gmi | normal), p(gmi | prediabetes), p(gmi | diabetes)."""
        kern = np.exp(-0.5 * ((gmi - A1C_GRID) / sd) ** 2) / (sd * np.sqrt(2 * np.pi))
        return np.array([float(np.sum(self.a1c_density[c] * kern) * 0.05)
                         for c in ("normal", "prediabetes", "diabetes")])

    def predict(self, inp: RiskInput, glucose: GlucoseEvidence | None = None) -> dict:
        if inp.diagnosed_diabetes:
            return {"applicable": False, "reason": "diagnosed_diabetes",
                    "message": "Risk screening is for people without a diagnosis; use glucose monitoring instead."}
        prof = self.profile_probs(inp)
        prior = np.array([1 - prof["dysglycemia"], prof["dysglycemia"] - prof["diabetes"], prof["diabetes"]])
        post, used, gmi = prior.copy(), False, None
        if glucose is not None and glucose.days >= 7 and glucose.error_sd_mgdl is not None:
            gmi = GMI_INTERCEPT + GMI_SLOPE * glucose.mean_mgdl
            sd = float(np.hypot(GMI_A1C_SD, GMI_SLOPE * glucose.error_sd_mgdl))
            like = self.class_likelihoods(gmi, sd)
            post = prior * like
            post = post / post.sum() if post.sum() > 0 else prior
            used = True
        p_dys = float(post[1] + post[2])
        p_dm = float(post[2])
        return {
            "applicable": True,
            "p_prediabetes_or_diabetes": p_dys,
            "p_diabetes": p_dm,
            "p_prediabetes": float(post[1]),
            "profile_only": {"p_prediabetes_or_diabetes": prof["dysglycemia"], "p_diabetes": prof["diabetes"]},
            "risk_score": round(100 * p_dys, 1),
            "category": category(p_dys, p_dm),
            "glucose_evidence_used": used,
            "gmi_pct": None if gmi is None else round(gmi, 2),
            "factors": self.explain(inp),
        }

    def explain(self, inp: RiskInput) -> list[dict]:
        """Per-input contribution to the log-odds of dysglycaemia, relative to
        a reference adult (45 y, BMI 25, waist 90 cm, HR 70, active, non-smoker)."""
        ref = design_row(45, 0.5, 25.0, 90.0, 70.0, 1.0, 0.0)
        age = float(np.clip(inp.age, 18, 90))
        bmi = inp.bmi_value()
        male = 0.5 if inp.male is None else float(inp.male)
        waist = inp.waist_cm if inp.waist_cm is not None else self._impute("waist_cm", age, male, bmi)
        pulse = inp.resting_hr_bpm if inp.resting_hr_bpm is not None else self._impute("pulse_bpm", age, male, bmi)
        act = self.prevalence["active"] if inp.physically_active is None else float(inp.physically_active)
        smk = self.prevalence["smoker"] if inp.smoker is None else float(inp.smoker)
        x = design_row(age, male, bmi, float(waist), float(pulse), act, smk)
        c = self.coef["dysglycemia"] * (x - ref)
        groups = {"age": c[0] + c[1], "sex": c[2], "bmi": c[3], "waist": c[4], "resting_hr": c[5],
                  "activity": c[6], "smoking": c[7]}
        return sorted(({"factor": k, "log_odds": round(float(v), 3)} for k, v in groups.items()),
                      key=lambda d: -abs(d["log_odds"]))


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
