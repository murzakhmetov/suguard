"""SuGuard ML inference API.

    uvicorn api.app:app --host 0.0.0.0 --port 8000      (from the ml/ folder)

Endpoints
    GET  /health                    models loaded, versions
    POST /v1/analyze                raw MAX30102 window -> quality, HR, SpO2, HRV,
                                    PPG features (only for reliable windows)
    POST /v1/glucose/estimate       features of >= 3 recent reliable windows
                                    (+ calibration state) -> glucose with status
    POST /v1/glucose/calibrate      fingerstick + the same window features
                                    -> new calibration state
    POST /v1/risk                   profile + resting HR -> diabetes-risk screening

The API is stateless: the per-user calibration state is returned to the
client, which stores it (e.g. Firebase users/<uid>/mlCalibration) and sends
it back. It is validated on every request. Set the environment variable
SUGUARD_STATE_KEY (any long random string, the same for every worker) to
have the server sign the states it issues and refuse any other: without it
a client can hand in a state it made up (the values are still range-checked).
"""

from __future__ import annotations

import hashlib
import hmac
import json
import math
import os
import sys
import time
from pathlib import Path
from typing import Literal, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, model_validator

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from suguard_ml import __version__  # noqa: E402
from suguard_ml.config import ADC_MAX  # noqa: E402
from suguard_ml.aggregation import FEATURE_AGGREGATION, aggregate_window_features  # noqa: E402
from suguard_ml.models.glucose import (  # noqa: E402
    REFERENCE_RANGE_MGDL,
    UNIX_RANGE,
    GlucoseEstimator,
    PersonalCalibration,
)
from suguard_ml.models.risk import GlucoseEvidence, RiskInput, RiskModel  # noqa: E402
from suguard_ml.pipeline import SuGuardPipeline  # noqa: E402

MODELS = Path(__file__).resolve().parents[1] / "models"
MAX_SAMPLES = 60_000            # per channel: 5 min at 200 Hz
MAX_BODY_BYTES = 2_000_000      # ~2 x 60k samples x 9 chars, with margin
UNIX_MIN, UNIX_MAX = UNIX_RANGE     # seconds; rejects millisecond epochs
STATE_KEY = os.environ.get("SUGUARD_STATE_KEY", "").encode() or None
# Features every SpO2-grade /v1/analyze window carries; a window without them is a placeholder.
CORE_FEATURES = ("hr_bpm", "pi_ir", "r_ratio")
DISCLAIMER = "Research prototype, not a medical device. Do not use for diagnosis or treatment decisions."


class BodySizeLimit:
    """Reject oversized bodies before they are read and parsed (413)."""

    def __init__(self, app, max_bytes: int = MAX_BODY_BYTES):
        self.app, self.max_bytes = app, max_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        cl = dict(scope.get("headers") or []).get(b"content-length")
        if cl is not None and cl.isdigit() and int(cl) > self.max_bytes:
            return await JSONResponse({"detail": "request body too large"}, status_code=413)(scope, receive, send)
        seen = 0

        async def limited_receive():
            nonlocal seen
            msg = await receive()
            if msg["type"] == "http.request":
                seen += len(msg.get("body", b""))
                if seen > self.max_bytes:
                    raise HTTPException(413, "request body too large")
            return msg

        return await self.app(scope, limited_receive, send)


app = FastAPI(title="SuGuard ML", version=__version__,
              description="Motion-robust PPG analysis for the MAX30102 bracelet, glucose estimation "
                          "with personal calibration, and diabetes-risk screening. Not a medical device.")
app.add_middleware(BodySizeLimit)


@app.exception_handler(RequestValidationError)
async def _validation_error(_: Request, exc: RequestValidationError):
    """422 without echoing the input: the default handler returns the whole
    payload (tens of thousands of samples), and crashes on NaN values."""
    errs = [{"loc": [str(x) for x in e.get("loc", ())], "msg": str(e.get("msg", "")), "type": e.get("type")}
            for e in exc.errors()]
    return JSONResponse(status_code=422, content={"detail": errs})


def _finite(obj):
    """Replace NaN/inf anywhere in a response with None (JSON has no NaN)."""
    if isinstance(obj, float):
        return obj if math.isfinite(obj) else None
    if isinstance(obj, dict):
        return {k: _finite(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_finite(v) for v in obj]
    return obj


PIPE = SuGuardPipeline.load(MODELS)
GLUCOSE = GlucoseEstimator.load(MODELS)
RISK = RiskModel.load(MODELS / "risk_model.json") if (MODELS / "risk_model.json").exists() else None
MODEL_VERSION = GLUCOSE.model.version if GLUCOSE.model is not None else None


# --- schemas ---------------------------------------------------------------

class Context(BaseModel):
    minutes_since_meal: Optional[float] = Field(None, ge=0, le=100_000, allow_inf_nan=False)
    carbs_last_meal_g: Optional[float] = Field(None, ge=0, le=1000, allow_inf_nan=False)
    carbs_3h_g: Optional[float] = Field(None, ge=0, le=2000, allow_inf_nan=False)
    age: Optional[float] = Field(None, ge=10, le=110, allow_inf_nan=False)
    bmi: Optional[float] = Field(None, ge=10, le=80, allow_inf_nan=False)
    male: Optional[bool] = None


class AnalyzeRequest(BaseModel):
    fs: float = Field(100.0, ge=25, le=1000, allow_inf_nan=False, description="MAX30102 output rate, Hz")
    red: list[float] = Field(..., max_length=MAX_SAMPLES, description="raw red counts (18-bit)")
    ir: list[float] = Field(..., max_length=MAX_SAMPLES, description="raw IR counts (18-bit)")
    timestamp: Optional[float] = Field(None, ge=UNIX_MIN, le=UNIX_MAX, allow_inf_nan=False,
                                       description="unix seconds of the first sample")
    temperature_c: Optional[float] = Field(None, ge=-20, le=80, allow_inf_nan=False)
    include_signals: bool = False

    @model_validator(mode="after")
    def _check(self):
        if len(self.red) != len(self.ir):
            raise ValueError("red and ir must have the same length")
        dur = len(self.ir) / self.fs
        if not 2.0 <= dur <= 300.0:
            raise ValueError(f"window must be 2-300 s long, got {dur:.1f} s")
        # NaN/inf would pass min/max comparisons silently; reject explicitly.
        if not all(0.0 <= v <= ADC_MAX for v in self.red) or not all(0.0 <= v <= ADC_MAX for v in self.ir):
            raise ValueError("samples must be finite raw 18-bit counts (0..262143)")
        return self


class GlucoseRequest(BaseModel):
    recent_features: list[dict] = Field(..., min_length=1, max_length=120,
                                        description="'features' of reliable /v1/analyze windows, newest last")
    timestamp: float = Field(..., ge=UNIX_MIN, le=UNIX_MAX, allow_inf_nan=False)
    tz_offset_h: float = Field(5.0, ge=-12, le=14, allow_inf_nan=False, description="UTC offset (Kazakhstan +5)")
    context: Optional[Context] = None
    calibration: Optional[dict] = Field(None, description="state returned by /v1/glucose/calibrate")


class CalibrateRequest(GlucoseRequest):
    recent_features: list[dict] = Field(default_factory=list, max_length=120,
                                        description="window features around the fingerstick (needed once a "
                                                    "glucose model is installed)")
    reference_mgdl: float = Field(..., ge=REFERENCE_RANGE_MGDL[0], le=REFERENCE_RANGE_MGDL[1], allow_inf_nan=False,
                                  description="glucometer reading")


class RiskRequest(BaseModel):
    age: float = Field(..., ge=18, le=110, allow_inf_nan=False)
    bmi: Optional[float] = Field(None, ge=12, le=80, allow_inf_nan=False)
    height_cm: Optional[float] = Field(None, ge=100, le=230, allow_inf_nan=False)
    weight_kg: Optional[float] = Field(None, ge=25, le=300, allow_inf_nan=False)
    male: Optional[bool] = None
    ancestry: Optional[Literal["asian", "european", "other"]] = None
    resting_hr_bpm: Optional[float] = Field(None, ge=35, le=150, allow_inf_nan=False)
    physically_active: Optional[bool] = None
    waist_cm: Optional[float] = Field(None, ge=40, le=200, allow_inf_nan=False)
    smoker: Optional[bool] = None
    diagnosed_diabetes: bool = False

    @model_validator(mode="after")
    def _need_bmi(self):
        if self.bmi is None and not (self.height_cm and self.weight_kg):
            raise ValueError("provide bmi or height_cm + weight_kg")
        return self


# --- helpers -------------------------------------------------------------------

def _signature(cal: PersonalCalibration) -> str:
    """HMAC over the canonical form of a state (types fixed by PersonalCalibration.parse,
    so 30 and 30.0 from a client's JSON library sign the same)."""
    body = json.dumps(cal.to_dict(), sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hmac.new(STATE_KEY, body.encode(), hashlib.sha256).hexdigest()


def _issue(cal: PersonalCalibration) -> dict:
    """The state as sent to the client, signed if a key is configured."""
    state = cal.to_dict()
    if STATE_KEY is not None:
        state["sig"] = _signature(cal)
    return state


def _calibration(state: dict | None) -> PersonalCalibration:
    if not state:
        return PersonalCalibration(model_version=MODEL_VERSION)
    try:
        cal = PersonalCalibration.parse(state)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    if STATE_KEY is not None:
        sig = state.get("sig")
        if not isinstance(sig, str) or not hmac.compare_digest(sig.encode(), _signature(cal).encode()):
            raise HTTPException(422, "calibration state was not issued by this server")
    # A state fitted against another population model does not apply to this one.
    return cal if cal.model_version == MODEL_VERSION else PersonalCalibration(model_version=MODEL_VERSION)


def _model_features(windows: list[dict], ctx: Context | None, t: float, tz_offset_h: float) -> dict:
    """Training-equivalent inputs: median over windows + context + local hour."""
    out = aggregate_window_features(windows)
    if ctx is not None:
        out.update({k: (float(v) if v is not None else None) for k, v in ctx.model_dump().items()})
    h = (t / 3600.0 + tz_offset_h) % 24.0
    out["hour_sin"], out["hour_cos"] = math.sin(2 * math.pi * h / 24), math.cos(2 * math.pi * h / 24)
    return out


def _check_windows(windows: list[dict]) -> None:
    """The 'features' of >= 3 distinct SpO2-grade /v1/analyze windows."""
    need = FEATURE_AGGREGATION["min_windows"]
    if len(windows) < need:
        raise HTTPException(422, f"need features of >= {need} reliable 10.24-s windows (got {len(windows)})")

    def number(v) -> bool:
        try:
            return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)
        except OverflowError:                       # an integer beyond the range of a double
            return False

    for w in windows:
        if not isinstance(w, dict) or len(w) > 200 or not all(v is None or number(v) for v in w.values()):
            raise HTTPException(422, "each window's features must be a flat dict of finite numbers")
        if not all(number(w.get(k)) for k in CORE_FEATURES):
            raise HTTPException(422, f"each window needs the features {', '.join(CORE_FEATURES)} "
                                     "(send the 'features' object of a reliable /v1/analyze result)")
    if len({json.dumps(w, sort_keys=True) for w in windows}) < need:
        raise HTTPException(422, f"need >= {need} different windows, not copies of one")


# --- endpoints ---------------------------------------------------------------

@app.get("/health")
def health():
    return {
        "status": "ok", "version": __version__,
        "denoiser": PIPE.denoiser is not None,
        "glucose_model": None if GLUCOSE.model is None else {
            "version": GLUCOSE.model.version, "validated_on_this_device": GLUCOSE.model.validated},
        "risk_model": None if RISK is None else RISK.spec.get("version"),
        "calibration_states_signed": STATE_KEY is not None,
    }


@app.post("/v1/analyze")
def analyze(req: AnalyzeRequest):
    t0 = time.perf_counter()
    try:
        res = PIPE.analyze(req.red, req.ir, fs=req.fs, temperature_c=req.temperature_c,
                           include_signals=req.include_signals)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    res["timestamp"] = req.timestamp if req.timestamp is not None else time.time()
    res["latency_ms"] = round((time.perf_counter() - t0) * 1000, 1)
    res["disclaimer"] = DISCLAIMER
    return _finite(res)


@app.post("/v1/glucose/estimate")
def glucose_estimate(req: GlucoseRequest):
    _check_windows(req.recent_features)
    cal = _calibration(req.calibration)
    feats = _model_features(req.recent_features, req.context, req.timestamp, req.tz_offset_h)
    out = GLUCOSE.estimate(feats, cal, req.timestamp)
    out["windows_used"] = len(req.recent_features)
    out["disclaimer"] = DISCLAIMER
    return _finite(out)


@app.post("/v1/glucose/calibrate")
def calibrate(req: CalibrateRequest):
    cal = _calibration(req.calibration)
    if GLUCOSE.model is not None:
        # The calibration maps the model's output to the reference, so it must
        # see the model output for the same moment (training-equivalent input).
        _check_windows(req.recent_features)
        f, _, _ = GLUCOSE.model.predict(_model_features(req.recent_features, req.context, req.timestamp,
                                                        req.tz_offset_h))
    else:
        f = cal.f0
    before = cal.predict(f, req.timestamp)[0]
    cal.update(f, req.reference_mgdl, req.timestamp)
    return _finite({"calibration": _issue(cal), "n_points": cal.n_points,
                    "estimate_before_mgdl": round(before, 1), "reference_mgdl": req.reference_mgdl})


@app.post("/v1/risk")
def risk(req: RiskRequest):
    if RISK is None:
        raise HTTPException(503, "risk model not available")
    inp = RiskInput(age=req.age, bmi=req.bmi, height_cm=req.height_cm, weight_kg=req.weight_kg, male=req.male,
                    waist_cm=req.waist_cm, resting_hr_bpm=req.resting_hr_bpm, ancestry=req.ancestry,
                    physically_active=req.physically_active, smoker=req.smoker,
                    diagnosed_diabetes=req.diagnosed_diabetes)
    # Glucose evidence is deliberately not accepted from clients: it would be
    # used only with a glucose model validated on this device, whose error the
    # server knows; no such model exists yet.
    out = RISK.predict(inp)
    out["model"] = {"version": RISK.spec.get("version"), "validation": {
        k: {"auc": v["auc"], "auc_95ci": v["auc_95ci"]} for k, v in RISK.spec.get("validation", {}).items()}}
    out["disclaimer"] = "Screening estimate, not a diagnosis. Confirm with an HbA1c or fasting glucose test."
    return _finite(out)
