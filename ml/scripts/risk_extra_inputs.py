"""Would more questions improve the diabetes-risk model? (NHANES 2017-2018)

    python scripts/risk_extra_inputs.py --out models/metrics

Adds one candidate input at a time to the shipped model ("app" variant of
train_risk.py) and compares out-of-fold AUCs on the same folds (repeated
stratified 5-fold cross-validation; a candidate's missing values get the
training-fold median). Candidates are things an app could ask or a user
could measure at home: blood pressure (the mean of the NHANES readings),
self-rated general health, sedentary time, sleep duration.

Not tested on purpose: the NHANES item "family history" in the bundled file
is DIQ175A, the reason given by people who already think they are at risk
of diabetes; it mixes family history with perceived risk (often after an
abnormal glucose test) and would leak the outcome into a screening model.

Writes models/metrics/risk_extra_inputs.json.
"""

from __future__ import annotations

import argparse
import json
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import RepeatedStratifiedKFold

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import train_risk as T  # noqa: E402
from suguard_ml.data import nhanes  # noqa: E402
from suguard_ml.models.risk import DESIGN_NAMES  # noqa: E402

GENERAL_HEALTH = {"Excellent": 1, "Very good": 2, "Good": 3, "Fair or": 4, "Fair": 4, "Poor?": 5, "Poor": 5}


def candidates(df: pd.DataFrame) -> dict[str, np.ndarray]:
    raw = nhanes.load_raw().set_index("SEQN").loc[df["seqn"].to_numpy()]

    def num(col):
        return pd.to_numeric(raw[col], errors="coerce").to_numpy(dtype=float, copy=True)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)          # people without any reading: NaN
        sbp = np.nanmean([num(f"SystolicBloodPres{k}MmHg") for k in ("1StRdg", "2NdRdg", "3RdRdg")], axis=0)
        dbp = np.nanmean([num(f"DiastolicBloodPres{k}MmHg") for k in ("1StRdg", "2NdRdg", "3RdRdg")], axis=0)
    health = raw["GeneralHealthCondition"].astype(object).map(
        lambda v: GENERAL_HEALTH.get(str(v).strip(), np.nan)).to_numpy(dtype=float)
    sedentary = num("MinutesSedentaryActivity")
    sedentary[sedentary > 1440] = np.nan                         # codes for "refused" / "don't know"
    sleep = df["sleep_h"].to_numpy(dtype=float)
    return {"systolic_bp": (sbp - 125.0) / 18.0, "diastolic_bp": (dbp - 72.0) / 12.0,
            "general_health_1_to_5": health - 3.0, "sedentary_hours": sedentary / 60.0 - 6.0,
            "sleep_hours_from_7_5": np.abs(sleep - 7.5)}


def oof_auc(df, extra: dict, keys: list[str], target: str, n_rep: int, seed: int) -> np.ndarray:
    y = df[target].to_numpy()
    idx = [DESIGN_NAMES.index(c) for c in T.VARIANTS[T.FINAL]]
    oof = np.zeros((n_rep, len(df)))
    folds = RepeatedStratifiedKFold(n_splits=5, n_repeats=n_rep, random_state=seed)
    for f, (tr, te) in enumerate(folds.split(np.zeros(len(y)), y)):
        X = [T.design(df, T.fit_imputers(df.iloc[tr]))[:, idx]]
        for k in keys:
            v = extra[k].copy()
            v[~np.isfinite(v)] = np.nanmedian(v[tr])
            X.append(v[:, None])
        X = np.hstack(X)
        m = LogisticRegression(C=1.0, max_iter=3000).fit(X[tr], y[tr])
        oof[f // 5, te] = m.predict_proba(X[te])[:, 1]
    return np.array([roc_auc_score(y, o) for o in oof])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="models/metrics")
    ap.add_argument("--repeats", type=int, default=5)
    a = ap.parse_args()
    df = T.screening_cohort()
    extra = candidates(df)
    report = {"cohort_n": int(len(df)), "base_variant": T.FINAL,
              "available_share": {k: float(np.isfinite(v).mean()) for k, v in extra.items()}, "targets": {}}
    for tname, tcol in T.TARGETS.items():
        base = oof_auc(df, extra, [], tcol, a.repeats, 0)
        res = {"base_auc": float(base.mean()), "added": {}}
        for keys in ([k] for k in extra):
            auc = oof_auc(df, extra, keys, tcol, a.repeats, 0)
            gain = auc - base
            res["added"]["+".join(keys)] = {"auc": float(auc.mean()), "paired_gain": float(gain.mean()),
                                            "paired_gain_per_repeat": [float(g) for g in gain]}
            print(f"{tname:12s} + {'+'.join(keys):24s} AUC {auc.mean():.4f}  gain {gain.mean():+.4f}", flush=True)
        report["targets"][tname] = res
    Path(a.out).mkdir(parents=True, exist_ok=True)
    (Path(a.out) / "risk_extra_inputs.json").write_text(json.dumps(report, indent=2))
    print("wrote", Path(a.out) / "risk_extra_inputs.json")


if __name__ == "__main__":
    main()
