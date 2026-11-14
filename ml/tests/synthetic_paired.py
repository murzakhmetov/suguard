"""Synthetic paired tables used ONLY to test the glucose training code.

They are positive/negative controls for the evaluation logic, not data about
glucose physiology: in the positive control the features are constructed to
contain glucose, in the negative control they are pure noise.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def make_table(signal: bool, n_subjects: int = 12, per_subject: int = 160, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    t0 = 1_700_000_000.0
    for s in range(n_subjects):
        level = rng.normal(110, 18)
        t = np.sort(rng.uniform(0, 7 * 86400, per_subject)) + t0
        # Meals at random clock times, so time of day carries no information.
        meals = np.sort(rng.uniform(t0, t0 + 8 * 86400, 24))
        for ti in t:
            since = ti - meals[meals <= ti].max() if (meals <= ti).any() else 1e5
            meal = 45 * np.exp(-((since / 3600 - 0.75) ** 2) / 0.5)
            g = level + meal + rng.normal(0, 8)
            f1 = (g - level) * 0.05 + rng.normal(0, 0.4) if signal else rng.normal(0, 1)
            f2 = level * 0.02 + rng.normal(0, 0.3) if signal else rng.normal(0, 1)
            rows.append({"subject_id": f"s{s}", "timestamp": ti, "glucose_mgdl": g,
                         "f1": f1, "f2": f2, "noise1": rng.normal(), "noise2": rng.normal()})
    return pd.DataFrame(rows)
