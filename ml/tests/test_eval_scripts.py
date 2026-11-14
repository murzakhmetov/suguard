import pickle
import subprocess
import sys
from pathlib import Path

import numpy as np

from suguard_ml.config import FS
from suguard_ml.signal.filters import resample
from suguard_ml.synth.ppg import simulate_window

ML = Path(__file__).resolve().parents[1]


def test_eval_dalia_on_fake_subject(tmp_path):
    """PPG-DaLiA layout: S1/S1.pkl with wrist BVP at 64 Hz and 8-s/2-s HR labels."""
    segs = [simulate_window(500 + k, n=int(10.24 * FS), kinds=[], hr_bpm=72.0) for k in range(6)]
    clean = np.concatenate([-(s.ir_clean_raw - s.ir_clean_raw.mean()) for s in segs])
    bvp = resample(clean, FS, 64.0)
    n_lab = int((bvp.size / 64.0 - 8) / 2) + 1
    d = {"signal": {"wrist": {"BVP": bvp[:, None]}}, "label": np.full(n_lab, 72.0),
         "activity": np.ones(int(bvp.size / 64.0 * 4))}
    (tmp_path / "S1").mkdir()
    with open(tmp_path / "S1" / "S1.pkl", "wb") as fh:
        pickle.dump(d, fh)
    subprocess.run([sys.executable, str(ML / "scripts" / "eval_dalia.py"), "--root", str(tmp_path),
                    "--out", str(tmp_path / "out"), "--models", str(ML / "models")],
                   check=True, capture_output=True, cwd=ML)
    import json
    rep = json.loads((tmp_path / "out" / "dalia_hr_eval.json").read_text())
    assert rep["mean_mae"]["spectral_tracked"] < 6.0
