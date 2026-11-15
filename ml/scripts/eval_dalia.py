"""Heart rate under real wrist motion: PPG-DaLiA (run in Colab).

PPG-DaLiA (Reiss et al., Sensors 2019; UCI id 495): 15 people, ~2.5 h each
of daily activities (sitting, stairs, table soccer, cycling, driving, lunch,
walking, working) with an Empatica E4 on the wrist and ECG-derived reference
heart rate for 8-s windows (2-s shift).

    python scripts/eval_dalia.py --root <folder that holds S1/S1.pkl ... S15/S15.pkl> --out models/metrics

(The UCI download is an archive that contains another archive; the Colab
notebook unpacks both and finds the folder.)

Two evaluations, written to dalia_hr_eval.json:

``gated_pipeline``  What the bracelet would show: the complete pipeline with
    every reliability check on consecutive 10.24-s windows, for the classical
    path, the server denoiser and the integer bracelet model. Reported: how
    often a heart rate is given (coverage), how wrong the given values are,
    and both per activity. This is the test of the claim "a value that is
    shown can be trusted" on motion that was not simulated.

``spectral_tracking``  Heart rate of every window from the spectral peak,
    with and without the denoiser, no checks, every window scored. For a
    rough comparison only: the dataset paper (Reiss et al. 2019) reports a
    mean absolute error of about 7.7 bpm for its CNN ensemble and of 15-20
    bpm for two earlier spectral methods; all of those also use the wrist
    accelerometer, which this pipeline does not have.

Caveats. The E4 records one (green) channel in arbitrary units, not raw
red/IR counts, so the recording is turned into MAX30102-like counts with
assumptions: the red channel is a copy of the IR one at a fixed ratio (so the
checks that compare the two wavelengths pass trivially and the network
cannot use the red/IR motion cue it was built around), and the quietest
quarter of each recording is given a pulse amplitude of 1 % of the light
level (which the amplitude checks then refer to). Which way up the E4 signal
is, is decided per subject with the ECG reference (the way in which the beat
detector agrees with it in more windows) and written to the report. Read
the result as a lower bound on what the two-wavelength sensor can reject.
"""

from __future__ import annotations

import argparse
import json
import pickle
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from suguard_ml.config import ADC_MAX, FS, WINDOW  # noqa: E402
from suguard_ml.models.denoiser import Denoiser  # noqa: E402
from suguard_ml.pipeline import SuGuardPipeline  # noqa: E402
from suguard_ml.signal.beats import pulse_polarity, spectral_hr  # noqa: E402
from suguard_ml.signal.filters import bandpass, resample  # noqa: E402

ACTIVITIES = {0: "transient", 1: "sitting", 2: "stairs", 3: "table_soccer", 4: "cycling", 5: "driving",
              6: "lunch", 7: "walking", 8: "working"}
BVP_FS = 64.0             # Empatica E4
LABEL_SHIFT_S, LABEL_CENTRE_S = 2.0, 4.0      # reference label i covers [2i, 2i + 8] s
ACTIVITY_FS = 4.0

# Assumptions that turn the single-channel recording into two-channel raw counts.
REST_PI = 0.01            # pulse amplitude (peak to peak, AC/DC) given to the quietest quarter of a recording
IR_DC, R_RATIO = 100_000.0, 0.6               # light level (counts) and red/IR ratio of ratios (SpO2 ~ 97 %)
RED_DC = 60_000.0


def load_subject(pkl: Path) -> dict:
    with open(pkl, "rb") as fh:
        return pickle.load(fh, encoding="latin1")


def labels_at(d: dict, centres_s: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Reference heart rate (NaN where there is none) and activity for windows centred at ``centres_s``."""
    centres_s = np.asarray(centres_s, dtype=float)
    label = np.asarray(d.get("label", np.zeros(0)), dtype=float).ravel()
    act = np.asarray(d.get("activity", np.zeros(0)), dtype=float).ravel()
    i = np.round((centres_s - LABEL_CENTRE_S) / LABEL_SHIFT_S).astype(int)
    ok = (i >= 0) & (i < label.size)
    hr = np.full(centres_s.size, np.nan)
    hr[ok] = label[i[ok]]
    a = act[np.clip((centres_s * ACTIVITY_FS).astype(int), 0, act.size - 1)] if act.size > 1 else np.zeros(centres_s.size)
    return hr, a


def pulse_signal(d: dict) -> tuple[np.ndarray, int]:
    """The wrist BVP at FS, band-limited, systolic peaks pointing up; and the
    sign that was applied to get it that way (see suguard_ml.signal.beats.pulse_polarity)."""
    bvp = np.asarray(d["signal"]["wrist"]["BVP"], dtype=float).ravel()
    bad = ~np.isfinite(bvp)
    if bvp.size < 2 or bad.all():
        return np.zeros(int(bvp.size * FS / BVP_FS)), 1
    if bad.any():                               # one NaN would spread over the whole zero-phase filter
        idx = np.arange(bvp.size)
        bvp = np.interp(idx, idx[~bad], bvp[~bad])
    x = resample(bandpass(bvp, BVP_FS, 0.4, 12.0), BVP_FS, FS)
    n = x.size // WINDOW
    ref, _ = labels_at(d, (np.arange(n) * WINDOW + WINDOW / 2) / FS)
    sign = pulse_polarity(x, FS, ref_bpm=ref, window=WINDOW)
    return sign * x, sign


def to_counts(x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Raw red and IR counts (as the MAX30102 would deliver them) from the pulse signal."""
    n = x.size // WINDOW
    amp = np.array([np.percentile(w, 97) - np.percentile(w, 3) for w in x[:n * WINDOW].reshape(n, WINDOW)])
    rest = float(np.percentile(amp[amp > 0], 25)) if np.any(amp > 0) else 1.0   # nothing to scale: any value will do
    bv = np.clip(REST_PI * x / rest, -0.95, 0.95)             # more blood, less light
    ir = np.clip(np.round(IR_DC * (1.0 - bv)), 0, ADC_MAX)
    red = np.clip(np.round(RED_DC * (1.0 - R_RATIO * bv)), 0, ADC_MAX)
    return red, ir


def gated_windows(d: dict, pipes: dict[str, SuGuardPipeline]) -> dict:
    """Per path: absolute heart-rate error of every consecutive 10.24-s window
    (NaN where the pipeline gave no value), with the activity of the window."""
    x, sign = pulse_signal(d)
    red, ir = to_counts(x)
    starts = np.arange(0, ir.size - WINDOW + 1, WINDOW)
    ref, act = labels_at(d, (starts + WINDOW / 2) / FS)
    keep = np.isfinite(ref)
    starts, ref, act = starts[keep], ref[keep], act[keep]
    out = {"activity": act, "polarity": sign}
    for name, pipe in pipes.items():
        err = np.full(starts.size, np.nan)
        for k, s in enumerate(starts):
            try:
                hr = pipe.analyze(red[s:s + WINDOW], ir[s:s + WINDOW], fs=FS)["heart_rate"]["bpm"]
            except ValueError:                  # a window the pipeline refuses to analyse gives no value
                hr = None
            if hr is not None:
                err[k] = abs(hr - ref[k])
        out[name] = err
    return out


def coverage_and_error(err: np.ndarray) -> dict:
    given = np.isfinite(err)
    e = err[given]
    return {"windows": int(err.size), "hr_coverage": float(given.mean()) if err.size else None,
            "hr_mae": float(e.mean()) if e.size else None,
            "hr_p95": float(np.percentile(e, 95)) if e.size else None,
            "hr_errors_over_10bpm": int(np.sum(e > 10)),
            "share_of_given_values_over_10bpm": float(np.mean(e > 10)) if e.size else None}


def summarise_gated(per_subject: dict[str, dict], paths: list[str]) -> dict:
    out = {"assumptions": {"rest_pulse_amplitude_ac_dc": REST_PI, "red_ir_ratio": R_RATIO,
                           "note": "single green channel: red is a copy of IR, red/IR checks pass trivially"},
           "polarity_by_subject": {s: int(r["polarity"]) for s, r in per_subject.items()}}
    act = np.concatenate([r["activity"] for r in per_subject.values()]) if per_subject else np.zeros(0)
    for p in paths:
        err = np.concatenate([r[p] for r in per_subject.values()]) if per_subject else np.zeros(0)
        res = coverage_and_error(err)
        res["by_activity"] = {ACTIVITIES.get(int(a), str(int(a))): {k: v for k, v in coverage_and_error(err[act == a]).items()
                                                                    if k in ("windows", "hr_coverage", "hr_mae", "hr_errors_over_10bpm")}
                              for a in np.unique(act)}
        res["by_subject"] = {s: {k: v for k, v in coverage_and_error(r[p]).items()
                                 if k in ("windows", "hr_coverage", "hr_mae", "hr_errors_over_10bpm")}
                             for s, r in per_subject.items()}
        out[p] = res
    return out


def spectral_errors(d: dict, den: Denoiser | None) -> dict:
    """Spectral heart rate of every reference window, no reliability checks."""
    x, _ = pulse_signal(d)
    label = np.asarray(d.get("label", np.zeros(0)), dtype=float).ravel()
    dn = den.denoise_bv(x, R_RATIO * x, FS) if (den is not None and x.size >= WINDOW) else None
    y_hat = {k: [] for k in ["spectral", "spectral_tracked"] + (["denoised_tracked"] if dn is not None else [])}
    p_s, p_d = None, None
    for i in range(label.size):
        c = (LABEL_CENTRE_S + LABEL_SHIFT_S * i) * FS
        a, b = int(c - WINDOW / 2), int(c + WINDOW / 2)
        if a < 0 or b > x.size:
            for k in y_hat:
                y_hat[k].append(np.nan)
            continue
        hs, _ = spectral_hr(x[a:b], FS)
        ht, _ = spectral_hr(x[a:b], FS, prior_bpm=p_s)
        y_hat["spectral"].append(hs)
        y_hat["spectral_tracked"].append(ht)
        p_s = ht or p_s
        if dn is not None:
            hd, _ = spectral_hr(dn.ir_bv[a:b], FS, prior_bpm=p_d)
            y_hat["denoised_tracked"].append(hd)
            p_d = hd or p_d
    _, acts = labels_at(d, LABEL_CENTRE_S + LABEL_SHIFT_S * np.arange(label.size))
    out = {}
    for k, v in y_hat.items():
        if not v:
            continue
        e = np.abs(np.array(v, dtype=float) - label)
        if not np.isfinite(e).any():
            continue
        out[k] = {"mae": float(np.nanmean(e)),
                  "by_activity": {ACTIVITIES.get(int(a), str(int(a))): float(np.nanmean(e[acts == a]))
                                  for a in np.unique(acts) if np.isfinite(e[acts == a]).any()}}
    return out


def gated_line(name: str, r: dict) -> str:
    if not r["windows"]:
        return f"{name:10s} no window with a reference heart rate"
    if r["hr_mae"] is None:
        return f"{name:10s} no heart rate given in any of {r['windows']} windows"
    return (f"{name:10s} heart rate given in {100 * r['hr_coverage']:.0f} % of {r['windows']} windows; "
            f"MAE {r['hr_mae']:.2f} bpm, p95 {r['hr_p95']:.1f}, errors > 10 bpm: {r['hr_errors_over_10bpm']} "
            f"({100 * r['share_of_given_values_over_10bpm']:.1f} % of the given values)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True, help="PPG_FieldStudy folder with S1..S15")
    ap.add_argument("--out", default="models/metrics")
    ap.add_argument("--models", default="models")
    ap.add_argument("--subjects", type=int, default=None, help="only the first N subjects (quick run)")
    a = ap.parse_args()
    models = Path(a.models)
    den = Denoiser(models / "denoiser.onnx") if (models / "denoiser.onnx").exists() else None
    pipes = {"classical": SuGuardPipeline(denoiser=None)}
    if den is not None:
        pipes["server"] = SuGuardPipeline(denoiser=den)
    if (models / "denoiser_edge_int.npz").exists():
        from suguard_ml.models.edge_int import EdgeDenoiserInt
        pipes["bracelet"] = SuGuardPipeline(denoiser=EdgeDenoiserInt(models / "denoiser_edge_int.npz"))

    files = sorted(Path(a.root).glob("S*/S*.pkl"), key=lambda p: int(p.stem[1:]))[:a.subjects]
    if not files:
        sys.exit(f"no S*/S*.pkl under {a.root}")
    spectral, gated = {}, {}
    for pkl in files:
        d = load_subject(pkl)
        gated[pkl.stem] = gated_windows(d, pipes)
        spectral[pkl.stem] = spectral_errors(d, den)
        line = {p: ("%.0f %% given, MAE %s" % (100 * np.isfinite(gated[pkl.stem][p]).mean(),
                                                "%.1f" % np.nanmean(gated[pkl.stem][p])
                                                if np.isfinite(gated[pkl.stem][p]).any() else "-")
                    if gated[pkl.stem][p].size else "no window") for p in pipes}
        print(pkl.stem, "gated:", line, "| spectral MAE:", {k: round(v["mae"], 1) for k, v in spectral[pkl.stem].items()},
              flush=True)

    methods = sorted({m for r in spectral.values() for m in r})
    report = {
        "gated_pipeline": summarise_gated(gated, list(pipes)),
        "spectral_tracking": {**spectral, "mean_mae": {
            m: float(np.mean([r[m]["mae"] for r in spectral.values() if m in r])) for m in methods}},
    }
    Path(a.out).mkdir(parents=True, exist_ok=True)              # written first: nothing below can lose the run
    (Path(a.out) / "dalia_hr_eval.json").write_text(json.dumps(report, indent=2))
    print("polarity by subject:", report["gated_pipeline"]["polarity_by_subject"])
    for p in pipes:
        print(gated_line(p, report["gated_pipeline"][p]))
    print("spectral tracking, mean MAE (bpm):", report["spectral_tracking"]["mean_mae"])


if __name__ == "__main__":
    main()
