"""How accurate is glucose from fingerstick calibration alone? (real CGM data)

    python scripts/benchmark_calibration.py --out models/metrics

For each person in two public CGM datasets, fingersticks are taken from the
CGM trace at fixed clock times (with ISO-grade 5 % meter noise) and used to
"predict" every later CGM value without any wearable signal:

* population mean   - mean of all *other* people's CGM (no calibration)
* last fingerstick  - carry the most recent fingerstick forward
* Kalman level      - suguard_ml PersonalCalibration with no PPG model

A PPG glucose model is worth shipping only if, with the same fingersticks,
it beats these numbers on held-out people and days.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from suguard_ml.data.cgm import load_cgm  # noqa: E402
from suguard_ml.eval.metrics import glucose_metrics  # noqa: E402
from suguard_ml.models.glucose import PersonalCalibration  # noqa: E402

SCHEDULES = {"1_per_day": [7.5], "2_per_day": [7.5, 19.5], "4_per_day": [7.5, 12.0, 17.0, 21.5]}


def run(df: pd.DataFrame, hours: list[float], seed: int = 0) -> dict:
    rng = np.random.default_rng(seed)
    rows = []
    for pid, g in df.groupby("id", sort=False):
        g = g.sort_values("time")
        others = df[df["id"] != pid]["gl"].mean()
        t = (g["time"] - pd.Timestamp("1970-01-01")).dt.total_seconds().to_numpy()
        y = g["gl"].to_numpy()
        hod = (g["time"].dt.hour + g["time"].dt.minute / 60.0).to_numpy()
        day = g["time"].dt.normalize().to_numpy()
        # One fingerstick per scheduled hour per day: the first CGM sample at/after it.
        stick = np.zeros(len(g), dtype=bool)
        for d in np.unique(day):
            for h in hours:
                cand = np.flatnonzero((day == d) & (hod >= h) & (hod < h + 0.5))
                if cand.size:
                    stick[cand[0]] = True
        if stick.sum() < 3:
            continue
        cal = PersonalCalibration()
        last = None
        first_day_end = t[np.flatnonzero(stick)[0]] + 86400
        for i in range(len(g)):
            if stick[i]:
                meas = y[i] * (1 + 0.05 * rng.standard_normal())
                cal.update(cal.f0, meas, t[i])
                last = meas
                continue
            if last is None or t[i] < first_day_end:
                continue  # score only after a day of calibration
            rows.append((pid, y[i], others, last, cal.predict(cal.f0, t[i])[0]))
    r = pd.DataFrame(rows, columns=["id", "y", "pop", "last", "kalman"])
    return {"n_people": int(r.id.nunique()), "n_points": int(len(r)),
            "population_mean": glucose_metrics(r.y, r["pop"]),
            "last_fingerstick": glucose_metrics(r.y, r["last"]),
            "kalman_level": glucose_metrics(r.y, r["kalman"])}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="models/metrics")
    ap.add_argument("--cache", default="data/iglu")
    a = ap.parse_args()
    report = {}
    for name in ("t2d5", "hall"):
        df = load_cgm(name, a.cache)
        report[name] = {"people": int(df.id.nunique()), "readings": int(len(df)),
                        "mean_mgdl": float(df.gl.mean()), "sd_mgdl": float(df.gl.std())}
        for sched, hours in SCHEDULES.items():
            res = run(df, hours)
            report[name][sched] = res
            print(f"{name:5s} {sched:10s} n={res['n_points']:6d} | " + " | ".join(
                f"{k}: MARD {res[k]['mard_pct']:5.1f}% ISO {res[k]['iso15197_pct']:5.1f}% A {res[k]['clarke_pct']['A']:5.1f}%"
                for k in ("population_mean", "last_fingerstick", "kalman_level")))
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "calibration_baselines_cgm.json").write_text(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
