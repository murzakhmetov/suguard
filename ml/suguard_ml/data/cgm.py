"""Real CGM traces bundled with the ``iglu-py`` package (PyPI).

* example_data_5_subject.csv - 5 adults with type 2 diabetes (Dexcom G4),
  from the iglu R package (Broll et al., PLoS One 2021).
* example_data_hall.csv - CGM of normoglycaemic, prediabetic and diabetic
  adults from Hall et al., PLoS Biology 2018 ("glucotypes").

Used to benchmark what fingerstick calibration alone achieves, i.e. the bar a
PPG model has to clear. The files are read from the downloaded wheel; they are
not redistributed in this repository.
"""

from __future__ import annotations

import subprocess
import sys
import zipfile
from pathlib import Path

import pandas as pd

FILES = {"t2d5": "iglu_py/data/example_data_5_subject.csv", "hall": "iglu_py/data/example_data_hall.csv"}


def ensure_iglu_data(cache: str | Path = "data/iglu") -> Path:
    cache = Path(cache)
    if all((cache / f).exists() for f in FILES.values()):
        return cache
    cache.mkdir(parents=True, exist_ok=True)
    subprocess.run([sys.executable, "-m", "pip", "download", "--no-deps", "-q", "-d", str(cache), "iglu-py==1.1.1"],
                   check=True)
    wheel = next(cache.glob("iglu_py-*.whl"))
    with zipfile.ZipFile(wheel) as z:
        for f in FILES.values():
            z.extract(f, cache)
    return cache


def load_cgm(name: str, cache: str | Path = "data/iglu") -> pd.DataFrame:
    """Columns: id, time (datetime), gl (mg/dL), [diagnosis]."""
    root = ensure_iglu_data(cache)
    df = pd.read_csv(root / FILES[name])
    df = df.drop(columns=[c for c in df.columns if c.startswith("Unnamed") or c == ""], errors="ignore")
    df["time"] = pd.to_datetime(df["time"], format="mixed")
    df["gl"] = pd.to_numeric(df["gl"], errors="coerce")
    df = df.dropna(subset=["gl"]).sort_values(["id", "time"]).reset_index(drop=True)
    df["dataset"] = name
    return df
