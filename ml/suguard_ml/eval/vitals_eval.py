"""Downstream evaluation of a (denoised) window: heart rate and SpO2 errors."""

from __future__ import annotations

import numpy as np

from ..config import FS
from ..signal.beats import detect_beats, spectral_hr
from ..signal.spo2 import estimate_spo2


def vitals_from_bv(ir_bv: np.ndarray, red_bv: np.ndarray, fs: float = FS,
                   artifact_prob: np.ndarray | None = None) -> dict:
    """HR (peaks, falling back to spectrum) and SpO2 from blood-volume signals."""
    beats = detect_beats(ir_bv, fs)
    hr = beats.hr_bpm
    hr_spec, purity = spectral_hr(ir_bv, fs)
    if hr is None:
        hr = hr_spec
    w = None if artifact_prob is None else 1.0 - artifact_prob
    sp = estimate_spo2(red_bv, ir_bv, weights=w)
    return {"hr": hr, "hr_spectral": hr_spec, "purity": purity, "spo2": sp.spo2, "r": sp.r_ratio,
            "red_ir_corr": sp.red_ir_corr,
            "artifact_frac": float(np.mean(artifact_prob > 0.5)) if artifact_prob is not None else None}


def summarize_errors(rows: list[dict], hr_true: np.ndarray, spo2_true: np.ndarray, keep: np.ndarray | None = None) -> dict:
    hr = np.array([np.nan if r["hr"] is None else r["hr"] for r in rows], dtype=float)
    sp = np.array([np.nan if r["spo2"] is None else r["spo2"] for r in rows], dtype=float)
    if keep is None:
        keep = np.ones(hr.size, dtype=bool)
    e_hr = np.abs(hr - hr_true)[keep]
    e_sp = np.abs(sp - spo2_true)[keep]

    def stat(e):
        e = e[np.isfinite(e)]
        if e.size == 0:
            return {"mae": None, "median": None, "p90": None}
        return {"mae": float(np.mean(e)), "median": float(np.median(e)), "p90": float(np.percentile(e, 90))}

    return {
        "n": int(keep.sum()),
        "coverage": float(keep.mean()),
        "hr": stat(e_hr),
        "hr_within_5bpm": float(np.mean(e_hr[np.isfinite(e_hr)] <= 5.0)) if np.isfinite(e_hr).any() else None,
        "spo2": stat(e_sp),
        "spo2_within_2pct": float(np.mean(e_sp[np.isfinite(e_sp)] <= 2.0)) if np.isfinite(e_sp).any() else None,
    }
