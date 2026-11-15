"""How per-window PPG features become one input row of the glucose model.

Shared by the training-table builders (suguard_ml.data) and by the inference
API, which must not need pandas for it.
"""

from __future__ import annotations

import math

import numpy as np

# Features whose value depends on how long the analysed span was (beat counts,
# HRV over a variable number of beats) rather than on physiology. They differ
# between training tables and serving, so they never enter the model.
LENGTH_DEPENDENT = {"n_beats", "sdnn_ms", "rmssd_ms", "pnn50", "excluded_intervals"}
# Every feature row is the median over >= MIN_WINDOWS reliable 10.24-s windows,
# both when building training tables and when serving (/v1/glucose/estimate).
FEATURE_AGGREGATION = {"window_s": 10.24, "statistic": "median", "min_windows": 3}


def _number(v) -> float | None:
    """A finite float, or None for anything else (missing, text, NaN, inf, huge integers)."""
    try:
        x = float(v)
    except (TypeError, ValueError, OverflowError):
        return None
    return x if math.isfinite(x) else None


def aggregate_window_features(feature_dicts: list[dict]) -> dict:
    """Median of per-window features (the FEATURE_AGGREGATION rule); None
    where no window has a finite value."""
    keys = dict.fromkeys(k for d in feature_dicts for k in d)        # union, first-seen order
    out = {}
    for k in keys:
        vals = [x for x in (_number(d.get(k)) for d in feature_dicts) if x is not None]
        out[k] = float(np.median(vals)) if vals else None
    return out
