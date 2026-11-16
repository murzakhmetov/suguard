from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from suguard_ml.config import FS
from suguard_ml.signal.filters import resample
from suguard_ml.synth.ppg import simulate_window

ML = Path(__file__).resolve().parents[1]
HAS_DENOISER = (ML / "models" / "denoiser.onnx").exists()


def raw_at_100hz(seed, **kw):
    """Simulated window, upsampled to the MAX30102's usual 100 Hz."""
    w = simulate_window(seed, n=1024, **kw)
    return w, resample(w.red_raw, FS, 100.0), resample(w.ir_raw, FS, 100.0)


def test_decision_does_not_depend_on_the_input_rate():
    """The same window delivered at 100 Hz and at 50 Hz gets the same decision and heart rate.
    (Edge ringing of the resampler used to reject every tenth good window at 100 Hz.)"""
    from scipy.interpolate import CubicSpline

    from suguard_ml.pipeline import SuGuardPipeline
    pipe = SuGuardPipeline(denoiser=None)
    differ, reliable = [], 0
    for seed in range(4_000_000, 4_000_060):
        w = simulate_window(seed)
        t = np.arange(w.ir_raw.size) / FS

        def at_100hz(v):
            return np.round(CubicSpline(t, v.astype(float))(np.arange(2 * v.size - 1) / (2 * FS)))
        a = pipe.analyze(w.red_raw, w.ir_raw, fs=FS)
        b = pipe.analyze(at_100hz(w.red_raw), at_100hz(w.ir_raw), fs=2 * FS)
        if a["reliable"] != b["reliable"]:
            differ.append(seed)
        elif a["reliable"]:
            reliable += 1
            assert abs(a["heart_rate"]["bpm"] - b["heart_rate"]["bpm"]) < 1.5, seed
    assert reliable >= 15
    assert len(differ) <= 1, differ


def test_pipeline_classical_clean():
    """Motion-free windows: the classical fallback may reject weak, noisy ones,
    but must accept most and be accurate when it does."""
    from suguard_ml.pipeline import SuGuardPipeline

    pipe = SuGuardPipeline(denoiser=None)
    ok, with_spo2, errs = 0, 0, []
    for seed in range(20):
        w, red, ir = raw_at_100hz(seed, kinds=[])
        res = pipe.analyze(red, ir, fs=100.0)
        assert res["method"] == "classical"
        if res["reliable"]:
            ok += 1
            errs.append(abs(res["heart_rate"]["bpm"] - w.hr_bpm))
        if res["spo2"]["percent"] is not None:
            with_spo2 += 1
            assert res["features"] is not None and abs(res["spo2"]["percent"] - w.spo2) < 3
    assert ok >= 15 and with_spo2 >= 10
    assert np.median(errs) < 2 and max(errs) < 6


def test_pipeline_rejects_no_contact():
    from suguard_ml.pipeline import SuGuardPipeline

    pipe = SuGuardPipeline.load()
    n = 1000
    rng = np.random.default_rng(0)
    res = pipe.analyze(rng.normal(900, 5, n), rng.normal(1200, 5, n), fs=100.0)
    assert not res["reliable"]
    assert res["heart_rate"]["bpm"] is None and res["spo2"]["percent"] is None
    assert "no_contact" in res["reason"]


@pytest.mark.skipif(not HAS_DENOISER, reason="denoiser not trained")
def test_denoiser_path_accepts_clean_windows():
    from suguard_ml.pipeline import SuGuardPipeline

    pipe = SuGuardPipeline.load()
    ok = 0
    for seed in range(20):
        w, red, ir = raw_at_100hz(seed, kinds=[])
        res = pipe.analyze(red, ir, fs=100.0)
        assert res["method"] == "denoiser"
        if res["reliable"] and res["spo2"]["percent"] is not None:
            ok += 1
            assert abs(res["heart_rate"]["bpm"] - w.hr_bpm) < 3 and abs(res["spo2"]["percent"] - w.spo2) < 3
    assert ok >= 18


@pytest.mark.skipif(not HAS_DENOISER, reason="denoiser not trained")
def test_denoiser_beats_raw_under_motion():
    """Under motion the denoised path must answer more often and be more
    accurate on the windows where both paths give an answer."""
    from suguard_ml.eval.vitals_eval import vitals_from_bv
    from suguard_ml.models.denoiser import Denoiser
    from suguard_ml.signal.filters import preprocess

    den = Denoiser.load()
    raw_hr, dn_hr, true_hr = [], [], []
    for seed in range(40):
        w = simulate_window(90_000 + seed, kinds=["periodic", "burst"], artifact_level=3.0)
        ir, _ = preprocess(w.ir_raw, w.fs)
        red, _ = preprocess(w.red_raw, w.fs)
        raw_hr.append(vitals_from_bv(ir, red, w.fs)["hr"])
        d = den.denoise_bv(ir, red, w.fs)
        dn_hr.append(vitals_from_bv(d.ir_bv, d.red_bv, w.fs, d.artifact_prob)["hr"])
        true_hr.append(w.hr_bpm)
    both = [i for i in range(40) if raw_hr[i] is not None and dn_hr[i] is not None]
    assert sum(h is not None for h in dn_hr) >= sum(h is not None for h in raw_hr)
    e_raw = np.mean([abs(raw_hr[i] - true_hr[i]) for i in both])
    e_dn = np.mean([abs(dn_hr[i] - true_hr[i]) for i in both])
    assert e_dn < 0.5 * e_raw


class _PassThroughDenoiser:
    """Stand-in for a network that turns anything into a confident 'pulse'."""

    def denoise_bv(self, ir_bv, red_bv, fs):
        from suguard_ml.models.denoiser import Denoised
        return Denoised(ir_bv=ir_bv, red_bv=red_bv, artifact_prob=np.zeros_like(ir_bv), fs=fs)


def test_noise_only_is_never_reliable():
    """Regression (review finding): finger on, no pulse, only noise."""
    from suguard_ml.pipeline import SuGuardPipeline

    rng = np.random.default_rng(0)
    red, ir = rng.normal(70_000, 30, 1024), rng.normal(100_000, 30, 1024)
    for pipe in (SuGuardPipeline(denoiser=None), SuGuardPipeline(denoiser=_PassThroughDenoiser())):
        res = pipe.analyze(red, ir, fs=100.0)
        assert not res["reliable"]
        assert res["heart_rate"]["bpm"] is None and res["spo2"]["percent"] is None
        assert res["spo2"]["r_ratio"] is None and res["features"] is None and res["reason"]


class _PulseDrawingDenoiser:
    """Stand-in for a network that answers any input with a textbook pulse."""

    def __init__(self):
        from suguard_ml.signal.filters import preprocess

        w = simulate_window(123, kinds=[], hr_bpm=72.0, spo2=97.0, pi_ir=0.01)
        self.window = w
        self.ir, self.red = preprocess(w.ir_raw, FS)[0], preprocess(w.red_raw, FS)[0]
        self.flagged = 0.0           # share of the window it calls motion (from the start)

    def denoise_bv(self, ir_bv, red_bv, fs):
        from suguard_ml.models.denoiser import Denoised
        p_art = (np.arange(self.ir.size) < self.flagged * self.ir.size).astype(float)
        return Denoised(ir_bv=self.ir, red_bv=self.red, artifact_prob=p_art, fs=fs)


def test_denoiser_output_must_be_supported_by_the_input():
    """Regression (review finding): a denoiser that draws a pulse into noise.
    Its output passes every quality check, so only the comparison with the
    measured signal can reject it."""
    from suguard_ml.pipeline import SuGuardPipeline

    drawer = _PulseDrawingDenoiser()
    pipe = SuGuardPipeline(denoiser=drawer)
    res = pipe.analyze(drawer.window.red_raw, drawer.window.ir_raw, fs=FS)      # the pulse really is in the input
    assert res["reliable"] and res["spo2"]["percent"] is not None
    rng = np.random.default_rng(3)
    for _ in range(40):
        sigma = float(np.exp(rng.uniform(np.log(5), np.log(400))))
        red, ir = rng.normal(70_000, sigma, 512).round(), rng.normal(100_000, sigma, 512).round()
        res = pipe.analyze(red, ir, fs=FS)
        assert not res["reliable"] and "denoiser_mismatch" in res["reason"]
        assert res["heart_rate"]["bpm"] is None and res["spo2"]["percent"] is None and res["features"] is None
    # IR pulse measured, red pulse drawn: heart rate yes, SpO2 no. Where the network calls the window
    # clean, SpO2 comes from the measured red/IR, which share no pulse ...
    red = np.median(drawer.window.red_raw) + rng.normal(0, 20, 512).round()
    res = pipe.analyze(red, drawer.window.ir_raw, fs=FS)
    assert res["reliable"] and res["heart_rate"]["bpm"] is not None
    assert res["spo2"]["percent"] is None and res["spo2"]["reason"] == "spo2_low_red_ir_agreement"
    assert res["features"] is None
    # ... and where it flags part of the window, its red output must be supported by the measurement.
    drawer.flagged = 0.3
    res = pipe.analyze(red, drawer.window.ir_raw, fs=FS)
    assert res["reliable"] and res["heart_rate"]["bpm"] is not None
    assert res["spo2"]["percent"] is None and res["spo2"]["reason"] == "red_denoiser_mismatch" and res["features"] is None


@pytest.mark.parametrize("model", ["server", "edge"])
def test_red_channel_without_pulse_gives_no_spo2(model):
    """The real networks tend to repair a pulse-free red channel from the IR
    one, which used to yield SpO2 ~100 % from nothing."""
    from suguard_ml.pipeline import SuGuardPipeline

    if model == "server":
        if not HAS_DENOISER:
            pytest.skip("denoiser not trained")
        pipe = SuGuardPipeline.load()
    else:
        from suguard_ml.models.edge_int import EdgeDenoiserInt
        if not (ML / "models" / "denoiser_edge_int.npz").exists():
            pytest.skip("edge model not exported")
        pipe = SuGuardPipeline(denoiser=EdgeDenoiserInt.load())
    rng = np.random.default_rng(1)
    for i in range(60):
        w = simulate_window(8_000_000 + i, kinds=[], pi_ir=float(np.exp(rng.uniform(np.log(0.002), np.log(0.03)))))
        dc = float(np.median(w.red_raw))
        weak = 0.0 if i % 2 == 0 else 0.2                       # no red pulse at all / a fifth of it in more noise
        red = np.round(dc + weak * (w.red_raw - dc) + rng.normal(0, (3e-4 + 2e-4 * (weak > 0)) * dc, 512))
        res = pipe.analyze(red, w.ir_raw, fs=FS)
        assert res["spo2"]["percent"] is None and res["features"] is None, (i, res["spo2"])


def test_non_arterial_ratio_makes_the_window_unreliable():
    """A clean waveform whose red/IR ratio no arterial blood produces (here: the
    two LED channels swapped) is not a pulse measurement."""
    from suguard_ml.pipeline import SuGuardPipeline

    pipe = SuGuardPipeline(denoiser=None)
    w = simulate_window(21, kinds=[], spo2=97.0, pi_ir=0.01)
    assert pipe.analyze(w.red_raw, w.ir_raw, fs=FS)["reliable"]
    res = pipe.analyze(w.ir_raw, w.red_raw, fs=FS)
    assert not res["reliable"] and res["reason"] == ["red_ir_inconsistent"]
    assert res["heart_rate"]["bpm"] is None and res["spo2"]["percent"] is None


def test_undefined_quality_metrics_fail():
    """Regression (review finding): a check that cannot be computed is not passed."""
    from suguard_ml.pipeline import SuGuardPipeline
    from suguard_ml.signal.quality import _ramp_down

    assert _ramp_down(np.inf, 0.2, 0.4) == 0.0 and _ramp_down(np.nan, 0.2, 0.4) == 0.0 and _ramp_down(0.1, 0.2, 0.4) == 1.0
    pipe = SuGuardPipeline(denoiser=None)
    for seed in range(12):                                   # 2.5 s: too short for the red/IR ratio stability
        w = simulate_window(30_000 + seed, n=125, kinds=[], pi_ir=0.01)
        res = pipe.analyze(w.red_raw, w.ir_raw, fs=FS)
        assert res["quality"]["components"]["r_stability"] == 0.0
        assert res["spo2"]["percent"] is None and res["features"] is None
    # ... and a window that fails the sensor checks is not "usable", whatever its waveform.
    w = simulate_window(4, kinds=[], pi_ir=0.01)
    res = pipe.analyze(w.red_raw * 0.1, w.ir_raw * 0.1, fs=FS)
    assert "no_contact" in res["reason"]
    assert res["quality"]["usable"] is False and res["quality"]["usable_spo2"] is False and res["quality"]["sqi"] == 0.0


def test_pipeline_handles_sparse_nan_and_rejects_many():
    from suguard_ml.pipeline import SuGuardPipeline

    pipe = SuGuardPipeline(denoiser=None)
    w, red, ir = raw_at_100hz(11, kinds=[])
    red, ir = red.copy(), ir.copy()
    red[100] = np.nan
    assert pipe.analyze(red, ir, fs=100.0)["interpolated_samples"] == 1
    ir[::10] = np.nan
    with pytest.raises(ValueError):
        pipe.analyze(red, ir, fs=100.0)


def test_api_endpoints():
    import json as _json

    from fastapi.testclient import TestClient

    import api.app as appmod

    client = TestClient(appmod.app)
    h = client.get("/health").json()
    assert h["status"] == "ok"

    windows, ts = [], 1.7e9
    for k in range(5):
        w, red, ir = raw_at_100hz(5 + k, kinds=[])
        r = client.post("/v1/analyze", json={"fs": 100.0, "red": red.round().tolist(), "ir": ir.round().tolist(),
                                             "timestamp": ts + 11 * k})
        assert r.status_code == 200, r.text
        body = r.json()
        if body["reliable"]:
            assert abs(body["heart_rate"]["bpm"] - w.hr_bpm) < 5
        if body["features"] is not None:
            windows.append(body["features"])
    assert len(windows) >= 3

    # Input validation: too short, NaN (JSON allows it), millisecond epoch, oversized body.
    assert client.post("/v1/analyze", json={"fs": 100.0, "red": [1.0] * 10, "ir": [1.0] * 10}).status_code == 422
    nan_red = red.round().tolist()
    nan_red[100] = float("nan")
    r_nan = client.post("/v1/analyze", content=_json.dumps({"fs": 100.0, "red": nan_red, "ir": ir.round().tolist()}),
                        headers={"content-type": "application/json"})
    assert r_nan.status_code == 422
    r_ms = client.post("/v1/analyze", json={"fs": 100.0, "red": red.round().tolist(), "ir": ir.round().tolist(),
                                            "timestamp": 1.7e12})
    assert r_ms.status_code == 422
    huge = client.post("/v1/analyze", content=b"{" + b" " * 2_100_000 + b"}", headers={"content-type": "application/json"})
    assert huge.status_code == 413

    # Glucose: with no trained model there is no number, only the fingerstick average after calibration.
    feats = windows[:3]
    g = client.post("/v1/glucose/estimate", json={"recent_features": feats, "timestamp": ts + 60}).json()
    if h["glucose_model"] is None:
        assert g["status"] == "unavailable" and g["mg_dl"] is None
    assert client.post("/v1/glucose/estimate", json={"recent_features": feats[:1], "timestamp": ts}).status_code == 422
    # Placeholders, copies of one window and numbers beyond a double are refused, not passed on.
    for bad in ([{}] * 3, [feats[0]] * 3, [dict(f, hr_bpm=None) for f in feats]):
        assert client.post("/v1/glucose/estimate", json={"recent_features": bad, "timestamp": ts}).status_code == 422
    huge_int = _json.dumps({"recent_features": feats, "timestamp": ts}).replace('"hr_bpm": ', '"hr_bpm": 1' + "0" * 400, 1)
    assert client.post("/v1/glucose/estimate", content=huge_int,
                       headers={"content-type": "application/json"}).status_code == 422
    cal = None
    for i, v in enumerate([110, 118, 115]):
        c = client.post("/v1/glucose/calibrate", json={"reference_mgdl": v, "timestamp": ts + i * 3600,
                                                        "recent_features": feats, "calibration": cal})
        assert c.status_code == 200, c.text
        if h["glucose_model"] is None:
            assert c.json()["estimate_before_mgdl"] is None     # no model, no estimate
        cal = c.json()["calibration"]
    assert cal["n_points"] == 3
    g2 = client.post("/v1/glucose/estimate", json={"recent_features": feats, "timestamp": ts + 4 * 3600,
                                                   "calibration": cal}).json()
    if h["glucose_model"] is None:
        assert g2["status"] == "calibration_only" and g2["mg_dl"] is None
        assert 105 < g2["fingerstick_average_mgdl"] < 125
    bad_cal = dict(cal, P=[[1.0, 0.0]], a=float("1e9"))
    assert client.post("/v1/glucose/estimate", json={"recent_features": feats, "timestamp": ts,
                                                     "calibration": bad_cal}).status_code == 422
    assert client.post("/v1/glucose/calibrate", json={"reference_mgdl": 100, "timestamp": ts,
                                                      "calibration": {"b": "x"}}).status_code == 422
    for field, value in (("a", "1" + "0" * 400), ("last_t", "1.7e12"), ("last_t", "-1e308"), ("P", "[[1e308,0],[0,1]]")):
        body = _json.dumps({"reference_mgdl": 100, "timestamp": ts, "calibration": {"n_points": 3, field: 0}})
        body = body.replace(f'"{field}": 0', f'"{field}": {value}')
        r_bad = client.post("/v1/glucose/calibrate", content=body, headers={"content-type": "application/json"})
        assert r_bad.status_code == 422, (field, r_bad.text)

    if h["risk_model"]:
        rk = client.post("/v1/risk", json={"age": 55, "height_cm": 170, "weight_kg": 92, "resting_hr_bpm": 80,
                                           "ancestry": "asian", "smoker": True})
        assert rk.status_code == 200
        body = rk.json()
        assert 0 < body["p_prediabetes_or_diabetes"] < 1 and "smoker" in body["inputs_not_used"]
        assert client.post("/v1/risk", json={"age": 55}).status_code == 422
        assert client.post("/v1/risk", json={"age": 55, "bmi": 25, "ancestry": "martian"}).status_code == 422


def test_calibration_state_always_round_trips():
    """Regression (review finding): the server issued states its own validation
    refused (level offset beyond the limit), locking the user out."""
    from fastapi.testclient import TestClient

    import api.app as appmod
    from suguard_ml.models.glucose import PersonalCalibration

    client = TestClient(appmod.app)
    for level in (600, 20):
        cal = None
        for i in range(40):                                   # extreme readings every 6 h
            r = client.post("/v1/glucose/calibrate", json={"reference_mgdl": level, "timestamp": 1.7e9 + i * 21600,
                                                            "calibration": cal})
            assert r.status_code == 200, (level, i, r.text)
            cal = r.json()["calibration"]
        g = client.post("/v1/glucose/estimate", json={"recent_features": [{"hr_bpm": 60.0 + k, "pi_ir": 1.0,
                                                                            "r_ratio": 0.5} for k in range(3)],
                                                      "timestamp": 1.7e9 + 41 * 21600, "calibration": cal})
        assert g.status_code == 200
        if appmod.GLUCOSE.model is None:
            assert abs(g.json()["fingerstick_average_mgdl"] - level) < 0.03 * level
    rng = np.random.default_rng(0)
    for trial in range(100):                                  # random extremes, out-of-order and huge time gaps
        cal, t = PersonalCalibration(), 1.7e9
        for _ in range(int(rng.integers(1, 40))):
            t = float(np.clip(t + rng.choice([-30 * 86400, 0, 60, 21600, 400 * 86400]), 1.5e9, 4.1e9))
            cal.update(float(rng.uniform(20, 600)) if trial % 2 else cal.f0, float(rng.choice([20, 600, 150])), t)
            assert PersonalCalibration.from_dict(cal.to_dict()).to_dict() == cal.to_dict()
            assert all(np.isfinite(cal.predict(105.0, t + 3600)))


def test_calibration_state_signature(monkeypatch):
    """With SUGUARD_STATE_KEY set, only states issued by the server are accepted."""
    from fastapi.testclient import TestClient

    import api.app as appmod

    monkeypatch.setattr(appmod, "STATE_KEY", b"test-key")
    client = TestClient(appmod.app)
    assert client.get("/health").json()["calibration_states_signed"] is True
    cal = None
    for i, v in enumerate([110, 118, 115]):
        r = client.post("/v1/glucose/calibrate", json={"reference_mgdl": v, "timestamp": 1.7e9 + i * 3600,
                                                        "calibration": cal})
        assert r.status_code == 200, r.text
        cal = r.json()["calibration"]
    assert isinstance(cal["sig"], str) and cal["n_points"] == 3
    feats = [{"hr_bpm": 60.0 + k, "pi_ir": 1.0, "r_ratio": 0.5} for k in range(3)]

    def estimate(state):
        return client.post("/v1/glucose/estimate", json={"recent_features": feats, "timestamp": 1.7e9 + 5 * 3600,
                                                         "calibration": state})

    assert estimate(cal).status_code == 200
    # A client library that writes 900.0 as 900 (or reorders keys) must still verify.
    as_ints = {k: (int(v) if isinstance(v, float) and v == int(v) else v) for k, v in reversed(list(cal.items()))}
    as_ints["P"] = [[int(x) if x == int(x) else x for x in row] for row in cal["P"]]
    assert estimate(as_ints).status_code == 200
    # Forged, altered or unsigned states are refused.
    assert estimate({"n_points": 3}).status_code == 422
    assert estimate({**cal, "a": cal["a"] + 50.0}).status_code == 422
    assert estimate({k: v for k, v in cal.items() if k != "sig"}).status_code == 422
    assert estimate({**cal, "sig": "0" * 64}).status_code == 422
    assert estimate(None).status_code == 200                 # no state at all is a fresh calibration


class _StubGlucoseModel:
    """A population model that reads 150 mg/dL for everyone."""
    version, validated, meta = "stub-1", False, {"version": "stub-1"}

    def predict(self, feats):
        assert feats["hr_bpm"] is not None and "hour_sin" in feats
        return 150.0, 130.0, 170.0


def test_glucose_endpoints_with_a_model(monkeypatch):
    """The calibration must be fitted against the model's prediction for the
    same moment, and belongs to that model version."""
    from fastapi.testclient import TestClient

    import api.app as appmod

    monkeypatch.setattr(appmod.GLUCOSE, "model", _StubGlucoseModel())
    monkeypatch.setattr(appmod, "MODEL_VERSION", "stub-1")
    client = TestClient(appmod.app)
    feats = [{"hr_bpm": 60.0 + k, "pi_ir": 1.0, "r_ratio": 0.5} for k in range(3)]
    # A model that has not passed validation gives no number ...
    g = client.post("/v1/glucose/estimate", json={"recent_features": feats, "timestamp": 1.7e9}).json()
    assert g["status"] == "not_validated" and g["mg_dl"] is None and "mmol_l" not in g and "interval_80" not in g
    assert client.get("/health").json()["experimental_glucose_output"] is False
    # ... not through the calibration endpoint either.
    c = None
    for i, v in enumerate([120, 121]):
        r = client.post("/v1/glucose/calibrate", json={"reference_mgdl": v, "timestamp": 1.7e9 + i * 3600,
                                                      "calibration": c, "recent_features": feats})
        assert r.status_code == 200 and r.json()["estimate_before_mgdl"] is None, r.text
        c = r.json()["calibration"]
    # ... unless the operator has switched experimental output on (SUGUARD_EXPERIMENTAL_GLUCOSE=1).
    monkeypatch.setattr(appmod, "EXPERIMENTAL_GLUCOSE", True)
    g = client.post("/v1/glucose/estimate", json={"recent_features": feats, "timestamp": 1.7e9}).json()
    assert g["status"] == "experimental" and g["mg_dl"] == 150.0 and g["interval_80"] == [130.0, 170.0]
    cal = None
    for i, v in enumerate([120, 121, 119, 120]):
        body = {"reference_mgdl": v, "timestamp": 1.7e9 + i * 3600, "calibration": cal}
        assert client.post("/v1/glucose/calibrate", json=body).status_code == 422          # features are required
        assert client.post("/v1/glucose/calibrate", json={**body, "recent_features": [{}] * 3}).status_code == 422
        r = client.post("/v1/glucose/calibrate", json={**body, "recent_features": feats})
        assert r.status_code == 200, r.text
        cal = r.json()["calibration"]
    assert cal["model_version"] == "stub-1" and cal["n_points"] == 4 and -31 < cal["a"] < -20
    g = client.post("/v1/glucose/estimate", json={"recent_features": feats, "timestamp": 1.7e9 + 5 * 3600,
                                                  "calibration": cal}).json()
    assert g["status"] == "experimental" and 118 < g["mg_dl"] < 130 and g["calibrations"] == 4
    # The same state against another model version starts from scratch.
    monkeypatch.setattr(appmod, "MODEL_VERSION", "stub-2")
    g = client.post("/v1/glucose/estimate", json={"recent_features": feats, "timestamp": 1.7e9 + 5 * 3600,
                                                  "calibration": cal}).json()
    assert g["mg_dl"] == 150.0 and g["calibrations"] == 0


def test_api_needs_no_pandas():
    """requirements-api.txt has no pandas, torch or scikit-learn: the service must start without them."""
    import subprocess
    import sys

    code = (
        "import importlib.abc, sys\n"
        "class Block(importlib.abc.MetaPathFinder):\n"
        "    def find_spec(self, name, path=None, target=None):\n"
        "        if name.split('.')[0] in ('pandas', 'torch', 'sklearn'):\n"
        "            raise ModuleNotFoundError(name)\n"
        "sys.meta_path.insert(0, Block())\n"
        "import api.app\n"
        "from suguard_ml.aggregation import aggregate_window_features as agg\n"
        "assert agg([{'a': 1.0, 'b': None}, {'a': 3.0}, {'a': float('nan'), 'b': 'x'}]) == {'a': 2.0, 'b': None}\n"
        "print('ok')\n")
    run = subprocess.run([sys.executable, "-c", code], cwd=ML, capture_output=True, text=True)
    assert run.returncode == 0 and run.stdout.strip().endswith("ok"), run.stderr[-2000:]


def _fake_bigideas(root: Path):
    """Minimal folder in the BIG IDEAs layout, filled with simulated data."""
    sub = root / "001"
    sub.mkdir(parents=True)
    t0 = pd.Timestamp("2020-02-13 08:00:00")
    fs_e4 = 64.0
    segs = [simulate_window(100 + k, n=int(10.24 * FS), kinds=[]) for k in range(70)]
    bvp = np.concatenate([resample(-(s.ir_clean_raw - s.ir_clean_raw.mean()), FS, fs_e4) for s in segs])
    tb = t0 + pd.to_timedelta(np.arange(bvp.size) / fs_e4, unit="s")
    pd.DataFrame({"datetime": tb.strftime("%Y-%m-%d %H:%M:%S.%f"), " bvp": bvp}).to_csv(sub / "BVP_001.csv", index=False)
    n_acc = int(bvp.size / fs_e4 * 32)
    ta = t0 + pd.to_timedelta(np.arange(n_acc) / 32.0, unit="s")
    pd.DataFrame({"datetime": ta.strftime("%Y-%m-%d %H:%M:%S.%f"), " acc_x": 0.0, " acc_y": 0.0,
                  " acc_z": 64.0 + np.random.default_rng(0).normal(0, 0.1, n_acc)}).to_csv(sub / "ACC_001.csv", index=False)
    tc = t0 + pd.to_timedelta(np.arange(5, bvp.size / fs_e4 / 60, 5), unit="min")
    pd.DataFrame({"Index": range(len(tc)), "Timestamp (YYYY-MM-DDThh:mm:ss)": tc.strftime("%Y-%m-%dT%H:%M:%S"),
                  "Event Type": "EGV", "Glucose Value (mg/dL)": np.linspace(95, 140, len(tc)).round()}
                 ).to_csv(sub / "Dexcom_001.csv", index=False)
    pd.DataFrame({"date": ["2020-02-13"], "time": ["08:00:00"], "time_begin": ["2020-02-13 07:50:00"],
                  "logged_food": ["oatmeal"], "total_carb": [45.0]}).to_csv(sub / "Food_Log_001.csv", index=False)
    pd.DataFrame({"ID": [1], "Gender": ["FEMALE"], "HbA1c": [5.6]}).to_csv(root / "Demographics.csv", index=False)


def test_bigideas_loader_on_fake_layout(tmp_path):
    from suguard_ml.data.bigideas import build_table

    _fake_bigideas(tmp_path)
    df = build_table(tmp_path)
    assert len(df) >= 1
    assert {"subject_id", "glucose_mgdl", "hr_bpm", "minutes_since_meal", "male"} <= set(df.columns)
    assert df["hr_bpm"].notna().all()
    assert (df["subject_id"] == "001").all()


class _AlteringDenoiser:
    """Stand-in for a network that passes a clean window through, altered: without the pulse's
    fundamental (``drop_hz``) and/or with the red channel scaled by ``red_gain``."""

    def __init__(self, drop_hz=None, red_gain=1.0):
        self.drop_hz, self.red_gain = drop_hz, red_gain

    def denoise_bv(self, ir_bv, red_bv, fs):
        from suguard_ml.models.denoiser import Denoised

        def without(x):
            if self.drop_hz is None:
                return x
            t = np.arange(x.size) / fs
            basis = np.stack([np.sin(2 * np.pi * self.drop_hz * t), np.cos(2 * np.pi * self.drop_hz * t)], 1)
            return x - basis @ np.linalg.lstsq(basis, x, rcond=None)[0]
        return Denoised(ir_bv=without(ir_bv), red_bv=self.red_gain * without(red_bv),
                        artifact_prob=np.zeros_like(ir_bv), fs=fs)


def _double_humped(hr_bpm=36.0, n=512):
    """A slow pulse whose 2nd harmonic is 1.6x its fundamental: raw red/IR counts."""
    t = np.arange(n) / FS
    th = 2 * np.pi * hr_bpm / 60.0 * t
    x = np.sin(th) + 1.6 * np.sin(2 * th + 1.0)
    x = x / np.ptp(x)
    rng = np.random.default_rng(0)
    return (np.round(70_000 * (1 - 0.6 * 0.01 * x) + rng.normal(0, 3, n)),
            np.round(100_000 * (1 - 0.01 * x) + rng.normal(0, 3, n)))


def test_clean_window_rate_is_checked_against_the_measured_spectrum(monkeypatch):
    """A network that suppresses the fundamental of a slow double-humped pulse doubles the beat
    count and makes its own spectrum agree; the measured spectrum keeps the fundamental. (Below
    about 38 bpm the band-pass filters weaken the fundamental so much that the measured spectrum
    picks the 2nd harmonic of such a pulse too.)"""
    import suguard_ml.pipeline as P

    red, ir = _double_humped(40.0)
    pipe = P.SuGuardPipeline(denoiser=_AlteringDenoiser(drop_hz=40.0 / 60.0))
    res = pipe.analyze(red, ir, fs=FS)
    assert not res["reliable"] and res["heart_rate"]["bpm"] is None and "motion" in res["reason"]
    monkeypatch.setattr(P, "CLEAN_MAX_MOTION", -1.0)          # the denoised spectrum as the reference
    res = pipe.analyze(red, ir, fs=FS)
    assert res["reliable"] and abs(res["heart_rate"]["bpm"] - 80.0) < 3.0      # the failure it prevents


def test_clean_window_spo2_comes_from_the_measured_signals(monkeypatch):
    """A network that attenuates red reads SpO2 high; in a clean window the measured red/IR count."""
    import suguard_ml.pipeline as P

    w = simulate_window(41, kinds=[], hr_bpm=150.0, spo2=85.0, pi_ir=0.01, shape="wave")
    classical = P.SuGuardPipeline(denoiser=None).analyze(w.red_raw, w.ir_raw, fs=FS)["spo2"]["percent"]
    pipe = P.SuGuardPipeline(denoiser=_AlteringDenoiser(red_gain=0.9))
    shown = pipe.analyze(w.red_raw, w.ir_raw, fs=FS)["spo2"]["percent"]
    assert classical is not None and shown is not None and abs(shown - classical) < 0.2
    monkeypatch.setattr(P, "CLEAN_MAX_MOTION", -1.0)
    biased = pipe.analyze(w.red_raw, w.ir_raw, fs=FS)["spo2"]["percent"]
    assert biased is not None and biased > classical + 2.0                      # the failure it prevents
