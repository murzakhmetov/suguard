"""Heart rate under real wrist motion: PPG-DaLiA (run in Colab).

PPG-DaLiA (Reiss et al., Sensors 2019; UCI id 495): 15 people, ~2.5 h each
of daily activities (sitting, stairs, table soccer, cycling, driving, lunch,
walking, working) with an Empatica E4 on the wrist and ECG-derived reference
heart rate for 8-s windows (2-s shift).

    wget https://archive.ics.uci.edu/static/public/495/ppg+dalia.zip && unzip ppg+dalia.zip && unzip -q PPG_FieldStudy.zip
    python scripts/eval_dalia.py --root PPG_FieldStudy --out models/metrics

Caveat: the E4 BVP is a single (green) channel, so the denoiser gets the same
signal on both inputs and cannot use the red/IR motion cue it was built
around; this measures its single-channel behaviour. For reference, published
results on this dataset: ~15-20 bpm MAE for classical spectral trackers
without accelerometer, ~7.7 bpm for DeepPPG with accelerometer (Reiss 2019).
"""

from __future__ import annotations

import argparse
import json
import pickle
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from suguard_ml.config import FS  # noqa: E402
from suguard_ml.models.denoiser import Denoiser  # noqa: E402
from suguard_ml.signal.beats import spectral_hr  # noqa: E402
from suguard_ml.signal.filters import bandpass, resample  # noqa: E402

ACTIVITIES = {0: "transient", 1: "sitting", 2: "stairs", 3: "table_soccer", 4: "cycling", 5: "driving",
              6: "lunch", 7: "walking", 8: "working"}


def load_subject(pkl: Path) -> dict:
    with open(pkl, "rb") as fh:
        return pickle.load(fh, encoding="latin1")


def subject_errors(d: dict, den: Denoiser | None) -> dict:
    bvp = np.asarray(d["signal"]["wrist"]["BVP"], dtype=float).ravel()
    x = resample(bvp, 64.0, FS)
    x = bandpass(x, FS, 0.4, 12.0)
    if np.mean(np.diff(x) > 0) > 0.5:
        x = -x
    label = np.asarray(d["label"], dtype=float).ravel()
    act_raw = np.asarray(d.get("activity", np.zeros(1)), dtype=float).ravel()  # 4 Hz
    y_hat = {"spectral": [], "spectral_tracked": [], "denoised_tracked": []}
    p_s, p_d = None, None
    dn = None
    if den is not None:
        dn = den.denoise_bv(x, 0.6 * x, FS)
    for i, hr_ref in enumerate(label):
        c = (4.0 + 2.0 * i) * FS
        a, b = int(c - 5.12 * FS), int(c + 5.12 * FS)
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
    acts = np.array([act_raw[min(int((4 + 2 * i) * 4), act_raw.size - 1)] for i in range(label.size)]) \
        if act_raw.size > 1 else np.zeros(label.size)
    out = {}
    for k, v in y_hat.items():
        if not v:
            continue
        e = np.abs(np.array(v, dtype=float) - label)
        out[k] = {"mae": float(np.nanmean(e)),
                  "by_activity": {ACTIVITIES.get(int(a), str(a)): float(np.nanmean(e[acts == a]))
                                  for a in np.unique(acts)}}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True, help="PPG_FieldStudy folder with S1..S15")
    ap.add_argument("--out", default="models/metrics")
    ap.add_argument("--models", default="models")
    a = ap.parse_args()
    onnx = Path(a.models) / "denoiser.onnx"
    den = Denoiser(onnx) if onnx.exists() else None
    report = {}
    for pkl in sorted(Path(a.root).glob("S*/S*.pkl"), key=lambda p: int(p.stem[1:])):
        report[pkl.stem] = subject_errors(load_subject(pkl), den)
        print(pkl.stem, {k: round(v["mae"], 2) for k, v in report[pkl.stem].items()}, flush=True)
    methods = {m for r in report.values() for m in r}
    report["mean_mae"] = {m: float(np.mean([r[m]["mae"] for k, r in report.items() if m in r])) for m in methods}
    print("mean MAE (bpm):", report["mean_mae"])
    Path(a.out).mkdir(parents=True, exist_ok=True)
    (Path(a.out) / "dalia_hr_eval.json").write_text(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
