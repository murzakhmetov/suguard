"""Heart rate and SpO2 of recorded bracelet windows against a reference device.

    python scripts/validate_vitals.py --windows rec/windows.jsonl --reference oximeter.csv \
        [--tz-offset-h 5] [--ref-lag-s 0 | auto] [--out validation.json] [--per-window per_window.csv]

``windows.jsonl``: the raw windows that ``firmware/tools/suguard_monitor.py --record`` writes
(docs/DATA_COLLECTION.md). ``oximeter.csv``: a reference pulse oximeter or chest strap, one row per
reading, with a time (one column, or a date and a time-of-day column) and a heart-rate and/or an
SpO2 column. Times may be unix seconds or milliseconds or date-and-time text; text without an
offset is local time at ``--tz-offset-h`` (default: this computer's time zone); dates like
05.11.2025 are read day first (``--dayfirst`` decides for dates with slashes, which are otherwise
read day first only where the first number exceeds 12). Column names are recognised in the usual
spellings, with or without units (Time, Date, HR, Pulse Rate, PR (bpm), SpO2 (%), ...), or given with
--time-col, --date-col, --hr-col, --spo2-col. Readings outside 25-250 bpm or 50-100 % (what oximeters
write while searching) and rows without a readable time are ignored.

Every window goes through the complete pipeline in three ways, as in scripts/eval_denoiser.py:
classical, the bracelet network in the firmware's integer arithmetic, and the server network (if
onnxruntime is installed). A window is compared with the median of the reference readings inside
its own time span (shifted by --ref-lag-s for a device that reports late; ``auto`` tries -15..15 s
and keeps a shift only if it clearly beats none, which needs heart-rate changes in the recording:
rest, then walking), if there are at least --min-ref of them. Reported per path: windows that get a
value, mean error (bias, device minus reference), mean absolute error, 95 % limits of agreement
(Bland-Altman), the share of heart rates within 5 bpm and the number beyond 10 bpm, SpO2 ARMS (the
accuracy measure of ISO 80601-2-61) and why the other windows got nothing.

With --per-window, every window's values, its red/IR ratio R (``<path>_r``, the input of
suguard_ml.signal.spo2.fit_spo2_calibration) and the reference readings go to a CSV.

The reference has its own error (a fingertip oximeter about ±2 bpm and 2-3 points of SpO2; a chest
strap is the better heart-rate reference), and at home SpO2 stays at 94-99 %: this measures the
bias at normal saturation, not the accuracy over 70-100 % that only a controlled desaturation
study can show.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

ML = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ML))

from suguard_ml.pipeline import SuGuardPipeline  # noqa: E402

TIME_NAMES = ("timestamp", "datetime", "date_time", "time", "ts", "t", "unix_time", "time_s")
DATE_NAMES = ("date", "day")
HR_NAMES = ("hr", "heart_rate", "heartrate", "hr_bpm", "pulse", "pulse_rate", "pr", "pr_bpm", "bpm", "heart_rate_bpm")
SPO2_NAMES = ("spo2", "spo2_pct", "spo2_percent", "sao2", "oxygen", "oxygen_level", "o2", "spo_2")
HR_RANGE, SPO2_RANGE = (25.0, 250.0), (50.0, 100.0)
LAG_SCAN_S = np.arange(-15.0, 15.5, 1.0)
TIME_OF_DAY = re.compile(r"^\s*\d{1,2}:\d{2}(:\d{2}(\.\d+)?)?\s*$")
NUMERIC_DATE = re.compile(r"^\s*(\d{1,2})([./-])(\d{1,2})\2(\d{2,4})")


def _norm(name) -> str:
    s = re.sub(r"\(.*?\)|\[.*?\]", "", str(name).lower())
    s = re.sub(r"[\s\-/.]+", "_", s.strip())
    return re.sub(r"[^a-z0-9_]", "", s).strip("_")


def _column(df: pd.DataFrame, names: tuple, given: str | None) -> str | None:
    if given:
        if given not in df:
            raise SystemExit(f"column {given!r} is not in the reference file (columns: {list(df.columns)})")
        return given
    by_norm = {}
    for c in df.columns:
        by_norm.setdefault(_norm(c), c)
    return next((by_norm[n] for n in names if n in by_norm), None)


def _dayfirst(text: pd.Series, choice: str) -> bool:
    """Whether numeric dates (05.11.2025, 05/11/2025) put the day first: 'yes'/'no', or for 'auto'
    day first when the separator is a dot or any first number exceeds 12, month first when any
    second number does."""
    if choice in ("yes", "no"):
        return choice == "yes"
    m = text.str.extract(NUMERIC_DATE)
    if m[0].isna().all():
        return False
    first, sep, second = pd.to_numeric(m[0], errors="coerce"), m[1], pd.to_numeric(m[2], errors="coerce")
    if (second > 12).any():
        return False
    return bool((first > 12).any() or (sep == ".").any())


def _times(col: pd.Series, tz_offset_h: float, dayfirst: str = "auto") -> np.ndarray:
    """Unix seconds of a time column: numbers are unix seconds (milliseconds above 1e11; small
    numbers are no time), text with an offset or a zone (+05:00, +0500, +05, Z, UTC) exact, other
    text local time at ``tz_offset_h``; unreadable entries (a device's placeholder rows) are NaN."""
    num = pd.to_numeric(col, errors="coerce").to_numpy(dtype=float)
    out = np.where(num > 1e11, num / 1000.0, np.where(num > 1e8, num, np.nan))
    rows = np.flatnonzero(np.isnan(num) & col.notna().to_numpy())
    if rows.size:
        text = col.iloc[rows].astype(str).str.strip()
        day_first = _dayfirst(text, dayfirst)
        epoch_utc = pd.Timestamp("1970-01-01", tz="UTC")
        for i, s in zip(rows, text):
            s = re.sub(r"(?<=\d)z$", "Z", s)                    # a lower-case zone letter is UTC too
            try:
                ts = pd.to_datetime(s, dayfirst=day_first and NUMERIC_DATE.match(s) is not None)
            except (ValueError, TypeError, OverflowError):
                continue
            if ts is pd.NaT or (isinstance(ts, float) and math.isnan(ts)):
                continue
            if ts.tzinfo is not None:
                out[i] = (ts.tz_convert("UTC") - epoch_utc).total_seconds()
            else:
                out[i] = (ts - pd.Timestamp("1970-01-01")).total_seconds() - tz_offset_h * 3600.0
    return out


def load_reference(path, time_col=None, date_col=None, hr_col=None, spo2_col=None, tz_offset_h=0.0,
                   dayfirst="auto"):
    """Reference readings as a table t (unix s), hr, spo2, and the columns used."""
    try:
        df = pd.read_csv(path)
    except pd.errors.EmptyDataError:
        raise SystemExit(f"the reference file {path} is empty") from None
    tc = _column(df, TIME_NAMES, time_col)
    dc = _column(df, DATE_NAMES, date_col)
    if tc is None and dc is not None:
        tc, dc = dc, None                                  # a single "Date" column with date and time
    if tc is None:
        raise SystemExit(f"no time column in {path} (columns: {list(df.columns)}); pass --time-col")
    hc, sc = _column(df, HR_NAMES, hr_col), _column(df, SPO2_NAMES, spo2_col)
    if hc is None and sc is None:
        raise SystemExit(f"no heart-rate or SpO2 column in {path} (columns: {list(df.columns)}); "
                         "pass --hr-col / --spo2-col")
    times = df[tc]
    clock_only = times.astype(str).str.match(TIME_OF_DAY)
    if clock_only.mean() > 0.5:                             # times of day: they need the date column
        if dc is None or dc == tc:
            raise SystemExit(f"the column {tc!r} holds times of day without a date; pass --date-col")
        times = df[dc].astype(str).str.strip() + " " + times.astype(str).str.strip()
    else:
        dc = None
    ref = pd.DataFrame({"t": _times(times, tz_offset_h, dayfirst)})
    for key, col, (lo, hi) in (("hr", hc, HR_RANGE), ("spo2", sc, SPO2_RANGE)):
        v = pd.to_numeric(df[col], errors="coerce") if col is not None else pd.Series(np.nan, index=df.index)
        ref[key] = v.where(v.between(lo, hi)).to_numpy(dtype=float)
    ref = ref[np.isfinite(ref["t"])].sort_values("t").reset_index(drop=True)
    return ref, {"time": tc, "date": dc, "hr": hc, "spo2": sc}


def load_windows(path) -> tuple[list[dict], int, int]:
    """Dated windows of a windows.jsonl file, the number without a time and the number unreadable
    (e.g. a line cut off when a recording stopped)."""
    out, undated, bad = [], 0, 0
    with open(path) as fh:
        for line in fh:
            if not line.strip():
                continue
            try:
                w = json.loads(line)
                ts = w.get("ts", w.get("timestamp"))
                if ts is None:
                    undated += 1
                    continue
                w["ts"] = float(ts)
                if not (len(w["red"]) == len(w["ir"]) and len(w["ir"]) > 0):
                    raise ValueError("red and ir differ")
            except (ValueError, KeyError, TypeError, AttributeError):
                bad += 1
                continue
            out.append(w)
    return out, undated, bad


def default_pipelines(models: Path) -> dict:
    pipes = {"classical": SuGuardPipeline(denoiser=None)}
    if (models / "denoiser_edge_int.npz").exists():
        from suguard_ml.models.edge_int import EdgeDenoiserInt
        pipes["bracelet"] = SuGuardPipeline(denoiser=EdgeDenoiserInt(models / "denoiser_edge_int.npz"))
    try:
        import onnxruntime  # noqa: F401
        has_ort = True
    except ImportError:
        has_ort = False
    if has_ort and (models / "denoiser.onnx").exists():
        from suguard_ml.models.denoiser import Denoiser
        pipes["server"] = SuGuardPipeline(denoiser=Denoiser(models / "denoiser.onnx"))
    return pipes


def analyze_windows(windows: list[dict], pipes: dict) -> list[dict]:
    """The pipeline's answer for every window and path (value None where it gives none)."""
    rows = []
    for w in windows:
        fs = float(w.get("fs") or 50.0)
        n = len(w["ir"])
        row = {"ts": w["ts"], "t_end": w["ts"] + n / fs, "seq": w.get("seq"), "results": {}}
        for name, pipe in pipes.items():
            try:
                r = pipe.analyze(w["red"], w["ir"], fs=fs, temperature_c=w.get("temp_c"))
            except (ValueError, TypeError, KeyError) as e:
                row["results"][name] = {"hr": None, "spo2": None, "r": None, "reasons": [f"invalid_window: {e}"],
                                        "spo2_reason": None, "fallback": False}
                continue
            row["results"][name] = {"hr": r["heart_rate"]["bpm"], "spo2": r["spo2"]["percent"], "r": r["spo2"]["r_ratio"],
                                    "reasons": list(r.get("reason") or []), "spo2_reason": r["spo2"]["reason"],
                                    "fallback": bool(r.get("low_perfusion_fallback"))}
        rows.append(row)
    return rows


def reference_for(rows: list[dict], ref: pd.DataFrame, lag_s: float, min_ref: int, stat=np.median) -> list[tuple]:
    """(reference heart rate, reference SpO2) per window: the median (``stat``) of the readings inside it."""
    t = ref["t"].to_numpy()
    out = []
    for row in rows:
        a, b = np.searchsorted(t, row["ts"] + lag_s, "left"), np.searchsorted(t, row["t_end"] + lag_s, "right")
        vals = []
        for key in ("hr", "spo2"):
            v = ref[key].to_numpy()[a:b]
            v = v[np.isfinite(v)]
            vals.append(float(stat(v)) if v.size >= min_ref else None)
        out.append(tuple(vals))
    return out


def summarize(err) -> dict:
    err = np.asarray(err, dtype=float)
    if err.size == 0:
        return {"n": 0}
    bias = float(np.mean(err))
    out = {"n": int(err.size), "bias": bias, "mae": float(np.mean(np.abs(err))),
           "rms": float(math.sqrt(np.mean(err ** 2))), "sd": None, "loa_95": None}
    if err.size >= 2:                                       # limits of agreement need a spread
        sd = float(np.std(err, ddof=1))
        out.update(sd=sd, loa_95=[bias - 1.96 * sd, bias + 1.96 * sd])
    return out


def score(rows: list[dict], refs: list[tuple], path: str) -> dict:
    hr_err, sp_err, why_hr, why_sp = [], [], Counter(), Counter()
    n_hr = n_sp = fallback = 0
    ref_sp = []
    for row, (r_hr, r_sp) in zip(rows, refs):
        res = row["results"][path]
        if r_hr is not None:
            n_hr += 1
            if res["hr"] is not None:
                hr_err.append(res["hr"] - r_hr)
                fallback += res["fallback"]
            else:
                why_hr.update(res["reasons"] or ["unreliable"])
        if r_sp is not None:
            n_sp += 1
            ref_sp.append(r_sp)
            if res["spo2"] is not None:
                sp_err.append(res["spo2"] - r_sp)
            else:
                why_sp.update([res["spo2_reason"] or "unreliable_window"])
    hr = summarize(hr_err)
    if hr_err:
        a = np.abs(hr_err)
        hr.update(within_5bpm=float(np.mean(a <= 5.0)), over_10bpm=int(np.sum(a > 10.0)))
    sp = summarize(sp_err)
    if sp_err:
        sp.update(arms=sp["rms"], over_4pts=int(np.sum(np.abs(sp_err) > 4.0)))
    return {"hr": {"windows_with_reference": n_hr, "coverage": len(hr_err) / n_hr if n_hr else None, **hr,
                   "decided_by_the_classical_checks": fallback, "why_no_value": dict(why_hr.most_common())},
            "spo2": {"windows_with_reference": n_sp, "coverage": len(sp_err) / n_sp if n_sp else None, **sp,
                     "reference_range": [min(ref_sp), max(ref_sp)] if ref_sp else None,
                     "why_no_value": dict(why_sp.most_common())}}


def choose_lag(rows, ref, min_ref, path="classical") -> dict:
    """Search a reference delay in LAG_SCAN_S on the heart rates of ``path`` (median absolute error
    against the mean reading inside each window, which, unlike the median, moves with every reading
    a shift adds or drops). A shift is kept only if the windows compared at no shift show heart-rate
    changes (interquartile range of the reference >= 3 bpm) and it lowers that error by more than
    20 % and 0.5 bpm; otherwise none is used."""
    def error(lag):
        refs = reference_for(rows, ref, float(lag), min_ref, stat=np.mean)
        pairs = [(row["results"][path]["hr"], r) for row, (r, _) in zip(rows, refs)
                 if r is not None and row["results"][path]["hr"] is not None]
        if len(pairs) < 10:
            return None, None
        e = np.array([a - b for a, b in pairs])
        return float(np.median(np.abs(e))), np.array([b for _, b in pairs])

    e0, ref0 = error(0.0)
    if e0 is None:
        return {"lag_s": 0.0, "status": "not determinable: fewer than 10 windows with a heart rate and a "
                                        "heart-rate reference at no shift"}
    spread = float(np.subtract(*np.percentile(ref0, [75, 25])))
    best = (0.0, e0)
    for lag in sorted(LAG_SCAN_S, key=abs):
        e, _ = error(lag)
        if e is not None and e < best[1] - 1e-9:
            best = (float(lag), e)
    out = {"error_at_0_s": e0, "best_lag_s": best[0], "error_at_best": best[1], "reference_hr_iqr": spread}
    if spread < 3.0:
        return {**out, "lag_s": 0.0, "status": "not determinable: the heart rate hardly changes in the "
                                               "recording (record rest, then walking)"}
    if best[0] != 0.0 and best[1] < 0.8 * e0 and best[1] < e0 - 0.5:
        return {**out, "lag_s": best[0], "status": "found"}
    return {**out, "lag_s": 0.0, "status": "no shift beats none clearly"}


def fmt(x, d=1):
    return "–" if x is None else f"{x:.{d}f}"


def print_report(rep: dict) -> None:
    w, cols = rep["windows"], rep["reference_columns"]
    print(f"{w['dated']} windows ({w['undated']} without a time, {w['unreadable']} unreadable), "
          f"{w['with_reference']} with reference readings")
    print(f"reference columns: time {cols['time']!r}" + (f" + date {cols['date']!r}" if cols.get("date") else "")
          + f", heart rate {cols['hr']!r}, SpO2 {cols['spo2']!r}; times without an offset read as "
          f"UTC{rep['tz_offset_h']:+g}")
    lag = rep["ref_lag"]
    if lag.get("status"):
        detail = (f" (median |error| {fmt(lag['error_at_0_s'])} bpm at 0 s, {fmt(lag['error_at_best'])} at "
                  f"{lag['best_lag_s']:+.0f} s)" if "error_at_0_s" in lag else "")
        print(f"reference shift: auto, {lag['status']}; {lag['lag_s']:+.0f} s used{detail}")
    else:
        print(f"reference shift: {lag['lag_s']:+.0f} s")
    if w["dated"] and not w["with_reference"]:
        print("\nNo window overlaps the reference.", rep.get("hint", ""))
        return
    for name, p in rep["paths"].items():
        h, s = p["hr"], p["spo2"]
        print(f"\n{name}:")
        if h["windows_with_reference"]:
            line = f"  heart rate: {h.get('n', 0)} of {h['windows_with_reference']} windows ({100 * h['coverage']:.0f} %)"
            if h.get("n"):
                line += f", bias {fmt(h['bias'])} bpm, MAE {fmt(h['mae'])}"
                if h["loa_95"]:
                    line += f", 95 % limits {fmt(h['loa_95'][0])} to {fmt(h['loa_95'][1])}"
                line += f", within 5 bpm {100 * h['within_5bpm']:.0f} %, beyond 10 bpm {h['over_10bpm']}"
                if h["n"] < 10:
                    line += " (few windows)"
            print(line)
            if h["why_no_value"]:
                print("    no value:", ", ".join(f"{k} {v}" for k, v in h["why_no_value"].items()))
        if s["windows_with_reference"]:
            line = f"  SpO2: {s.get('n', 0)} of {s['windows_with_reference']} windows ({100 * s['coverage']:.0f} %)"
            if s.get("n"):
                line += (f", bias {fmt(s['bias'])} points, ARMS {fmt(s['arms'])}, beyond 4 points {s['over_4pts']} "
                         f"(reference {s['reference_range'][0]:.0f}-{s['reference_range'][1]:.0f} %)")
            print(line)
            if s["why_no_value"]:
                print("    no value:", ", ".join(f"{k} {v}" for k, v in s["why_no_value"].items()))


def overlap_hint(rows, ref) -> str:
    """Why nothing overlaps: the two time ranges and, when they are a whole number of hours apart,
    the likely time-zone mistake."""
    if not rows or ref.empty:
        return "The reference file has no readable times." if ref.empty else ""
    w0, w1 = rows[0]["ts"], max(r["t_end"] for r in rows)
    r0, r1 = float(ref["t"].iloc[0]), float(ref["t"].iloc[-1])
    utc = lambda t: pd.Timestamp(t, unit="s").strftime("%Y-%m-%d %H:%M:%S")  # noqa: E731
    msg = f"Windows {utc(w0)} to {utc(w1)} UTC, reference {utc(r0)} to {utc(r1)} UTC."
    hours = ((r0 + r1) / 2 - (w0 + w1) / 2) / 3600.0
    if 0.5 <= abs(hours) <= 14.5 and abs(hours - round(hours)) < 0.25:
        msg += f" They are about {abs(round(hours)):.0f} h apart: check --tz-offset-h."
    return msg


def local_offset_h() -> float:
    return time.localtime().tm_gmtoff / 3600.0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--windows", required=True, help="windows.jsonl recorded with suguard_monitor.py --record")
    ap.add_argument("--reference", required=True, help="CSV of the reference device")
    ap.add_argument("--time-col", help="name of the time column (default: recognised)")
    ap.add_argument("--date-col", help="name of the date column, for files with times of day in another column")
    ap.add_argument("--hr-col", help="name of the heart-rate column")
    ap.add_argument("--spo2-col", help="name of the SpO2 column")
    ap.add_argument("--tz-offset-h", type=float, default=None,
                    help="UTC offset of reference times written without one (default: this computer's)")
    ap.add_argument("--dayfirst", choices=("auto", "yes", "no"), default="auto",
                    help="numeric dates day first (05/11/2025 = 5 November)")
    ap.add_argument("--ref-lag-s", default="0", help="seconds by which the reference lags, or 'auto'")
    ap.add_argument("--min-ref", type=int, default=3, help="reference readings needed inside a window")
    ap.add_argument("--models", default=str(ML / "models"))
    ap.add_argument("--out", help="write the report as JSON")
    ap.add_argument("--per-window", help="write every window's values and reference as CSV")
    a = ap.parse_args(argv)

    tz = local_offset_h() if a.tz_offset_h is None else a.tz_offset_h
    ref, cols = load_reference(a.reference, a.time_col, a.date_col, a.hr_col, a.spo2_col, tz, a.dayfirst)
    windows, undated, bad = load_windows(a.windows)
    rows = analyze_windows(windows, default_pipelines(Path(a.models)))
    if a.ref_lag_s == "auto":
        lag = choose_lag(rows, ref, a.min_ref)
    else:
        lag = {"lag_s": float(a.ref_lag_s)}
    refs = reference_for(rows, ref, lag["lag_s"], a.min_ref)
    paths = list(rows[0]["results"]) if rows else []
    rep = {"reference_file": str(a.reference), "reference_columns": cols, "tz_offset_h": tz, "ref_lag": lag,
           "windows": {"dated": len(rows), "undated": undated, "unreadable": bad,
                       "with_reference": int(sum(r != (None, None) for r in refs))},
           "paths": {p: score(rows, refs, p) for p in paths}}
    if rows and not rep["windows"]["with_reference"]:
        rep["hint"] = overlap_hint(rows, ref)
    print_report(rep)
    if a.out:
        Path(a.out).write_text(json.dumps(rep, indent=2))
        print("\nwrote", a.out)
    if a.per_window:
        recs = []
        for row, (r_hr, r_sp) in zip(rows, refs):
            rec = {"ts": row["ts"], "seq": row["seq"], "ref_hr": r_hr, "ref_spo2": r_sp}
            for p, res in row["results"].items():
                rec.update({f"{p}_hr": res["hr"], f"{p}_spo2": res["spo2"], f"{p}_r": res["r"],
                            f"{p}_reasons": ";".join(res["reasons"])})
            recs.append(rec)
        pd.DataFrame(recs).to_csv(a.per_window, index=False)
        print("wrote", a.per_window)
    if rows and not rep["windows"]["with_reference"]:
        raise SystemExit(2)
    return rep


if __name__ == "__main__":
    main()
