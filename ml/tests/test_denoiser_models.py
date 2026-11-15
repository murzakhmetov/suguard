"""The shipped networks against what they must and must not do.

The first networks took smooth, wrist-like pulses for motion and gave a
heart rate for almost none of them (a sine: 0 %; the classical path: 99 %);
the next ones still took real pulses with a deep notch and a large
diastolic wave for motion (11 of 52 clean real windows rejected). These
tests keep a retrained model from losing either again, and from paying for
it by reporting rhythmic motion as a pulse.
"""
import sys
from pathlib import Path

import numpy as np
import pytest

from suguard_ml.config import FS, WINDOW
from suguard_ml.pipeline import SuGuardPipeline
from suguard_ml.synth.ppg import corrupt_pulse, simulate_window

ML = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ML / "scripts"))
import eval_denoiser as E  # noqa: E402


def _models():
    out = []
    if (ML / "models" / "denoiser.onnx").exists():
        from suguard_ml.models.denoiser import Denoiser
        out.append(pytest.param(lambda: Denoiser(ML / "models" / "denoiser.onnx"), id="server"))
    if (ML / "models" / "denoiser_edge_int.npz").exists():
        from suguard_ml.models.edge_int import EdgeDenoiserInt
        out.append(pytest.param(lambda: EdgeDenoiserInt(ML / "models" / "denoiser_edge_int.npz"), id="bracelet"))
    return out


MODELS = _models()


def _shape_windows(shape: str, n: int, seed: int):
    gen = E._shape_generators()[shape]
    rng = np.random.default_rng(seed)
    wins, hr = [], []
    for _ in range(n):
        th = E._phase(rng, float(rng.uniform(50, 110)), WINDOW + 200)
        x = np.asarray(gen(th), dtype=float)[100:100 + WINDOW]
        rate = float((th[100 + WINDOW - 1] - th[100]) / (2 * np.pi) / ((WINDOW - 1) / FS) * 60.0)
        wins.append(corrupt_pulse(x, rng, spo2=float(rng.uniform(90, 99.5)),
                                  pi_ir=float(np.exp(rng.uniform(np.log(0.003), np.log(0.03)))), hr_bpm=rate, kinds=[]))
        hr.append(rate)
    return wins, hr


@pytest.mark.skipif(not MODELS, reason="no trained model in models/")
@pytest.mark.parametrize("make", MODELS)
@pytest.mark.parametrize("shape", ["sharp_with_reflected_wave", "skewed_triangle_rise_35pct_smooth", "two_harmonics", "sine"])
def test_clean_pulses_of_any_shape_are_reported(make, shape):
    pipe = SuGuardPipeline(denoiser=make())
    wins, hr = _shape_windows(shape, 30, seed=11)
    res = [pipe.analyze(w.red_raw, w.ir_raw, fs=FS) for w in wins]
    given = [abs(r["heart_rate"]["bpm"] - t) for r, t in zip(res, hr) if r["reliable"]]
    assert len(given) >= 26, (shape, len(given), [r.get("reason") for r in res if not r["reliable"]][:5])
    assert max(given) < 5.0, (shape, max(given))


@pytest.mark.skipif(not MODELS, reason="no trained model in models/")
@pytest.mark.parametrize("make", MODELS)
def test_rhythmic_motion_without_a_pulse_is_not_reported(make):
    """Periodic motion as large as a pulse, no pulse at all: the classical path reports a
    quarter of these windows; a network must not."""
    pipe = SuGuardPipeline(denoiser=make())
    rng = np.random.default_rng(3)
    wins = [simulate_window(8_100_000 + i, pi_ir=1e-4, kinds=["periodic"],
                            artifact_level=float(np.exp(rng.uniform(np.log(30), np.log(300))))) for i in range(60)]
    reported = sum(pipe.analyze(w.red_raw, w.ir_raw, fs=FS)["reliable"] for w in wins)
    assert reported <= 1, reported


REAL = ML / "data" / "heartpy"


@pytest.mark.skipif(not MODELS, reason="no trained model in models/")
@pytest.mark.skipif(not all((REAL / f).exists() for f in ("heartpy/data/data2.csv", "heartpy/data/data3.csv")),
                    reason="real recordings not cached (scripts/eval_denoiser.py downloads them)")
@pytest.mark.parametrize("make", MODELS)
def test_clean_real_pulses_are_reported(make):
    """Real pulse shapes (heartpy recordings) through the simulated optics, at rest: the network path
    must report about as many windows as the classical path does, and correctly."""
    from suguard_ml.data.realppg import load_recordings
    from suguard_ml.signal.beats import beat_template, detect_beats, pulse_polarity
    from suguard_ml.signal.filters import bandpass

    pipe, classical = SuGuardPipeline(denoiser=make()), SuGuardPipeline(denoiser=None)
    rng = np.random.default_rng(0)
    n = ok = ok_classical = 0
    for x in load_recordings(REAL).values():
        x = pulse_polarity(x, FS) * bandpass(x, FS, 0.4, 12.0)
        for s in range(0, len(x) - WINDOW + 1, WINDOW):
            seg = x[s:s + WINDOW]
            b = detect_beats(seg, FS)
            if b.hr_bpm is None or b.valid_ibi.sum() < 5 or beat_template(seg, b)[1] < 0.9:
                continue
            w = corrupt_pulse(seg, rng, spo2=float(rng.uniform(90, 99.5)), pi_ir=float(rng.uniform(0.004, 0.02)),
                              hr_bpm=b.hr_bpm, kinds=[])
            r, rc = pipe.analyze(w.red_raw, w.ir_raw, fs=FS), classical.analyze(w.red_raw, w.ir_raw, fs=FS)
            n += 1
            ok_classical += rc["reliable"]
            if r["reliable"]:
                assert abs(r["heart_rate"]["bpm"] - b.hr_bpm) < 3.0
                ok += 1
    assert n >= 20
    assert ok >= 0.9 * ok_classical, (ok, ok_classical, n)
