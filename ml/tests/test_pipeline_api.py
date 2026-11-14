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
    from suguard_ml.pipeline import SuGuardPipeline

    pipe = SuGuardPipeline(denoiser=None)
    w, red, ir = raw_at_100hz(11, kinds=[])
    res = pipe.analyze(red, ir, fs=100.0)
    assert res["method"] == "classical"
    assert res["reliable"]
    assert res["heart_rate"]["bpm"] == pytest.approx(w.hr_bpm, abs=4)
    assert res["features"] is not None


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
def test_denoiser_beats_raw_under_motion():
    from suguard_ml.eval.vitals_eval import vitals_from_bv
    from suguard_ml.models.denoiser import Denoiser
    from suguard_ml.signal.filters import preprocess

    den = Denoiser.load()
    e_raw, e_dn = [], []
    for seed in range(40):
        w = simulate_window(90_000 + seed, kinds=["periodic", "burst"], artifact_level=3.0)
        ir, _ = preprocess(w.ir_raw, w.fs)
        red, _ = preprocess(w.red_raw, w.fs)
        raw = vitals_from_bv(ir, red, w.fs)
        d = den.denoise_bv(ir, red, w.fs)
        dn = vitals_from_bv(d.ir_bv, d.red_bv, w.fs, d.artifact_prob)
        e_raw.append(abs((raw["spo2"] or 0) - w.spo2))
        e_dn.append(abs((dn["spo2"] or 0) - w.spo2))
    assert np.mean(e_dn) < 0.5 * np.mean(e_raw)


def test_api_endpoints():
    from fastapi.testclient import TestClient

    import api.app as appmod

    client = TestClient(appmod.app)
    h = client.get("/health").json()
    assert h["status"] == "ok"

    w, red, ir = raw_at_100hz(5, kinds=[])
    r = client.post("/v1/analyze", json={"fs": 100.0, "red": red.round().tolist(), "ir": ir.round().tolist(),
                                         "timestamp": 1.7e9})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["reliable"] and abs(body["heart_rate"]["bpm"] - w.hr_bpm) < 5
    assert body["glucose"]["status"] in {"unavailable", "experimental", "uncalibrated", "calibrated",
                                         "calibration_only", "poor_signal"}

    bad = client.post("/v1/analyze", json={"fs": 100.0, "red": [1.0] * 10, "ir": [1.0] * 10})
    assert bad.status_code == 422

    cal = None
    for i, v in enumerate([110, 118, 115]):
        c = client.post("/v1/glucose/calibrate", json={"reference_mgdl": v, "timestamp": 1.7e9 + i * 3600,
                                                        "calibration": cal})
        assert c.status_code == 200
        cal = c.json()["calibration"]
    assert cal["n_points"] == 3

    if h["risk_model"]:
        rk = client.post("/v1/risk", json={"age": 55, "height_cm": 170, "weight_kg": 92, "resting_hr_bpm": 80})
        assert rk.status_code == 200
        assert 0 < rk.json()["p_prediabetes_or_diabetes"] < 1
        assert client.post("/v1/risk", json={"age": 55}).status_code == 422


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
