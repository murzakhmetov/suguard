"""Glucose estimation: population model + per-user calibration + honest status.

Why this structure: subject-independent studies show that PPG features alone
do not predict glucose across people (models collapse to near-zero R^2 once
the same person is never in both train and test; Reassessing the Feasibility
of PPG-Based Non-Invasive Blood Glucose Level Estimation, arXiv 2608.01820).
What does work in the literature is *personalisation*: a population model
supplies a prior, and a few fingerstick readings per user calibrate it.

* ``GlucosePopulationModel`` - LightGBM median + 10/90 % quantile models on
  PPG features and context (time of day, time since last meal and its carbs,
  age, BMI). Trained only on real paired data (scripts/train_glucose.py).
  Its metadata records whether it beat the trivial baseline in
  subject-independent validation (``validated``).
* ``PersonalCalibration`` - Kalman filter on y = a + b * f + noise, where f is
  the population prediction (or a constant if there is none). Each
  fingerstick updates (a, b); process noise lets them drift as the strap
  moves or physiology changes.
* ``GlucoseEstimator`` - combines both and returns a status that the caller
  must respect: "unavailable" (no model, no calibration -> no number),
  "calibration_only" (no model: the level of the user's own fingersticks, no
  number from the bracelet), "experimental" (a model that has not passed
  validation on this bracelet: a number for research use; the API withholds
  it unless the operator switches it on), "uncalibrated", "calibrated".
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import ClassVar

import numpy as np

PRIOR_MEAN_MGDL = 105.0          # typical fasting/postprandial mix, non-diabetic adult
GLUCOMETER_CV = 0.05             # ISO 15197-grade meter, ~5 % CV
SUGUARD_DEVICE = "suguard_max30102"   # meta_source of tables recorded with the bracelet


# ---------------------------------------------------------------------------
# Population model
# ---------------------------------------------------------------------------

class GlucosePopulationModel:
    def __init__(self, boosters: dict, features: list[str], meta: dict):
        self.boosters = boosters          # {"q50": Booster, "q10": ..., "q90": ...}
        self.features = features
        self.meta = meta

    @property
    def validated(self) -> bool:
        """Validated *for this device*: a model validated on another sensor
        (e.g. Empatica E4 green PPG in BIG IDEAs) stays experimental here."""
        return bool(self.meta.get("validated", False)) and self.meta.get("validated_on_device") == SUGUARD_DEVICE

    @property
    def version(self) -> str | None:
        return self.meta.get("version")

    @classmethod
    def load(cls, model_dir: str | Path) -> "GlucosePopulationModel | None":
        d = Path(model_dir)
        meta_path = d / "glucose_model.json"
        if not meta_path.exists():
            return None
        import lightgbm as lgb

        meta = json.loads(meta_path.read_text())
        boosters = {q: lgb.Booster(model_file=str(d / f"glucose_{q}.txt")) for q in ("q10", "q50", "q90")}
        return cls(boosters, meta["features"], meta)

    def save(self, model_dir: str | Path) -> None:
        d = Path(model_dir)
        d.mkdir(parents=True, exist_ok=True)
        for q, b in self.boosters.items():
            b.save_model(str(d / f"glucose_{q}.txt"))
        (d / "glucose_model.json").write_text(json.dumps({**self.meta, "features": self.features}, indent=1))

    def _row(self, feats: dict) -> np.ndarray:
        return np.array([[np.nan if feats.get(f) is None else float(feats[f]) for f in self.features]])

    def predict(self, feats: dict) -> tuple[float, float, float]:
        x = self._row(feats)
        q = {k: float(b.predict(x)[0]) for k, b in self.boosters.items()}
        lo, mid, hi = sorted((q["q10"], q["q50"], q["q90"]))
        return mid, lo, hi


# ---------------------------------------------------------------------------
# Personal calibration
# ---------------------------------------------------------------------------

# Limits of a calibration state. update() never produces a state outside them
# and from_dict() refuses one, so a state the server issued is always accepted
# back, and a corrupted or hand-made one cannot yield absurd numbers.
REFERENCE_RANGE_MGDL = (20.0, 600.0)   # fingerstick values a calibration accepts
A_LIMIT = 500.0                        # |level offset|, mg/dL: spans the reference range around the prior mean
B_RANGE = (0.0, 3.0)                   # scale of the model's deviations
P_LIMIT = (1000.0**2, 10.0**2)         # variances of a and b
RESID_VAR_RANGE = (4.0, 60.0**2)
# What is not explained by the level (and the model, if there is one), before anything is known
# about the person: glucose moves by tens of mg/dL around its running level over a day. Too small
# a start makes the first intervals too narrow for exactly the people whose glucose varies most.
RESID_PRIOR_SD = 30.0
# Before the first fingerstick nothing is known about the person's level: someone with diabetes may
# run at twice the prior mean. A narrow prior (it was 30 mg/dL) made the filter explain the first,
# large innovations as noise and then converge slowly (readings of 600 mg/dL, two a day: 406 / 487 /
# 593 after 3 / 10 / 40, against 572 / 595 / 600 with this prior; check_model_card.py,
# calibration_level_prior).
LEVEL_PRIOR_SD = 100.0
RESID_PRIOR_WEIGHT = 3                 # the start value counts as this many fingersticks
RESID_MIN_WEIGHT = 0.1                 # later on: a slow running average
MAX_POINTS = 100_000
MAX_DRIFT_DAYS = 365.0                 # a longer gap adds no further uncertainty
UNIX_RANGE = (1.5e9, 4.1e9)            # unix seconds a new request may carry (rejects millisecond epochs)
STATE_T_RANGE = (0.0, UNIX_RANGE[1])   # ... and a stored state (older research recordings are fine)


@dataclass
class PersonalCalibration:
    """Kalman filter on theta = (a, b) in  y = a + b * (f - f0) + f0.

    With a population prediction f, b scales its deviations from f0 and a
    shifts the level. Without a model, f == f0 and only a is identified: the
    estimate becomes the user's own running glucose level.

    The dataclass fields are the state a client stores between requests; the
    reference level and the drift rates are constants of the algorithm.
    """
    a: float = 0.0
    b: float = 1.0
    P: list = field(default_factory=lambda: [[LEVEL_PRIOR_SD**2, 0.0], [0.0, 0.3**2]])
    resid_var: float = RESID_PRIOR_SD**2  # variance of what the state does not explain, updated online
    n_points: int = 0
    last_t: float | None = None          # unix seconds of the latest update
    model_version: str | None = None     # population model the state was fitted against

    f0: ClassVar[float] = PRIOR_MEAN_MGDL
    drift_a_per_day: ClassVar[float] = 6.0**2      # process noise (mg/dL)^2 / day
    drift_b_per_day: ClassVar[float] = 0.03**2

    def _predict_state(self, t: float | None) -> np.ndarray:
        P = np.array(self.P, dtype=float)
        if t is not None and self.last_t is not None and math.isfinite(t) and math.isfinite(self.last_t):
            days = min(max(t - self.last_t, 0.0) / 86400.0, MAX_DRIFT_DAYS)
            P = P + np.diag([self.drift_a_per_day * days, self.drift_b_per_day * days])
        return P

    def predict(self, f: float, t: float | None = None) -> tuple[float, float]:
        """Calibrated estimate and its SD (mg/dL)."""
        P = self._predict_state(t)
        h = np.array([1.0, f - self.f0])
        y = self.f0 + self.a + self.b * (f - self.f0)
        var = float(h @ P @ h) + self.resid_var
        return float(y), math.sqrt(max(var, 0.0))

    def update(self, f: float, y_ref: float, t: float | None = None) -> "PersonalCalibration":
        """Assimilate one fingerstick. A reading older than the newest one
        (entered late) is used with correspondingly less weight: the state
        has drifted since it was taken."""
        P = self._predict_state(t)
        h = np.array([1.0, f - self.f0])
        y_hat = self.f0 + self.a + self.b * (f - self.f0)
        r = (GLUCOMETER_CV * y_ref) ** 2 + self.resid_var
        late = t is not None and self.last_t is not None and t < self.last_t
        if late:
            days_back = min((self.last_t - t) / 86400.0, MAX_DRIFT_DAYS)
            r += float(h @ np.diag([self.drift_a_per_day * days_back, self.drift_b_per_day * days_back]) @ h)
        predicted_var = float(h @ P @ h)
        s = predicted_var + r
        k = P @ h / s
        innov = y_ref - y_hat
        theta = np.array([self.a, self.b]) + k * innov
        P = (np.eye(2) - np.outer(k, h)) @ P
        P = 0.5 * (P + P.T)                                  # rounding must not break the symmetry
        P *= min(1.0, P_LIMIT[0] / max(P[0, 0], 1e-300), P_LIMIT[1] / max(P[1, 1], 1e-300))
        # Online estimate of what the state does not explain: E[innovation^2] = predicted variance
        # + meter variance + that, so the excess estimates the last term. The first fingersticks
        # count fully against the start value, later ones enter a slow running average. (The
        # estimate is right if the level drifts as assumed; for a level that does not drift it
        # comes out low and the predicted variance high by the same amount, so the interval keeps
        # its coverage: see tests/test_models.py::test_calibration_interval_coverage.)
        if self.n_points >= 2 and not late:
            excess = innov**2 - predicted_var - (GLUCOMETER_CV * y_ref) ** 2
            w = max(RESID_MIN_WEIGHT, 1.0 / (RESID_PRIOR_WEIGHT + self.n_points - 1))
            self.resid_var = float(np.clip((1.0 - w) * self.resid_var + w * excess, *RESID_VAR_RANGE))
        self.a = float(np.clip(theta[0], -A_LIMIT, A_LIMIT))
        self.b = float(np.clip(theta[1], *B_RANGE))
        self.P = P.tolist()
        self.n_points = min(self.n_points + 1, MAX_POINTS)
        if t is not None and STATE_T_RANGE[0] <= t <= STATE_T_RANGE[1]:
            self.last_t = float(t) if self.last_t is None else max(self.last_t, float(t))  # never runs backwards
        return self

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def parse(cls, d: dict) -> "PersonalCalibration":
        """A state sent back by a client, every field validated and brought to
        its canonical type. Unknown keys are ignored; malformed or implausible
        values raise ValueError."""
        def real(v) -> float:
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                raise ValueError("not a number")
            x = float(v)                                      # OverflowError for integers beyond a double
            if not math.isfinite(x):
                raise ValueError("not finite")
            return x

        try:
            if not isinstance(d, dict):
                raise ValueError("not an object")
            rows = d.get("P", cls().P)
            if not (isinstance(rows, (list, tuple)) and len(rows) == 2
                    and all(isinstance(r, (list, tuple)) and len(r) == 2 for r in rows)):
                raise ValueError("P must be 2 x 2")
            P = np.array([[real(x) for x in r] for r in rows])
            n = d.get("n_points", 0)
            if isinstance(n, bool) or not isinstance(n, int):
                raise ValueError("n_points must be an integer")
            version = d.get("model_version")
            if version is not None and not (isinstance(version, str) and len(version) <= 100):
                raise ValueError("model_version must be a short string")
            c = cls(a=real(d.get("a", 0.0)), b=real(d.get("b", 1.0)), P=P.tolist(),
                    resid_var=real(d.get("resid_var", RESID_PRIOR_SD**2)), n_points=n,
                    last_t=None if d.get("last_t") is None else real(d["last_t"]), model_version=version)
        except (TypeError, ValueError, OverflowError) as e:
            raise ValueError(f"invalid calibration state: {e}") from e
        ok = bool(np.abs(P).max() <= max(P_LIMIT) * (1 + 1e-9) and np.allclose(P, P.T, rtol=1e-9, atol=1e-9))
        if ok:
            eig = np.linalg.eigvalsh(0.5 * (P + P.T))
            ok = eig[0] >= -1e-9 * max(1.0, eig[-1])
        ok = (ok and P[0, 0] <= P_LIMIT[0] * (1 + 1e-9) and P[1, 1] <= P_LIMIT[1] * (1 + 1e-9)
              and -A_LIMIT <= c.a <= A_LIMIT and B_RANGE[0] <= c.b <= B_RANGE[1]
              and RESID_VAR_RANGE[0] <= c.resid_var <= RESID_VAR_RANGE[1] and 0 <= c.n_points <= MAX_POINTS
              and (c.last_t is None or STATE_T_RANGE[0] <= c.last_t <= STATE_T_RANGE[1]))
        if not ok:
            raise ValueError("invalid calibration state: value out of range")
        return c

    @classmethod
    def from_dict(cls, d: dict | None, model_version: str | None = None) -> "PersonalCalibration":
        """``parse`` plus the version rule: no state, or a state fitted against
        a different population model, gives a fresh calibration (the old
        offsets do not apply to the new model)."""
        if not d:
            return cls(model_version=model_version)
        c = cls.parse(d)
        return c if c.model_version == model_version else cls(model_version=model_version)


# ---------------------------------------------------------------------------
# Estimator
# ---------------------------------------------------------------------------

class GlucoseEstimator:
    MIN_CALIBRATIONS = 3

    def __init__(self, model: GlucosePopulationModel | None):
        self.model = model

    @classmethod
    def load(cls, model_dir: str | Path | None = None) -> "GlucoseEstimator":
        d = Path(model_dir) if model_dir else Path(__file__).resolve().parents[2] / "models"
        return cls(GlucosePopulationModel.load(d))

    def estimate(self, feats: dict, calibration: PersonalCalibration | None = None,
                 t: float | None = None, sqi: float | None = None) -> dict:
        cal = calibration or PersonalCalibration()
        if sqi is not None and sqi < 0.5:
            return {"status": "poor_signal", "mg_dl": None,
                    "message": "Signal quality too low (motion or poor contact); keep still and retry."}
        if self.model is None:
            if cal.n_points >= self.MIN_CALIBRATIONS:
                y, sd = cal.predict(cal.f0, t)
                return {"status": "calibration_only", "mg_dl": None,
                        "fingerstick_average_mgdl": round(y, 1),
                        "interval_80": [round(y - 1.2816 * sd, 1), round(y + 1.2816 * sd, 1)],
                        "message": "No glucose model: this is the average of your recent fingerstick readings, "
                                   "not a reading from the bracelet."}
            return {"status": "unavailable", "mg_dl": None,
                    "message": "No glucose model trained on paired data yet; add fingerstick readings "
                               "to collect training data (docs/DATA_COLLECTION.md)."}
        f, lo, hi = self.model.predict(feats)
        if cal.n_points >= self.MIN_CALIBRATIONS:
            y, sd = cal.predict(f, t)
            status = "calibrated" if self.model.validated else "experimental"
            interval = [y - 1.2816 * sd, y + 1.2816 * sd]
        else:
            y = f
            status = "uncalibrated" if self.model.validated else "experimental"
            interval = [lo, hi]
        return {"status": status, "mg_dl": round(y, 1), "mmol_l": round(y / 18.0, 2),
                "interval_80": [round(v, 1) for v in interval],
                "population_estimate": round(f, 1), "calibrations": cal.n_points,
                "model_version": self.model.meta.get("version")}
