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
    for k in range(3):
        w, red, ir = raw_at_100hz(5 + k, kinds=[])
        r = client.post("/v1/analyze", json={"fs": 100.0, "red": red.round().tolist(), "ir": ir.round().tolist(),
                                             "timestamp": ts + 11 * k})
        assert r.status_code == 200, r.text
        body = r.json()
        if body["reliable"]:
            assert abs(body["heart_rate"]["bpm"] - w.hr_bpm) < 5
            windows.append(body["features"])
    assert len(windows) >= 2

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
    feats = (windows * 3)[:3]
    g = client.post("/v1/glucose/estimate", json={"recent_features": feats, "timestamp": ts + 60}).json()
    if h["glucose_model"] is None:
        assert g["status"] == "unavailable" and g["mg_dl"] is None
    assert client.post("/v1/glucose/estimate", json={"recent_features": feats[:1], "timestamp": ts}).status_code == 422
    cal = None
    for i, v in enumerate([110, 118, 115]):
        c = client.post("/v1/glucose/calibrate", json={"reference_mgdl": v, "timestamp": ts + i * 3600,
                                                        "recent_features": feats, "calibration": cal})
        assert c.status_code == 200, c.text
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

    if h["risk_model"]:
        rk = client.post("/v1/risk", json={"age": 55, "height_cm": 170, "weight_kg": 92, "resting_hr_bpm": 80,
                                           "ancestry": "asian", "smoker": True})
        assert rk.status_code == 200
        body = rk.json()
        assert 0 < body["p_prediabetes_or_diabetes"] < 1 and "smoker" in body["inputs_not_used"]
        assert client.post("/v1/risk", json={"age": 55}).status_code == 422
        assert client.post("/v1/risk", json={"age": 55, "bmi": 25, "ancestry": "martian"}).status_code == 422


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
