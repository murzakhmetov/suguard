"""Train and *honestly* evaluate the glucose model on real paired data.

    python scripts/train_glucose.py --table data/paired.parquet --out models

Input: a "paired table" (see suguard_ml/data/paired.py), one row per
reference glucose value with the PPG features of the minutes before it:
    subject_id, timestamp, glucose_mgdl, <feature columns...>

Three evaluation protocols, all reported side by side:

A. random 5-fold over rows        - leaky (same person in train and test);
                                     shown only to expose the inflation
B. subject-wise GroupKFold        - population model on unseen people,
                                     against "predict the training mean"
C. personalised, chronological    - per person: the first calibration
                                     fingersticks update a Kalman calibration
                                     of model B's out-of-fold output; scored on
                                     that person's *later* readings, against
                                     calibration-only baselines (no PPG)

A context-only model (time of day, meals, profile; no PPG) is run through B
and C as well: meal timing alone explains much of glucose, and a model that
wins only through context features measures nothing from the PPG.

The model is marked ``validated`` only if it beats the baselines in B and C
by a margin and the PPG features add to the context-only model; otherwise
the API reports its glucose as "experimental".
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from suguard_ml.data.paired import load_paired, model_columns  # noqa: E402
from suguard_ml.eval.metrics import glucose_metrics  # noqa: E402
from suguard_ml.models.glucose import GlucosePopulationModel, PersonalCalibration  # noqa: E402

PARAMS = dict(objective="quantile", learning_rate=0.03, num_leaves=15, min_data_in_leaf=50,
              feature_fraction=0.7, bagging_fraction=0.8, bagging_freq=1, lambda_l2=1.0, verbose=-1, num_threads=1)
ROUNDS = 400
CONTEXT = {"hour_sin", "hour_cos", "minutes_since_meal", "carbs_last_meal_g", "carbs_3h_g", "age", "bmi", "male"}


def fit_quantiles(X: pd.DataFrame, y: np.ndarray, seed: int = 0) -> dict:
    import lightgbm as lgb

    out = {}
    for name, alpha in (("q10", 0.1), ("q50", 0.5), ("q90", 0.9)):
        params = dict(PARAMS, alpha=alpha, seed=seed)
        out[name] = lgb.train(params, lgb.Dataset(X, y), num_boost_round=ROUNDS)
    return out


def protocol_random(df, feats, seed=0):
    from sklearn.model_selection import KFold

    pred = np.full(len(df), np.nan)
    for tr, te in KFold(5, shuffle=True, random_state=seed).split(df):
        b = fit_quantiles(df.iloc[tr][feats], df.glucose_mgdl.to_numpy()[tr], seed)["q50"]
        pred[te] = b.predict(df.iloc[te][feats])
    return pred


def protocol_subject(df, feats, seed=0):
    from sklearn.model_selection import GroupKFold

    subjects = df.subject_id.to_numpy()
    k = int(min(5, len(np.unique(subjects))))
    pred = np.full((len(df), 3), np.nan)
    base = np.full(len(df), np.nan)
    for tr, te in GroupKFold(k).split(df, groups=subjects):
        y_tr = df.glucose_mgdl.to_numpy()[tr]
        m = fit_quantiles(df.iloc[tr][feats], y_tr, seed)
        for j, q in enumerate(("q10", "q50", "q90")):
            pred[te, j] = m[q].predict(df.iloc[te][feats])
        base[te] = y_tr.mean()
    return pred, base


def calibration_times(t: np.ndarray, per_day: int, days: float) -> np.ndarray:
    """Indices of rows used as fingersticks: up to ``per_day`` per day, spread
    >= 24/per_day/2 h apart, during the first ``days`` of the person's data."""
    t0 = t[0]
    chosen, last = [], -np.inf
    gap = 86400.0 / per_day / 2.0
    for i, ti in enumerate(t):
        if ti - t0 > days * 86400:
            break
        if ti - last >= gap:
            chosen.append(i)
            last = ti
    return np.asarray(chosen, dtype=int)


def protocol_personal(df, f_oof, per_day=2, days=3.0):
    """Kalman calibration of the out-of-fold population prediction."""
    rows = []
    for sid, g in df.assign(f=f_oof).groupby("subject_id", sort=False):
        g = g.sort_values("t")
        t, y, f = g.t.to_numpy(), g.glucose_mgdl.to_numpy(), g.f.to_numpy()
        cal_idx = calibration_times(t, per_day, days)
        if cal_idx.size < 2 or cal_idx[-1] >= len(g) - 5:
            continue
        cal_m = PersonalCalibration()          # PPG model + calibration
        cal_0 = PersonalCalibration()          # calibration only (no PPG)
        for i in cal_idx:
            cal_m.update(f[i], y[i], t[i])
            cal_0.update(cal_0.f0, y[i], t[i])
        test = np.arange(cal_idx[-1] + 1, len(g))
        last_stick = y[cal_idx[-1]]
        for i in test:
            rows.append((sid, y[i], cal_m.predict(f[i], t[i])[0], cal_0.predict(cal_0.f0, t[i])[0], last_stick))
    if not rows:
        return None
    r = pd.DataFrame(rows, columns=["sid", "y", "model_cal", "cal_only", "last_stick"])
    return {
        "n_subjects": int(r.sid.nunique()),
        "model_plus_calibration": glucose_metrics(r.y, r.model_cal),
        "calibration_only_kalman": glucose_metrics(r.y, r.cal_only),
        "last_fingerstick_carried_forward": glucose_metrics(r.y, r.last_stick),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--table", required=True)
    ap.add_argument("--out", default="models")
    ap.add_argument("--per-day", type=int, default=2, help="calibration fingersticks per day (protocol C)")
    ap.add_argument("--cal-days", type=float, default=3.0)
    ap.add_argument("--name", default="glucose")
    ap.add_argument("--min-gain", type=float, default=0.10, help="required relative MARD gain over baselines")
    a = ap.parse_args()

    df = load_paired(a.table)
    feats = model_columns(df)
    y = df.glucose_mgdl.to_numpy()
    print(f"{len(df)} pairs, {df.subject_id.nunique()} subjects, {len(feats)} features; "
          f"glucose {y.mean():.0f}+-{y.std():.0f} mg/dL")

    report = {"n_pairs": int(len(df)), "n_subjects": int(df.subject_id.nunique()), "features": feats}
    report["A_random_rows_LEAKY"] = glucose_metrics(y, protocol_random(df, feats))
    pred_b, base_b = protocol_subject(df, feats)
    report["B_subject_wise"] = {"model": glucose_metrics(y, pred_b[:, 1]),
                                "baseline_train_mean": glucose_metrics(y, base_b),
                                "interval_80_coverage": float(np.mean((y >= pred_b[:, 0]) & (y <= pred_b[:, 2])))}
    report["C_personalised"] = protocol_personal(df, pred_b[:, 1], a.per_day, a.cal_days)

    # Does the PPG add anything over context (time of day, meals, profile)?
    # Meal timing alone explains much of glucose; a "PPG" model that wins only
    # through context features measures nothing.
    ctx = [f for f in feats if f in CONTEXT]
    ppg_gain = None
    if ctx and len(ctx) < len(feats):
        pred_ctx, _ = protocol_subject(df, ctx)
        pred_cx = protocol_personal(df, pred_ctx[:, 1], a.per_day, a.cal_days)
        report["B_context_only"] = glucose_metrics(y, pred_ctx[:, 1])
        report["C_context_only"] = pred_cx["model_plus_calibration"] if pred_cx else None
        ref = report["C_context_only"] or report["B_context_only"]
        mine = (report["C_personalised"] or {}).get("model_plus_calibration") or report["B_subject_wise"]["model"]
        ppg_gain = 1 - mine["mard_pct"] / ref["mard_pct"]
    elif not ctx:
        ppg_gain = None  # nothing to compare with: every feature is a PPG feature

    b_gain = 1 - report["B_subject_wise"]["model"]["mard_pct"] / report["B_subject_wise"]["baseline_train_mean"]["mard_pct"]
    c = report["C_personalised"]
    c_gain = None
    if c:
        best_base = min(c["calibration_only_kalman"]["mard_pct"], c["last_fingerstick_carried_forward"]["mard_pct"])
        c_gain = 1 - c["model_plus_calibration"]["mard_pct"] / best_base
    validated = bool(b_gain >= a.min_gain and c_gain is not None and c_gain >= a.min_gain
                     and (ppg_gain is None or ppg_gain >= a.min_gain / 2))
    report["relative_mard_gain"] = {"B_vs_mean": b_gain, "C_vs_best_calibration_baseline": c_gain,
                                    "PPG_vs_context_only": ppg_gain}
    report["validated"] = validated

    for k in ("A_random_rows_LEAKY", "B_subject_wise", "C_personalised"):
        print(k, json.dumps(report[k], indent=1)[:1500])
    print("validated:", validated, report["relative_mard_gain"])

    out = Path(a.out)
    (out / "metrics").mkdir(parents=True, exist_ok=True)
    final = GlucosePopulationModel(fit_quantiles(df[feats], y), feats,
                                   {"version": "1.0.0", "validated": validated, "trained_on": a.table,
                                    "n_pairs": int(len(df)), "n_subjects": int(df.subject_id.nunique()),
                                    "evaluation": {k: report[k] for k in ("B_subject_wise", "C_personalised",
                                                                           "relative_mard_gain")}})
    final.save(out)
    (out / "metrics" / f"{a.name}_eval.json").write_text(json.dumps(report, indent=2, default=float))
    print("saved model to", out)


if __name__ == "__main__":
    main()
