import pickle
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from suguard_ml.config import FS
from suguard_ml.signal.filters import resample
from suguard_ml.synth.ppg import simulate_window

ML = Path(__file__).resolve().parents[1]


def test_eval_dalia_on_fake_subject(tmp_path):
    """PPG-DaLiA layout: S1/S1.pkl with wrist BVP at 64 Hz and 8-s/2-s HR labels."""
    rec = simulate_window(500, n=6 * 512, kinds=[], hr_bpm=72.0, pi_ir=0.01)       # one minute, at rest
    bvp = resample(-(rec.ir_clean_raw - rec.ir_clean_raw.mean()), FS, 64.0)
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
    assert rep["spectral_tracking"]["mean_mae"]["spectral_tracked"] < 6.0
    # The gated pipeline on the same recording: a clean pulse gets a value, and the value is right.
    gated = rep["gated_pipeline"]
    for path in ("classical", "server", "bracelet"):
        r = gated[path]
        assert r["windows"] == 6 and r["by_activity"]["sitting"]["windows"] == 6, r
        assert r["hr_coverage"] >= 0.8 and r["hr_mae"] < 2.0 and r["hr_errors_over_10bpm"] == 0, (path, r)


def test_eval_dalia_counts_and_labels():
    """The conversion of a one-channel recording to raw counts and the alignment of the labels."""
    sys.path.insert(0, str(ML / "scripts"))
    import eval_dalia as E

    from suguard_ml.signal.filters import bandpass
    w = simulate_window(7, n=4 * 512, kinds=[], hr_bpm=80.0)
    x = bandpass(-(w.ir_clean_raw - w.ir_clean_raw.mean()), FS, 0.4, 12.0)     # pulse signal, peaks up
    red, ir = E.to_counts(x * 37.0)                               # in an arbitrary unit, like the E4
    assert red.shape == ir.shape == x.shape

    def ac(v):                                                    # pulse amplitude relative to the light level, per window
        v = v.reshape(4, 512)
        return (np.percentile(v, 97, axis=1) - np.percentile(v, 3, axis=1)) / np.median(v, axis=1)
    assert np.percentile(ac(ir), 25) == pytest.approx(E.REST_PI, rel=0.05)     # the quiet quarter is set to 1 %
    assert np.allclose(ac(red) / ac(ir), E.R_RATIO, rtol=0.03)    # red is the IR pulse at the fixed ratio
    assert np.corrcoef(ir, -x)[0, 1] > 0.99                       # more blood, less light
    # an inverted recording is turned upright
    d = {"signal": {"wrist": {"BVP": resample(-x, FS, E.BVP_FS)[:, None]}}, "label": np.arange(10.0), "activity": np.r_[
        np.ones(40), 7 * np.ones(200)]}
    assert np.corrcoef(E.pulse_signal(d)[100:x.size - 100], x[100:-100])[0, 1] > 0.95
    # label i describes [2 i, 2 i + 8] s: centre 4 + 2 i
    hr, act = E.labels_at(d, np.array([4.0, 5.2, 12.0, 21.9, 30.0]))
    assert hr[:4].tolist() == [0.0, 1.0, 4.0, 9.0] and np.isnan(hr[4])
    assert act.tolist() == [1.0, 1.0, 7.0, 7.0, 7.0]
