import numpy as np
import pytest

from suguard_ml.config import FS
from suguard_ml.signal.beats import detect_beats, spectral_hr
from suguard_ml.signal.features import extract_features
from suguard_ml.signal.filters import blood_volume, preprocess, resample
from suguard_ml.signal.quality import sensor_state
from suguard_ml.signal.spo2 import estimate_spo2, fit_spo2_calibration, spo2_from_ratio
from suguard_ml.synth.ppg import r_from_spo2, simulate_window, spo2_from_r


def test_resample_keeps_tone():
    fs_in = 100.0
    t = np.arange(0, 10, 1 / fs_in)
    x = 1e5 + 100 * np.sin(2 * np.pi * 1.2 * t)
    y = resample(x, fs_in, FS)
    assert y.size == pytest.approx(x.size * FS / fs_in, abs=1)
    f = np.fft.rfftfreq(y.size, 1 / FS)[np.argmax(np.abs(np.fft.rfft(y - y.mean())))]
    assert f == pytest.approx(1.2, abs=0.11)


def test_blood_volume_is_inverted_and_normalised():
    t = np.arange(0, 10, 1 / FS)
    pulse = 0.01 * np.sin(2 * np.pi * t)            # 1 % blood-volume modulation
    raw = 100_000 * (1 - pulse)                     # more blood -> fewer counts
    bv, dc = blood_volume(raw, FS)
    core = slice(100, -100)
    assert np.corrcoef(bv[core], pulse[core])[0, 1] > 0.99
    assert np.ptp(bv[core]) == pytest.approx(0.02, rel=0.1)


def test_spo2_curve_inverse():
    for s in (88.0, 92.0, 95.0, 98.0):
        assert spo2_from_r(r_from_spo2(s)) == pytest.approx(s, abs=1e-6)
    assert spo2_from_ratio(None) is None


@pytest.mark.parametrize("seed", range(8))
def test_clean_window_hr_and_spo2(seed):
    w = simulate_window(seed, kinds=[])
    ir, _ = preprocess(w.ir_raw, w.fs)
    red, _ = preprocess(w.red_raw, w.fs)
    beats = detect_beats(ir, w.fs)
    assert beats.hr_bpm == pytest.approx(w.hr_bpm, abs=4)
    hr_s, purity = spectral_hr(ir, w.fs)
    assert hr_s == pytest.approx(w.hr_bpm, abs=6)
    sp = estimate_spo2(red, ir)
    assert sp.r_ratio == pytest.approx(w.r_ratio, abs=0.05)


def test_sensor_state_flags_no_contact_and_saturation():
    n = 512
    off = sensor_state(np.full(n, 500.0), np.full(n, 800.0))
    assert not off.finger_detected and "no_contact" in off.reasons
    sat = sensor_state(np.full(n, 262_143.0), np.full(n, 262_143.0))
    assert "adc_saturated" in sat.reasons


def test_features_on_clean_window():
    w = simulate_window(3, kinds=[])
    ir, dci = preprocess(w.ir_raw, w.fs)
    red, dcr = preprocess(w.red_raw, w.fs)
    f = extract_features(ir, red, w.fs, ir_dc=float(np.median(dci)), red_dc=float(np.median(dcr)))
    assert f["hr_bpm"] == pytest.approx(w.hr_bpm, abs=4)
    assert f["r_ratio"] == pytest.approx(w.r_ratio, abs=0.05)
    for k in ("crest_time_ratio", "width50_ratio", "ipa", "h2_h1", "r_h1"):
        assert k in f


def test_spo2_calibration_fit():
    r = np.linspace(0.4, 1.0, 20)
    y = 110 - 25 * r
    a, b, c = fit_spo2_calibration(r, y, quadratic=False)
    assert (a, b, c) == pytest.approx((0.0, -25.0, 110.0), abs=1e-6)


def test_tls_ratio_is_not_biased_by_noise():
    """OLS of red on noisy IR reads R low (SpO2 high); TLS must not."""
    from suguard_ml.signal.spo2 import ratio_of_ratios

    rng = np.random.default_rng(1)
    t = np.arange(0, 10.24, 1 / FS)
    pulse = 0.001 * np.sin(2 * np.pi * 1.2 * t)   # weak pulse, 0.1 % PI
    r_true = 0.9
    est = []
    for _ in range(30):
        ir = pulse + rng.normal(0, 0.0004, t.size)
        red = r_true * pulse + rng.normal(0, 0.0004, t.size)
        est.append(ratio_of_ratios(red, ir)[0])
    assert np.mean(est) == pytest.approx(r_true, abs=0.05)


def test_hrv_ignores_removed_ectopic_intervals():
    from suguard_ml.signal.beats import hrv_metrics

    ibi = np.full(40, 0.8)
    ibi[20], ibi[21] = 0.5, 1.1                      # ectopic beat + compensatory pause
    valid = np.ones(40, dtype=bool)
    valid[20] = False                                # the premature interval is rejected
    h = hrv_metrics(ibi, valid)
    assert h["rmssd_ms"] == pytest.approx(0.0, abs=1e-9) and h["pnn50"] == 0.0


def test_hrv_edits_premature_beats_the_detector_accepts():
    """Regression (review finding): a premature beat within +-30 % of the
    median interval is 'valid' for the beat detector and used to multiply
    RMSSD; it is recognised by its short-long pattern."""
    from suguard_ml.signal.beats import hrv_metrics

    rng = np.random.default_rng(4)
    for coupling in (0.72, 0.78, 0.84):
        ratios = []
        for _ in range(40):
            ibi = 0.83 + rng.normal(0, 0.013 / np.sqrt(2), 140)          # quiet sinus rhythm, RMSSD ~13 ms
            clean = hrv_metrics(ibi)["rmssd_ms"]
            for i in (20, 55, 90, 120):                                  # premature beat + compensatory pause
                ibi[i], ibi[i + 1] = coupling * ibi[i], (2 - coupling) * ibi[i]
            valid = np.abs(ibi - np.median(ibi)) <= 0.3 * np.median(ibi)   # what detect_beats calls valid
            h = hrv_metrics(ibi, valid)
            assert h["excluded_intervals"] >= 8
            ratios.append(h["rmssd_ms"] / clean)
        assert 0.9 < np.median(ratios) < 1.1 and max(ratios) < 1.3, (coupling, np.median(ratios), max(ratios))
    # Normal rhythm is left alone, also with strong respiratory arrhythmia.
    excluded = []
    for k in range(60):
        n = np.arange(140)
        ibi = (0.9 + rng.normal(0, 0.02, 140) + 0.06 * np.sin(2 * np.pi * n / (3.0 + k % 3))
               + 0.03 * np.sin(2 * np.pi * n / 12.0))
        excluded.append(hrv_metrics(ibi)["excluded_intervals"])
    assert np.mean(excluded) < 0.5


def test_spo2_rejects_out_of_range_ratio():
    assert spo2_from_ratio(2.0) is None and spo2_from_ratio(0.1) is None
    assert spo2_from_ratio(0.3) == pytest.approx(spo2_from_ratio(0.34), abs=0.1)   # vertex, ~100 %


def test_notch_features_nan_without_inflection():
    from suguard_ml.signal.features import N_T, template_features

    x = np.linspace(0, 1, N_T)
    rng = np.random.default_rng(0)
    for tau in (0.15, 0.25, 0.4):
        tmpl = np.where(x < 0.2, x / 0.2, np.exp(-(x - 0.2) / tau))   # monotone decay: no notch
        f = template_features(tmpl, 0.8)
        assert f["notch_present"] == 0.0 and np.isnan(f["notch_height"]) and np.isnan(f["ipa"])
        # Regression (review finding): ripple from noise is not a notch either.
        defined = 0
        for _ in range(200):
            noisy = tmpl + rng.normal(0, 0.002, N_T)
            defined += np.isfinite(template_features(noisy, 0.8, stderr=0.002)["notch_time_ratio"])
        assert defined <= 10, (tau, defined)                  # was 200 of 200
    # A real notch is found where it is, with the same noise.
    notched = tmpl + 0.25 * np.exp(-0.5 * ((x - 0.55) / 0.07) ** 2)
    i_true = 20 + int(np.argmin(notched[20:55]))
    hits = 0
    for _ in range(200):
        f = template_features(notched + rng.normal(0, 0.002, N_T), 0.8, stderr=0.002)
        hits += f["notch_present"] == 1.0 and abs(f["notch_time_ratio"] - i_true / N_T) <= 0.03
    assert hits >= 190


def test_like_for_like_comparison_is_per_vital():
    """Regression (review finding): SpO2 of two methods was compared on
    different windows under the name 'common'."""
    from suguard_ml.eval.vitals_eval import both_finite, summarize_errors

    a = [{"hr": 70.0, "spo2": 97.0}, {"hr": None, "spo2": None}, {"hr": 80.0, "spo2": None}, {"hr": 60.0, "spo2": 95.0}]
    b = [{"hr": 71.0, "spo2": None}, {"hr": 75.0, "spo2": 96.0}, {"hr": 82.0, "spo2": 98.0}, {"hr": 61.0, "spo2": 94.0}]
    hr_true, spo2_true = np.array([70.0, 75.0, 80.0, 60.0]), np.array([97.0, 96.0, 97.0, 95.0])
    common = both_finite(a, b)
    ra, rb = (summarize_errors(rows, hr_true, spo2_true, common=common) for rows in (a, b))
    for vital, n in (("hr", 3), ("spo2", 1)):
        assert ra[vital]["n"] == rb[vital]["n"] == ra[vital]["n_scored"] == rb[vital]["n_scored"] == n
    assert ra["spo2"]["mae"] == 0.0 and rb["spo2"]["mae"] == 1.0
    assert summarize_errors(a, hr_true, spo2_true)["spo2"] == {
        "n": 4, "n_scored": 2, "abstain_rate": 0.5, "mae": 0.0, "median": 0.0, "p90": 0.0,
        "within_tol_counting_abstentions": 0.5}
