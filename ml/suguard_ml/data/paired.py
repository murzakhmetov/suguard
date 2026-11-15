"""Paired PPG <-> reference-glucose tables for training the glucose model.

Standard table (CSV or Parquet), one row per reference glucose reading:

    subject_id   str     person identifier (never mix people across rows)
    timestamp    ISO-8601 local wall-clock time, or unix seconds (then pass
                 tz_offset_h so that hour-of-day features use local time)
    glucose_mgdl float   reference value (or glucose_mmol, converted)
    <features>   float   PPG features from the minutes before the reading
                         (suguard_ml.signal.features) and optional context:
                         minutes_since_meal, carbs_last_meal_g, carbs_3h_g,
                         age, bmi, male

``build_from_device_logs`` creates this table from SuGuard bracelet data
(see docs/DATA_COLLECTION.md for the logging format).
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from ..aggregation import FEATURE_AGGREGATION, LENGTH_DEPENDENT, aggregate_window_features  # noqa: F401

RESERVED = {"subject_id", "timestamp", "t", "glucose_mgdl", "glucose_mmol", "n_windows"}

_TZ_SUFFIX = r"(?:Z|[+-]\d{2}:?\d{2})$"


def _to_unix(ts: pd.Series, tz_offset_h: float = 0.0) -> np.ndarray:
    """Timestamps -> true UTC unix seconds.

    Numbers are taken as unix seconds. Strings with an explicit offset
    ("...+05:00", "...Z") are converted exactly; naive strings are local
    wall-clock time at ``tz_offset_h``.
    """
    if pd.api.types.is_numeric_dtype(ts):
        return ts.to_numpy(dtype=float)
    s = ts.astype(str).str.strip()
    aware = s.str.contains(_TZ_SUFFIX, regex=True).to_numpy()
    out = np.full(len(s), np.nan)
    epoch = pd.Timestamp("1970-01-01", tz="UTC")
    if aware.any():
        dt = pd.to_datetime(s[aware], format="mixed", utc=True)
        out[aware] = (dt - epoch).dt.total_seconds().to_numpy()
    if (~aware).any():
        dt = pd.to_datetime(s[~aware], format="mixed").dt.tz_localize("UTC")
        out[~aware] = (dt - epoch).dt.total_seconds().to_numpy() - tz_offset_h * 3600.0
    return out


def _local_offsets(ts: pd.Series, tz_offset_h: float | None) -> np.ndarray:
    """UTC offset (hours) of the wall clock each timestamp was written in:
    the offset inside the string where there is one, else ``tz_offset_h``
    (NaN where neither is known)."""
    default = np.nan if tz_offset_h is None else float(tz_offset_h)
    out = np.full(len(ts), default)
    if pd.api.types.is_numeric_dtype(ts):
        return out
    s = ts.astype(str).str.strip()
    m = s.str.extract(r"(Z|[+-]\d{2}:?\d{2})$")[0]
    for i, suffix in enumerate(m.to_numpy()):
        if isinstance(suffix, str):
            if suffix == "Z":
                out[i] = 0.0
            else:
                sign = -1.0 if suffix[0] == "-" else 1.0
                digits = suffix[1:].replace(":", "")
                out[i] = sign * (int(digits[:2]) + int(digits[2:]) / 60.0)
    return out


def add_time_features(df: pd.DataFrame, tz_offset_h=0.0) -> pd.DataFrame:
    """Hour-of-day as sin/cos (circadian and meal timing), in local time:
    ``t`` is UTC unix seconds and ``tz_offset_h`` the participants' offset
    (one number, or one per row)."""
    hours = ((df["t"] / 3600.0) + np.asarray(tz_offset_h, dtype=float)) % 24.0
    df["hour_sin"] = np.sin(2 * np.pi * hours / 24.0)
    df["hour_cos"] = np.cos(2 * np.pi * hours / 24.0)
    return df


def load_paired(path: str | Path, tz_offset_h: float | None = None) -> pd.DataFrame:
    """A paired table with ``t`` (unix seconds) and ``meta_tz_offset_h``: the
    hours to add to ``t`` to get the participant's wall clock. Everything that
    depends on the time of day (hour features, the fingerstick schedule of the
    evaluation) uses that column, so it cannot disagree with the table.

    The offset comes, in this order, from the table's own ``meta_tz_offset_h``
    column, from the offset written in each timestamp ("...+05:00"), or from
    ``tz_offset_h``. Timestamps without any of these raise ValueError, except
    naive strings without ``tz_offset_h``: those are taken as the wall clock
    itself (``t`` is then "local seconds" with offset 0, as in BIG IDEAs).
    """
    p = Path(path)
    df = pd.read_parquet(p) if p.suffix == ".parquet" else pd.read_csv(p)
    if "glucose_mgdl" not in df and "glucose_mmol" in df:
        df["glucose_mgdl"] = df["glucose_mmol"] * 18.0
    df["subject_id"] = df["subject_id"].astype(str)
    naive_strings = "t" not in df and not pd.api.types.is_numeric_dtype(df["timestamp"])
    if "t" in df:
        df["t"] = df["t"].astype(float)
        offsets = np.full(len(df), np.nan if tz_offset_h is None else float(tz_offset_h))
    else:
        offsets = _local_offsets(df["timestamp"], tz_offset_h)
        if naive_strings and tz_offset_h is None:
            offsets = np.where(np.isnan(offsets), 0.0, offsets)       # wall clock taken as it is
        df["t"] = _to_unix(df["timestamp"], 0.0 if tz_offset_h is None else tz_offset_h)
    if "meta_tz_offset_h" in df:
        stored = pd.to_numeric(df["meta_tz_offset_h"], errors="coerce").to_numpy(dtype=float)
        offsets = np.where(np.isfinite(stored), stored, offsets)
    if np.isnan(offsets).any():
        raise ValueError("the table has unix timestamps and no meta_tz_offset_h column: pass the participants' "
                         "UTC offset (tz_offset_h), needed for the local hour of day")
    df["meta_tz_offset_h"] = offsets
    df = df[np.isfinite(df["glucose_mgdl"]) & (df["glucose_mgdl"] > 20) & (df["glucose_mgdl"] < 600)]
    if "hour_sin" not in df:
        df = add_time_features(df, df["meta_tz_offset_h"].to_numpy())
    return df.sort_values(["subject_id", "t"]).reset_index(drop=True)


def model_columns(df: pd.DataFrame) -> list[str]:
    return [c for c in df.columns if c not in RESERVED and c not in LENGTH_DEPENDENT
            and not c.startswith("meta_") and pd.api.types.is_numeric_dtype(df[c])]


# ---------------------------------------------------------------------------
# SuGuard device logs -> paired table
# ---------------------------------------------------------------------------

def meal_context(t: float, meals: pd.DataFrame | None) -> dict:
    if meals is None or meals.empty:
        return {}
    past = meals[meals["t"] <= t]
    if past.empty:
        return {"minutes_since_meal": 360.0, "carbs_last_meal_g": 0.0, "carbs_3h_g": 0.0}
    last = past.iloc[-1]
    mins = min((t - last["t"]) / 60.0, 360.0)
    carbs_3h = float(past[past["t"] >= t - 3 * 3600]["carbs_g"].sum())
    return {"minutes_since_meal": float(mins),
            "carbs_last_meal_g": float(last.get("carbs_g", np.nan)) if mins < 360 else 0.0,
            "carbs_3h_g": carbs_3h}


def build_from_device_logs(windows_jsonl: str | Path, fingersticks_csv: str | Path,
                           meals_csv: str | Path | None = None, profiles_csv: str | Path | None = None,
                           before_s: float = 900.0, after_s: float = 300.0, min_windows: int = 3,
                           tz_offset_h: float = 5.0, pipeline=None) -> pd.DataFrame:
    """Pair each fingerstick with the bracelet windows recorded around it.

    Features of all reliable windows in [T - before_s, T + after_s] are
    aggregated with the median. Rows with fewer than ``min_windows`` reliable
    windows are dropped (the reading cannot be matched to a clean signal).
    """
    from ..pipeline import SuGuardPipeline

    pipe = pipeline or SuGuardPipeline.load()
    sticks = pd.read_csv(fingersticks_csv)
    if "glucose_mgdl" not in sticks and "glucose_mmol" in sticks:
        sticks["glucose_mgdl"] = sticks["glucose_mmol"] * 18.0
    sticks["t"] = _to_unix(sticks["ts"], tz_offset_h)
    meals = None
    if meals_csv:
        meals = pd.read_csv(meals_csv)
        meals["t"] = _to_unix(meals["ts"], tz_offset_h)
        meals = meals.sort_values("t")
    profiles = pd.read_csv(profiles_csv).set_index("user_id") if profiles_csv else None

    by_user: dict[str, list[dict]] = {}
    undated = 0
    with open(windows_jsonl) as fh:
        for line in fh:
            if line.strip():
                w = json.loads(line)
                # Accept both the documented keys and the firmware's JSON keys.
                ts = w.get("ts", w.get("timestamp"))
                if ts is None:                       # recorded without any clock: cannot be paired
                    undated += 1
                    continue
                w["ts"] = float(ts)
                w["temp_c"] = w.get("temp_c", w.get("temperature_c"))
                by_user.setdefault(str(w["user_id"]), []).append(w)

    rows = []
    skipped = 0
    for s in sticks.itertuples():
        uid = str(s.user_id)
        near = [w for w in by_user.get(uid, []) if s.t - before_s <= float(w["ts"]) <= s.t + after_s]
        feats = []
        for w in near:
            try:
                res = pipe.analyze(w["red"], w["ir"], fs=float(w.get("fs", 100)), temperature_c=w.get("temp_c"))
            except (ValueError, TypeError, KeyError):
                skipped += 1  # corrupt window: skip it, do not abort the whole table
                continue
            if res["reliable"] and res["features"]:
                feats.append(res["features"])
        if len(feats) < min_windows:
            continue
        f = aggregate_window_features(feats)
        row = {"subject_id": uid, "t": float(s.t), "timestamp": float(s.t),
               "glucose_mgdl": float(s.glucose_mgdl), "n_windows": len(feats),
               "meta_source": "suguard_max30102", "meta_tz_offset_h": float(tz_offset_h), **f}
        if meals is not None:
            row.update(meal_context(s.t, meals[meals["user_id"].astype(str) == uid]))
        if profiles is not None and uid in profiles.index:
            p = profiles.loc[uid]
            row["age"] = float(p.get("age", np.nan))
            if "height_cm" in p and "weight_kg" in p:
                row["bmi"] = float(p["weight_kg"] / (p["height_cm"] / 100) ** 2)
            if "sex" in p:
                row["male"] = 1.0 if str(p["sex"]).lower().startswith("m") else 0.0
        rows.append(row)
    if skipped:
        print(f"build_from_device_logs: skipped {skipped} corrupt windows")
    if undated:
        print(f"build_from_device_logs: skipped {undated} windows without a time stamp")
    df = pd.DataFrame(rows)
    return add_time_features(df, tz_offset_h) if len(df) else df
