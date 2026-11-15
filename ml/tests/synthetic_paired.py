"""Synthetic paired tables used ONLY to test the glucose training code.

They are positive/negative controls for the evaluation logic, not data about
glucose physiology: in the positive control the features are constructed to
contain glucose, in the negative control they are pure noise.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def make_table(signal: bool, n_subjects: int = 12, per_subject: int = 160, seed: int = 0, scheduled: bool = True,
               ppg: bool = True, source: str | None = None) -> pd.DataFrame:
    """``scheduled``: every person also has a reading at 07:35 and 19:35 each
    day (the fingerstick times of the personalised protocol), as a person
    wearing a CGM would. ``ppg=False`` leaves only the context column.
    ``source`` fills ``meta_source``."""
    rng = np.random.default_rng(seed)
    rows = []
    t0 = 1_700_000_000.0 - 1_700_000_000.0 % 86400.0          # midnight UTC
    for s in range(n_subjects):
        level = rng.normal(110, 18)
        t = rng.uniform(0, 7 * 86400, per_subject)
        if scheduled:
            slots = np.array([d * 86400 + h * 3600 for d in range(7) for h in (7.5, 19.5)])
            t = np.concatenate([t, slots + rng.uniform(120, 900, slots.size)])
        t = np.sort(t) + t0
        # Meals at random clock times, so time of day carries no information.
        meals = np.sort(rng.uniform(t0, t0 + 8 * 86400, 24))
        for ti in t:
            since = ti - meals[meals <= ti].max() if (meals <= ti).any() else 1e5
            meal = 45 * np.exp(-((since / 3600 - 0.75) ** 2) / 0.5)
            g = level + meal + rng.normal(0, 8)
            f1 = (g - level) * 0.05 + rng.normal(0, 0.4) if signal else rng.normal(0, 1)
            f2 = level * 0.02 + rng.normal(0, 0.3) if signal else rng.normal(0, 1)
            row = {"subject_id": f"s{s}", "timestamp": ti, "glucose_mgdl": g}
            if ppg:
                row.update({"f1": f1, "f2": f2, "noise1": rng.normal(), "noise2": rng.normal()})
            else:
                row["minutes_since_meal"] = min(since / 60.0, 360.0)
            if source:
                row["meta_source"] = source
            rows.append(row)
    return pd.DataFrame(rows)
