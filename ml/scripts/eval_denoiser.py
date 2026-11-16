"""Evaluate a trained denoiser against the classical pipeline.

    python scripts/eval_denoiser.py --data data/denoiser --out models/metrics
    python scripts/eval_denoiser.py --data data/denoiser --edge-int models/denoiser_edge_int.npz --name denoiser_edge_eval

1. ``synthetic_test``: held-out simulated test set (seeds never used in
   training): HR/SpO2 errors by artefact severity, artefact-mask AUC, and the
   coverage/accuracy trade-off of the motion-share gate. No other check.
2. ``pipeline_with_gates``: the full pipeline with every reliability check
   on fresh simulated windows.
3. ``must_not_report``: inputs that must never give a value (no pulse, a red
   channel without a pulse, noise only, swapped LED channels, motion without
   a pulse).
4. ``shape_robustness``: clean windows of pulse shapes that were built
   independently of the training simulator, from sharp to sinusoidal. A model
   that has learned "sharp = pulse, smooth = motion" fails here.
5. ``real_ppg_simulated_motion``: real PPG (heartpy recordings: real
   morphology and heart-rate variability) passed through the simulated
   MAX30102 optics and motion, without checks and through the full pipeline.
   The reference heart rate comes from the clean real signal.
6. ``hard_cases``: inputs the checks are known not to handle (found by an
   independent red team), measured so that these limits stay visible: steady
   periodic motion with an arterial red/IR ratio, with or without a pulse,
   motion at half the pulse rate, motion locked to the pulse rate, fast
   breathing, bigeminy, slow double-humped pulses, fast rates at low SpO2.
Real *motion* on real MAX30102 data is not covered here (no such public
data); scripts/eval_dalia.py in the Colab notebook covers real wrist motion
on PPG-DaLiA.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from suguard_ml.config import ADC_MAX, FS, WINDOW  # noqa: E402
from suguard_ml.data.realppg import load_recordings  # noqa: E402
from suguard_ml.eval.vitals_eval import both_finite, summarize_errors, vitals_from_bv  # noqa: E402
from suguard_ml.pipeline import SuGuardPipeline  # noqa: E402
from suguard_ml.synth.ppg import simulate_window  # noqa: E402
from suguard_ml.models.denoiser import Denoiser  # noqa: E402
from suguard_ml.signal.beats import beat_template, detect_beats, pulse_polarity  # noqa: E402
from suguard_ml.signal.filters import bandpass, lowpass, preprocess  # noqa: E402
from suguard_ml.synth.ppg import corrupt_pulse, r_from_spo2  # noqa: E402

SEVERITY = [("clean", 0.0, 0.01), ("light", 0.01, 0.3), ("moderate", 0.3, 0.7), ("heavy", 0.7, 1.01)]


def _sig(x):
    return 1 / (1 + np.exp(-x))


def eval_synthetic(den: Denoiser, path: Path) -> dict:
    d = np.load(path)
    X, M, meta = d["X"].astype(np.float32), d["M"], d["meta"]
    Y = np.concatenate([den.run(X[i:i + 256]) for i in range(0, len(X), 256)])
    P = _sig(Y[:, 2])
    from sklearn.metrics import roc_auc_score

    rows_raw = [vitals_from_bv(X[i, 0].astype(float), X[i, 1].astype(float), FS) for i in range(len(X))]
    rows_dn = [vitals_from_bv(Y[i, 0], Y[i, 1], FS, P[i]) for i in range(len(X))]
    hr, spo2, mfrac = meta[:, 0], meta[:, 1], meta[:, 6]
    art = np.array([r["artifact_frac"] for r in rows_dn])
    common = both_finite(rows_raw, rows_dn)
    res = {"n": int(len(X)), "mask_auc": float(roc_auc_score(M.reshape(-1)[::5], P.reshape(-1)[::5])),
           "all": {"raw": summarize_errors(rows_raw, hr, spo2), "denoised": summarize_errors(rows_dn, hr, spo2),
                   "raw_on_common": summarize_errors(rows_raw, hr, spo2, common=common),
                   "denoised_on_common": summarize_errors(rows_dn, hr, spo2, common=common)},
           "by_severity": {}, "gate_sweep": []}
    for name, lo, hi in SEVERITY:
        s = (mfrac >= lo) & (mfrac < hi)
        res["by_severity"][name] = {"share": float(s.mean()),
                                    "raw": summarize_errors(rows_raw, hr, spo2, s),
                                    "denoised": summarize_errors(rows_dn, hr, spo2, s)}
    for thr in (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 1.01):
        keep = art <= thr
        e = summarize_errors(rows_dn, hr, spo2, keep)
        res["gate_sweep"].append({"max_artifact_fraction": thr, **e})
    return res


def score_pipeline(results: list[dict], hr_true, spo2_true=None) -> dict:
    """Coverage and accuracy of a list of SuGuardPipeline.analyze results."""
    hr_true = np.asarray(hr_true, dtype=float)
    hr_e = np.array([abs(r["heart_rate"]["bpm"] - t) if r["heart_rate"]["bpm"] is not None else np.nan
                     for r, t in zip(results, hr_true)])
    ok_h = np.isfinite(hr_e)
    out = {"windows": len(results), "hr_coverage": float(ok_h.mean()) if len(results) else None,
           "hr_mae": float(np.mean(hr_e[ok_h])) if ok_h.any() else None,
           "hr_p95": float(np.percentile(hr_e[ok_h], 95)) if ok_h.any() else None,
           "hr_errors_over_10bpm": int(np.sum(hr_e[ok_h] > 10))}
    if spo2_true is not None:
        sp_e = np.array([abs(r["spo2"]["percent"] - t) if r["spo2"]["percent"] is not None else np.nan
                         for r, t in zip(results, np.asarray(spo2_true, dtype=float))])
        ok_s = np.isfinite(sp_e)
        out.update({"spo2_coverage": float(ok_s.mean()) if len(results) else None,
                    "spo2_mae": float(np.mean(sp_e[ok_s])) if ok_s.any() else None,
                    "spo2_p95": float(np.percentile(sp_e[ok_s], 95)) if ok_s.any() else None,
                    "spo2_errors_over_4pts": int(np.sum(sp_e[ok_s] > 4))})
    return out


def reject_reasons(results: list[dict]) -> dict:
    """How often each reason code appears among the rejected windows."""
    c: dict[str, int] = {}
    for r in results:
        if not r["reliable"]:
            for q in r.get("reason", []):
                c[q] = c.get(q, 0) + 1
    return dict(sorted(c.items(), key=lambda kv: -kv[1]))


def shape_family(w) -> str:
    m = w.meta.get("morph", {})
    return "harmonic_series" if m.get("harmonics") is not None else ("wave_model_low_passed" if m.get("lp_hz") else "wave_model")


def eval_pipeline(den: Denoiser, n: int = 600, seed0: int = 4_000_000) -> dict:
    """Full pipeline with every reliability gate, on fresh simulated raw
    windows: classical fallback vs denoiser. Reports how often a value is
    given (coverage) and how accurate the given values are."""
    out = {}
    wins = [simulate_window(seed0 + i) for i in range(n)]
    hr_t, sp_t = [w.hr_bpm for w in wins], [w.spo2 for w in wins]
    mf = np.array([float(w.mask.mean()) for w in wins])
    fam = np.array([shape_family(w) for w in wins])
    for name, pipe in (("classical", SuGuardPipeline(denoiser=None)), ("denoiser", SuGuardPipeline(denoiser=den))):
        res = [pipe.analyze(w.red_raw, w.ir_raw, fs=w.fs) for w in wins]
        given = np.array([r["reliable"] for r in res])
        hr_bad = np.array([r["heart_rate"]["bpm"] is not None and abs(r["heart_rate"]["bpm"] - t) > 10.0
                           for r, t in zip(res, hr_t)])
        sp_bad = np.array([r["spo2"]["percent"] is not None and abs(r["spo2"]["percent"] - t) > 4.0
                           for r, t in zip(res, sp_t)])
        clean = mf < 0.05
        out[name] = {
            **score_pipeline(res, hr_t, sp_t),
            "clean_window_hr_coverage": float(given[clean].mean()),
            "clean_window_hr_coverage_by_shape": {f: {"windows": int((clean & (fam == f)).sum()),
                                                      "hr_coverage": float(given[clean & (fam == f)].mean())}
                                                  for f in sorted(set(fam)) if (clean & (fam == f)).any()},
            "by_motion_share": {f"{lo}-{hi}": {"windows": int(((mf >= lo) & (mf < hi)).sum()),
                                               "hr_coverage": float(given[(mf >= lo) & (mf < hi)].mean()),
                                               "hr_errors_over_10bpm": int(hr_bad[(mf >= lo) & (mf < hi)].sum()),
                                               "spo2_errors_over_4pts": int(sp_bad[(mf >= lo) & (mf < hi)].sum())}
                                for lo, hi in ((0, 0.05), (0.05, 0.3), (0.3, 0.7), (0.7, 1.01))},
        }
        print(name, json.dumps({k: v for k, v in out[name].items() if not isinstance(v, dict)}), flush=True)
    return out


def eval_rest_by_perfusion(den: Denoiser, n: int = 1000, seed0: int = 6_100_000) -> dict:
    """Windows without motion, by the simulated pulse amplitude (perfusion): how many get a heart
    rate / an SpO2 value, the errors, and (networks) how many the classical checks decided
    (pipeline.LOW_PERFUSION_PI), also without that rule. At a small pulse the networks take sensor
    noise for motion."""
    import suguard_ml.pipeline as pipeline

    wins = [simulate_window(seed0 + i, kinds=[]) for i in range(n)]
    bins = ((0.0008, 0.0015), (0.0015, 0.003), (0.003, 0.01), (0.01, 0.05))
    out = {}
    rule = pipeline.LOW_PERFUSION_PI
    for name, pipe, low_pi in (("classical", SuGuardPipeline(denoiser=None), rule),
                               ("denoiser", SuGuardPipeline(denoiser=den), rule),
                               ("denoiser_without_low_perfusion_fallback", SuGuardPipeline(denoiser=den), 0.0)):
        pipeline.LOW_PERFUSION_PI = low_pi
        try:
            res = [pipe.analyze(w.red_raw, w.ir_raw, fs=FS) for w in wins]
        finally:
            pipeline.LOW_PERFUSION_PI = rule
        out[name] = {}
        for lo, hi in bins:
            idx = [i for i, w in enumerate(wins) if lo <= w.pi_ir < hi]
            hr = [(res[i]["heart_rate"]["bpm"], wins[i].hr_bpm) for i in idx if res[i]["reliable"]]
            sp = [(res[i]["spo2"]["percent"], wins[i].spo2) for i in idx if res[i]["spo2"]["percent"] is not None]
            out[name][f"{100 * lo:g}-{100 * hi:g}%"] = {
                "windows": len(idx), "hr_coverage": len(hr) / max(len(idx), 1),
                "hr_errors_over_10bpm": int(sum(abs(a - b) > 10.0 for a, b in hr)),
                "spo2_coverage": len(sp) / max(len(idx), 1),
                "spo2_errors_over_4pts": int(sum(abs(a - b) > 4.0 for a, b in sp)),
                "classical_fallback": int(sum(bool(res[i].get("low_perfusion_fallback")) for i in idx))}
        print(name, json.dumps(out[name]), flush=True)
    return out


def eval_must_not_report(den: Denoiser, n: int = 300, n_motion: int = 1500, seed0: int = 4_500_000) -> dict:
    """Inputs for which any reported value is wrong: how often does the gated
    pipeline report one? (Heart rate from the IR channel is legitimate when
    only the red channel is broken; SpO2 never is.)"""
    rng = np.random.default_rng(seed0)
    sets: dict[str, list] = {k: [] for k in ("noise_only", "ir_without_pulse", "red_without_pulse",
                                             "red_pulse_a_fifth_in_noise", "led_channels_swapped")}
    for i in range(n):
        w = simulate_window(seed0 + i, kinds=[], pi_ir=float(np.exp(rng.uniform(np.log(0.002), np.log(0.03)))))
        red, ir = w.red_raw.astype(float), w.ir_raw.astype(float)
        dr, di = float(np.median(red)), float(np.median(ir))
        sigma = float(np.exp(rng.uniform(np.log(5), np.log(400))))
        sets["noise_only"].append((np.round(dr + rng.normal(0, sigma, red.size)),
                                   np.round(di + rng.normal(0, sigma, ir.size))))
        sets["ir_without_pulse"].append((red, np.round(di + rng.normal(0, 3e-4 * di, ir.size))))
        sets["red_without_pulse"].append((np.round(dr + rng.normal(0, 3e-4 * dr, red.size)), ir))
        sets["red_pulse_a_fifth_in_noise"].append(
            (np.round(dr + 0.2 * (red - dr) + rng.normal(0, 5e-4 * dr, red.size)), ir))
        sets["led_channels_swapped"].append((ir, red))
    # A pulse of 0.01 % (below the sensor noise) under the usual mix of motion (a fifth of the
    # windows have none; the motion scales with the pulse and is mostly small here).
    sets["no_pulse_with_motion"] = [(w.red_raw, w.ir_raw) for w in
                                    (simulate_window(seed0 + 10_000 + i, pi_ir=1e-4) for i in range(n_motion))]
    # The same without a visible pulse, but with periodic motion as large as a pulse (0.1-6 % of the
    # light level; 0.7-3.2 Hz, or within 15 % of the simulated heart rate in a quarter of the windows,
    # 0.6-3.5 Hz in all): rhythmic motion is the one thing that looks like a pulse to a sensor without
    # an accelerometer. Whatever is reported here is the motion rate.
    sets["periodic_motion_no_pulse"] = [
        (w.red_raw, w.ir_raw) for w in
        (simulate_window(seed0 + 20_000 + i, pi_ir=1e-4, kinds=["periodic"],
                         artifact_level=float(np.exp(rng.uniform(np.log(30), np.log(300))))) for i in range(n))]
    out = {}
    for name, pipe in (("classical", SuGuardPipeline(denoiser=None)), ("denoiser", SuGuardPipeline(denoiser=den))):
        out[name] = {}
        for key, wins in sets.items():
            res = [pipe.analyze(red, ir, fs=FS) for red, ir in wins]
            out[name][key] = {"windows": len(wins), "heart_rate_reported": int(sum(r["reliable"] for r in res)),
                              "spo2_reported": int(sum(r["spo2"]["percent"] is not None for r in res))}
        print(name, json.dumps(out[name]), flush=True)
    return out


def _phase(rng, hr_bpm: float, n: int) -> np.ndarray:
    """Phase of a beat train with respiratory sinus arrhythmia and a slow random walk (rad)."""
    t = np.arange(n) / FS
    f = hr_bpm / 60.0 * (1 + 0.05 * np.sin(2 * np.pi * rng.uniform(0.15, 0.35) * t + rng.uniform(0, 6.28)))
    f = f * (1 + 0.01 * np.cumsum(rng.standard_normal(n)) / np.sqrt(FS))
    return 2 * np.pi * np.cumsum(f) / FS + rng.uniform(0, 6.28)


def _shape_generators() -> dict:
    """Pulse shapes built here, not by the training simulator: periodic
    waveforms on a phase with heart-rate variability, from sharp to sinusoidal."""
    def harmonic(*terms):                       # terms: (harmonic number, amplitude, phase)
        return lambda th: sum(a * np.sin(k * th + q) for k, a, q in terms)

    def skewed_triangle(rise: float, cut_hz: float):
        def f(th):
            u = (th / (2 * np.pi)) % 1.0
            x = np.where(u < rise, u / rise, (1.0 - u) / (1.0 - rise))
            return lowpass(x - x.mean(), FS, cut_hz, order=2)
        return f

    def gaussian_pulse(width: float):
        def f(th):
            u = ((th / (2 * np.pi)) % 1.0) - 0.3
            return np.exp(-0.5 * (u / width) ** 2) + 0.35 * np.exp(-0.5 * ((u - 0.33) / (1.6 * width)) ** 2)
        return f

    def deep_notch(th):
        # The median beat of the longest public recording (heartpy data3): a sharp systolic peak,
        # a notch below the diastolic foot and a diastolic wave of ~40 % (2nd harmonic > 1st).
        # The slow diastolic decay ramps in during the upstroke, so the shape is continuous at the foot.
        u = (th / (2 * np.pi)) % 1.0
        ramp = 0.5 * (1.0 - np.cos(np.pi * np.minimum(u / 0.15, 1.0)))
        return (np.exp(-0.5 * ((u - 0.2) / 0.055) ** 2) + 0.42 * np.exp(-0.5 * ((u - 0.55) / 0.09) ** 2)
                - 0.12 * np.exp(-0.5 * ((u - 0.37) / 0.035) ** 2) + 0.15 * (1.0 - u) * ramp)

    return {
        "sharp_with_reflected_wave": gaussian_pulse(0.07),
        "deep_notch_large_diastolic_wave": deep_notch,
        "rounded_with_reflected_wave": gaussian_pulse(0.13),
        "skewed_triangle_rise_20pct": skewed_triangle(0.2, 6.0),
        "skewed_triangle_rise_35pct_smooth": skewed_triangle(0.35, 3.0),
        "three_harmonics": harmonic((1, 1.0, 0.0), (2, 0.35, 0.4), (3, 0.12, 0.9)),
        "two_harmonics": harmonic((1, 1.0, 0.0), (2, 0.5, 0.0)),
        "sine": harmonic((1, 1.0, 0.0)),
    }


def eval_shapes(den: Denoiser, n: int = 150, seed: int = 4_700_000) -> dict:
    """Clean windows (no motion) of pulse shapes that do not come from the
    training simulator: does the pipeline still report them? The classical
    path does not care about the shape; a network that has learned the
    simulator's shapes instead of what separates a pulse from motion takes
    the smooth ones for motion."""
    pipes = (("classical", SuGuardPipeline(denoiser=None)), ("denoiser", SuGuardPipeline(denoiser=den)))
    out = {}
    for sname, gen in _shape_generators().items():
        rng = np.random.default_rng(seed)
        wins, hr_t, sp_t = [], [], []
        for _ in range(n):
            hr = float(rng.uniform(50, 110))
            spo2 = float(rng.uniform(90, 99.5))
            pi = float(np.exp(rng.uniform(np.log(0.003), np.log(0.03))))
            th = _phase(rng, hr, WINDOW + 200)
            x = np.asarray(gen(th), dtype=float)[100:100 + WINDOW]
            hr_true = float((th[100 + WINDOW - 1] - th[100]) / (2 * np.pi) / ((WINDOW - 1) / FS) * 60.0)
            w = corrupt_pulse(x, rng, spo2=spo2, pi_ir=pi, hr_bpm=hr_true, kinds=[])
            wins.append(w)
            hr_t.append(hr_true)
            sp_t.append(spo2)
        out[sname] = {}
        for name, pipe in pipes:
            res = [pipe.analyze(w.red_raw, w.ir_raw, fs=FS) for w in wins]
            out[sname][name] = {**score_pipeline(res, hr_t, sp_t),
                                "median_motion_share_flagged": float(np.median([r["quality"]["motion_fraction"] for r in res])),
                                "reject_reasons": reject_reasons(res)}
        print(sname, json.dumps({k: {q: v[q] for q in ("hr_coverage", "hr_mae", "hr_errors_over_10bpm")}
                                 for k, v in out[sname].items()}), flush=True)
    return out


def eval_real(den: Denoiser, n_corrupt: int = 6, seed: int = 0) -> dict:
    """Real recordings x simulated optics/motion."""
    rng = np.random.default_rng(seed)
    recs = load_recordings()
    scenarios = {
        "clean": dict(kinds=[]),
        "walking": dict(kinds=["periodic"]),
        "gestures": dict(kinds=["burst", "step"]),
        "mixed": dict(kinds=None, clean_prob=0.0),
    }
    out = {"recordings": {k: round(len(v) / FS, 1) for k, v in recs.items()}, "scenarios": {}}
    pipes = {"classical": SuGuardPipeline(denoiser=None), "denoiser": SuGuardPipeline(denoiser=den)}
    polarity = {name: pulse_polarity(x, FS) for name, x in recs.items()}
    out["polarity"] = polarity
    for sname, kw in scenarios.items():
        rows_raw, rows_dn, hr_true, sp_true, corr_clean = [], [], [], [], []
        full = {k: [] for k in pipes}
        for name, x in recs.items():
            x = polarity[name] * bandpass(x, FS, 0.4, 12.0)
            for s in range(0, len(x) - WINDOW + 1, WINDOW // 2):
                seg = x[s:s + WINDOW]
                b = detect_beats(seg, FS)
                _, tc = beat_template(seg, b)
                if b.hr_bpm is None or b.valid_ibi.sum() < 5 or tc < 0.9:
                    continue  # reference itself is not clean enough
                for _ in range(n_corrupt if sname != "clean" else 1):
                    spo2 = float(rng.uniform(88, 99.5))
                    pi = float(np.exp(rng.uniform(np.log(0.002), np.log(0.03))))
                    level = None if sname == "mixed" else float(np.exp(rng.uniform(np.log(0.5), np.log(8))))
                    w = corrupt_pulse(seg, rng, spo2=spo2, pi_ir=pi, hr_bpm=b.hr_bpm,
                                      artifact_level=level, **kw)
                    ir, _ = preprocess(w.ir_raw, FS)
                    red, _ = preprocess(w.red_raw, FS)
                    d = den.denoise_bv(ir, red, FS)
                    rows_raw.append(vitals_from_bv(ir, red, FS))
                    rows_dn.append(vitals_from_bv(d.ir_bv, d.red_bv, FS, d.artifact_prob))
                    for k, pipe in pipes.items():
                        full[k].append(pipe.analyze(w.red_raw, w.ir_raw, fs=FS))
                    hr_true.append(b.hr_bpm)
                    sp_true.append(spo2)
                    if sname == "clean":
                        clean, _ = preprocess(w.ir_clean_raw, FS)
                        corr_clean.append(float(np.corrcoef(clean[32:-32], d.ir_bv[32:-32])[0, 1]))
        hr_true, sp_true = np.array(hr_true), np.array(sp_true)
        art = np.array([r["artifact_frac"] for r in rows_dn])
        common = both_finite(rows_raw, rows_dn)
        entry = {"windows": len(hr_true), "raw": summarize_errors(rows_raw, hr_true, sp_true),
                 "denoised": summarize_errors(rows_dn, hr_true, sp_true),
                 "raw_on_common": summarize_errors(rows_raw, hr_true, sp_true, common=common),
                 "denoised_on_common": summarize_errors(rows_dn, hr_true, sp_true, common=common),
                 # only the windows of which the network flags at most half as motion (no other check)
                 "denoised_mask_at_most_half": summarize_errors(rows_dn, hr_true, sp_true, art <= 0.5),
                 # the complete pipeline with every reliability check: what would be shown
                 "pipeline": {k: {**score_pipeline(v, hr_true, sp_true), "reject_reasons": reject_reasons(v)}
                              for k, v in full.items()}}
        if corr_clean:
            entry["waveform_corr_clean_vs_denoised"] = float(np.median(corr_clean))
        out["scenarios"][sname] = entry
        print(sname, json.dumps({k: entry[k]["hr"] if isinstance(entry[k], dict) and "hr" in entry[k] else entry[k]
                                 for k in entry}, default=str)[:400], flush=True)
    return out


def _steady_periodic(rng, f_hz: float, n: int = WINDOW) -> np.ndarray:
    """Periodic modulation of constant amplitude (unit 3rd-97th percentile range): a fundamental,
    up to two harmonics and a 3 % frequency wobble, like a steady gait or arm swing."""
    t = np.arange(n) / FS
    wobble = 1.0 + 0.03 * np.sin(2 * np.pi * rng.uniform(0.05, 0.3) * t + rng.uniform(0, 2 * np.pi))
    ph = 2 * np.pi * np.cumsum(f_hz * wobble) / FS
    x = sum(a * np.sin(h * ph + rng.uniform(0, 2 * np.pi))
            for h, a in ((1, 1.0), (2, rng.uniform(0, 0.5)), (3, rng.uniform(0, 0.2))))
    return x / (np.percentile(x, 97) - np.percentile(x, 3))


def _modulated(w, m_ir: np.ndarray, m_red: np.ndarray):
    """Both channels' detected light multiplied by (1 + m), as motion does."""
    return (np.clip(np.round(w.red_raw * (1.0 + m_red)), 0, ADC_MAX),
            np.clip(np.round(w.ir_raw * (1.0 + m_ir)), 0, ADC_MAX))


def _bigeminy_pulse(rng, hr_bpm: float, coupling: float, weak: float) -> np.ndarray:
    """Normal and premature beats alternating (premature after ``coupling`` x the normal interval,
    then the compensatory pause), the premature ones at ``weak`` x the normal amplitude."""
    rr = 60.0 / hr_bpm
    t = np.arange(WINDOW) / FS
    x = np.zeros(WINDOW)
    on, k = -2.0 + rng.uniform(0, rr), 0
    while on < t[-1] + 1.0:
        a = 1.0 if k % 2 == 0 else weak
        tau = t - on
        x += a * (np.exp(-0.5 * ((tau - 0.12) / 0.045) ** 2) + 0.4 * np.exp(-0.5 * ((tau - 0.33) / 0.08) ** 2))
        on += coupling * rr if k % 2 == 0 else (2.0 - coupling) * rr
        k += 1
    return x


def eval_hard_cases(den: Denoiser, n: int = 150, seed: int = 4_800_000) -> dict:
    """Inputs the checks are known not to handle, with the count of values that are reported and
    wrong (heart rate off by more than 10 bpm, SpO2 by more than 4 points; any value where there
    is no pulse). Motion is common to both LEDs with a red/IR ratio that arterial blood could give
    (R of 85-99.9 % SpO2) unless stated: without an accelerometer such motion looks like a pulse."""
    rng = np.random.default_rng(seed)
    loguni = lambda lo, hi: float(np.exp(rng.uniform(np.log(lo), np.log(hi))))  # noqa: E731
    arterial = lambda: r_from_spo2(float(rng.uniform(85, 99.9)))               # noqa: E731
    sets = {k: [] for k in ("steady_periodic_motion_no_pulse", "pulse_with_steady_motion_at_another_rate",
                            "pulse_with_motion_at_half_the_rate", "motion_locked_to_the_pulse_rate_venous_ratio",
                            "fast_breathing", "bigeminy_weak_premature_beats", "slow_35_45bpm_double_humped",
                            "fast_150_210bpm_spo2_82_90", "venous_pulsation_locked_to_the_beat",
                            "cadence_locked_to_the_pulse")}
    for i in range(n):
        s = seed + 16 * i
        # No visible pulse (0.01 %), steady motion of 0.1-6 % of the light level at 0.7-3.2 Hz over the whole window.
        w = simulate_window(s, pi_ir=1e-4, kinds=[])
        m = loguni(0.001, 0.06) * _steady_periodic(rng, float(rng.uniform(0.7, 3.2)))
        sets["steady_periodic_motion_no_pulse"].append((*_modulated(w, m, arterial() * m), None, None))
        # A pulse and steady motion 1.5-4x as large, at least 15 bpm away from the pulse rate.
        pi = loguni(0.003, 0.03)
        w = simulate_window(s + 1, kinds=[], hr_bpm=float(rng.uniform(55, 110)), pi_ir=pi,
                            spo2=float(rng.uniform(90, 99.5)))
        fm = float(rng.uniform(0.7, 3.3))
        while abs(fm * 60 - w.hr_bpm) < 15:
            fm = float(rng.uniform(0.7, 3.3))
        m = pi * rng.uniform(1.5, 4.0) * _steady_periodic(rng, fm)
        sets["pulse_with_steady_motion_at_another_rate"].append((*_modulated(w, m, arterial() * m), w.hr_bpm, w.spo2))
        # Arm swing while walking: motion at half the pulse rate, 0.5-2x the pulse.
        pi = loguni(0.003, 0.03)
        w = simulate_window(s + 2, kinds=[], hr_bpm=float(rng.uniform(75, 120)), pi_ir=pi,
                            spo2=float(rng.uniform(90, 99.5)))
        m = pi * rng.uniform(0.5, 2.0) * _steady_periodic(rng, w.hr_bpm / 120.0)
        sets["pulse_with_motion_at_half_the_rate"].append((*_modulated(w, m, arterial() * m), w.hr_bpm, w.spo2))
        # Running cadence locked to the pulse (+-2 %), 0.5-3x the pulse, red/IR ratio of 70-86 % SpO2.
        pi = loguni(0.003, 0.03)
        w = simulate_window(s + 3, kinds=[], hr_bpm=float(rng.uniform(60, 110)), pi_ir=pi,
                            spo2=float(rng.uniform(94, 99.5)))
        m = pi * rng.uniform(0.5, 3.0) * _steady_periodic(rng, w.hr_bpm / 60.0 * rng.uniform(0.98, 1.02))
        sets["motion_locked_to_the_pulse_rate_venous_ratio"].append(
            (*_modulated(w, m, r_from_spo2(float(rng.uniform(70, 86))) * m), w.hr_bpm, w.spo2))
        # Breathing at 27-45 per minute (0.45-0.75 Hz) swinging the baseline 1-4x the pulse, venous red/IR ratio.
        pi = loguni(0.003, 0.03)
        w = simulate_window(s + 4, kinds=[], hr_bpm=float(rng.uniform(60, 120)), pi_ir=pi,
                            spo2=float(rng.uniform(90, 99.5)))
        t = np.arange(WINDOW) / FS
        m = pi * rng.uniform(1.0, 4.0) * 0.5 * np.sin(2 * np.pi * rng.uniform(0.45, 0.75) * t + rng.uniform(0, 6.3))
        sets["fast_breathing"].append((*_modulated(w, m, rng.uniform(0.8, 1.3) * m), w.hr_bpm, w.spo2))
        # Bigeminy: premature beats at 0.55-0.8 of the normal interval and 0.3-0.9 of its amplitude.
        hr = float(rng.uniform(55, 95))
        x = _bigeminy_pulse(rng, hr, float(rng.uniform(0.55, 0.8)), float(rng.uniform(0.3, 0.9)))
        sp = float(rng.uniform(90, 99.5))
        w = corrupt_pulse(x, rng, spo2=sp, pi_ir=loguni(0.003, 0.03), hr_bpm=hr, kinds=[])
        sets["bigeminy_weak_premature_beats"].append((w.red_raw, w.ir_raw, hr, sp))
        # Slow rates with the double-humped pulses of the rich-harmonics family, no motion.
        w = simulate_window(s + 6, kinds=[], hr_bpm=float(rng.uniform(35, 45)), shape="rich_harmonics")
        sets["slow_35_45bpm_double_humped"].append((w.red_raw, w.ir_raw, w.hr_bpm, w.spo2))
        # Fast rates at low saturation and low perfusion, no motion.
        w = simulate_window(s + 7, kinds=[], hr_bpm=float(rng.uniform(150, 210)), spo2=float(rng.uniform(82, 90)),
                            pi_ir=loguni(0.001, 0.003), shape="rich_harmonics")
        sets["fast_150_210bpm_spo2_82_90"].append((w.red_raw, w.ir_raw, w.hr_bpm, w.spo2))
        # Venous pulsation (a tight strap): the window's own pulse, 0.05-0.3 s later, at 0.3-0.6 of its size,
        # with the red/IR ratio of 65-80 % saturated blood. No motion.
        w = simulate_window(s + 8, kinds=[], pi_ir=loguni(0.003, 0.03), spo2=float(rng.uniform(90, 99.5)))
        clean = w.ir_clean_raw.astype(float)
        p = bandpass(-(clean - clean.mean()) / clean.mean(), FS, 0.4, 12.0)
        v = np.roll(p, int(rng.uniform(0.05, 0.3) * FS)) * rng.uniform(0.3, 0.6)
        sets["venous_pulsation_locked_to_the_beat"].append(
            (*_modulated(w, -v, -r_from_spo2(float(rng.uniform(65, 80))) * v), w.hr_bpm, w.spo2))
        # A cadence locked to the pulse (+-2 %), 0.3-1x the pulse, with the simulator's own motion red/IR gains.
        pi = loguni(0.003, 0.03)
        w = simulate_window(s + 9, kinds=[], hr_bpm=float(rng.uniform(55, 110)), pi_ir=pi,
                            spo2=float(rng.uniform(90, 99.5)))
        m = pi * rng.uniform(0.3, 1.0) * _steady_periodic(rng, w.hr_bpm / 60.0 * rng.uniform(0.98, 1.02))
        sets["cadence_locked_to_the_pulse"].append((*_modulated(w, m, rng.uniform(0.5, 1.8) * m), w.hr_bpm, w.spo2))
    out = {}
    for name, pipe in (("classical", SuGuardPipeline(denoiser=None)), ("denoiser", SuGuardPipeline(denoiser=den))):
        out[name] = {}
        for key, wins in sets.items():
            hr_rep = hr_bad = sp_rep = sp_bad = 0
            sp_err = []
            for red, ir, hr_t, sp_t in wins:
                r = pipe.analyze(red, ir, fs=FS)
                hr, sp = r["heart_rate"]["bpm"], r["spo2"]["percent"]
                if hr is not None:
                    hr_rep += 1
                    hr_bad += hr_t is None or abs(hr - hr_t) > 10.0
                if sp is not None:
                    sp_rep += 1
                    sp_bad += sp_t is None or abs(sp - sp_t) > 4.0
                    if sp_t is not None:
                        sp_err.append(sp - sp_t)
            out[name][key] = {"windows": len(wins), "heart_rate_reported": hr_rep, "heart_rate_wrong": int(hr_bad),
                              "spo2_reported": sp_rep, "spo2_wrong": int(sp_bad),
                              "spo2_mean_signed_error": float(np.mean(sp_err)) if sp_err else None}
        print("hard cases", name, json.dumps(out[name]), flush=True)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/denoiser")
    ap.add_argument("--out", default="models/metrics")
    ap.add_argument("--models", default="models")
    ap.add_argument("--onnx", default=None, help="evaluate this model file instead of models/denoiser.onnx")
    ap.add_argument("--edge-int", default=None, help="evaluate the integer edge model (.npz) instead")
    ap.add_argument("--name", default="denoiser_eval")
    a = ap.parse_args()
    if a.edge_int:
        from suguard_ml.models.edge_int import EdgeDenoiserInt
        den = EdgeDenoiserInt(a.edge_int)          # the integer model, exactly as the firmware runs it
    else:
        den = Denoiser(Path(a.onnx) if a.onnx else Path(a.models) / "denoiser.onnx")
    report = {"synthetic_test": eval_synthetic(den, Path(a.data) / "test.npz")}
    s = report["synthetic_test"]
    print("synthetic all:", json.dumps(s["all"], indent=1)[:900])
    report["pipeline_with_gates"] = eval_pipeline(den)
    report["rest_by_perfusion"] = eval_rest_by_perfusion(den)
    report["must_not_report"] = eval_must_not_report(den)
    report["shape_robustness"] = eval_shapes(den)
    report["real_ppg_simulated_motion"] = eval_real(den)
    report["hard_cases"] = eval_hard_cases(den)
    Path(a.out).mkdir(parents=True, exist_ok=True)
    (Path(a.out) / f"{a.name}.json").write_text(json.dumps(report, indent=2))
    print("wrote", Path(a.out) / f"{a.name}.json")


if __name__ == "__main__":
    main()
