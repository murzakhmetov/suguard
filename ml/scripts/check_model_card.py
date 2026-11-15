"""Reproduce the statements of docs/MODEL_CARD.md that are not covered by
eval_denoiser.py, train_risk.py or benchmark_calibration.py.

    python scripts/check_model_card.py --out models/metrics          (about 15 min on 4 CPUs)

Writes models/metrics/model_card_checks.json with four sections:

``hrv_premature_beats``  RMSSD from one minute of inter-beat intervals with
    four premature beats (each with its compensatory pause), relative to the
    RMSSD of the same rhythm without them: with the editing rule of
    signal.beats.hrv_metrics, with the plausibility mask alone, and without
    any editing. By baseline variability and by how early the premature beat
    comes (coupling interval / normal interval).
``dicrotic_notch``  How often a notch or inflection is reported in a noisy
    window although the noise-free beat has none, with the noise criterion
    of signal.features (NOTCH_NOISE_FACTOR) and without it, for simulated
    beats without a reflected wave and for the simulator's whole family.
``spo2_bias``  Mean signed SpO2 error by true saturation, 82-95 %, with and
    without motion, for the classical path and both networks. The simulator
    builds red/IR from the same calibration curve the estimate uses, so this
    is the bias of the estimator, not of the sensor.
``calibration_filter``  The personal calibration filter without a
    population model: the spread it learns and how often its 80 % interval
    holds the next true values / meter readings, after 6 and 30 fingersticks
    (two a day), for a level that drifts as the filter assumes and for one
    that does not.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from suguard_ml.config import FS  # noqa: E402
from suguard_ml.models.glucose import GLUCOMETER_CV, PersonalCalibration  # noqa: E402
from suguard_ml.signal import beats as B  # noqa: E402
from suguard_ml.signal import features as F  # noqa: E402
from suguard_ml.signal.filters import preprocess  # noqa: E402
from suguard_ml.synth import ppg  # noqa: E402

Z80 = 1.2816


# --- HRV ---------------------------------------------------------------------------------------

def _rhythm(rng, n, rmssd_ms, rsa_ms=0.0, lf_ms=0.0, mean_s=0.83):
    white = rng.normal(0, rmssd_ms / 1000 / np.sqrt(2), n)
    rsa = rsa_ms / 1000 * np.sin(2 * np.pi * np.arange(n) / 4.0 + rng.uniform(0, 6.3))
    lf = lf_ms / 1000 * np.sin(2 * np.pi * np.arange(n) / 12.0 + rng.uniform(0, 6.3))
    return mean_s + white + rsa + lf


def _with_premature(rng, ibi, k, coupling):
    ibi = ibi.copy()
    for i in rng.choice(np.arange(5, ibi.size - 5, 7), size=k, replace=False):
        m = ibi[i]
        ibi[i], ibi[i + 1] = coupling * m, (2 - coupling) * m
    return ibi


def check_hrv(trials: int, seed: int = 11) -> dict:
    rng = np.random.default_rng(seed)
    rule = B._premature_pairs
    out = {}
    rhythms = {"rmssd_13ms": dict(rmssd_ms=13.0), "rmssd_30ms": dict(rmssd_ms=30.0), "rmssd_60ms": dict(rmssd_ms=60.0),
               "rsa_40ms_lf_30ms_white_15ms": dict(rmssd_ms=15.0, rsa_ms=40.0, lf_ms=30.0)}
    try:
        for rname, kw in rhythms.items():
            out[rname] = {}
            for coupling in (0.60, 0.70, 0.80, 0.88):
                with_rule, mask_only, raw = [], [], []
                for _ in range(trials):
                    base = _rhythm(rng, 72, **kw)
                    truth = float(np.sqrt(np.mean(np.diff(base * 1000) ** 2)))
                    ibi = _with_premature(rng, base, 4, coupling)
                    valid = np.abs(ibi - np.median(ibi)) <= 0.3 * np.median(ibi)      # like Beats.valid_ibi
                    B._premature_pairs = rule
                    h = B.hrv_metrics(ibi, valid)
                    if h["rmssd_ms"] is not None:
                        with_rule.append(h["rmssd_ms"] / truth)
                    B._premature_pairs = lambda ibi_ms, nn: np.zeros(ibi_ms.size, dtype=bool)
                    h = B.hrv_metrics(ibi, valid)
                    if h["rmssd_ms"] is not None:
                        mask_only.append(h["rmssd_ms"] / truth)
                    raw.append(float(np.sqrt(np.mean(np.diff(ibi * 1000) ** 2))) / truth)
                out[rname][f"coupling_{coupling:.2f}"] = {
                    "with_rule_median": float(np.median(with_rule)),
                    "with_rule_p5_p95": [float(np.percentile(with_rule, 5)), float(np.percentile(with_rule, 95))],
                    "mask_only_median": float(np.median(mask_only)),
                    "no_editing_median": float(np.median(raw))}
    finally:
        B._premature_pairs = rule
    return {"design": "72 intervals (one minute at 72 bpm), 4 premature beats each followed by its compensatory "
                      "pause; ratio = RMSSD / RMSSD of the rhythm without them", "trials": trials, "results": out}


# --- dicrotic notch ------------------------------------------------------------------------------

def _kind(f: dict) -> str:
    if not np.isfinite(f.get("notch_time_ratio", np.nan)):
        return "none"
    return "notch" if f["notch_present"] == 1.0 else "inflection"


def check_notch(n: int, seed0: int = 40_000) -> dict:
    sample = ppg.sample_morphology

    def no_reflected_wave(rng, hr_bpm=75.0):
        m = sample(rng, hr_bpm)
        m.lp_hz, m.harmonics = None, None          # the wave model itself ...
        m.a2, m.a3 = 0.0, float(rng.uniform(0.2, 0.5))    # ... without a reflected wave: no notch
        return m

    factor = F.NOTCH_NOISE_FACTOR
    out = {}
    try:
        for label, sampler in (("beats_without_reflected_wave", no_reflected_wave), ("simulator_family", sample)):
            ppg.sample_morphology = sampler
            out[label] = {}
            for pi in (0.01, 0.003, 0.001):
                rows = []
                for i in range(n):
                    w = ppg.simulate_window(seed0 + i, kinds=[], pi_ir=pi, hr_bpm=float(60 + i % 40))
                    clean, _ = preprocess(w.ir_clean_raw, FS)
                    noisy, _ = preprocess(w.ir_raw, FS)
                    F.NOTCH_NOISE_FACTOR = factor
                    truth = _kind(F.extract_features(clean, None, FS))
                    with_test = _kind(F.extract_features(noisy, None, FS))
                    F.NOTCH_NOISE_FACTOR = 0.0
                    without = _kind(F.extract_features(noisy, None, FS))
                    rows.append((truth, with_test, without))
                F.NOTCH_NOISE_FACTOR = factor
                none = [r for r in rows if r[0] == "none"]
                some = [r for r in rows if r[0] != "none"]
                out[label][f"pi_{pi * 100:.1f}pct"] = {
                    "windows": n, "clean_beat_has_none": len(none),
                    "reported_although_none_with_noise_test": float(np.mean([r[1] != "none" for r in none])) if none else None,
                    "reported_although_none_without_noise_test": float(np.mean([r[2] != "none" for r in none])) if none else None,
                    "missed_with_noise_test": float(np.mean([r[1] == "none" for r in some])) if some else None,
                    "missed_without_noise_test": float(np.mean([r[2] == "none" for r in some])) if some else None}
    finally:
        ppg.sample_morphology = sample
        F.NOTCH_NOISE_FACTOR = factor
    return out


# --- SpO2 bias -----------------------------------------------------------------------------------

def check_spo2(models: Path, n: int, seed: int = 123) -> dict:
    from suguard_ml.models.denoiser import Denoiser
    from suguard_ml.models.edge_int import EdgeDenoiserInt
    from suguard_ml.pipeline import SuGuardPipeline

    pipes = {"classical": SuGuardPipeline(denoiser=None)}
    if (models / "denoiser.onnx").exists():
        pipes["server"] = SuGuardPipeline(denoiser=Denoiser(models / "denoiser.onnx"))
    if (models / "denoiser_edge_int.npz").exists():
        pipes["bracelet"] = SuGuardPipeline(denoiser=EdgeDenoiserInt(models / "denoiser_edge_int.npz"))
    bins = ((82, 84), (84, 86), (86, 88), (88, 90), (82, 90), (90, 95))
    out = {}
    for label, kw in (("usual_motion_mix", {}), ("no_motion", {"kinds": []})):
        rng = np.random.default_rng(seed)
        target = rng.uniform(82, 95, n)
        wins = [ppg.simulate_window(7_000_000 + i, spo2=float(s), **kw) for i, s in enumerate(target)]
        out[label] = {}
        for name, pipe in pipes.items():
            est = np.array([np.nan if (r := pipe.analyze(w.red_raw, w.ir_raw, fs=w.fs))["spo2"]["percent"] is None
                            else r["spo2"]["percent"] for w in wins])
            err = est - target
            out[label][name] = {}
            for lo, hi in bins:
                s = (target >= lo) & (target < hi) & np.isfinite(err)
                out[label][name][f"{lo}-{hi}"] = {"n": int(s.sum()),
                                                   "mean_signed_error": float(err[s].mean()) if s.any() else None,
                                                   "mae": float(np.abs(err[s]).mean()) if s.any() else None}
        print("spo2", label, json.dumps({k: {b: round(v[b]["mean_signed_error"] or np.nan, 2) for b in ("82-90", "90-95")}
                                         for k, v in out[label].items()}), flush=True)
    return {"design": f"{n} simulated windows per condition, true SpO2 uniform in 82-95 %", "results": out}


# --- calibration filter --------------------------------------------------------------------------

def check_calibration(people: int, seed: int = 5) -> dict:
    rng = np.random.default_rng(seed)
    out = {}
    for sd_true in (5.0, 20.0, 40.0):
        for drift in (0.0, 6.0):
            key = f"residual_sd_{sd_true:.0f}_level_drift_{drift:.0f}_per_sqrt_day"
            cover_true = {6: [], 30: []}
            cover_meter = {6: [], 30: []}
            learnt = {6: [], 30: []}
            for _ in range(people):
                level = rng.normal(110, 20.0)
                cal = PersonalCalibration()
                t = 1.7e9
                for i in range(1, 31):
                    t += 43200.0
                    level += rng.normal(0, drift / np.sqrt(2.0)) if drift else 0.0
                    y = level + rng.normal(0, sd_true)
                    cal.update(cal.f0, y * (1 + GLUCOMETER_CV * rng.standard_normal()), t)
                    if i in learnt:
                        est, sd = cal.predict(cal.f0, t + 3600.0)
                        new = level + rng.normal(0, sd_true, 20)
                        meter = new * (1 + GLUCOMETER_CV * rng.standard_normal(20))
                        cover_true[i].append(np.mean(np.abs(new - est) <= Z80 * sd))
                        cover_meter[i].append(np.mean(np.abs(meter - est) <= Z80 * sd))
                        learnt[i].append(np.sqrt(cal.resid_var))
            out[key] = {f"after_{k}": {"learnt_sd_median": float(np.median(learnt[k])),
                                       "interval_80_holds_true_values": float(np.mean(cover_true[k])),
                                       "interval_80_holds_meter_readings": float(np.mean(cover_meter[k]))}
                        for k in learnt}
    return {"design": f"{people} people per setting, glucose = level + N(0, residual_sd), meter error "
                      f"{GLUCOMETER_CV:.0%}, two fingersticks a day, no population model", "results": out}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="models/metrics")
    ap.add_argument("--models", default="models")
    ap.add_argument("--quick", action="store_true", help="small samples, for a test run")
    ap.add_argument("--only", nargs="*", default=None, choices=["hrv", "notch", "spo2", "calibration"])
    a = ap.parse_args()
    q = a.quick
    parts = a.only or ["hrv", "notch", "spo2", "calibration"]
    path = Path(a.out) / "model_card_checks.json"
    report = json.loads(path.read_text()) if path.exists() and a.only else {}
    if "hrv" in parts:
        report["hrv_premature_beats"] = check_hrv(40 if q else 400)
    if "notch" in parts:
        report["dicrotic_notch"] = check_notch(20 if q else 150)
    if "spo2" in parts:
        report["spo2_bias"] = check_spo2(Path(a.models), 60 if q else 2000)
    if "calibration" in parts:
        report["calibration_filter"] = check_calibration(40 if q else 300)
    Path(a.out).mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2))
    print("wrote", path)


if __name__ == "__main__":
    main()
