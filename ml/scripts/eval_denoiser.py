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

from suguard_ml.config import FS, WINDOW  # noqa: E402
from suguard_ml.data.realppg import load_recordings  # noqa: E402
from suguard_ml.eval.vitals_eval import both_finite, summarize_errors, vitals_from_bv  # noqa: E402
from suguard_ml.pipeline import SuGuardPipeline  # noqa: E402
from suguard_ml.synth.ppg import simulate_window  # noqa: E402
from suguard_ml.models.denoiser import Denoiser  # noqa: E402
from suguard_ml.signal.beats import beat_template, detect_beats, pulse_polarity  # noqa: E402
from suguard_ml.signal.filters import bandpass, lowpass, preprocess  # noqa: E402
from suguard_ml.synth.ppg import corrupt_pulse  # noqa: E402

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
        clean = mf < 0.05
        out[name] = {
            **score_pipeline(res, hr_t, sp_t),
            "clean_window_hr_coverage": float(given[clean].mean()),
            "clean_window_hr_coverage_by_shape": {f: {"windows": int((clean & (fam == f)).sum()),
                                                      "hr_coverage": float(given[clean & (fam == f)].mean())}
                                                  for f in sorted(set(fam)) if (clean & (fam == f)).any()},
            "by_motion_share": {f"{lo}-{hi}": {"windows": int(((mf >= lo) & (mf < hi)).sum()),
                                               "hr_coverage": float(given[(mf >= lo) & (mf < hi)].mean())}
                                for lo, hi in ((0, 0.05), (0.05, 0.3), (0.3, 0.7), (0.7, 1.01))},
        }
        print(name, json.dumps({k: v for k, v in out[name].items() if not isinstance(v, dict)}), flush=True)
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
    # light level, 0.7-3.2 Hz): rhythmic motion is the one thing that looks like a pulse to a sensor
    # without an accelerometer. Whatever is reported here is the motion rate.
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

    return {
        "sharp_with_reflected_wave": gaussian_pulse(0.07),
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
    report["must_not_report"] = eval_must_not_report(den)
    report["shape_robustness"] = eval_shapes(den)
    report["real_ppg_simulated_motion"] = eval_real(den)
    Path(a.out).mkdir(parents=True, exist_ok=True)
    (Path(a.out) / f"{a.name}.json").write_text(json.dumps(report, indent=2))
    print("wrote", Path(a.out) / f"{a.name}.json")


if __name__ == "__main__":
    main()
