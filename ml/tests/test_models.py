import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from suguard_ml.eval.metrics import clarke_zones, glucose_metrics, iso15197_within
from suguard_ml.models.glucose import GlucoseEstimator, PersonalCalibration
from suguard_ml.models.risk import GlucoseEvidence, RiskInput, RiskModel

ML = Path(__file__).resolve().parents[1]
RISK_JSON = ML / "models" / "risk_model.json"


def test_clarke_known_points():
    ref = np.array([100, 60, 250, 50, 300, 100])
    pred = np.array([110, 65, 60, 200, 200, 230])
    assert list(clarke_zones(ref, pred)) == ["A", "A", "E", "E", "B", "C"]


def test_iso15197_rule():
    assert iso15197_within(np.array([80.0]), np.array([94.0]))[0]       # +14 mg/dL below 100
    assert not iso15197_within(np.array([80.0]), np.array([96.0]))[0]
    assert iso15197_within(np.array([200.0]), np.array([229.0]))[0]     # +14.5 %
    assert not iso15197_within(np.array([200.0]), np.array([231.0]))[0]


def test_glucose_metrics_perfect_and_constant():
    y = np.array([80, 100, 120, 160, 200.0])
    m = glucose_metrics(y, y)
    assert m["mard_pct"] == 0 and m["clarke_pct"]["A"] == 100
    m0 = glucose_metrics(y, np.full(5, y.mean()))
    assert m0["r2"] == pytest.approx(0.0, abs=1e-9)


def test_calibration_learns_offset():
    cal = PersonalCalibration()
    rng = np.random.default_rng(0)
    for i in range(10):
        f = 100 + 20 * rng.standard_normal()
        cal.update(f, f + 25 + rng.normal(0, 3), t=1e9 + i * 3600 * 8)
    y, sd = cal.predict(110.0, t=1e9 + 11 * 3600 * 8)
    assert y == pytest.approx(135, abs=6)
    assert sd < 20
    assert PersonalCalibration.from_dict(cal.to_dict()).a == pytest.approx(cal.a)


def test_estimator_is_honest_without_model():
    est = GlucoseEstimator(model=None)
    assert est.estimate({}, PersonalCalibration())["mg_dl"] is None
    cal = PersonalCalibration()
    for i, v in enumerate([120, 130, 125]):
        cal.update(cal.f0, v, t=1e9 + i * 3600)
    r = est.estimate({}, cal, t=1e9 + 4 * 3600)
    assert r["status"] == "calibration_only" and 110 < r["mg_dl"] < 135
    assert est.estimate({}, cal, sqi=0.1)["status"] == "poor_signal"


@pytest.mark.skipif(not RISK_JSON.exists(), reason="risk model not trained")
def test_risk_model_behaviour():
    m = RiskModel.load(RISK_JSON)
    young = m.predict(RiskInput(age=25, bmi=22, male=False, resting_hr_bpm=65, physically_active=True))
    old = m.predict(RiskInput(age=62, bmi=34, male=True, resting_hr_bpm=85, physically_active=False))
    assert old["p_diabetes"] > young["p_diabetes"]
    assert old["p_prediabetes_or_diabetes"] > young["p_prediabetes_or_diabetes"]
    assert 0 <= young["p_diabetes"] <= young["p_prediabetes_or_diabetes"] <= 1
    # Missing inputs are marginalised, not crashed on.
    mid = m.predict(RiskInput(age=45, height_cm=175, weight_kg=80))
    assert 0 < mid["p_prediabetes_or_diabetes"] < 1
    # Glucose evidence moves the posterior the right way, and only if validated.
    base = RiskInput(age=50, bmi=29)
    hi = m.predict(base, GlucoseEvidence(mean_mgdl=170, error_sd_mgdl=10, days=14))
    lo = m.predict(base, GlucoseEvidence(mean_mgdl=95, error_sd_mgdl=10, days=14))
    assert hi["p_diabetes"] > m.predict(base)["p_diabetes"] > lo["p_diabetes"]
    short = m.predict(base, GlucoseEvidence(mean_mgdl=170, error_sd_mgdl=10, days=2))
    assert not short["glucose_evidence_used"]
    assert m.predict(RiskInput(age=50, bmi=29, diagnosed_diabetes=True))["applicable"] is False


def _run_train(table: Path, out: Path):
    cmd = [sys.executable, str(ML / "scripts" / "train_glucose.py"), "--table", str(table), "--out", str(out),
           "--name", "ctrl"]
    subprocess.run(cmd, check=True, capture_output=True, cwd=ML)
    return json.loads((out / "metrics" / "ctrl_eval.json").read_text())


@pytest.mark.slow
def test_glucose_training_controls(tmp_path):
    sys.path.insert(0, str(ML / "tests"))
    from synthetic_paired import make_table

    make_table(True, n_subjects=8, per_subject=120).to_csv(tmp_path / "pos.csv", index=False)
    make_table(False, n_subjects=8, per_subject=120, seed=1).to_csv(tmp_path / "neg.csv", index=False)
    pos = _run_train(tmp_path / "pos.csv", tmp_path / "pos")
    neg = _run_train(tmp_path / "neg.csv", tmp_path / "neg")
    assert pos["validated"] is True
    assert neg["validated"] is False
    # Leaky random split must look better than the honest subject-wise one.
    assert pos["A_random_rows_LEAKY"]["mard_pct"] <= pos["B_subject_wise"]["model"]["mard_pct"]
    est = GlucoseEstimator.load(tmp_path / "pos")
    assert est.model is not None and est.model.validated
