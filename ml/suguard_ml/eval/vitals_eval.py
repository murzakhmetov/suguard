"""Downstream evaluation of a (denoised) window: heart rate and SpO2 errors."""

from __future__ import annotations

import numpy as np

from ..config import FS
from ..signal.beats import detect_beats, spectral_hr
from ..signal.spo2 import estimate_spo2


def vitals_from_bv(ir_bv: np.ndarray, red_bv: np.ndarray, fs: float = FS,
                   artifact_prob: np.ndarray | None = None) -> dict:
    """HR (peaks, falling back to a clean spectral peak) and SpO2 from
    blood-volume signals, without the reliability gates of the pipeline."""
    beats = detect_beats(ir_bv, fs)
    hr = beats.hr_bpm
    hr_spec, purity = spectral_hr(ir_bv, fs)
    if hr is None and purity >= 0.3:   # ungated evaluation only; the pipeline reports beat-based HR alone
        hr = hr_spec
    w = None if artifact_prob is None else 1.0 - artifact_prob
    sp = estimate_spo2(red_bv, ir_bv, weights=w)
    return {"hr": hr, "hr_spectral": hr_spec, "purity": purity, "spo2": sp.spo2, "r": sp.r_ratio,
            "red_ir_corr": sp.red_ir_corr,
            "artifact_frac": float(np.mean(artifact_prob > 0.5)) if artifact_prob is not None else None}


def summarize_errors(rows: list[dict], hr_true: np.ndarray, spo2_true: np.ndarray, keep: np.ndarray | None = None,
                     common: dict | None = None) -> dict:
    """Error summary that makes abstentions explicit.

    ``n`` = windows selected by ``keep``; per vital, ``n`` = windows the
    vital is scored over, ``n_scored`` = those that produced an estimate,
    ``abstain_rate`` = 1 - n_scored / n, and the "within" rate counts an
    abstention as a miss. Pass ``common`` (from :func:`both_finite`) to
    compare methods on the same windows: each vital is then scored only where
    *every* compared method produced that vital.
    """
    hr = np.array([np.nan if r["hr"] is None else r["hr"] for r in rows], dtype=float)
    sp = np.array([np.nan if r["spo2"] is None else r["spo2"] for r in rows], dtype=float)
    keep = np.ones(hr.size, dtype=bool) if keep is None else np.asarray(keep, dtype=bool)

    def stat(est, truth, key, thr):
        sel = keep if common is None else keep & np.asarray(common[key], dtype=bool)
        e = np.abs(est - truth)[sel]
        f = np.isfinite(e)
        n = int(sel.sum())
        out = {"n": n, "n_scored": int(f.sum()), "abstain_rate": float(1 - f.sum() / max(n, 1))}
        if f.any():
            out.update(mae=float(np.mean(e[f])), median=float(np.median(e[f])), p90=float(np.percentile(e[f], 90)))
        else:
            out.update(mae=None, median=None, p90=None)
        out["within_tol_counting_abstentions"] = float(np.sum(e[f] <= thr) / max(n, 1))
        return out

    return {"n": int(keep.sum()), "selected_fraction": float(keep.mean()) if keep.size else 0.0,
            "hr": stat(hr, hr_true, "hr", 5.0), "spo2": stat(sp, spo2_true, "spo2", 2.0)}


def both_finite(*row_lists: list[dict]) -> dict:
    """Per vital, the windows where every method produced it (like-for-like comparison)."""
    return {key: np.logical_and.reduce([[r[key] is not None for r in rows] for rows in row_lists])
            for key in ("hr", "spo2")}
