"""Train and *honestly* evaluate the glucose model on real paired data.

    python scripts/train_glucose.py --table data/paired.parquet --out models [--tz-offset-h 5]

Input: a "paired table" (see suguard_ml/data/paired.py), one row per
reference glucose value with the median PPG features of the 10.24-s windows
recorded around it:  subject_id, timestamp, glucose_mgdl, <features...>,
meta_source ("suguard_max30102" for bracelet data).

Evaluation, all reported side by side:

A. random 5-fold over rows      - leaky (same person in train and test); shown
                                  only to expose the inflation
B. subject-wise GroupKFold      - population model on unseen people, against
                                  "predict the training mean"
C. personalised, chronological  - per person, fingersticks at fixed local clock
                                  times (with 5 % meter noise) during the first
                                  days update a Kalman calibration of model B's
                                  out-of-fold output; scored on that person's
                                  *later* readings against non-PPG baselines:
                                  Kalman level, last fingerstick, and a personal
                                  time-of-day profile
Controls: the same pipeline with context features only (time, meals,
profile) and with the PPG features shuffled within each person. A model that
does not beat them measures nothing from the PPG.

``validated`` (the only status under which the API presents glucose as a
measurement) requires ALL of:
* data recorded with the SuGuard bracelet (meta_source == suguard_max30102)
* >= --min-subjects people
* relative MARD gain >= --min-gain over the best baseline in B and in C,
  with the subject-bootstrap 95 % CI of the C gain above zero
* PPG beats both controls by >= --min-gain / 2
* absolute bar in C: MARD <= --max-mard and Clarke A+B >= 99 %
* the same absolute bar on a locked hold-out of people (--holdout-frac),
  never used for any choice above
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from suguard_ml.data.paired import FEATURE_AGGREGATION, load_paired, model_columns  # noqa: E402
from suguard_ml.eval.metrics import glucose_metrics  # noqa: E402
from suguard_ml.models.glucose import (  # noqa: E402
    GLUCOMETER_CV, SUGUARD_DEVICE, GlucosePopulationModel, PersonalCalibration)

PARAMS = dict(objective="quantile", learning_rate=0.03, num_leaves=15, min_data_in_leaf=50,
              feature_fraction=0.7, bagging_fraction=0.8, bagging_freq=1, lambda_l2=1.0, verbose=-1, num_threads=1)
ROUNDS = 400
CONTEXT = {"hour_sin", "hour_cos", "minutes_since_meal", "carbs_last_meal_g", "carbs_3h_g", "age", "bmi", "male"}
SCHEDULES = {1: [7.5], 2: [7.5, 19.5], 3: [7.5, 13.0, 19.5], 4: [7.5, 12.0, 17.0, 21.5]}


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


def local_hours(t: np.ndarray, tz_offset_h: float) -> tuple[np.ndarray, np.ndarray]:
    loc = t + tz_offset_h * 3600.0
    return np.floor(loc / 86400.0), (loc % 86400.0) / 3600.0


def calibration_times(t: np.ndarray, per_day: int, days: float, tz_offset_h: float = 0.0) -> np.ndarray:
    """At most ``per_day`` fingersticks per local calendar day: the first row
    within 30 min after each scheduled clock time, during the first ``days``."""
    hours = SCHEDULES.get(per_day) or list(np.linspace(7.5, 21.5, per_day))
    day, hod = local_hours(t, tz_offset_h)
    in_window = (t - t[0]) <= days * 86400.0
    chosen = []
    for d in np.unique(day[in_window]):
        for h in hours:
            c = np.flatnonzero(in_window & (day == d) & (hod >= h) & (hod < h + 0.5))
            if c.size:
                chosen.append(int(c[0]))
    return np.asarray(sorted(chosen), dtype=int)


def protocol_personal(df, f_oof, per_day=2, days=3.0, tz_offset_h=0.0, seed=0):
    """Kalman calibration of the out-of-fold population prediction, scored on
    later days, against calibration-only baselines (same noisy fingersticks)."""
    rng = np.random.default_rng(seed)
    rows = []
    hours = np.array(SCHEDULES.get(per_day) or list(np.linspace(7.5, 21.5, per_day)))
    for sid, g in df.assign(f=f_oof).groupby("subject_id", sort=False):
        g = g.sort_values("t")
        t, y, f = g.t.to_numpy(), g.glucose_mgdl.to_numpy(), g.f.to_numpy()
        cal_idx = calibration_times(t, per_day, days, tz_offset_h)
        if cal_idx.size < 2 or cal_idx[-1] >= len(g) - 5:
            continue
        meas = y[cal_idx] * (1.0 + GLUCOMETER_CV * rng.standard_normal(cal_idx.size))
        cal_m = PersonalCalibration()          # PPG model + calibration
        cal_0 = PersonalCalibration()          # calibration only (no PPG)
        for i, m in zip(cal_idx, meas):
            cal_m.update(f[i], m, t[i])
            cal_0.update(cal_0.f0, m, t[i])
        _, hod_cal = local_hours(t[cal_idx], tz_offset_h)
        slot_cal = np.argmin(np.abs(hod_cal[:, None] - hours[None, :]), axis=1)
        profile = {s: float(np.mean(meas[slot_cal == s])) for s in np.unique(slot_cal)}
        _, hod = local_hours(t, tz_offset_h)
        for i in range(cal_idx[-1] + 1, len(g)):
            d = np.abs(((hod[i] - hours) + 12) % 24 - 12)          # circular hour distance
            slot = min(profile, key=lambda s: d[s])
            y_hat, sd = cal_m.predict(f[i], t[i])
            rows.append((sid, y[i], y_hat, sd, cal_0.predict(cal_0.f0, t[i])[0], meas[-1], profile[slot]))
    if not rows:
        return None, None
    r = pd.DataFrame(rows, columns=["sid", "y", "model_cal", "sd", "cal_only", "last_stick", "tod_profile"])
    z = 1.2816
    res = {
        "n_subjects": int(r.sid.nunique()),
        "fingersticks_per_day": per_day, "calibration_days": days,
        "model_plus_calibration": glucose_metrics(r.y, r.model_cal),
        "interval_80_coverage": float(np.mean(np.abs(r.y - r.model_cal) <= z * r.sd)),
        "calibration_only_kalman": glucose_metrics(r.y, r.cal_only),
        "last_fingerstick_carried_forward": glucose_metrics(r.y, r.last_stick),
        "personal_time_of_day_profile": glucose_metrics(r.y, r.tod_profile),
    }
    return res, r


BASELINES_C = ("calibration_only_kalman", "last_fingerstick_carried_forward", "personal_time_of_day_profile")


def best_baseline(c: dict) -> str:
    return min(BASELINES_C, key=lambda k: c[k]["mard_pct"])


def bootstrap_gain(r: pd.DataFrame, base_col: str, n: int = 1000, seed: int = 0) -> list[float]:
    """Subject-bootstrap 95 % CI of 1 - MARD(model) / MARD(baseline)."""
    rng = np.random.default_rng(seed)
    ard_m = (r.model_cal - r.y).abs() / r.y
    ard_b = (r[base_col] - r.y).abs() / r.y
    by = pd.DataFrame({"sid": r.sid, "m": ard_m, "b": ard_b}).groupby("sid").agg(["sum", "count"])
    sids = by.index.to_numpy()
    gains = []
    for _ in range(n):
        pick = rng.choice(sids, size=sids.size, replace=True)
        s = by.loc[pick]
        gains.append(1 - s[("m", "sum")].sum() / s[("b", "sum")].sum())
    return [float(np.percentile(gains, 2.5)), float(np.percentile(gains, 97.5))]


def shuffle_within_subject(df: pd.DataFrame, cols: list[str], seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    out = df.copy()
    for _, idx in out.groupby("subject_id").groups.items():
        idx = np.asarray(list(idx))
        perm = rng.permutation(idx)
        out.loc[idx, cols] = out.loc[perm, cols].to_numpy()
    return out


def absolute_ok(m: dict, max_mard: float) -> bool:
    return m["mard_pct"] <= max_mard and m["clarke_ab_pct"] >= 99.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--table", required=True)
    ap.add_argument("--out", default="models")
    ap.add_argument("--name", default="glucose")
    ap.add_argument("--tz-offset-h", type=float, default=None,
                    help="UTC offset of the participants; required for unix-second timestamps")
    ap.add_argument("--per-day", type=int, default=2, help="calibration fingersticks per day (protocol C)")
    ap.add_argument("--cal-days", type=float, default=3.0)
    ap.add_argument("--min-gain", type=float, default=0.10, help="required relative MARD gain over baselines")
    ap.add_argument("--max-mard", type=float, default=15.0, help="absolute MARD bar after calibration (%%)")
    ap.add_argument("--min-subjects", type=int, default=20)
    ap.add_argument("--holdout-frac", type=float, default=0.2, help="people locked away for the final check")
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()

    raw = pd.read_parquet(a.table) if a.table.endswith(".parquet") else pd.read_csv(a.table, nrows=5)
    numeric_ts = "t" in raw or pd.api.types.is_numeric_dtype(raw.get("timestamp", pd.Series(dtype=float)))
    if "hour_sin" not in raw and numeric_ts and a.tz_offset_h is None:
        sys.exit("unix timestamps without hour_sin/hour_cos: pass --tz-offset-h (the API uses local time)")
    tz = a.tz_offset_h or 0.0
    df = load_paired(a.table, tz_offset_h=tz)
    feats = model_columns(df)
    ppg = [f for f in feats if f not in CONTEXT]
    sources = sorted(df["meta_source"].astype(str).unique()) if "meta_source" in df else ["unknown"]
    device_ok = sources == [SUGUARD_DEVICE]

    # Locked hold-out of people: set aside before anything else.
    subjects = np.array(sorted(df.subject_id.unique()))
    rng = np.random.default_rng(a.seed)
    n_hold = int(round(a.holdout_frac * subjects.size)) if subjects.size >= 10 else 0
    hold = set(rng.choice(subjects, size=n_hold, replace=False)) if n_hold else set()
    dev = df[~df.subject_id.isin(hold)].reset_index(drop=True)
    test = df[df.subject_id.isin(hold)].reset_index(drop=True)
    y = dev.glucose_mgdl.to_numpy()
    print(f"{len(df)} pairs, {subjects.size} subjects ({len(hold)} held out), {len(feats)} features "
          f"({len(ppg)} PPG); sources {sources}; glucose {y.mean():.0f}+-{y.std():.0f} mg/dL")

    report = {"n_pairs": int(len(df)), "n_subjects": int(subjects.size), "holdout_subjects": len(hold),
              "sources": sources, "features": feats, "feature_aggregation": FEATURE_AGGREGATION,
              "hour_features": {"tz_offset_h": tz}}
    report["A_random_rows_LEAKY"] = glucose_metrics(y, protocol_random(dev, feats, a.seed))
    pred_b, base_b = protocol_subject(dev, feats, a.seed)
    report["B_subject_wise"] = {"model": glucose_metrics(y, pred_b[:, 1]),
                                "baseline_train_mean": glucose_metrics(y, base_b),
                                "interval_80_coverage": float(np.mean((y >= pred_b[:, 0]) & (y <= pred_b[:, 2])))}
    c, c_rows = protocol_personal(dev, pred_b[:, 1], a.per_day, a.cal_days, tz, a.seed)
    report["C_personalised"] = c

    # Controls: context only, and PPG shuffled within each person.
    controls = {}
    ctx = [f for f in feats if f in CONTEXT]
    if ctx and ppg:
        p_ctx, _ = protocol_subject(dev, ctx, a.seed)
        controls["context_only"] = (glucose_metrics(y, p_ctx[:, 1]),
                                    protocol_personal(dev, p_ctx[:, 1], a.per_day, a.cal_days, tz, a.seed)[0])
    if ppg:
        shuf = shuffle_within_subject(dev, ppg, a.seed)
        p_sh, _ = protocol_subject(shuf, feats, a.seed)
        controls["ppg_shuffled"] = (glucose_metrics(y, p_sh[:, 1]),
                                    protocol_personal(shuf, p_sh[:, 1], a.per_day, a.cal_days, tz, a.seed)[0])
    report["controls"] = {k: {"B": v[0], "C": (v[1] or {}).get("model_plus_calibration")} for k, v in controls.items()}

    reasons = []
    b_gain = 1 - report["B_subject_wise"]["model"]["mard_pct"] / report["B_subject_wise"]["baseline_train_mean"]["mard_pct"]
    c_gain, c_ci, ctrl_gain = None, None, {}
    if c:
        base = best_baseline(c)
        c_gain = 1 - c["model_plus_calibration"]["mard_pct"] / c[base]["mard_pct"]
        c_ci = bootstrap_gain(c_rows, {"calibration_only_kalman": "cal_only", "last_fingerstick_carried_forward":
                                       "last_stick", "personal_time_of_day_profile": "tod_profile"}[base], seed=a.seed)
        for k, v in report["controls"].items():
            ref = v["C"] or v["B"]
            mine = c["model_plus_calibration"] if v["C"] else report["B_subject_wise"]["model"]
            ctrl_gain[k] = 1 - mine["mard_pct"] / ref["mard_pct"]
    report["relative_mard_gain"] = {"B_vs_train_mean": b_gain, "C_vs_best_non_ppg_baseline": c_gain,
                                    "C_gain_subject_bootstrap_95ci": c_ci, "vs_controls": ctrl_gain}

    if not device_ok:
        reasons.append(f"data not from the SuGuard bracelet ({sources})")
    if subjects.size < a.min_subjects:
        reasons.append(f"only {subjects.size} subjects (< {a.min_subjects})")
    if b_gain < a.min_gain:
        reasons.append("population model does not beat the mean on new people")
    if c is None:
        reasons.append("no subject with enough data for the personalised protocol")
    else:
        if c_gain < a.min_gain or c_ci[0] <= 0:
            reasons.append("calibrated model does not beat fingerstick-only baselines")
        if not absolute_ok(c["model_plus_calibration"], a.max_mard):
            reasons.append(f"calibrated MARD/Clarke above the absolute bar ({a.max_mard} %, A+B 99 %)")
    for k, g in ctrl_gain.items():
        if g < a.min_gain / 2:
            reasons.append(f"PPG adds nothing over the {k} control")

    # Final model on the development people only (the evaluated one).
    final_boosters = fit_quantiles(dev[feats], y, a.seed)
    if len(test):
        tmp = GlucosePopulationModel(final_boosters, feats, {})
        f_test = np.array([tmp.predict(r)[0] for r in test[feats].to_dict("records")])
        report["holdout"] = {"population": glucose_metrics(test.glucose_mgdl, f_test)}
        h_c, _ = protocol_personal(test, f_test, a.per_day, a.cal_days, tz, a.seed)
        report["holdout"]["personalised"] = h_c
        if h_c is None or not absolute_ok(h_c["model_plus_calibration"], a.max_mard):
            reasons.append("fails the absolute bar on the locked hold-out")
    else:
        reasons.append("no locked hold-out (too few subjects)")

    validated = not reasons
    report["validated"] = validated
    report["not_validated_because"] = reasons
    for k in ("A_random_rows_LEAKY", "B_subject_wise", "C_personalised", "controls", "relative_mard_gain"):
        print(k, json.dumps(report[k], indent=1, default=float)[:1200])
    print("validated:", validated, reasons)

    out = Path(a.out)
    (out / "metrics").mkdir(parents=True, exist_ok=True)
    meta = {"version": "1.0.0", "validated": validated, "validated_on_device": sources[0] if device_ok else sources,
            "not_validated_because": reasons, "trained_on": a.table, "n_pairs": int(len(dev)),
            "n_subjects": int(dev.subject_id.nunique()), "feature_aggregation": FEATURE_AGGREGATION,
            "hour_features": {"tz_offset_h": tz},
            "evaluation": {k: report.get(k) for k in ("B_subject_wise", "C_personalised", "relative_mard_gain",
                                                       "holdout")}}
    GlucosePopulationModel(final_boosters, feats, meta).save(out)
    (out / "metrics" / f"{a.name}_eval.json").write_text(json.dumps(report, indent=2, default=float))
    print("saved model to", out)


if __name__ == "__main__":
    main()
