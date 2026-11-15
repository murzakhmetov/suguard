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


def test_calibration_state_validation():
    good = PersonalCalibration().update(100.0, 110.0, 1.7e9).to_dict()
    assert PersonalCalibration.from_dict(good).n_points == 1
    for bad in ({"a": float("nan")}, {"P": [[1.0, 0.0]]}, {"b": 99.0}, {"P": [[-5.0, 0.0], [0.0, 1.0]]}):
        with pytest.raises(ValueError):
            PersonalCalibration.from_dict({**good, **bad})
    # Unknown keys are ignored; a state fitted for another model version is reset.
    assert PersonalCalibration.from_dict({**good, "foo": 1}).n_points == 1
    assert PersonalCalibration.from_dict(good, model_version="2.0").n_points == 0
    # The clock never runs backwards and NaN times do not poison the state.
    c = PersonalCalibration.from_dict(good).update(100.0, 120.0, 1.6e9)
    assert c.last_t == 1.7e9
    y, sd = c.predict(100.0, float("nan"))
    assert np.isfinite(y) and np.isfinite(sd)


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
    assert r["status"] == "calibration_only" and r["mg_dl"] is None
    assert 110 < r["fingerstick_average_mgdl"] < 135
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
    hi = m.predict(base, GlucoseEvidence(mean_mgdl=170, error_sd_mgdl=10, days=14), glucose_validated=True)
    lo = m.predict(base, GlucoseEvidence(mean_mgdl=95, error_sd_mgdl=10, days=14), glucose_validated=True)
    assert hi["p_diabetes"] > m.predict(base)["p_diabetes"] > lo["p_diabetes"]
    # A healthy mean (~100 mg/dL) must not raise the risk (GMI would read 5.7 %).
    healthy = m.predict(base, GlucoseEvidence(mean_mgdl=100, error_sd_mgdl=5, days=14), glucose_validated=True)
    assert healthy["p_prediabetes_or_diabetes"] < m.predict(base)["p_prediabetes_or_diabetes"]
    short = m.predict(base, GlucoseEvidence(mean_mgdl=170, error_sd_mgdl=10, days=2), glucose_validated=True)
    assert not short["glucose_evidence_used"]
    unvalidated = m.predict(base, GlucoseEvidence(mean_mgdl=250, error_sd_mgdl=10, days=30))
    assert not unvalidated["glucose_evidence_used"] and unvalidated["glucose_evidence_ignored"]
    # Ancestry: same profile, Asian ancestry -> higher risk; unanswered inputs are not "factors".
    asian = m.predict(RiskInput(age=45, bmi=26, ancestry="asian"))
    euro = m.predict(RiskInput(age=45, bmi=26, ancestry="european"))
    assert asian["p_prediabetes_or_diabetes"] > euro["p_prediabetes_or_diabetes"]
    names = {f["factor"] for f in m.predict(RiskInput(age=45, bmi=26))["factors"]}
    assert "resting_hr" not in names and "smoking" not in names
    # Unanswered questions are named: the estimate is then an average over US adults, not this user.
    assert m.predict(RiskInput(age=45, bmi=26))["inputs_averaged_over_reference_population"] == [
        "male", "physically_active", "ancestry"]
    full = RiskInput(age=45, bmi=26, male=True, physically_active=False, ancestry="asian")
    assert m.predict(full)["inputs_averaged_over_reference_population"] == []
    assert m.predict(RiskInput(age=95, bmi=26))["age_clipped"]
    assert m.predict(RiskInput(age=50, bmi=29, diagnosed_diabetes=True))["applicable"] is False


@pytest.mark.parametrize("sd_true,drift", [(20.0, 0.0), (20.0, 6.0), (40.0, 0.0), (40.0, 6.0)])
def test_calibration_interval_coverage(sd_true, drift):
    """Without a population model the filter tracks a person's level from fingersticks alone. Its
    80 % interval has to hold about 80 % of the true values that follow, early (6 fingersticks) and
    late (30), whether the level drifts as the filter assumes or not at all; and the spread it
    learns has to be the person's. (Glucose that scatters by sd_true around the level, a meter with
    5 % error, two fingersticks a day.)"""
    from suguard_ml.models.glucose import GLUCOMETER_CV

    rng = np.random.default_rng(int(sd_true) * 10 + int(drift))
    cover = {6: [], 30: []}
    learnt = []
    for _ in range(250):
        level = rng.normal(110, 20.0)
        cal = PersonalCalibration()
        t = 1.7e9
        for i in range(1, 31):
            t += 43200.0
            level += rng.normal(0, drift / np.sqrt(2.0)) if drift else 0.0
            y = level + rng.normal(0, sd_true)
            cal.update(cal.f0, y * (1 + GLUCOMETER_CV * rng.standard_normal()), t)
            if i in cover:
                est, sd = cal.predict(cal.f0, t + 3600.0)
                new = level + rng.normal(0, sd_true, 20)
                cover[i].append(np.mean(np.abs(new - est) <= 1.2816 * sd))
        learnt.append(np.sqrt(cal.resid_var))
    assert 0.66 <= np.mean(cover[6]) <= 0.93, np.mean(cover[6])
    assert 0.72 <= np.mean(cover[30]) <= 0.88, np.mean(cover[30])
    assert 0.8 * sd_true <= np.median(learnt) <= 1.15 * sd_true, np.median(learnt)


def _run_train(table: Path, out: Path, *extra):
    cmd = [sys.executable, str(ML / "scripts" / "train_glucose.py"), "--table", str(table), "--out", str(out),
           "--name", "ctrl", "--tz-offset-h", "0", "--min-subjects", "10", *extra]
    subprocess.run(cmd, check=True, capture_output=True, cwd=ML)
    return json.loads((out / "metrics" / "ctrl_eval.json").read_text())


@pytest.mark.slow
def test_glucose_training_controls(tmp_path):
    sys.path.insert(0, str(ML / "tests"))
    from synthetic_paired import make_table

    make_table(True, n_subjects=15, per_subject=120).to_csv(tmp_path / "pos.csv", index=False)
    make_table(False, n_subjects=15, per_subject=120, seed=1).to_csv(tmp_path / "neg.csv", index=False)
    pos = _run_train(tmp_path / "pos.csv", tmp_path / "pos")
    neg = _run_train(tmp_path / "neg.csv", tmp_path / "neg")
    # Synthetic tables are not bracelet data, so neither may be "validated" ...
    assert pos["validated"] is False and neg["validated"] is False
    assert any("SuGuard bracelet" in r for r in pos["not_validated_because"])
    # ... but only the positive control passes every evidence criterion.
    assert pos["not_validated_because"] == [r for r in pos["not_validated_because"] if "SuGuard bracelet" in r]
    assert len(neg["not_validated_because"]) > 1
    assert pos["C_personalised"]["n_subjects"] == 12 and pos["C_personalised"]["subjects_not_scored"] == []
    assert pos["holdout"]["personalised"]["n_subjects"] == 3 and pos["holdout"]["gain_vs_best_non_ppg_baseline"] > 0
    # Leaky random split must look better than the honest subject-wise one.
    assert pos["A_random_rows_LEAKY"]["mard_pct"] <= pos["B_subject_wise"]["model"]["mard_pct"]
    est = GlucoseEstimator.load(tmp_path / "pos")
    assert est.model is not None and not est.model.validated   # experimental on this device
    assert est.model.version.startswith("1.0.0+") and len(est.model.version) == 18   # unique per trained model


@pytest.mark.slow
def test_glucose_gate_fails_closed(tmp_path):
    """Regression (review findings): tables labelled as bracelet data that must
    still not come out validated."""
    sys.path.insert(0, str(ML / "tests"))
    from synthetic_paired import make_table

    dev = "suguard_max30102"
    # The same strong signal, labelled as bracelet data: this one is validated ...
    make_table(True, n_subjects=15, per_subject=120, source=dev).to_csv(tmp_path / "ok.csv", index=False)
    ok = _run_train(tmp_path / "ok.csv", tmp_path / "ok")
    assert ok["validated"] is True and ok["not_validated_because"] == []
    assert GlucoseEstimator.load(tmp_path / "ok").model.validated
    # ... but not if most people have no readings at the fingerstick times (the gain was then
    # "shown" on a handful of people while --min-subjects counted everybody in the table),
    thin = make_table(True, n_subjects=15, per_subject=60, scheduled=False, source=dev)
    thin.to_csv(tmp_path / "thin.csv", index=False)
    r = _run_train(tmp_path / "thin.csv", tmp_path / "thin")
    assert r["validated"] is False and any("could score only" in x for x in r["not_validated_because"])
    assert len(r["C_personalised"]["subjects_not_scored"]) >= 3
    # ... and not if the table has no PPG features at all (the two controls used to be skipped).
    make_table(True, n_subjects=15, per_subject=120, ppg=False, source=dev).to_csv(tmp_path / "ctx.csv", index=False)
    r = _run_train(tmp_path / "ctx.csv", tmp_path / "ctx")
    assert r["validated"] is False and "the table has no PPG features" in r["not_validated_because"]
    assert not GlucoseEstimator.load(tmp_path / "ctx").model.validated


def test_table_time_base(tmp_path):
    """Regression (review findings): the local clock of a table comes from the
    table, so hour features and the fingerstick schedule cannot run on UTC by
    accident."""
    import pandas as pd

    from suguard_ml.data.paired import load_paired

    sys.path.insert(0, str(ML / "scripts"))
    from train_glucose import calibration_times

    def hours(df):
        return (np.degrees(np.arctan2(df.hour_sin, df.hour_cos)) % 360) / 15.0

    base = {"subject_id": ["a"] * 3, "glucose_mgdl": [100.0, 110.0, 120.0], "f1": [0.1, 0.2, 0.3]}
    # Offsets written in the timestamps (what the PC recorder writes): used as they are.
    pd.DataFrame({**base, "timestamp": ["2026-11-14T08:05:00+05:00", "2026-11-14T09:05:00+0500",
                                        "2026-11-14T05:05:00Z"]}).to_csv(tmp_path / "aware.csv", index=False)
    df = load_paired(tmp_path / "aware.csv")
    assert sorted(df.meta_tz_offset_h) == [0.0, 5.0, 5.0]
    assert sorted(np.round(hours(df), 2)) == pytest.approx([5.08, 8.08, 9.08], abs=0.01)
    assert df.t.min() == pytest.approx(1794625500.0)                    # 03:05 UTC
    # Unix seconds: the offset must come from the table or from the caller.
    t = [1794625500.0, 1794629100.0, 1794632700.0]
    pd.DataFrame({**base, "timestamp": t}).to_csv(tmp_path / "unix.csv", index=False)
    with pytest.raises(ValueError, match="tz_offset_h"):
        load_paired(tmp_path / "unix.csv")
    assert np.round(hours(load_paired(tmp_path / "unix.csv", tz_offset_h=5)), 2).tolist() == [8.08, 9.08, 10.08]
    pd.DataFrame({**base, "t": t, "timestamp": t, "meta_tz_offset_h": 5.0}).to_csv(tmp_path / "own.csv", index=False)
    assert np.round(hours(load_paired(tmp_path / "own.csv")), 2).tolist() == [8.08, 9.08, 10.08]
    assert load_paired(tmp_path / "own.csv", tz_offset_h=0).meta_tz_offset_h.tolist() == [5.0] * 3   # the table wins
    # Naive wall-clock strings without an offset are the wall clock itself (as in BIG IDEAs).
    pd.DataFrame({**base, "timestamp": ["2026-11-14 08:05:00", "2026-11-14 09:05:00", "2026-11-14 10:05:00"]}).to_csv(
        tmp_path / "naive.csv", index=False)
    assert np.round(hours(load_paired(tmp_path / "naive.csv")), 2).tolist() == [8.08, 9.08, 10.08]
    # The fingerstick schedule (07:30 and 19:30) follows the local clock of each row.
    day0 = 1794614400.0                                                  # 2026-11-14 00:00 UTC
    t = day0 + 900.0 * np.arange(4 * 96)                                 # a reading every 15 min for 4 days
    picked = calibration_times(t, per_day=2, days=3.0, tz_offset_h=np.full(t.size, 5.0))
    local_hour = ((t[picked] + 5 * 3600) % 86400) / 3600
    assert set(np.round(local_hour, 2)) == {7.5, 19.5} and picked.size == 6
