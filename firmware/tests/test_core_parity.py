"""The portable C++ signal core (firmware/suguard/src/core) against its Python
reference (ml/suguard_ml).

tests/host/core_cli.cpp is compiled with the host g++ and fed the same raw
windows as the reference: decisions (booleans, reason masks, counts) must be
identical, numbers must agree to the precision of the arithmetic that
produced them. The same program, cross-built for RV32IMC and run under QEMU,
must reproduce the host results (test marked ``rv32``; it is skipped when the
cross toolchain or QEMU is not installed).

    python -m pytest tests/test_core_parity.py -q -s      # -s prints the largest errors
"""
from __future__ import annotations

import math
import os
import shutil
import subprocess
import sys
import warnings
from dataclasses import dataclass

import numpy as np
import pytest
from scipy import ndimage, signal

from conftest import CORE, FW, ML, build_host

from suguard_ml.config import ADC_MAX, FINGER_IR_DC_MIN, FS, WINDOW  # noqa: E402
from suguard_ml.pipeline import vitals_from_signals  # noqa: E402
from suguard_ml.signal import filters  # noqa: E402
from suguard_ml.signal.filters import preprocess  # noqa: E402
from suguard_ml.signal.quality import _ramp, _ramp_down, sensor_state  # noqa: E402
from suguard_ml.synth.ppg import simulate_window  # noqa: E402

sys.path.insert(0, str(FW / "tools"))
import gen_tables  # noqa: E402

SOURCES = [CORE / "sg_dsp.cpp", CORE / "sg_vitals.cpp", FW / "tests" / "host" / "core_cli.cpp"]
# No fused multiply-add (bit-exact doubles on any host CPU) and the core's stack budget per function.
HOST_FLAGS = ["-ffp-contract=off", "-Wstack-usage=1024"]
DENOISER = ML / "models" / "denoiser.onnx"

with warnings.catch_warnings():  # the marker is not registered in conftest.py
    warnings.simplefilter("ignore", pytest.PytestUnknownMarkWarning)
    rv32 = pytest.mark.rv32

# sg_core.h: SgReason bits, SgSpo2Reason.
REASON_BITS = {"no_contact": 0, "adc_saturated": 1, "led_current_too_high": 2, "weak_pulse": 3,
               "implausible_amplitude": 4, "motion": 5, "irregular_or_noisy": 6, "red_ir_inconsistent": 7,
               "denoiser_mismatch": 8}
SPO2_REASONS = {None: 0, "no_common_pulse": 1, "spo2_low_red_ir_agreement": 2, "r_out_of_calibration_range": 3,
                "red_denoiser_mismatch": 4, "red_ir_inconsistent": 5}

# Outputs of core_cli by the precision they must reach.
EXACT = ["n", "finger_detected", "sensor_reasons", "reliable", "reasons", "has_hr", "n_beats", "n_valid_ibi",
         "has_spo2", "has_r", "spo2_reason", "spo2_withheld", "q_usable", "q_usable_spo2", "q_reasons"]
# Double-precision arithmetic in the same order as numpy/scipy: 1e-9 relative.
TIGHT = ["saturated_fraction", "ir_dc", "red_dc", "pi_in", "hr_bpm", "spo2", "r_ratio", "q_perfusion_index",
         "q_template_corr", "q_red_ir_corr", "q_beat_amp_cv", "q_valid_ibi_fraction", "q_r_spread",
         "q_motion_fraction", "q_comp_perfusion", "q_comp_template", "q_comp_amplitude", "q_comp_rhythm",
         "q_comp_r_stability", "q_comp_red_ir", "q_comp_motion", "support_ir_corr", "support_ir_gain",
         "support_red_corr", "support_red_gain"]
# Downstream of the single-precision FFT: 1e-4 absolute.
SPECTRAL = ["q_spectral_purity", "q_hr_agreement_bpm", "q_comp_purity", "q_comp_hr_agreement", "q_sqi"]
TIGHT_REL, SPECTRAL_ABS, BV_ABS = 1e-9, 1e-4, 1e-12
NFFT = gen_tables.NFFT

# core_cli.cpp: DspOp, and its filter numbers (the order of the tables).
DSP_OPS = {name: i for i, name in enumerate(["sum", "std", "median", "percentile", "arg", "interp", "uniform",
                                             "hann", "peaks", "fft", "filtfilt"])}
FILTERS = [(kind, cutoff, order) for _, kind, cutoff, order, _ in gen_tables.FILTERS]


@dataclass
class Case:
    name: str
    red: np.ndarray                 # raw counts
    ir: np.ndarray
    denoised: tuple | None = None   # (c_ir, c_red, p_art) as a denoiser would return them for this window


# --------------------------------------------------------------------------
# Python reference
# --------------------------------------------------------------------------

def reason_mask(reasons) -> int:
    return sum(1 << REASON_BITS[r] for r in set(reasons))


def unrounded_components(q) -> dict:
    """Quality.components is rounded to 3 decimals; recompute the exact values
    with the expressions of assess_quality() and check them against it."""
    pi = q.perfusion_index
    comp = {
        "perfusion": _ramp(pi, 0.03, 0.12) * (1.0 - _ramp(pi, 10.0, 20.0)),
        "template": _ramp(q.template_corr, 0.5, 0.9),
        "purity": _ramp(q.spectral_purity, 0.15, 0.5),
        "amplitude": _ramp_down(q.beat_amp_cv, 0.2, 0.4),
        "rhythm": _ramp(q.valid_ibi_fraction, 0.85, 0.95),
        "hr_agreement": _ramp_down(q.hr_agreement_bpm, 5.0, 15.0),
        "r_stability": _ramp_down(q.r_spread, 0.08, 0.25),
        "red_ir": _ramp(q.red_ir_corr, 0.5, 0.8),
        "motion": 1.0 - q.motion_fraction,
    }
    assert {k: round(v, 3) for k, v in comp.items()} == q.components, "assess_quality() changed its components"
    return comp


def reference(case: Case) -> dict:
    """The Python pipeline on one case, keyed like the outputs of core_cli.
    None becomes NaN next to a false has_* flag."""
    def num(v):
        return math.nan if v is None else float(v)

    with warnings.catch_warnings(), np.errstate(all="ignore"):
        warnings.simplefilter("ignore")           # degenerate windows make numpy complain
        sensor = sensor_state(case.red, case.ir)
        ir_bv, _ = preprocess(case.ir, FS)
        red_bv, _ = preprocess(case.red, FS)
        v = vitals_from_signals(ir_bv, red_bv, sensor, *(case.denoised or ()))
    q = v.quality
    assert v.spo2_ok == (v.spo2 is not None) and (v.hr_bpm is not None or not v.reliable)
    assert (v.support_ir is None) == (v.support_red is None) == (case.denoised is None)
    support = [x for s in (v.support_ir, v.support_red) for x in ((s.corr, s.gain) if s else (math.nan, math.nan))]
    out = dict(
        n=case.ir.size, finger_detected=sensor.finger_detected, saturated_fraction=sensor.saturated_fraction,
        ir_dc=sensor.ir_dc, red_dc=sensor.red_dc, sensor_reasons=reason_mask(sensor.reasons), pi_in=v.pi_in,
        reliable=v.reliable, reasons=reason_mask(v.reasons), has_hr=v.hr_bpm is not None, hr_bpm=num(v.hr_bpm),
        n_beats=v.beats.peaks.size, n_valid_ibi=int(v.beats.valid_ibi.sum()),
        has_spo2=v.spo2_ok, spo2=num(v.spo2), has_r=v.sp.r_ratio is not None,
        r_ratio=num(v.sp.r_ratio), spo2_reason=SPO2_REASONS[v.sp.reason], spo2_withheld=SPO2_REASONS[v.spo2_reason],
        support_ir_corr=support[0], support_ir_gain=support[1], support_red_corr=support[2],
        support_red_gain=support[3], denoised=case.denoised is not None,
        q_perfusion_index=q.perfusion_index, q_template_corr=q.template_corr, q_spectral_purity=q.spectral_purity,
        q_red_ir_corr=q.red_ir_corr, q_beat_amp_cv=q.beat_amp_cv, q_valid_ibi_fraction=q.valid_ibi_fraction,
        q_hr_agreement_bpm=q.hr_agreement_bpm, q_r_spread=q.r_spread, q_motion_fraction=q.motion_fraction,
        q_sqi=q.sqi, q_usable=q.usable, q_usable_spo2=q.usable_spo2, q_reasons=reason_mask(q.reasons),
        ir_bv=ir_bv, red_bv=red_bv,
    )
    out.update({f"q_comp_{k}": val for k, val in unrounded_components(q).items()})
    return out


# --------------------------------------------------------------------------
# Test vectors
# --------------------------------------------------------------------------

def classical_cases(count=300, seed0=7_000_000) -> list[Case]:
    cases = []
    for i in range(count):
        win = simulate_window(seed0 + i)
        cases.append(Case(f"classical[{seed0 + i}]", win.red_raw, win.ir_raw))
    return cases


def denoised_cases(count=200, seed0=7_100_000) -> list[Case]:
    from suguard_ml.models.denoiser import Denoiser

    denoiser = Denoiser(DENOISER)
    cases = []
    for i in range(count):
        win = simulate_window(seed0 + i)
        dn = denoiser.denoise_bv(preprocess(win.ir_raw, FS)[0], preprocess(win.red_raw, FS)[0], FS)
        signals = tuple(np.asarray(a, dtype=np.float64) for a in (dn.ir_bv, dn.red_bv, dn.artifact_prob))
        cases.append(Case(f"denoised[{seed0 + i}]", win.red_raw, win.ir_raw, denoised=signals))
    return cases


def denoiser_available() -> bool:
    try:
        import onnxruntime  # noqa: F401
    except ImportError:
        return False
    return DENOISER.exists()


def edge_cases() -> list[Case]:
    rng = np.random.default_rng(2026)
    n = WINDOW
    clean = simulate_window(7_200_000, kinds=[], pi_ir=0.02, hr_bpm=72.0)
    t = np.arange(n) / FS
    beat = np.sin(2 * np.pi * 1.2 * t)

    def counts(x):
        return np.clip(np.round(x), 0, ADC_MAX)

    def as_denoised(win, p_art):
        return preprocess(win.ir_raw, FS)[0], preprocess(win.red_raw, FS)[0], np.asarray(p_art, dtype=np.float64)

    def with_signals(name, c_ir, c_red):
        """A clean raw window whose vitals are computed from the given signals."""
        return Case(name, clean.red_raw, clean.ir_raw, denoised=(c_ir, c_red, np.zeros(n)))

    def tone(hz):
        return np.sin(2 * np.pi * hz * t)

    def with_signals_flagged(name, c_ir, c_red):
        """As with_signals, but 30 % of the window flagged: the denoised spectrum is the reference."""
        return Case(name, clean.red_raw, clean.ir_raw, denoised=(c_ir, c_red, np.where(t < 0.3 * t[-1], 1.0, 0.0)))

    def flagged_share(k):
        p = np.zeros(n)
        p[:k] = 0.9
        return p

    half_rate = tone(1.8) + 0.35 * tone(0.9)          # a pulse and arm swing at half its rate
    ir_bv, red_bv, _ = as_denoised(clean, np.zeros(n))
    doublet = np.zeros(n)             # +1, -1: its spectrum rises monotonically through the cardiac band
    doublet[255:257] = 1.0, -1.0
    cases = [
        Case("no_contact", counts(800 + 15 * rng.standard_normal(n)), counts(1000 + 20 * rng.standard_normal(n))),
        Case("red_no_contact", counts(2_000 * (1 - 0.006 * beat)), clean.ir_raw),
        Case("ir_saturated", clean.red_raw, np.full(n, float(ADC_MAX))),
        Case("ir_partly_saturated", clean.red_raw, np.where((t > 3) & (t < 5), float(ADC_MAX), clean.ir_raw)),
        Case("led_current_too_high", counts(150_000 * (1 - 0.006 * beat)), counts(245_000 * (1 - 0.01 * beat))),
        Case("constant", np.full(n, 80_000.0), np.full(n, 100_000.0)),
        Case("constant_fractional", np.full(n, 80_000.3), np.full(n, 100_000.7)),
        Case("gaussian_noise", counts(80_000 + 250 * rng.standard_normal(n)),
             counts(100_000 + 300 * rng.standard_normal(n))),
        Case("single_spike", clean.red_raw, np.where(np.arange(n) == 200, clean.ir_raw + 100_000.0, clean.ir_raw)),
        Case("spike_both_channels", np.where(np.arange(n) == 300, 0.0, clean.red_raw),
             np.where(np.arange(n) == 300, 0.0, clean.ir_raw)),
        Case("huge_pulse", counts(90_000 * (1 - 0.2 * beat)), counts(100_000 * (1 - 0.3 * beat))),
        Case("square_wave", counts(80_000 - 300 * np.sign(beat)), counts(100_000 - 500 * np.sign(beat))),
        Case("all_zeros", np.zeros(n), np.zeros(n)),
        Case("all_zeros_denoised", np.zeros(n), np.zeros(n), denoised=(np.zeros(n), np.zeros(n), np.zeros(n))),
        Case("clean_but_zero_signals", clean.red_raw, clean.ir_raw,
             denoised=(np.zeros(n), np.zeros(n), np.zeros(n))),
        Case("artifact_prob_ones", clean.red_raw, clean.ir_raw, denoised=as_denoised(clean, np.ones(n))),
        Case("artifact_prob_zeros", clean.red_raw, clean.ir_raw, denoised=as_denoised(clean, np.zeros(n))),
        Case("artifact_prob_out_of_range", clean.red_raw, clean.ir_raw,
             denoised=as_denoised(clean, rng.uniform(-0.5, 1.5, n))),
        Case("artifact_prob_few_clean_samples", clean.red_raw, clean.ir_raw,
             denoised=as_denoised(clean, np.where(np.arange(n) < 9, 0.0, 1.0))),
        with_signals("constant_signals", np.full(n, 0.5), np.full(n, 0.25)),
        with_signals("tone_above_cardiac_band", 0.01 * tone(5.0), 0.006 * tone(5.0)),
        with_signals("tone_at_cardiac_band_edge", 0.01 * tone(4.0), 0.006 * tone(4.0)),
        with_signals("tone_below_cardiac_band", 0.01 * tone(0.3), 0.006 * tone(0.3)),
        with_signals("spectrum_without_peak", doublet, 0.6 * doublet),
        with_signals("red_signal_zero", ir_bv, np.zeros(n)),
        with_signals("red_signal_not_finite", ir_bv, np.where(np.arange(n) == 100, np.nan, red_bv)),
        with_signals("r_below_plausible_range", ir_bv, 0.1 * ir_bv),
        with_signals("r_below_curve_vertex", ir_bv, 0.3 * ir_bv),
        # pipeline.CLEAN_MAX_MOTION: 102 of 512 samples flagged is clean, 103 is not.
        Case("flagged_at_clean_limit", clean.red_raw, clean.ir_raw, denoised=as_denoised(clean, flagged_share(102))),
        Case("flagged_just_above_clean_limit", clean.red_raw, clean.ir_raw,
             denoised=as_denoised(clean, flagged_share(103))),
        # Clean window, denoised beats at twice the measured rate: the measured spectrum disagrees.
        with_signals("denoised_at_twice_the_measured_rate", 0.01 * tone(2.4), 0.006 * tone(2.4)),
        with_signals_flagged("flagged_denoised_at_twice_the_rate", 0.01 * tone(2.4), 0.006 * tone(2.4)),
        # A component at half the pulse rate must not win the harmonic sum.
        with_signals_flagged("flagged_pulse_with_half_rate_component", 0.01 * half_rate, 0.006 * half_rate),
        Case("classical_pulse_with_half_rate_motion", counts(70_000 * (1 - 0.003 * tone(1.8)) * (1 + 0.001 * tone(0.9))),
             counts(100_000 * (1 - 0.005 * tone(1.8)) * (1 + 0.00175 * tone(0.9)))),
    ]
    for length in (100, 256, 400):
        for seed, kinds in ((7_300_000, []), (7_300_001, None)):
            win = simulate_window(seed + length, n=length, kinds=kinds)
            cases.append(Case(f"n={length}[{'clean' if kinds == [] else 'mixed'}]", win.red_raw, win.ir_raw))
        win = simulate_window(7_300_002 + length, n=length)
        cases.append(Case(f"n={length}[weights]", win.red_raw, win.ir_raw,
                          denoised=as_denoised(win, rng.uniform(0, 1, length))))
    return cases


# --------------------------------------------------------------------------
# Running the C++ core and comparing
# --------------------------------------------------------------------------

def write_vectors(path, cases):
    parts = [[len(cases)]]
    for case in cases:
        parts.append([case.ir.size, 0 if case.denoised is None else 1, FINGER_IR_DC_MIN])
        parts += [case.red, case.ir, *(case.denoised or ())]
    np.concatenate([np.asarray(p, dtype="<f8").ravel() for p in parts]).tofile(path)


def read_results(path, names):
    """-> (one dict per case, sg_work_size())."""
    data = np.fromfile(path, dtype="<f8")
    n_cases, n_fields, work_size = (int(v) for v in data[:3])
    assert n_fields == len(names)
    pos, results = 3, []
    for _ in range(n_cases):
        rec = dict(zip(names, data[pos:pos + n_fields].tolist()))
        pos += n_fields
        n = int(rec["n"])
        rec["ir_bv"], rec["red_bv"] = data[pos:pos + n], data[pos + n:pos + 2 * n]
        pos += 2 * n
        results.append(rec)
    assert pos == data.size, "truncated result file"
    return results, work_size


def write_dsp_calls(path, calls):
    parts = []
    for _, op, a, b, param, _, _ in calls:
        parts += [[op, a.size, b.size, param], a, b]
    np.concatenate([np.asarray(p, dtype="<f8").ravel() for p in parts]).tofile(path)


def read_dsp_results(path, n_calls):
    data = np.fromfile(path, dtype="<f8")
    pos, results = 0, []
    for _ in range(n_calls):
        count = int(data[pos])
        results.append(data[pos + 1:pos + 1 + count])
        pos += 1 + count
    assert pos == data.size, "truncated result file"
    return results


@pytest.fixture(scope="module")
def cli(build_dir):
    """core_cli built for the host and the names of its scalar outputs."""
    exe = build_host(SOURCES, build_dir / "core_cli", extra=HOST_FLAGS)
    names = subprocess.run([str(exe), "--fields"], check=True, capture_output=True, text=True).stdout.split()
    assert sorted(names) == sorted(EXACT + TIGHT + SPECTRAL)
    return exe, names


def run_host(cli, build_dir, tag, cases):
    exe, names = cli
    fin, fout = build_dir / f"core_{tag}_in.bin", build_dir / f"core_{tag}_out.bin"
    write_vectors(fin, cases)
    subprocess.run([str(exe), str(fin), str(fout)], check=True, capture_output=True, timeout=600)
    return read_results(fout, names)


def rel_err(a, b):
    """Relative difference; 0 for equal values (including equal infinities and two NaNs)."""
    if a == b or (math.isnan(a) and math.isnan(b)):
        return 0.0
    if not (math.isfinite(a) and math.isfinite(b)):
        return math.inf
    return abs(a - b) / max(abs(a), abs(b))


def abs_err(a, b):
    return 0.0 if a == b or (math.isnan(a) and math.isnan(b)) else abs(a - b)


def compare(cases, results, label):
    """Checks every case against the reference; returns the largest error per field group."""
    assert len(results) == len(cases)
    problems = []
    worst = {"bv": (0.0, ""), "tight": (0.0, ""), "spectral": (0.0, "")}

    def track(group, err, what):
        if err > worst[group][0]:
            worst[group] = (err, what)

    for case, got in zip(cases, results):
        ref = reference(case)
        for key in EXACT:
            if got[key] != ref[key]:
                problems.append(f"{case.name}: {key} = {got[key]:g}, reference {ref[key]}")
        for key in ("ir_bv", "red_bv"):
            err = float(np.max(np.abs(got[key] - ref[key])))
            track("bv", err, f"{case.name} {key}")
            if not err <= BV_ABS:
                problems.append(f"{case.name}: {key} differs by {err:.3g}")
        # Values that are None in Python are compared through their has_* flag only.
        skip = {"hr_bpm": not ref["has_hr"], "spo2": not ref["has_spo2"], "r_ratio": not ref["has_r"]}
        skip.update({f"support_{ch}_{what}": not ref["denoised"] for ch in ("ir", "red") for what in ("corr", "gain")})
        for key in TIGHT:
            if skip.get(key):
                continue
            err = rel_err(got[key], ref[key])
            track("tight", err, f"{case.name} {key}")
            if not err <= TIGHT_REL:
                problems.append(f"{case.name}: {key} = {got[key]!r}, reference {ref[key]!r}")
        for key in SPECTRAL:
            if skip.get(key):
                continue
            err = abs_err(got[key], ref[key])
            track("spectral", err, f"{case.name} {key}")
            if not err <= SPECTRAL_ABS:
                problems.append(f"{case.name}: {key} = {got[key]!r}, reference {ref[key]!r}")
        if not ref["denoised"] and any(got[f"support_{ch}_{what}"] for ch in ("ir", "red") for what in ("corr", "gain")):
            problems.append(f"{case.name}: input support reported on the classical path")
    print(f"\n{label}: {len(cases)} windows; max |preprocess diff| {worst['bv'][0]:.3g} ({worst['bv'][1]}); "
          f"max rel. error of double-precision outputs {worst['tight'][0]:.3g} ({worst['tight'][1]}); "
          f"max abs. error of FFT-dependent outputs {worst['spectral'][0]:.3g} ({worst['spectral'][1]})")
    assert not problems, f"{len(problems)} mismatches, first ones:\n" + "\n".join(problems[:25])
    return worst


# --------------------------------------------------------------------------
# Tests
# --------------------------------------------------------------------------

def test_tables_are_up_to_date(tmp_path):
    """sg_tables.h is exactly what gen_tables.py derives from the Python reference."""
    regenerated = tmp_path / "sg_tables.h"
    subprocess.run([sys.executable, str(FW / "tools" / "gen_tables.py"), "-o", str(regenerated)],
                   check=True, capture_output=True, text=True)
    assert regenerated.read_text() == (CORE / "sg_tables.h").read_text(), "run firmware/tools/gen_tables.py"


def test_classical_path(cli, build_dir):
    """Raw counts -> sensor state, preprocessing, vitals without a denoiser."""
    cases = classical_cases()
    results, work_size = run_host(cli, build_dir, "classical", cases)
    assert work_size <= 65536
    compare(cases, results, "classical path")
    assert {r["has_hr"] for r in results} == {0, 1}
    assert any(r["reliable"] for r in results) and any(r["has_spo2"] for r in results)


def test_denoised_path(cli, build_dir):
    """Vitals from the denoiser's signals and artefact probabilities."""
    if not denoiser_available():
        pytest.skip("needs onnxruntime and ml/models/denoiser.onnx")
    cases = denoised_cases()
    results, _ = run_host(cli, build_dir, "denoised", cases)
    compare(cases, results, "denoised path")
    assert any(r["reliable"] for r in results) and any(r["has_spo2"] for r in results)
    # Both sides of pipeline.CLEAN_MAX_MOTION (measured or denoised signals as the reference).
    shares = [r["q_motion_fraction"] for r in results]
    assert any(s <= 0.2 for s in shares) and any(0.2 < s <= 0.7 for s in shares)


def test_edge_cases(cli, build_dir):
    """Degenerate inputs: no crash and the same decisions as the reference."""
    cases = edge_cases()
    results, _ = run_host(cli, build_dir, "edge", cases)
    compare(cases, results, "edge cases")
    # The cases reach every outcome.
    seen = 0
    for r in results:
        seen |= int(r["reasons"])
    assert seen == (1 << len(REASON_BITS)) - 1
    assert {r["spo2_reason"] for r in results} == {0, 1, 2, 3}


def test_window_length_out_of_range(cli, build_dir):
    """Lengths outside [100, SG_WINDOW] give an empty, unreliable result instead of a buffer overflow."""
    win = simulate_window(7_400_000, n=600, kinds=[])
    cases = [Case(f"n={n}", win.red_raw[:n], win.ir_raw[:n]) for n in (0, 1, 99, WINDOW + 1, 600)]
    results, _ = run_host(cli, build_dir, "range", cases)
    for case, r in zip(cases, results):
        assert r["n"] == case.ir.size
        assert not r["finger_detected"] and r["sensor_reasons"] == 1 << REASON_BITS["no_contact"], case.name
        assert not (r["reliable"] or r["has_hr"] or r["has_spo2"] or r["has_r"]), case.name
        assert r["pi_in"] == 0 and not np.any(r["ir_bv"]) and not np.any(r["red_bv"]), case.name


def dsp_calls() -> list[tuple]:
    """Calls of single sg_dsp functions with what numpy/scipy return for the same input:
    (label, op, a, b, param, expected, absolute tolerance)."""
    rng = np.random.default_rng(99)
    calls = []

    def add(label, op, expected, a=(), b=(), param=0.0, tol=0.0):
        calls.append((label, DSP_OPS[op], np.asarray(a, dtype=np.float64), np.asarray(b, dtype=np.float64),
                      float(param), np.atleast_1d(np.asarray(expected, dtype=np.float64)), tol))

    for n in (1, 2, 3, 7, 8, 9, 15, 16, 17, 36, 100, 127, 128, 129, 136, 255, 256, 257, 400, 511, 512):
        x = rng.standard_normal(n) * 10.0 ** rng.uniform(-3, 3) + rng.uniform(-1, 1)
        add(f"sum[{n}]", "sum", np.sum(x), x)
        add(f"std[{n}]", "std", np.std(x), x)
        add(f"median[{n}]", "median", np.median(x), x)
        for q in (0, 3, 50, 97, 100):
            add(f"percentile[{n}, {q}]", "percentile", np.percentile(x, q), x, param=q)
        ties = rng.integers(0, 4, n).astype(float)             # first of several equal extrema
        add(f"arg[{n}]", "arg", [np.argmax(ties), np.argmin(ties)], ties)
        pos = np.concatenate([[-1.0, 0.0, n - 1.0, n - 0.5, n + 3.0], rng.uniform(0, n - 1, 40),
                              rng.integers(0, n, 10).astype(float)])
        add(f"interp[{n}]", "interp", np.interp(pos, np.arange(n), x), x, pos)
        y = np.clip(x, 0, None) ** 2
        for size in (1, 2, 5, 6, 33, 34):                       # odd and even windows, also longer than the signal
            add(f"uniform[{n}, {size}]", "uniform", ndimage.uniform_filter1d(y, size, mode="nearest"), y, param=size)
    for n in (2, 3, 100, 101, 256, 400, 512):
        add(f"hann[{n}]", "hann", signal.windows.hann(n), param=n, tol=1e-15)

    # find_peaks: flat tops, plateaus at the edges, monotonic and constant signals.
    shapes = [[], [1], [1, 2], [2, 1], [1, 2, 1], [1, 2, 2, 1], [1, 2, 2, 2, 1], [1, 2, 2, 3], [3, 2, 2, 1],
              [2, 2, 1], [1, 2, 2], [1, 1, 1, 1], [1, 3, 2, 3, 3, 1, 4, 4, 4, 4, 0, 5], list(range(20)),
              list(range(20, 0, -1))]
    shapes += [rng.integers(0, 3, int(rng.integers(3, 60))).tolist() for _ in range(300)]
    shapes += [rng.standard_normal(239).astype(np.float32).tolist() for _ in range(5)]   # the C++ scans floats
    for i, shape in enumerate(shapes):
        add(f"peaks[{i}]", "peaks", signal.find_peaks(np.asarray(shape, dtype=float))[0], shape)

    for i, (kind, cutoff, order) in enumerate(FILTERS):
        for n in (100, 101, 256, 400, 512):
            x = rng.standard_normal(n) * 0.01 + 0.3 * np.sin(np.arange(n) / 7.0)
            expected = filters._filtfilt(filters._sos(kind, cutoff, FS, order), x)
            add(f"filtfilt[{kind} {cutoff}, {n}]", "filtfilt", expected, x, param=i)

    # The FFT is single precision: compare with the double-precision spectrum of the same float32 samples.
    t = np.arange(512) / FS
    for i, x in enumerate([np.sin(2 * np.pi * 1.2 * t) * np.hanning(512), rng.standard_normal(512),
                           rng.standard_normal(100), np.eye(1, NFFT, 5)[0], rng.standard_normal(NFFT)]):
        x = x.astype(np.float32).astype(np.float64)
        power = np.abs(np.fft.rfft(x, NFFT)) ** 2
        add(f"fft[{i}]", "fft", power, x, tol=2e-6 * power.max())
    return calls


def check_dsp(calls, results, label):
    problems, fft_err = [], 0.0
    for (name, _, _, _, _, expected, tol), got in zip(calls, results):
        if got.shape != expected.shape:
            problems.append(f"{name}: {got.size} values, expected {expected.size}")
            continue
        err = float(np.max(np.abs(got - expected), initial=0.0))
        if name.startswith("fft"):
            fft_err = max(fft_err, err / expected.max())
        if not err <= tol:
            problems.append(f"{name}: differs by {err:.3g} (tolerance {tol:.3g})")
    print(f"\n{label}: {len(calls)} calls; FFT power error up to {fft_err:.3g} of the largest bin")
    assert not problems, f"{len(problems)} mismatches, first ones:\n" + "\n".join(problems[:25])


def test_dsp_building_blocks(cli, build_dir):
    """Each sg_dsp routine against the numpy/scipy routine it replaces: bit-identical
    in double precision, close to rounding for the Hann window and the float FFT."""
    exe, _ = cli
    calls = dsp_calls()
    fin, fout = build_dir / "dsp_in.bin", build_dir / "dsp_out.bin"
    write_dsp_calls(fin, calls)
    subprocess.run([str(exe), "--dsp", str(fin), str(fout)], check=True, capture_output=True, timeout=600)
    check_dsp(calls, read_dsp_results(fout, len(calls)), "building blocks")


def rv32_toolchain():
    """(compiler, qemu), or None if the RV32 check cannot run on this machine."""
    cxx, qemu = shutil.which("riscv64-unknown-elf-g++"), shutil.which("qemu-system-riscv32")
    if not (cxx and qemu and shutil.which("bash")):
        return None
    probe = subprocess.run([cxx, "--specs=picolibc.specs", "-march=rv32imc", "-mabi=ilp32",
                            "-print-file-name=libc.a"], capture_output=True, text=True)
    return (cxx, qemu) if probe.returncode == 0 else None


def run_rv32(build_dir, *args):
    """Cross-builds core_cli and runs it under QEMU with the given arguments."""
    cmd = ["bash", str(FW / "tests" / "build_rv32.sh"), str(build_dir / "core_cli_rv32.elf"), *map(str, SOURCES),
           "--", *map(str, args)]
    run = subprocess.run(cmd, capture_output=True, text=True, timeout=1800,
                         env={**os.environ, "RV32_CXXFLAGS": "-Wstack-usage=1024"})
    assert run.returncode == 0, run.stdout[-2000:] + run.stderr[-4000:]


@rv32
def test_rv32_matches_host(cli, build_dir):
    """The core cross-built for RV32IMC (the instruction set of the ESP32-C3, soft-float)
    and run under QEMU: same building blocks, same results as on the host."""
    if rv32_toolchain() is None:
        pytest.skip("needs riscv64-unknown-elf-g++ with picolibc and qemu-system-riscv32")
    _, names = cli

    calls = dsp_calls()
    fin, fout = build_dir / "dsp_rv32_in.bin", build_dir / "dsp_rv32_out.bin"
    write_dsp_calls(fin, calls)
    run_rv32(build_dir, "--dsp", fin, fout)
    check_dsp(calls, read_dsp_results(fout, len(calls)), "RV32 building blocks")

    cases = classical_cases(count=24) + edge_cases() + (denoised_cases(count=24) if denoiser_available() else [])
    host, host_work_size = run_host(cli, build_dir, "rv32_host", cases)
    fin, fout = build_dir / "core_rv32_host_in.bin", build_dir / "core_rv32_out.bin"
    run_rv32(build_dir, fin, fout)
    target, work_size = read_results(fout, names)
    assert work_size <= 65536 and len(target) == len(cases)

    worst, problems = (0.0, ""), []
    for case, h, t in zip(cases, host, target):
        for key in names:
            err = rel_err(t[key], h[key])
            if err > worst[0]:
                worst = (err, f"{case.name} {key}")
            if (key in EXACT and t[key] != h[key]) or not err <= 1e-12:
                problems.append(f"{case.name}: {key} = {t[key]!r} on RV32, {h[key]!r} on the host")
        for key in ("ir_bv", "red_bv"):
            err = float(np.max(np.abs(t[key] - h[key]), initial=0.0))
            if err > worst[0]:
                worst = (err, f"{case.name} {key}")
            if not err <= 1e-12:
                problems.append(f"{case.name}: {key} differs by {err:.3g} between RV32 and host")
    print(f"RV32 vs host: {len(cases)} windows, sizeof(SgWork) = {work_size} (host {host_work_size}); "
          f"largest difference {worst[0]:.3g} ({worst[1]})")
    assert not problems, f"{len(problems)} differences, first ones:\n" + "\n".join(problems[:25])
