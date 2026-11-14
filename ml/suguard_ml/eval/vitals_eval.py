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
    if hr is None and purity >= 0.3:   # same fallback rule as the pipeline
        hr = hr_spec
    w = None if artifact_prob is None else 1.0 - artifact_prob
    sp = estimate_spo2(red_bv, ir_bv, weights=w)
    return {"hr": hr, "hr_spectral": hr_spec, "purity": purity, "spo2": sp.spo2, "r": sp.r_ratio,
            "red_ir_corr": sp.red_ir_corr,
            "artifact_frac": float(np.mean(artifact_prob > 0.5)) if artifact_prob is not None else None}


def summarize_errors(rows: list[dict], hr_true: np.ndarray, spo2_true: np.ndarray, keep: np.ndarray | None = None,
                     common: np.ndarray | None = None) -> dict:
    """Error summary that makes abstentions explicit.

    ``n`` = windows selected by ``keep``; per vital, ``n_scored`` = windows
    that produced an estimate, ``abstain_rate`` = 1 - n_scored / n, and the
    "within" rates count an abstention as a miss. Pass ``common`` (windows
    where *all* compared methods produced an estimate) to compare methods on
    the same windows.
    """
    hr = np.array([np.nan if r["hr"] is None else r["hr"] for r in rows], dtype=float)
    sp = np.array([np.nan if r["spo2"] is None else r["spo2"] for r in rows], dtype=float)
    keep = np.ones(hr.size, dtype=bool) if keep is None else np.asarray(keep, dtype=bool)
    if common is not None:
        keep = keep & np.asarray(common, dtype=bool)
    n = int(keep.sum())
    e_hr = np.abs(hr - hr_true)[keep]
    e_sp = np.abs(sp - spo2_true)[keep]

    def stat(e, thr):
        f = np.isfinite(e)
        out = {"n_scored": int(f.sum()), "abstain_rate": float(1 - f.sum() / max(n, 1))}
        if f.any():
            out.update(mae=float(np.mean(e[f])), median=float(np.median(e[f])), p90=float(np.percentile(e[f], 90)))
        else:
            out.update(mae=None, median=None, p90=None)
        out["within_tol_counting_abstentions"] = float(np.sum(e[f] <= thr) / max(n, 1))
        return out

    return {"n": n, "selected_fraction": float(keep.mean()) if keep.size else 0.0,
            "hr": stat(e_hr, 5.0), "spo2": stat(e_sp, 2.0)}


def both_finite(*row_lists: list[dict]) -> np.ndarray:
    """Windows where every method produced HR (for like-for-like HR comparison)."""
    m = None
    for rows in row_lists:
        f = np.array([r["hr"] is not None for r in rows])
        m = f if m is None else (m & f)
    return m
