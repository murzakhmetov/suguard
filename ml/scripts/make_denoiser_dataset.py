"""Generate simulated MAX30102 windows for the denoiser.

    python scripts/make_denoiser_dataset.py --out data/denoiser --train 200000 --val 4000 --test 4000

(the defaults; the shipped models were trained on exactly this set)

Each split uses a disjoint seed range, so no window appears twice. The heart
rate is drawn over the whole band the pipeline accepts (35-210 bpm, see
``training_hr``); the simulator's own default (40-185 bpm) left the networks
without examples at the slowest and fastest rates.
"""

from __future__ import annotations

import argparse
import sys
from multiprocessing import Pool
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from suguard_ml.config import HR_MAX_BPM, HR_MIN_BPM  # noqa: E402
from suguard_ml.models.denoiser import model_input  # noqa: E402
from suguard_ml.signal.filters import preprocess  # noqa: E402
from suguard_ml.synth.ppg import simulate_window  # noqa: E402

SEED_OFFSET = {"train": 1_000_000, "val": 2_000_000, "test": 3_000_000}


def training_hr(seed: int) -> float:
    """Three quarters around a resting 75 bpm, a quarter uniform over the pipeline's band."""
    rng = np.random.default_rng([seed, 1])
    hr = rng.normal(75, 15) if rng.random() < 0.75 else rng.uniform(HR_MIN_BPM, HR_MAX_BPM)
    return float(np.clip(hr, HR_MIN_BPM, HR_MAX_BPM))


def make_one(seed: int):
    w = simulate_window(seed, hr_bpm=training_hr(seed))
    x, scale, _, _ = model_input(w.red_raw, w.ir_raw, w.fs)
    ir_c, _ = preprocess(w.ir_clean_raw, w.fs)
    red_c, _ = preprocess(w.red_clean_raw, w.fs)
    y = np.stack([ir_c, red_c]) / scale
    meta = (w.hr_bpm, w.spo2, w.r_ratio, w.pi_ir, w.artifact_level, len(w.artifact_types), float(w.mask.mean()))
    return x.astype(np.float16), np.clip(y, -50, 50).astype(np.float16), w.mask.astype(np.uint8), meta


def make_split(name: str, n: int, out: Path, workers: int):
    seeds = range(SEED_OFFSET[name], SEED_OFFSET[name] + n)
    with Pool(workers) as pool:
        res = pool.map(make_one, seeds, chunksize=256)
    X = np.stack([r[0] for r in res])
    Y = np.stack([r[1] for r in res])
    M = np.stack([r[2] for r in res])
    meta = np.array([r[3] for r in res], dtype=np.float32)
    np.savez(out / f"{name}.npz", X=X, Y=Y, M=M, meta=meta,
             meta_cols=np.array(["hr", "spo2", "r", "pi", "level", "n_types", "mask_frac"]))
    print(f"{name}: {X.shape} mask_frac={meta[:, 6].mean():.3f}", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/denoiser")
    ap.add_argument("--train", type=int, default=200_000)
    ap.add_argument("--val", type=int, default=4_000)
    ap.add_argument("--test", type=int, default=4_000)
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    for name, n in [("val", a.val), ("test", a.test), ("train", a.train)]:
        make_split(name, n, out, a.workers)


if __name__ == "__main__":
    main()
