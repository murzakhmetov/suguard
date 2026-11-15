"""Real PPG recordings bundled with the ``heartpy`` package (PyPI, GPL-3.0).

Three finger/ear PPG recordings (100 Hz / ~117 Hz / ~67 Hz; 25 s, 128 s,
11 min) published as HeartPy's example data (van Gent et al. 2019). They
are used only to *evaluate* the denoiser on real pulse morphology and real
heart-rate variability; they are read from the downloaded wheel and are not
redistributed or used for training.
"""

from __future__ import annotations

import subprocess
import sys
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

from ..config import FS
from ..signal.filters import resample, resample_irregular

FILES = ["heartpy/data/data.csv", "heartpy/data/data2.csv", "heartpy/data/data3.csv"]


def ensure_heartpy_data(cache: str | Path = "data/heartpy") -> Path:
    cache = Path(cache)
    if all((cache / f).exists() for f in FILES):
        return cache
    cache.mkdir(parents=True, exist_ok=True)
    subprocess.run([sys.executable, "-m", "pip", "download", "--no-deps", "-q", "-d", str(cache), "heartpy==1.2.7"],
                   check=True)
    with zipfile.ZipFile(next(cache.glob("heartpy-*.whl"))) as z:
        for f in FILES:
            z.extract(f, cache)
    return cache


def load_recordings(cache: str | Path = "data/heartpy") -> dict[str, np.ndarray]:
    """Recordings resampled to the pipeline rate (FS), blood-volume polarity."""
    root = ensure_heartpy_data(cache)
    out = {}
    d1 = pd.read_csv(root / FILES[0], header=None)[0].to_numpy(dtype=float)
    out["heartpy_data1"] = resample(d1, 100.0, FS)
    d2 = pd.read_csv(root / FILES[1])
    t2 = d2["timer"].to_numpy(dtype=float) / 1000.0
    out["heartpy_data2"] = resample_irregular(t2, d2["hr"].to_numpy(dtype=float), FS)[1]
    d3 = pd.read_csv(root / FILES[2])
    t3 = pd.to_datetime(d3["datetime"], format="mixed")
    t3 = (t3 - t3.iloc[0]).dt.total_seconds().to_numpy()
    out["heartpy_data3"] = resample_irregular(t3, d3["hr"].to_numpy(dtype=float), FS)[1]
    return out
