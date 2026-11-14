"""SuGuard ML inference API.

    uvicorn api.app:app --host 0.0.0.0 --port 8000      (from the ml/ folder)

Endpoints
    GET  /health                    models loaded, versions
    POST /v1/analyze                raw MAX30102 window -> quality, HR, SpO2,
                                    HRV, PPG features, glucose estimate
    POST /v1/glucose/calibrate      add a fingerstick -> new calibration state
    POST /v1/risk                   profile + resting HR (+ glucose evidence)
                                    -> diabetes risk

The API is stateless: the per-user calibration state is returned to the
client, which stores it (e.g. Firebase users/<uid>/mlCalibration) and sends
it back with later requests.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, model_validator

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from suguard_ml import __version__  # noqa: E402
from suguard_ml.config import ADC_MAX  # noqa: E402
from suguard_ml.models.glucose import GlucoseEstimator, PersonalCalibration  # noqa: E402
from suguard_ml.models.risk import GlucoseEvidence, RiskInput, RiskModel  # noqa: E402
from suguard_ml.pipeline import SuGuardPipeline  # noqa: E402

MODELS = Path(__file__).resolve().parents[1] / "models"

app = FastAPI(title="SuGuard ML", version=__version__,
              description="Motion-robust PPG analysis for the MAX30102 bracelet, glucose estimation "
                          "with personal calibration, and diabetes risk screening. Not a medical device.")

PIPE = SuGuardPipeline.load(MODELS)
GLUCOSE = GlucoseEstimator.load(MODELS)
RISK = RiskModel.load(MODELS / "risk_model.json") if (MODELS / "risk_model.json").exists() else None


# --- schemas ---------------------------------------------------------------

class Context(BaseModel):
    minutes_since_meal: Optional[float] = Field(None, ge=0)
    carbs_last_meal_g: Optional[float] = Field(None, ge=0)
    carbs_3h_g: Optional[float] = Field(None, ge=0)
    age: Optional[float] = Field(None, ge=10, le=110)
    bmi: Optional[float] = Field(None, ge=10, le=80)
    male: Optional[bool] = None


class AnalyzeRequest(BaseModel):
    fs: float = Field(100.0, ge=25, le=1000, description="MAX30102 output sample rate, Hz")
    red: list[float] = Field(..., description="raw red counts (18-bit)")
    ir: list[float] = Field(..., description="raw IR counts (18-bit)")
    timestamp: Optional[float] = Field(None, description="unix seconds of the first sample")
    temperature_c: Optional[float] = Field(None, description="MAX30102 die temperature")
    prior_hr: Optional[float] = Field(None, ge=30, le=220, description="previous window's HR, for tracking")
    tz_offset_h: float = Field(5.0, ge=-12, le=14, description="user's UTC offset (Kazakhstan: +5)")
    context: Optional[Context] = None
    calibration: Optional[dict] = Field(None, description="state returned by /v1/glucose/calibrate")
    include_signals: bool = False

    @model_validator(mode="after")
    def _check(self):
        if len(self.red) != len(self.ir):
            raise ValueError("red and ir must have the same length")
        dur = len(self.ir) / self.fs
        if not 2.0 <= dur <= 300.0:
            raise ValueError(f"window must be 2-300 s long, got {dur:.1f} s")
        lo = min(min(self.red), min(self.ir))
        hi = max(max(self.red), max(self.ir))
        if lo < 0 or hi > ADC_MAX:
            raise ValueError("samples must be raw 18-bit counts (0..262143)")
        return self


class CalibrateRequest(BaseModel):
    reference_mgdl: float = Field(..., ge=20, le=600, description="glucometer reading")
    timestamp: float = Field(..., description="unix seconds of the fingerstick")
    features: Optional[dict] = Field(None, description="features from /v1/analyze near the fingerstick")
    tz_offset_h: float = Field(5.0, ge=-12, le=14)
    context: Optional[Context] = None
    calibration: Optional[dict] = None


class GlucoseEvidenceIn(BaseModel):
    mean_mgdl: float = Field(..., ge=40, le=500)
    error_sd_mgdl: float = Field(..., gt=0, le=200, description="validated SD of the mean's error")
    days: float = Field(..., ge=0)


class RiskRequest(BaseModel):
    age: float = Field(..., ge=18, le=100)
    bmi: Optional[float] = Field(None, ge=12, le=80)
    height_cm: Optional[float] = Field(None, ge=100, le=230)
    weight_kg: Optional[float] = Field(None, ge=25, le=300)
    male: Optional[bool] = None
    waist_cm: Optional[float] = Field(None, ge=40, le=200)
    resting_hr_bpm: Optional[float] = Field(None, ge=35, le=150)
    physically_active: Optional[bool] = None
    smoker: Optional[bool] = None
    diagnosed_diabetes: bool = False
    glucose: Optional[GlucoseEvidenceIn] = None

    @model_validator(mode="after")
    def _need_bmi(self):
        if self.bmi is None and not (self.height_cm and self.weight_kg):
            raise ValueError("provide bmi or height_cm + weight_kg")
        return self


# --- endpoints ---------------------------------------------------------------

@app.get("/health")
def health():
    return {
        "status": "ok", "version": __version__,
        "denoiser": PIPE.denoiser is not None,
        "glucose_model": None if GLUCOSE.model is None else {
            "version": GLUCOSE.model.meta.get("version"), "validated": GLUCOSE.model.validated},
        "risk_model": None if RISK is None else RISK.spec.get("version"),
    }


def _model_features(feats: dict | None, ctx: Context | None, t: float | None, tz_offset_h: float) -> dict:
    """Model inputs: PPG features + context + local hour of day (as in training)."""
    import math

    out = dict(feats or {})
    if ctx is not None:
        out.update({k: (float(v) if v is not None else None) for k, v in ctx.model_dump().items()})
    if t is not None:
        h = (t / 3600.0 + tz_offset_h) % 24.0
        out["hour_sin"], out["hour_cos"] = math.sin(2 * math.pi * h / 24), math.cos(2 * math.pi * h / 24)
    return out


@app.post("/v1/analyze")
def analyze(req: AnalyzeRequest):
    t0 = time.perf_counter()
    try:
        res = PIPE.analyze(req.red, req.ir, fs=req.fs, temperature_c=req.temperature_c,
                           prior_hr=req.prior_hr, include_signals=req.include_signals)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    cal = PersonalCalibration.from_dict(req.calibration)
    t = req.timestamp or time.time()
    if res["features"] is not None:
        res["glucose"] = GLUCOSE.estimate(_model_features(res["features"], req.context, t, req.tz_offset_h), cal, t,
                                          sqi=res["quality"]["sqi"])
    else:
        res["glucose"] = {"status": "poor_signal", "mg_dl": None}
    res["latency_ms"] = round((time.perf_counter() - t0) * 1000, 1)
    res["disclaimer"] = "Research prototype, not a medical device. Do not use for treatment decisions."
    return res


@app.post("/v1/glucose/calibrate")
def calibrate(req: CalibrateRequest):
    cal = PersonalCalibration.from_dict(req.calibration)
    if GLUCOSE.model is not None and req.features:
        f, _, _ = GLUCOSE.model.predict(_model_features(req.features, req.context, req.timestamp, req.tz_offset_h))
    else:
        f = cal.f0
    before = cal.predict(f, req.timestamp)[0]
    cal.update(f, req.reference_mgdl, req.timestamp)
    return {"calibration": cal.to_dict(), "n_points": cal.n_points,
            "estimate_before_mgdl": round(before, 1), "reference_mgdl": req.reference_mgdl}


@app.post("/v1/risk")
def risk(req: RiskRequest):
    if RISK is None:
        raise HTTPException(503, "risk model not available")
    inp = RiskInput(age=req.age, bmi=req.bmi, height_cm=req.height_cm, weight_kg=req.weight_kg, male=req.male,
                    waist_cm=req.waist_cm, resting_hr_bpm=req.resting_hr_bpm,
                    physically_active=req.physically_active, smoker=req.smoker,
                    diagnosed_diabetes=req.diagnosed_diabetes)
    ev = None if req.glucose is None else GlucoseEvidence(**req.glucose.model_dump())
    out = RISK.predict(inp, ev)
    out["model"] = {"version": RISK.spec.get("version"), "validation": {
        k: {"auc": v["auc"], "auc_95ci": v["auc_95ci"]} for k, v in RISK.spec.get("validation", {}).items()}}
    out["disclaimer"] = "Screening estimate, not a diagnosis. Confirm with an HbA1c or fasting glucose test."
    return out
