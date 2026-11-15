"""BIG IDEAs Lab Glycemic Variability and Wearable Device Data (PhysioNet).

16 adults (normoglycaemic to prediabetic) wore an Empatica E4 wristband
(PPG/BVP 64 Hz, accelerometer 32 Hz, skin temperature, EDA) and a Dexcom G6
CGM for ~10 days, with food logs. Cho, Kim, Bent, Dunn; PhysioNet 2023,
doi:10.13026/zthx-s524 (ODC-By 1.0).

    python scripts/build_bigideas_table.py --root /content/big-ideas --out data/bigideas_paired.parquet

This is the closest public match to SuGuard's use case (wrist PPG +
continuous glucose + meals), but note the domain gap: the E4 BVP is a
green-light, AC-only signal, while SuGuard measures red/IR raw counts. Only
SuGuard-compatible features (PPG morphology, HR/HRV, temperature, context)
are used as model inputs; E4-only signals (EDA, accelerometer) are kept as
``meta_`` columns for analysis and gating.

Column names differ slightly between dataset versions, so files and columns
are located by pattern rather than hard-coded.
"""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd

from ..config import FS, WINDOW
from ..signal.features import extract_features
from .paired import FEATURE_AGGREGATION, add_time_features, aggregate_window_features
from ..signal.filters import bandpass, resample


def _find(folder: Path, kind: str) -> Path | None:
    pats = [f"{kind}_*.csv", f"{kind}.csv", f"{kind.lower()}*.csv", f"*{kind}*.csv"]
    for p in pats:
        hits = sorted(folder.glob(p))
        if hits:
            return hits[0]
    return None


def _datetime_col(df: pd.DataFrame) -> str:
    for c in df.columns:
        if re.search(r"time|date", str(c), re.I):
            return c
    return df.columns[0]


def read_e4(path: Path) -> pd.DataFrame:
    """E4 CSV -> DataFrame(t [unix s, local wall clock], value columns)."""
    df = pd.read_csv(path)
    df.columns = [str(c).strip() for c in df.columns]
    tc = _datetime_col(df)
    dt = pd.to_datetime(df[tc], format="mixed", errors="coerce")
    out = pd.DataFrame({"t": (dt - pd.Timestamp("1970-01-01")).dt.total_seconds()})
    vals = [c for c in df.columns if c != tc]
    for c in vals:
        out[c.lower()] = pd.to_numeric(df[c], errors="coerce").astype(np.float32)
    return out.dropna(subset=["t"]).sort_values("t").reset_index(drop=True)


def read_dexcom(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df.columns = [str(c).strip() for c in df.columns]
    gcol = next(c for c in df.columns if re.search(r"glucose value", c, re.I))
    tcol = next((c for c in df.columns if re.search(r"timestamp", c, re.I)), _datetime_col(df))
    g = pd.to_numeric(df[gcol].replace({"Low": 40, "High": 400}), errors="coerce")
    dt = pd.to_datetime(df[tcol], format="mixed", errors="coerce")
    out = pd.DataFrame({"t": (dt - pd.Timestamp("1970-01-01")).dt.total_seconds(), "glucose_mgdl": g})
    if any(re.search(r"event type", c, re.I) for c in df.columns):
        ec = next(c for c in df.columns if re.search(r"event type", c, re.I))
        out = out[df[ec].astype(str).str.upper().str.contains("EGV").to_numpy() | df[ec].isna().to_numpy()]
    return out.dropna().sort_values("t").reset_index(drop=True)


FOOD_COLS = ["date", "time", "time_begin", "time_end", "logged_food", "amount", "unit",
             "searched_food", "calorie", "total_carb", "dietary_fiber", "sugar", "protein", "total_fat"]


def read_food(path: Path) -> pd.DataFrame:
    """Individual food-log entries (t, carbs_g); items at the same time summed.

    Meals are *not* merged here: grouping later items into an earlier meal
    would put carbohydrates eaten after a glucose reading into its features.
    ``meal_features`` groups causally at query time.
    """
    df = pd.read_csv(path)
    df.columns = [str(c).strip().lower() for c in df.columns]
    if not any(re.search(r"date|time", c) for c in df.columns) and df.shape[1] == len(FOOD_COLS):
        df = pd.read_csv(path, header=None, names=FOOD_COLS)   # headerless log

    def col(name: str) -> pd.Series:
        return df[name].astype(str) if name in df else pd.Series("", index=df.index)

    if "time_begin" in df:
        tb = df["time_begin"].astype(str)
        has_date = tb.str.contains(r"\d{4}-\d{2}-\d{2}", regex=True)
        stamp = tb.where(has_date, (col("date") + " " + tb).str.strip())
    else:
        stamp = (col("date") + " " + col("time")).str.strip()
    dt = pd.to_datetime(stamp, format="mixed", errors="coerce")
    carbs = pd.to_numeric(df["total_carb"], errors="coerce") if "total_carb" in df else pd.Series(np.nan, index=df.index)
    out = pd.DataFrame({"t": (dt - pd.Timestamp("1970-01-01")).dt.total_seconds(), "carbs_g": carbs})
    out = out.dropna(subset=["t"])
    return out.groupby("t", as_index=False)["carbs_g"].sum(min_count=1).sort_values("t").reset_index(drop=True)


def meal_features(food: pd.DataFrame | None, T: float) -> dict:
    """Meal context known at time T (only entries at or before T are used).
    The last meal = entries within 30 min before the latest entry <= T."""
    if food is None or not len(food):
        return {}
    past = food[food["t"] <= T]
    if not len(past):
        return {"minutes_since_meal": 360.0, "carbs_last_meal_g": 0.0, "carbs_3h_g": 0.0}
    t_last = float(past["t"].iloc[-1])
    mins = (T - t_last) / 60.0
    last_meal = past[past["t"] >= t_last - 1800]
    return {"minutes_since_meal": float(min(mins, 360.0)),
            "carbs_last_meal_g": float(last_meal["carbs_g"].sum()) if mins < 360 else 0.0,
            "carbs_3h_g": float(past[past["t"] >= T - 3 * 3600]["carbs_g"].sum())}


def orient_upright(x: np.ndarray) -> np.ndarray:
    """Flip a PPG so the systolic upstroke (the shorter phase) rises."""
    d = np.diff(x)
    return -x if np.mean(d > 0) > 0.5 else x


def participant_table(folder: Path, every_n: int = 1, window_s: float = 300.0,
                      max_acc_std_g: float = 0.05, min_clean_s: float = 60.0) -> pd.DataFrame:
    """One row per CGM reading with features of the preceding ``window_s``.

    Only still periods are analysed: 10-s blocks whose accelerometer-magnitude
    SD exceeds ``max_acc_std_g`` are discarded before feature extraction (the
    E4 BVP has no second wavelength for the denoiser).
    """
    sid = folder.name
    bvp_p, acc_p = _find(folder, "BVP"), _find(folder, "ACC")
    dex_p, temp_p, food_p = _find(folder, "Dexcom"), _find(folder, "TEMP"), _find(folder, "Food_Log")
    if bvp_p is None or dex_p is None:
        return pd.DataFrame()
    bvp = read_e4(bvp_p)
    bcol = [c for c in bvp.columns if c != "t"][0]
    acc = read_e4(acc_p) if acc_p else None
    temp = read_e4(temp_p) if temp_p else None
    food = read_food(food_p) if food_p else None
    cgm = read_dexcom(dex_p).iloc[::every_n]

    tb, vb = bvp["t"].to_numpy(), bvp[bcol].to_numpy(dtype=np.float64)
    fs_in = 1.0 / np.median(np.diff(tb[: 10_000]))
    if acc is not None:
        ta = acc["t"].to_numpy()
        acols = [c for c in acc.columns if c != "t"][:3]
        amag = np.sqrt(np.sum(acc[acols].to_numpy(dtype=np.float64) ** 2, axis=1))
        amag = amag / np.median(amag) if np.median(amag) > 0 else amag  # ~1 g at rest, any units
    rows = []
    for T, g in zip(cgm["t"].to_numpy(), cgm["glucose_mgdl"].to_numpy()):
        i0, i1 = np.searchsorted(tb, [T - window_s, T])
        if i1 - i0 < 0.8 * window_s * fs_in:
            continue
        seg = resample(vb[i0:i1], fs_in, FS)
        n_blk = int(10 * FS)
        keep = np.ones(seg.size // n_blk, dtype=bool)
        move = np.nan
        if acc is not None:
            j0, j1 = np.searchsorted(ta, [T - window_s, T])
            if j1 - j0 > 10:
                a = amag[j0:j1]
                blk = np.array_split(a, keep.size) if keep.size else []
                stds = np.array([np.std(b) if b.size else np.inf for b in blk])
                keep &= stds <= max_acc_std_g
                move = float(np.std(a))
        # Longest contiguous still run: joining separate runs would create
        # fake beats at the joints.
        best, run_start, best_start = 0, None, 0
        for k, ok in enumerate(np.append(keep, False)):
            if ok and run_start is None:
                run_start = k
            elif not ok and run_start is not None:
                if k - run_start > best:
                    best, best_start = k - run_start, run_start
                run_start = None
        if best * 10 < min_clean_s:
            continue
        clean = seg[best_start * n_blk:(best_start + best) * n_blk]
        x = orient_upright(bandpass(clean, FS))
        x = x / (np.std(x) + 1e-12) * 0.005  # arbitrary units -> nominal 0.5 % pulse scale
        # Same aggregation as for the bracelet: median over 10.24-s windows.
        per_win = []
        for k in range(x.size // WINDOW):
            f_k = extract_features(x[k * WINDOW:(k + 1) * WINDOW], None, FS)
            if np.isfinite(f_k.get("hr_bpm", np.nan)) and np.isfinite(f_k.get("crest_time_ratio", np.nan)):
                per_win.append(f_k)
        if len(per_win) < FEATURE_AGGREGATION["min_windows"]:
            continue
        f = aggregate_window_features(per_win)
        f.pop("pi_ir", None)  # E4 BVP amplitude is not a perfusion index
        if temp is not None:
            k0, k1 = np.searchsorted(temp["t"].to_numpy(), [T - window_s, T])
            tv = temp.iloc[k0:k1, 1].to_numpy(dtype=float)
            f["temperature_c"] = float(np.nanmedian(tv)) if tv.size else np.nan
        row = {"subject_id": sid, "t": float(T), "timestamp": float(T), "glucose_mgdl": float(g),
               "n_windows": len(per_win), "meta_source": "bigideas_empatica_e4",
               "meta_acc_std": move, "meta_clean_s": float(best * 10), **f}
        row.update(meal_features(food, T))
        rows.append(row)
    return pd.DataFrame(rows)


def build_table(root: str | Path, every_n: int = 1, demographics: bool = True) -> pd.DataFrame:
    root = Path(root)
    parts = []
    folders = sorted(p for p in root.iterdir() if p.is_dir() and re.fullmatch(r"\d{3}", p.name))
    for folder in folders:
        t = participant_table(folder, every_n=every_n)
        print(f"{folder.name}: {len(t)} paired rows", flush=True)
        parts.append(t)
    df = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()
    demo = next(iter(root.glob("Demographics*.csv")), None)
    if demographics and demo is not None and len(df):
        d = pd.read_csv(demo)
        d.columns = [c.strip().lower() for c in d.columns]
        idc = next(c for c in d.columns if "id" in c)
        d["subject_id"] = d[idc].astype(int).astype(str).str.zfill(3)
        if "gender" in d:
            d["male"] = d["gender"].astype(str).str.upper().str.startswith("M").astype(float)
        if "hba1c" in d:
            d["meta_hba1c"] = pd.to_numeric(d["hba1c"], errors="coerce")
        df = df.merge(d[[c for c in ("subject_id", "male", "meta_hba1c") if c in d]], on="subject_id", how="left")
    # Timestamps in this dataset are naive local wall-clock times, so ``t`` is
    # "local seconds" and the local hour of day is obtained with offset 0.
    return add_time_features(df, 0.0) if len(df) else df
