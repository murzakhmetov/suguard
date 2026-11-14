"""End-to-end analysis of raw MAX30102 recordings.

    from suguard_ml.pipeline import SuGuardPipeline
    pipe = SuGuardPipeline.load()                 # bundled models in ml/models
    res = pipe.analyze(red, ir, fs=100)           # raw 18-bit counts
    res["heart_rate"], res["spo2"], res["quality"], res["features"]

Steps: resample to 50 Hz -> sensor checks (contact, saturation) -> DC
normalisation and band-pass -> motion-artefact denoiser (falls back to the
classical path if no model is available) -> beats, heart rate, HRV, SpO2 ->
quality index -> PPG features for the glucose model.
Values are reported only when the window is reliable; otherwise they are
None with a reason, never a guess.
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

# A window is reported only if the denoiser flags at most this share of it as
# motion-dominated (tuned on the held-out simulated test set, see
# scripts/eval_denoiser.py and models/metrics/denoiser_eval.json).
MAX_ARTIFACT_FRACTION = 0.5


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
        red = resample(np.asarray(red_raw, dtype=np.float64), fs, FS)
        ir = resample(np.asarray(ir_raw, dtype=np.float64), fs, FS)
        if ir.size < 2 * FS:
            raise ValueError("need at least 2 s of data")
        sensor = sensor_state(red, ir)
        ir_bv, ir_dc = preprocess(ir, FS)
        red_bv, red_dc = preprocess(red, FS)

        if self.denoiser is not None:
            dn = self.denoiser.denoise_bv(ir_bv, red_bv, FS)
            c_ir, c_red, p_art = dn.ir_bv, dn.red_bv, dn.artifact_prob
            method = "denoiser"
        else:
            c_ir, c_red, p_art = ir_bv, red_bv, None
            method = "classical"

        beats = detect_beats(c_ir, FS)
        sp = estimate_spo2(c_red, c_ir, weights=None if p_art is None else 1 - p_art,
                           **({"coeffs": self.spo2_coeffs} if self.spo2_coeffs else {}))
        q = assess_quality(c_ir, c_red, beats, FS, artifact_prob=p_art, sensor=sensor,
                           red_ir_corr=sp.red_ir_corr)
        reliable = sensor.finger_detected and sensor.saturated_fraction <= 0.05 and q.motion_fraction <= MAX_ARTIFACT_FRACTION
        if p_art is None:
            reliable = reliable and q.usable

        hr = beats.hr_bpm
        hr_spec, purity = spectral_hr(c_ir, FS, prior_bpm=prior_hr)
        hr_source = "beats"
        if hr is None:
            hr, hr_source = hr_spec, "spectrum"
        good_ibi = beats.ibi_s[beats.valid_ibi]
        duration = ir.size / FS

        out = {
            "method": method,
            "duration_s": round(duration, 2),
            "sensor": {"finger_detected": sensor.finger_detected,
                       "saturated_fraction": round(sensor.saturated_fraction, 4),
                       "ir_dc": round(sensor.ir_dc), "red_dc": round(sensor.red_dc)},
            "quality": {k: (round(v, 4) if isinstance(v, float) else v) for k, v in q.to_dict().items()},
            "reliable": bool(reliable),
            "heart_rate": {"bpm": round(hr, 1) if (hr and reliable) else None,
                           "source": hr_source, "spectral_bpm": round(hr_spec, 1) if hr_spec else None,
                           "beats": int(beats.peaks.size)},
            "spo2": {"percent": round(sp.spo2, 1) if (sp.spo2 and reliable) else None,
                     "r_ratio": round(sp.r_ratio, 4) if sp.r_ratio is not None else None,
                     "calibration": "device" if self.spo2_coeffs else "maxim_reference_curve"},
            "hrv": hrv_metrics(good_ibi) if (reliable and duration >= 60) else None,
            "features": None,
        }
        if reliable:
            feats = extract_features(c_ir, c_red, FS, artifact_prob=p_art, ir_dc=float(np.median(ir_dc)),
                                     red_dc=float(np.median(red_dc)), temperature_c=temperature_c)
            out["features"] = {k: (None if (isinstance(v, float) and not np.isfinite(v)) else v)
                               for k, v in feats.items()}
        else:
            out["reason"] = q.reasons or ["unreliable"]
        if include_signals:
            out["signals"] = {"fs": FS, "ir_clean": c_ir.tolist(), "red_clean": c_red.tolist(),
                              "artifact_prob": None if p_art is None else p_art.tolist()}
        return out
