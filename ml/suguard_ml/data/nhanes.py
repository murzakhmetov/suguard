"""NHANES 2017-2018 cohort for the diabetes-risk model.

Source: the ``nhanes`` package on PyPI (Poldrack lab), which bundles the
public-domain NHANES 2017-2018 files merged per participant with readable
column names. NHANES is a US population survey; using it for SuGuard's
users (Kazakhstan) assumes the risk-factor relationships transfer, which is
reasonable for age/BMI/waist/heart rate but calibration may differ and should
be checked on local data.

Labels follow the ADA HbA1c criteria (laboratory-measured glycohaemoglobin):
diabetes >= 6.5 %, prediabetes 5.7-6.4 %.
"""

from __future__ import annotations

import importlib.util
import os

import numpy as np
import pandas as pd

TSV = "combined_data/2017-2018/NHANES_data_2017-2018.tsv"

FEATURES = ["age", "male", "bmi", "waist_cm", "pulse_bpm", "active", "smoker", "sleep_h", "asian", "european"]


def _path() -> str:
    spec = importlib.util.find_spec("nhanes")
    if spec is None or not spec.submodule_search_locations:
        raise ImportError("pip install nhanes  # bundles NHANES 2017-2018")
    return os.path.join(list(spec.submodule_search_locations)[0], TSV)


def load_raw() -> pd.DataFrame:
    return pd.read_csv(_path(), sep="\t", low_memory=False)


def _flag(s: pd.Series) -> pd.Series:
    v = pd.to_numeric(s, errors="coerce")
    return v.where(v.isin([0, 1]))


def load_cohort(min_age: int = 18) -> pd.DataFrame:
    """One row per adult with features, labels and the diagnosis status."""
    raw = load_raw()
    df = pd.DataFrame({
        "seqn": raw["SEQN"],
        "age": pd.to_numeric(raw["AgeInYearsAtScreening"], errors="coerce"),
        "male": (raw["Gender"] == "Male").astype(float).where(raw["Gender"].notna()),
        "bmi": pd.to_numeric(raw["BodyMassIndexKgm2"], errors="coerce"),
        "waist_cm": pd.to_numeric(raw["WaistCircumferenceCm"], errors="coerce"),
        "pulse_bpm": pd.to_numeric(raw["60SecPulse30SecPulse2"], errors="coerce"),
        "sleep_h": pd.to_numeric(raw["SleepHoursWeekdaysOrWorkdays"], errors="coerce"),
        "a1c": pd.to_numeric(raw["Glycohemoglobin"], errors="coerce"),
        "ethnicity": raw["RacehispanicOriginWNhAsian"].astype(object),
    })
    df["asian"] = df["ethnicity"].eq("Non-Hispanic Asian").astype(float)
    df["european"] = df["ethnicity"].eq("Non-Hispanic White").astype(float)
    vig = _flag(raw["VigorousRecreationalActivities"])
    mod = _flag(raw["ModerateRecreationalActivities"])
    df["active"] = np.where(vig.isna() & mod.isna(), np.nan, ((vig == 1) | (mod == 1)).astype(float))
    ever = _flag(raw["SmokedAtLeast100CigarettesInLife"])
    now = raw["DoYouNowSmokeCigarettes"].astype(object)
    current = now.isin(["Every day", "Some days"]).to_numpy()
    quit_ = now.eq("Not at all").fillna(False).to_numpy(dtype=bool)
    never = ever.eq(0).fillna(False).to_numpy(dtype=bool)
    df["smoker"] = np.where(never | quit_, 0.0, np.where(current, 1.0, np.nan))

    diag = raw["DoctorToldYouHaveDiabetes"].astype(object)
    insulin = _flag(raw["TakingInsulinNow"]).eq(1).fillna(False)
    pills = _flag(raw["TakeDiabeticPillsToLowerBloodSugar"]).eq(1).fillna(False)
    df["diagnosed"] = (diag.eq("1").fillna(False) | insulin | pills).astype(int)
    df["told_prediabetes"] = (diag.eq("Borderline").fillna(False)
                              | _flag(raw["EverToldYouHavePrediabetes"]).eq(1).fillna(False)).astype(int)
    df["y_diabetes"] = ((df["a1c"] >= 6.5) | (df["diagnosed"] == 1)).astype(int)
    df["y_dysglycemia"] = ((df["a1c"] >= 5.7) | (df["diagnosed"] == 1)).astype(int)

    df = df[(df["age"] >= min_age) & df["a1c"].notna() & df["bmi"].notna()].reset_index(drop=True)
    return df


def attach_weights(df: pd.DataFrame, path: str) -> pd.DataFrame:
    """Add NHANES MEC exam weights (WTMEC2YR) from DEMO_J.XPT or a CSV with
    SEQN,WTMEC2YR (the bundled table has no survey weights). Download in Colab:
    https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/DEMO_J.xpt"""
    w = pd.read_sas(path, format="xport") if path.lower().endswith(".xpt") else pd.read_csv(path)
    w = w[["SEQN", "WTMEC2YR"]].rename(columns={"SEQN": "seqn", "WTMEC2YR": "weight"})
    w["seqn"] = w["seqn"].astype(int)
    out = df.merge(w, on="seqn", how="left")
    if out["weight"].isna().any():
        raise ValueError("some participants have no survey weight")
    return out


def screening_cohort(min_age: int = 18) -> pd.DataFrame:
    """Adults *without* a diabetes diagnosis: the population a screening
    wearable addresses. Labels are purely laboratory (HbA1c)."""
    df = load_cohort(min_age)
    df = df[df["diagnosed"] == 0].reset_index(drop=True)
    df["y_diabetes"] = (df["a1c"] >= 6.5).astype(int)
    df["y_dysglycemia"] = (df["a1c"] >= 5.7).astype(int)
    return df
