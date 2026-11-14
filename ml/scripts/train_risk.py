"""Train and validate the diabetes-risk model on NHANES 2017-2018.

    python scripts/train_risk.py --out models

Compares model variants with repeated stratified 5-fold cross-validation
(out-of-fold predictions, so every reported number is on unseen people),
then fits the chosen variant on all data and writes models/risk_model.json
and models/metrics/risk_cv.json.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score
from sklearn.model_selection import RepeatedStratifiedKFold

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from suguard_ml.data.nhanes import screening_cohort  # noqa: E402
from suguard_ml.models.risk import A1C_GRID, DESIGN_NAMES, design_row  # noqa: E402

TARGETS = {"dysglycemia": "y_dysglycemia", "diabetes": "y_diabetes"}
IMPUTED = ["waist_cm", "pulse_bpm"]

VARIANTS = {
    "age_bmi": ["age_z", "age_z2", "log_bmi"],
    "age_sex_bmi_waist": ["age_z", "age_z2", "male", "log_bmi", "waist_z"],
    "no_pulse": ["age_z", "age_z2", "male", "log_bmi", "waist_z", "active", "smoker"],
    "full": DESIGN_NAMES,
    # Final model: drops waist (r=0.91 with BMI, unstable sign) and smoking
    # (cross-sectional NHANES gives it a spurious protective sign); neither
    # improves discrimination, and an app must not explain risk with them.
    "app": ["age_z", "age_z2", "male", "log_bmi", "pulse_z", "active"],
}
FINAL = "app"


def fit_imputers(df: pd.DataFrame) -> dict:
    out = {}
    for col in IMPUTED:
        d = df.dropna(subset=[col])
        lr = LinearRegression().fit(d[["age", "male", "bmi"]].to_numpy(), d[col].to_numpy())
        out[col] = {"intercept": float(lr.intercept_), "age": float(lr.coef_[0]),
                    "male": float(lr.coef_[1]), "bmi": float(lr.coef_[2]),
                    "resid_sd": float(np.std(d[col] - lr.predict(d[["age", "male", "bmi"]].to_numpy())))}
    return out


def design(df: pd.DataFrame, imputers: dict) -> np.ndarray:
    d = df.copy()
    for col in IMPUTED:
        m = imputers[col]
        guess = m["intercept"] + m["age"] * d["age"] + m["male"] * d["male"] + m["bmi"] * d["bmi"]
        d[col] = d[col].fillna(guess)
    return np.stack([design_row(r.age, r.male, r.bmi, r.waist_cm, r.pulse_bpm, r.active, r.smoker)
                     for r in d.itertuples()])


def calib_slope_intercept(y, p):
    p = np.clip(p, 1e-6, 1 - 1e-6)
    lo = np.log(p / (1 - p)).reshape(-1, 1)
    lr = LogisticRegression(C=1e6).fit(lo, y)
    return float(lr.coef_[0, 0]), float(lr.intercept_[0])


def bootstrap_auc(y, p, n=1000, seed=0):
    rng = np.random.default_rng(seed)
    vals = []
    for _ in range(n):
        i = rng.integers(0, y.size, y.size)
        if y[i].min() == y[i].max():
            continue
        vals.append(roc_auc_score(y[i], p[i]))
    return [float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))]


def cross_validate(df, cols_idx, target, C, n_rep=5, seed=0):
    y = df[target].to_numpy()
    oof = np.zeros((n_rep, y.size))
    rskf = RepeatedStratifiedKFold(n_splits=5, n_repeats=n_rep, random_state=seed)
    for k, (tr, te) in enumerate(rskf.split(df, y)):
        imp = fit_imputers(df.iloc[tr])
        Xtr, Xte = design(df.iloc[tr], imp)[:, cols_idx], design(df.iloc[te], imp)[:, cols_idx]
        m = LogisticRegression(C=C, max_iter=2000).fit(Xtr, y[tr])
        oof[k // 5, te] = m.predict_proba(Xte)[:, 1]
    aucs = [roc_auc_score(y, o) for o in oof]
    p = oof.mean(axis=0)
    slope, inter = calib_slope_intercept(y, oof[0])
    return {
        "auc": float(np.mean(aucs)), "auc_sd_over_repeats": float(np.std(aucs)),
        "auc_95ci": bootstrap_auc(y, oof[0]),
        "average_precision": float(average_precision_score(y, oof[0])),
        "brier": float(brier_score_loss(y, oof[0])),
        "brier_null": float(brier_score_loss(y, np.full(y.size, y.mean()))),
        "calibration_slope": slope, "calibration_intercept": inter,
        "prevalence": float(y.mean()), "n": int(y.size), "n_pos": int(y.sum()),
    }, p


def a1c_densities(df: pd.DataFrame) -> dict:
    out = {}
    for name, (lo, hi) in {"normal": (0, 5.7), "prediabetes": (5.7, 6.5), "diabetes": (6.5, 99)}.items():
        v = df["a1c"][(df["a1c"] >= lo) & (df["a1c"] < hi)].to_numpy()
        bw = 0.06
        dens = np.exp(-0.5 * ((A1C_GRID[:, None] - v[None, :]) / bw) ** 2).sum(axis=1)
        dens[(A1C_GRID < lo - 0.05) | (A1C_GRID >= hi)] = 0.0
        dens /= dens.sum() * 0.05
        out[name] = [round(float(x), 6) for x in dens]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="models")
    ap.add_argument("--C", type=float, default=1.0)
    a = ap.parse_args()
    out = Path(a.out)
    (out / "metrics").mkdir(parents=True, exist_ok=True)

    df = screening_cohort()
    print(f"screening cohort: {len(df)} adults without diagnosed diabetes; "
          f"HbA1c>=5.7: {df.y_dysglycemia.mean():.1%}, >=6.5: {df.y_diabetes.mean():.1%}")

    report = {"cohort": {"source": "NHANES 2017-2018 (nhanes PyPI package)", "n": len(df),
                         "definition": "age>=18, no diabetes diagnosis/medication, HbA1c and BMI measured"},
              "variants": {}}
    oof_full = {}
    for vname, cols in VARIANTS.items():
        idx = [DESIGN_NAMES.index(c) for c in cols]
        report["variants"][vname] = {}
        for tname, tcol in TARGETS.items():
            res, p = cross_validate(df, idx, tcol, a.C)
            report["variants"][vname][tname] = res
            if vname == FINAL:
                oof_full[tname] = p
            print(f"{vname:20s} {tname:12s} AUC {res['auc']:.3f} [{res['auc_95ci'][0]:.3f}-{res['auc_95ci'][1]:.3f}] "
                  f"AP {res['average_precision']:.3f} Brier {res['brier']:.4f} (null {res['brier_null']:.4f}) "
                  f"cal slope {res['calibration_slope']:.2f}")

    # Category table on out-of-fold predictions of the final variant.
    from suguard_ml.models.risk import category
    cats = np.array([category(pd_, pm) for pd_, pm in zip(oof_full["dysglycemia"], oof_full["diabetes"])])
    table = {}
    for c in ["low", "moderate", "elevated", "high"]:
        s = cats == c
        table[c] = {"share_of_population": float(s.mean()),
                    "observed_hba1c_ge_5_7": float(df.y_dysglycemia[s].mean()) if s.any() else None,
                    "observed_hba1c_ge_6_5": float(df.y_diabetes[s].mean()) if s.any() else None}
    report["categories_oof"] = table
    print(json.dumps(table, indent=1))

    # Final fit on all data.
    imp = fit_imputers(df)
    X = design(df, imp)
    spec = {"name": "suguard-risk", "version": "1.0.0", "design": DESIGN_NAMES, "models": {},
            "imputers": imp,
            "binary_prevalence": {"male": float(df.male.mean()), "active": float(df.active.mean()),
                                  "smoker": float(df.smoker.mean())},
            "a1c_grid": {"start": 4.0, "stop": 15.0, "step": 0.05},
            "a1c_density": a1c_densities(df),
            "training": report["cohort"]}
    idx = [DESIGN_NAMES.index(c) for c in VARIANTS[FINAL]]
    spec["features_used"] = VARIANTS[FINAL]
    for tname, tcol in TARGETS.items():
        m = LogisticRegression(C=a.C, max_iter=5000).fit(X[:, idx], df[tcol].to_numpy())
        coef = np.zeros(len(DESIGN_NAMES))
        coef[idx] = m.coef_[0]
        spec["models"][tname] = {"intercept": float(m.intercept_[0]), "coef": [float(c) for c in coef]}
        print(tname, dict(zip(DESIGN_NAMES, np.round(coef, 3))), round(float(m.intercept_[0]), 3))
    spec["validation"] = {t: report["variants"][FINAL][t] for t in TARGETS}
    spec["categories_oof"] = table
    (out / "risk_model.json").write_text(json.dumps(spec, indent=1))
    (out / "metrics" / "risk_cv.json").write_text(json.dumps(report, indent=2))
    print("wrote", out / "risk_model.json")


if __name__ == "__main__":
    main()
