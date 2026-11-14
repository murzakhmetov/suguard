"""Evaluate the trained denoiser (ONNX) against the classical pipeline.

    python scripts/eval_denoiser.py --data data/denoiser --out models/metrics

1. Held-out simulated test set (seeds never used in training): HR/SpO2
   errors by artefact severity, artefact-mask AUC, and the coverage/accuracy
   trade-off of the reliability gate (share of window flagged as motion).
2. Real PPG (heartpy recordings: real morphology and heart-rate variability)
   passed through the simulated MAX30102 optics and motion. Ground-truth HR
   comes from the clean real signal. This checks that a model trained on
   synthetic beats generalises to real pulses.
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
from suguard_ml.eval.vitals_eval import summarize_errors, vitals_from_bv  # noqa: E402
from suguard_ml.models.denoiser import Denoiser  # noqa: E402
from suguard_ml.signal.beats import beat_template, detect_beats  # noqa: E402
from suguard_ml.signal.filters import bandpass, preprocess  # noqa: E402
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
    res = {"n": int(len(X)), "mask_auc": float(roc_auc_score(M.reshape(-1)[::5], P.reshape(-1)[::5])),
           "all": {"raw": summarize_errors(rows_raw, hr, spo2), "denoised": summarize_errors(rows_dn, hr, spo2)},
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
    for sname, kw in scenarios.items():
        rows_raw, rows_dn, hr_true, sp_true, corr_clean = [], [], [], [], []
        for name, x in recs.items():
            x = bandpass(x, FS, 0.4, 12.0)
            x = -x if np.mean(np.diff(x) > 0) > 0.5 else x  # systolic upstroke is the short phase
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
                    hr_true.append(b.hr_bpm)
                    sp_true.append(spo2)
                    if sname == "clean":
                        clean, _ = preprocess(w.ir_clean_raw, FS)
                        corr_clean.append(float(np.corrcoef(clean[32:-32], d.ir_bv[32:-32])[0, 1]))
        hr_true, sp_true = np.array(hr_true), np.array(sp_true)
        art = np.array([r["artifact_frac"] for r in rows_dn])
        entry = {"windows": len(hr_true), "raw": summarize_errors(rows_raw, hr_true, sp_true),
                 "denoised": summarize_errors(rows_dn, hr_true, sp_true),
                 "denoised_gated": summarize_errors(rows_dn, hr_true, sp_true, art <= 0.5)}
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
    a = ap.parse_args()
    den = Denoiser(Path(a.models) / "denoiser.onnx")
    report = {"synthetic_test": eval_synthetic(den, Path(a.data) / "test.npz")}
    s = report["synthetic_test"]
    print("synthetic all:", json.dumps(s["all"], indent=1)[:900])
    report["real_ppg_simulated_motion"] = eval_real(den)
    Path(a.out).mkdir(parents=True, exist_ok=True)
    (Path(a.out) / "denoiser_eval.json").write_text(json.dumps(report, indent=2))
    print("wrote", Path(a.out) / "denoiser_eval.json")


if __name__ == "__main__":
    main()
