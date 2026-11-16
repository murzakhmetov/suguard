"""Heart rate and SpO2 of recorded bracelet windows against a reference device.

    python scripts/validate_vitals.py --windows rec/windows.jsonl --reference oximeter.csv \
        [--tz-offset-h 5] [--ref-lag-s 0 | auto] [--out validation.json] [--per-window per_window.csv]

``windows.jsonl``: the raw windows that ``firmware/tools/suguard_monitor.py --record`` writes
(docs/DATA_COLLECTION.md). ``oximeter.csv``: a reference pulse oximeter or chest strap, one row per
reading, with a time column (unix seconds, or ISO-8601; times without an offset are local time at
``--tz-offset-h``) and a heart-rate and/or an SpO2 column. Column names are recognised
(time/timestamp/ts, hr/pulse/pr/bpm/heart_rate, spo2/sao2) or given with --time-col, --hr-col,
--spo2-col. Readings outside 25-250 bpm or 50-100 % (what oximeters write while searching) are
ignored.

Every window goes through the complete pipeline in three ways, as in scripts/eval_denoiser.py:
classical, the bracelet network in the firmware's integer arithmetic, and the server network (if
onnxruntime is installed). A window is compared with the median of the reference readings inside
its own time span (shifted by --ref-lag-s for a device that reports with a delay; ``auto`` picks
the shift in -15..15 s with the smallest heart-rate error of the classical path), if there are at
least --min-ref of them. Reported per path: windows that get a value, mean error (bias), mean
absolute error, 95 % limits of agreement (Bland-Altman), heart-rate errors within 5 / beyond 10 bpm,
SpO2 ARMS (the accuracy measure of ISO 80601-2-61) and why the other windows got nothing.

The reference has its own error (a fingertip oximeter about ±2 bpm and 2-3 points of SpO2; a chest
strap is the better heart-rate reference), and at home SpO2 stays at 94-99 %: this measures the
bias at normal saturation, not the accuracy over 70-100 % that only a controlled desaturation
study can show.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

ML = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ML))

from suguard_ml.pipeline import SuGuardPipeline  # noqa: E402

TIME_NAMES = ("time", "timestamp", "ts", "datetime", "date_time", "date", "t")
HR_NAMES = ("hr", "heart_rate", "heartrate", "hr_bpm", "pulse", "pulse_rate", "pr", "pr_bpm", "bpm")
SPO2_NAMES = ("spo2", "spo2_pct", "spo2_percent", "sao2", "oxygen", "o2")
HR_RANGE, SPO2_RANGE = (25.0, 250.0), (50.0, 100.0)
LAG_SCAN_S = np.arange(-15.0, 15.5, 1.0)


def _column(df: pd.DataFrame, names: tuple, given: str | None) -> str | None:
    if given:
        if given not in df:
            raise SystemExit(f"column {given!r} is not in the reference file (columns: {list(df.columns)})")
        return given
    low = {str(c).lower().strip(): c for c in df.columns}
    return next((low[n] for n in names if n in low), None)


def _times(col: pd.Series, tz_offset_h: float) -> np.ndarray:
    """Unix seconds of a time column: numbers are unix seconds (small ones are no time), strings with
    an offset ("...+05:00", "...Z") exact, other strings local time at ``tz_offset_h``; anything
    unreadable (a device's placeholder rows) becomes NaN."""
    num = pd.to_numeric(col, errors="coerce").to_numpy(dtype=float)
    out = np.where(num > 1e8, num, np.nan)
    text = np.flatnonzero(np.isnan(num))
    if text.size:
        s = col.iloc[text].astype(str).str.strip()
        aware = s.str.contains(r"(?:Z|[+-]\d{2}:?\d{2})$", regex=True).to_numpy()
        if aware.any():
            dt = pd.to_datetime(s[aware], format="mixed", utc=True, errors="coerce")
            out[text[aware]] = (dt - pd.Timestamp("1970-01-01", tz="UTC")).dt.total_seconds().to_numpy()
        if (~aware).any():
            dt = pd.to_datetime(s[~aware], format="mixed", errors="coerce")
            out[text[~aware]] = (dt - pd.Timestamp("1970-01-01")).dt.total_seconds().to_numpy() - tz_offset_h * 3600.0
    return out


def load_reference(path, time_col=None, hr_col=None, spo2_col=None, tz_offset_h=0.0):
    """Reference readings as a table t (unix s), hr, spo2, and the columns used."""
    df = pd.read_csv(path)
    tc = _column(df, TIME_NAMES, time_col)
    if tc is None:
        raise SystemExit(f"no time column in {path} (columns: {list(df.columns)}); pass --time-col")
    hc, sc = _column(df, HR_NAMES, hr_col), _column(df, SPO2_NAMES, spo2_col)
    if hc is None and sc is None:
        raise SystemExit(f"no heart-rate or SpO2 column in {path} (columns: {list(df.columns)}); "
                         "pass --hr-col / --spo2-col")
    ref = pd.DataFrame({"t": _times(df[tc], tz_offset_h)})
    for key, col, (lo, hi) in (("hr", hc, HR_RANGE), ("spo2", sc, SPO2_RANGE)):
        v = pd.to_numeric(df[col], errors="coerce") if col is not None else pd.Series(np.nan, index=df.index)
        ref[key] = v.where(v.between(lo, hi)).to_numpy(dtype=float)
    ref = ref[np.isfinite(ref["t"])].sort_values("t").reset_index(drop=True)
    return ref, {"time": tc, "hr": hc, "spo2": sc}


def load_windows(path) -> tuple[list[dict], int]:
    """Dated windows of a windows.jsonl file, and the number skipped for lack of a time."""
    out, undated = [], 0
    with open(path) as fh:
        for line in fh:
            if not line.strip():
                continue
            w = json.loads(line)
            ts = w.get("ts", w.get("timestamp"))
            if ts is None:
                undated += 1
                continue
            w["ts"] = float(ts)
            out.append(w)
    return out, undated


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
                row["results"][name] = {"hr": None, "spo2": None, "reasons": [f"invalid_window: {e}"],
                                        "spo2_reason": None, "fallback": False}
                continue
            row["results"][name] = {"hr": r["heart_rate"]["bpm"], "spo2": r["spo2"]["percent"],
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
    sd = float(np.std(err, ddof=1)) if err.size > 1 else 0.0
    return {"n": int(err.size), "bias": bias, "mae": float(np.mean(np.abs(err))), "sd": sd,
            "loa_95": [bias - 1.96 * sd, bias + 1.96 * sd], "rms": float(math.sqrt(np.mean(err ** 2)))}


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


def choose_lag(rows, ref, min_ref, path="classical"):
    """The shift in LAG_SCAN_S at which the heart rates of ``path`` agree best with the reference
    (median absolute error against the mean reading inside each window, which, unlike the median,
    moves with every reading the shift adds or drops); ties go to the smaller shift. Shifts at which
    fewer than 10 windows can be compared are skipped; None if that leaves none."""
    best = None
    for lag in sorted(LAG_SCAN_S, key=abs):
        refs = reference_for(rows, ref, float(lag), min_ref, stat=np.mean)
        err = [row["results"][path]["hr"] - r for row, (r, _) in zip(rows, refs)
               if r is not None and row["results"][path]["hr"] is not None]
        if len(err) < 10:
            continue
        m = float(np.median(np.abs(err)))
        if best is None or m < best[1] - 1e-9:
            best = (float(lag), m)
    return None if best is None else best[0]


def fmt(x, d=1):
    return "–" if x is None else f"{x:.{d}f}"


def print_report(rep: dict) -> None:
    print(f"{rep['windows']['dated']} windows ({rep['windows']['undated']} without a time), "
          f"{rep['windows']['with_reference']} with reference readings; reference shift {rep['ref_lag_s']:+.0f} s")
    for name, p in rep["paths"].items():
        h, s = p["hr"], p["spo2"]
        print(f"\n{name}:")
        if h["windows_with_reference"]:
            print(f"  heart rate: {h.get('n', 0)} of {h['windows_with_reference']} windows "
                  f"({100 * h['coverage']:.0f} %)" + (
                      f", bias {fmt(h['bias'])} bpm, MAE {fmt(h['mae'])}, 95 % limits {fmt(h['loa_95'][0])} to "
                      f"{fmt(h['loa_95'][1])}, within 5 bpm {100 * h['within_5bpm']:.0f} %, beyond 10 bpm {h['over_10bpm']}"
                      if h.get("n") else ""))
            if h["why_no_value"]:
                print("    no value:", ", ".join(f"{k} {v}" for k, v in h["why_no_value"].items()))
        if s["windows_with_reference"]:
            print(f"  SpO2: {s.get('n', 0)} of {s['windows_with_reference']} windows ({100 * s['coverage']:.0f} %)" + (
                f", bias {fmt(s['bias'])} points, ARMS {fmt(s['arms'])}, beyond 4 points {s['over_4pts']} "
                f"(reference {s['reference_range'][0]:.0f}-{s['reference_range'][1]:.0f} %)" if s.get("n") else ""))
            if s["why_no_value"]:
                print("    no value:", ", ".join(f"{k} {v}" for k, v in s["why_no_value"].items()))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--windows", required=True, help="windows.jsonl recorded with suguard_monitor.py --record")
    ap.add_argument("--reference", required=True, help="CSV of the reference device")
    ap.add_argument("--time-col", help="name of the time column (default: recognised)")
    ap.add_argument("--hr-col", help="name of the heart-rate column")
    ap.add_argument("--spo2-col", help="name of the SpO2 column")
    ap.add_argument("--tz-offset-h", type=float, default=0.0,
                    help="UTC offset of reference times written without one (Kazakhstan: 5)")
    ap.add_argument("--ref-lag-s", default="0", help="seconds by which the reference lags, or 'auto'")
    ap.add_argument("--min-ref", type=int, default=3, help="reference readings needed inside a window")
    ap.add_argument("--models", default=str(ML / "models"))
    ap.add_argument("--out", help="write the report as JSON")
    ap.add_argument("--per-window", help="write every window's values and reference as CSV")
    a = ap.parse_args(argv)

    ref, cols = load_reference(a.reference, a.time_col, a.hr_col, a.spo2_col, a.tz_offset_h)
    windows, undated = load_windows(a.windows)
    rows = analyze_windows(windows, default_pipelines(Path(a.models)))
    lag = 0.0
    if a.ref_lag_s == "auto":
        found = choose_lag(rows, ref, a.min_ref)
        lag = 0.0 if found is None else found
    else:
        lag = float(a.ref_lag_s)
    refs = reference_for(rows, ref, lag, a.min_ref)
    paths = list(rows[0]["results"]) if rows else []
    rep = {"reference_file": str(a.reference), "reference_columns": cols, "ref_lag_s": lag,
           "windows": {"dated": len(rows), "undated": undated,
                       "with_reference": int(sum(r != (None, None) for r in refs))},
           "paths": {p: score(rows, refs, p) for p in paths}}
    print_report(rep)
    if a.out:
        Path(a.out).write_text(json.dumps(rep, indent=2))
        print("\nwrote", a.out)
    if a.per_window:
        recs = []
        for row, (r_hr, r_sp) in zip(rows, refs):
            rec = {"ts": row["ts"], "seq": row["seq"], "ref_hr": r_hr, "ref_spo2": r_sp}
            for p, res in row["results"].items():
                rec.update({f"{p}_hr": res["hr"], f"{p}_spo2": res["spo2"], f"{p}_reasons": ";".join(res["reasons"])})
            recs.append(rec)
        pd.DataFrame(recs).to_csv(a.per_window, index=False)
        print("wrote", a.per_window)
    return rep


if __name__ == "__main__":
    main()
