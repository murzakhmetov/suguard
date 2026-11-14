"""End-to-end analysis of raw MAX30102 recordings.

    from suguard_ml.pipeline import SuGuardPipeline
    pipe = SuGuardPipeline.load()                 # bundled models in ml/models
    res = pipe.analyze(red, ir, fs=100)           # raw 18-bit counts
    res["heart_rate"], res["spo2"], res["quality"], res["features"]

Steps: resample to 50 Hz -> sensor checks (contact, saturation) -> DC
normalisation and band-pass -> motion-artefact denoiser (falls back to the
classical path if no model is available or the window is shorter than
``MIN_DENOISER_S``) -> beats, heart rate, HRV, SpO2 -> quality index -> PPG
features for the glucose model.

Values are reported only when the window is reliable: sensor checks pass,
the pulse is measurably strong *in the input* (a denoiser can draw a pulse
into noise, so its output cannot vouch for itself), the denoiser flags at
most ``MAX_ARTIFACT_FRACTION`` of the window as motion, and every quality
component passes. Otherwise they are None with reasons, never a guess.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from .config import FS
from .models.denoiser import Denoiser
from .signal.beats import detect_beats, hrv_metrics, spectral_hr
from .signal.features import extract_features
from .signal.filters import preprocess, resample
from .signal.quality import assess_quality, sensor_state
from .signal.spo2 import estimate_spo2

MODELS_DIR = Path(__file__).resolve().parents[1] / "models"

# Share of the window the denoiser may flag as motion-dominated before the
# window is rejected (see models/metrics/denoiser_eval.json -> gate_sweep).
MAX_ARTIFACT_FRACTION = 0.5
# Minimum peak-to-peak IR perfusion (%) of the *input* signal.
MIN_INPUT_PI = 0.03
# Spectral HR is used as a fallback only with a clean, dominant peak.
MIN_SPECTRAL_PURITY = 0.3
# Shorter windows go through the classical path (the denoiser saw 10.24 s).
MIN_DENOISER_S = 6.0
MAX_NONFINITE_FRACTION = 0.02


def _clean_input(red_raw, ir_raw) -> tuple[np.ndarray, np.ndarray, int]:
    red = np.asarray(red_raw, dtype=np.float64).ravel()
    ir = np.asarray(ir_raw, dtype=np.float64).ravel()
    if red.shape != ir.shape:
        raise ValueError("red and ir must be 1-D arrays of equal length")
    bad = ~(np.isfinite(red) & np.isfinite(ir))
    if bad.any():
        if bad.mean() > MAX_NONFINITE_FRACTION or bad.all():
            raise ValueError(f"{int(bad.sum())} non-finite samples in the window")
        idx = np.arange(red.size)
        red = np.interp(idx, idx[~bad], red[~bad])
        ir = np.interp(idx, idx[~bad], ir[~bad])
    return red, ir, int(bad.sum())


class SuGuardPipeline:
    def __init__(self, denoiser: Denoiser | None = None, spo2_coeffs=None):
        self.denoiser = denoiser
        self.spo2_coeffs = spo2_coeffs

    @classmethod
    def load(cls, models_dir: str | Path | None = None) -> "SuGuardPipeline":
        d = Path(models_dir) if models_dir else MODELS_DIR
        den = Denoiser(d / "denoiser.onnx") if (d / "denoiser.onnx").exists() else None
        return cls(denoiser=den)

    def analyze(self, red_raw, ir_raw, fs: float = 100.0, temperature_c: float | None = None,
                prior_hr: float | None = None, include_signals: bool = False) -> dict:
        red_in, ir_in, n_bad = _clean_input(red_raw, ir_raw)
        red = resample(red_in, fs, FS)
        ir = resample(ir_in, fs, FS)
        if ir.size < 2 * FS:
            raise ValueError("need at least 2 s of data")
        duration = ir.size / FS
        sensor = sensor_state(red, ir)
        ir_bv, ir_dc = preprocess(ir, FS)
        red_bv, red_dc = preprocess(red, FS)
        pi_in = float(np.percentile(ir_bv, 97) - np.percentile(ir_bv, 3)) * 100.0

        if self.denoiser is not None and duration >= MIN_DENOISER_S:
            dn = self.denoiser.denoise_bv(ir_bv, red_bv, FS)
            c_ir, c_red, p_art = dn.ir_bv, dn.red_bv, dn.artifact_prob
            method = "denoiser"
        else:
            c_ir, c_red, p_art = ir_bv, red_bv, None
            method = "classical"

        beats = detect_beats(c_ir, FS)
        coeffs = {"coeffs": self.spo2_coeffs} if self.spo2_coeffs else {}
        sp = estimate_spo2(c_red, c_ir, weights=None if p_art is None else 1 - p_art, **coeffs)
        q = assess_quality(c_ir, c_red, beats, FS, artifact_prob=p_art, sensor=sensor,
                           red_ir_corr=sp.red_ir_corr)
        reasons = list(q.reasons)
        if pi_in < MIN_INPUT_PI and "weak_pulse" not in reasons:
            reasons.append("weak_pulse")
        reliable = bool(sensor.finger_detected and sensor.saturated_fraction <= 0.05
                        and q.motion_fraction <= MAX_ARTIFACT_FRACTION and pi_in >= MIN_INPUT_PI and q.usable)

        hr, hr_source = beats.hr_bpm, "beats"
        hr_spec, purity = spectral_hr(c_ir, FS, prior_bpm=prior_hr)
        if hr is None:
            hr, hr_source = (hr_spec, "spectrum") if purity >= MIN_SPECTRAL_PURITY else (None, None)
        if reliable and hr is None:
            reliable = False
            reasons.append("no_heart_rate")

        spo2_ok = reliable and q.usable_spo2
        spo2_val = sp.spo2 if spo2_ok else None
        out = {
            "method": method,
            "duration_s": round(duration, 2),
            "interpolated_samples": n_bad,
            "sensor": {"finger_detected": sensor.finger_detected,
                       "saturated_fraction": round(sensor.saturated_fraction, 4),
                       "ir_dc": round(sensor.ir_dc), "red_dc": round(sensor.red_dc)},
            "quality": {k: (round(v, 4) if isinstance(v, float) and np.isfinite(v) else v)
                        for k, v in q.to_dict().items()},
            "reliable": reliable,
            "heart_rate": {"bpm": round(hr, 1) if (reliable and hr) else None,
                           "source": hr_source if reliable else None,
                           "beats": int(beats.peaks.size)},
            "spo2": {"percent": round(spo2_val, 1) if spo2_val is not None else None,
                     "r_ratio": round(sp.r_ratio, 4) if (spo2_ok and sp.r_ratio is not None) else None,
                     "reason": None if spo2_val is not None else (
                         (sp.reason or "red_ir_inconsistent") if reliable else "unreliable_window"),
                     "calibration": "device" if self.spo2_coeffs else "maxim_reference_curve_uncalibrated"},
            "hrv": hrv_metrics(beats.ibi_s, beats.valid_ibi) if (reliable and duration >= 60) else None,
            "features": None,
        }
        if spo2_ok:
            # Features include red/IR ratios, so they need the SpO2-grade gate.
            feats = extract_features(c_ir, c_red, FS, artifact_prob=p_art, ir_dc=float(np.median(ir_dc)),
                                     red_dc=float(np.median(red_dc)), temperature_c=temperature_c)
            out["features"] = {k: (None if (isinstance(v, float) and not np.isfinite(v)) else v)
                               for k, v in feats.items()}
            out["feature_span_s"] = round(duration, 2)
        if not reliable:
            out["reason"] = sorted(set(reasons)) or ["unreliable"]
        if include_signals:
            out["signals"] = {"fs": FS, "ir_clean": c_ir.tolist(), "red_clean": c_red.tolist(),
                              "artifact_prob": None if p_art is None else p_art.tolist()}
        return out
