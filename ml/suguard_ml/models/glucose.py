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
* ``GlucoseEstimator`` - combines both and returns a status that the app must
  respect: "unavailable" (no model, no calibration -> no number),
  "experimental" (model not validated), "uncalibrated", "calibrated".
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np

PRIOR_MEAN_MGDL = 105.0          # typical fasting/postprandial mix, non-diabetic adult
GLUCOMETER_CV = 0.05             # ISO 15197-grade meter, ~5 % CV


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
        return bool(self.meta.get("validated", False))

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

@dataclass
class PersonalCalibration:
    """Kalman filter on theta = (a, b) in  y = a + b * (f - f0) + f0.

    With a population prediction f, b scales its deviations from f0 and a
    shifts the level. Without a model, f == f0 and only a is identified: the
    estimate becomes the user's own running glucose level.
    """
    a: float = 0.0
    b: float = 1.0
    P: list = field(default_factory=lambda: [[30.0**2, 0.0], [0.0, 0.3**2]])
    f0: float = PRIOR_MEAN_MGDL
    resid_var: float = 15.0**2           # model error variance, updated online
    n_points: int = 0
    last_t: float | None = None          # unix seconds of last update
    drift_a_per_day: float = 6.0**2      # process noise (mg/dL)^2 / day
    drift_b_per_day: float = 0.03**2

    def _predict_state(self, t: float | None) -> np.ndarray:
        P = np.array(self.P, dtype=float)
        if t is not None and self.last_t is not None:
            days = max(t - self.last_t, 0.0) / 86400.0
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
        P = self._predict_state(t)
        h = np.array([1.0, f - self.f0])
        y_hat = self.f0 + self.a + self.b * (f - self.f0)
        r = (GLUCOMETER_CV * y_ref) ** 2 + self.resid_var
        s = float(h @ P @ h) + r
        k = P @ h / s
        innov = y_ref - y_hat
        theta = np.array([self.a, self.b]) + k * innov
        P = (np.eye(2) - np.outer(k, h)) @ P
        # Online estimate of the model's own error (bounded, slow).
        if self.n_points >= 2:
            excess = innov**2 - float(h @ P @ h) - (GLUCOMETER_CV * y_ref) ** 2
            self.resid_var = float(np.clip(0.9 * self.resid_var + 0.1 * max(excess, 4.0), 4.0, 60.0**2))
        self.a, self.b = float(theta[0]), float(np.clip(theta[1], 0.0, 3.0))
        self.P = P.tolist()
        self.n_points += 1
        self.last_t = t if t is not None else self.last_t
        return self

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict | None) -> "PersonalCalibration":
        return cls(**d) if d else cls()


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
                return {"status": "calibration_only", "mg_dl": round(y, 1),
                        "interval_80": [round(y - 1.2816 * sd, 1), round(y + 1.2816 * sd, 1)],
                        "message": "No trained glucose model: this is your recent level from fingerstick "
                                   "calibrations, not a live measurement."}
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
