"""Accuracy metrics for glucose estimates (all inputs in mg/dL).

Always report them next to a trivial baseline (e.g. predicting the training
mean): in published PPG-glucose work, Clarke A+B above 90 % and a MARD of
~15 % are often reached by the baseline itself, because most readings sit in
a narrow normoglycaemic range.
"""

from __future__ import annotations

import numpy as np


def clarke_zones(ref: np.ndarray, pred: np.ndarray) -> np.ndarray:
    """Clarke error grid zone per pair ('A'..'E'), standard boundaries."""
    ref = np.asarray(ref, dtype=float)
    pred = np.asarray(pred, dtype=float)
    out = np.empty(ref.size, dtype="<U1")
    for i, (r, p) in enumerate(zip(ref, pred)):
        if (r <= 70 and p <= 70) or (0.8 * r <= p <= 1.2 * r):
            out[i] = "A"
        elif (r >= 180 and p <= 70) or (r <= 70 and p >= 180):
            out[i] = "E"
        elif (70 <= r <= 290 and p >= r + 110) or (130 <= r <= 180 and p <= (7 / 5) * r - 182):
            out[i] = "C"
        elif (r >= 240 and 70 <= p <= 180) or (r <= 175 / 3 and 70 <= p <= 180) or (175 / 3 <= r <= 70 and p >= (6 / 5) * r):
            out[i] = "D"
        else:
            out[i] = "B"
    return out


def iso15197_within(ref: np.ndarray, pred: np.ndarray, tol_abs: float = 15.0, tol_rel: float = 0.15) -> np.ndarray:
    """ISO 15197:2013 accuracy criterion per pair: within +-15 mg/dL below
    100 mg/dL, within +-15 % at or above (requirement: >= 95 % of pairs)."""
    ref = np.asarray(ref, dtype=float)
    err = np.abs(np.asarray(pred, dtype=float) - ref)
    return np.where(ref < 100, err <= tol_abs, err <= tol_rel * ref)


def glucose_metrics(ref: np.ndarray, pred: np.ndarray) -> dict:
    ref = np.asarray(ref, dtype=float)
    pred = np.asarray(pred, dtype=float)
    ok = np.isfinite(ref) & np.isfinite(pred) & (ref > 0)
    ref, pred = ref[ok], pred[ok]
    if ref.size == 0:
        return {"n": 0}
    err = pred - ref
    ard = np.abs(err) / ref * 100.0
    zones = clarke_zones(ref, pred)
    ss_res = float(np.sum(err**2))
    ss_tot = float(np.sum((ref - ref.mean()) ** 2))
    r = float(np.corrcoef(ref, pred)[0, 1]) if ref.size > 2 and np.std(pred) > 0 and np.std(ref) > 0 else None
    return {
        "n": int(ref.size),
        "mae_mgdl": float(np.mean(np.abs(err))),
        "rmse_mgdl": float(np.sqrt(np.mean(err**2))),
        "bias_mgdl": float(np.mean(err)),
        "mard_pct": float(np.mean(ard)),
        "median_ard_pct": float(np.median(ard)),
        "r2": float(1 - ss_res / ss_tot) if ss_tot > 0 else None,
        "pearson_r": r,
        "iso15197_pct": float(np.mean(iso15197_within(ref, pred)) * 100),
        "within_20_20_pct": float(np.mean(iso15197_within(ref, pred, 20.0, 0.20)) * 100),
        "clarke_pct": {z: float(np.mean(zones == z) * 100) for z in "ABCDE"},
        "clarke_ab_pct": float(np.mean(np.isin(zones, ["A", "B"])) * 100),
    }


def mmol_to_mgdl(x):
    return np.asarray(x, dtype=float) * 18.0


def mgdl_to_mmol(x):
    return np.asarray(x, dtype=float) / 18.0
