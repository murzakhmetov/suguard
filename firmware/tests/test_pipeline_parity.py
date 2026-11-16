"""sg_process_window (the function the firmware calls for every window) against

    SuGuardPipeline(denoiser=EdgeDenoiserInt(model)).analyze(red, ir, fs=50)

on simulated raw windows covering clean signals, every artefact type and
severity, weak perfusion and missing contact. The network runs in the same
integer arithmetic on both sides, so the results must agree to rounding.
"""
import json
import subprocess

import numpy as np
import pytest

from conftest import CORE, FW, ML, build_host

from suguard_ml.pipeline import SuGuardPipeline, vitals_from_signals  # noqa: E402
from suguard_ml.signal.filters import preprocess  # noqa: E402
from suguard_ml.signal.quality import sensor_state  # noqa: E402
from suguard_ml.synth.ppg import simulate_window  # noqa: E402

N_WINDOWS = 300


@pytest.fixture(scope="module")
def cli(build_dir):
    if not (CORE / "sg_model.h").exists():
        pytest.skip("edge model not exported yet")
    return build_host([FW / "tests" / "host" / "pipeline_cli.cpp", *sorted(CORE.glob("*.cpp"))],
                      build_dir / "pipeline_cli")


def make_windows():
    ws = []
    for i in range(N_WINDOWS):
        w = simulate_window(8_000_000 + i)
        ws.append((w.red_raw.astype(np.uint32), w.ir_raw.astype(np.uint32)))
    rng = np.random.default_rng(5)
    ws.append((rng.normal(900, 4, 512).round().astype(np.uint32), rng.normal(1200, 4, 512).round().astype(np.uint32)))
    ws.append((np.full(512, 262143, np.uint32), np.full(512, 262143, np.uint32)))                 # saturated
    ws.append((rng.normal(70000, 30, 512).round().astype(np.uint32),
               rng.normal(100000, 30, 512).round().astype(np.uint32)))                             # noise only
    ws.append((np.full(512, 80000, np.uint32), np.full(512, 120000, np.uint32)))                  # constant
    # The red LED sees no pulse (sensor noise on a plausible DC level): a denoiser tends to draw
    # one from the IR channel, which the input-support check has to catch on both sides.
    for i in range(12):
        w = simulate_window(8_100_000 + i, kinds=[], pi_ir=0.01)
        dc = float(np.median(w.red_raw))
        ws.append((np.round(dc + rng.normal(0, 3e-4 * dc, 512)).astype(np.uint32), w.ir_raw.astype(np.uint32)))
    # Weak pulses (0.09-0.11 %) the bracelet network flags as motion: the classical checks decide them.
    for seed in (6_100_002, 6_100_016):
        w = simulate_window(seed, kinds=[])
        ws.append((w.red_raw.astype(np.uint32), w.ir_raw.astype(np.uint32)))
    return ws


def run_cli(cli, build_dir, ws, use_nn):
    path = build_dir / f"pipe_in_{int(use_nn)}.bin"
    with open(path, "wb") as fh:
        for red, ir in ws:
            fh.write(red.astype("<u4").tobytes())
            fh.write(ir.astype("<u4").tobytes())
    out = subprocess.run([str(cli), str(path), str(int(use_nn))], capture_output=True, text=True, check=True).stdout
    rows = [json.loads(line) for line in out.splitlines()]
    assert len(rows) == len(ws)
    return rows


def python_reference(pipe, red, ir):
    """Unrounded reference values (analyze() rounds what it reports)."""
    red, ir = red.astype(np.float64), ir.astype(np.float64)
    sensor = sensor_state(red, ir)
    ir_bv, _ = preprocess(ir, 50.0)
    red_bv, _ = preprocess(red, 50.0)
    if pipe.denoiser is not None:
        dn = pipe.denoiser.denoise_bv(ir_bv, red_bv, 50.0)
        v = vitals_from_signals(ir_bv, red_bv, sensor, dn.ir_bv, dn.red_bv, dn.artifact_prob)
    else:
        v = vitals_from_signals(ir_bv, red_bv, sensor)
    return v, sensor


@pytest.mark.parametrize("use_nn", [False, True])
def test_process_window_matches_python(cli, build_dir, use_nn):
    from suguard_ml.models.edge_int import EdgeDenoiserInt

    pipe = SuGuardPipeline(denoiser=EdgeDenoiserInt.load() if use_nn else None)
    ws = make_windows()
    rows = run_cli(cli, build_dir, ws, use_nn)
    n_reliable = n_mismatch = n_fallback = 0
    for (red, ir), c in zip(ws, rows):
        v, sensor = python_reference(pipe, red, ir)
        assert bool(c["reliable"]) == v.reliable
        assert bool(c["has_hr"]) == (v.hr_bpm is not None)
        assert bool(c["has_spo2"]) == v.spo2_ok == (v.spo2 is not None)
        assert sorted(filter(None, c["reasons"].split(","))) == sorted(set(v.reasons))
        assert c["spo2_why"] == (v.spo2_reason or "")          # why an accepted window has no SpO2
        assert bool(c["fallback"]) == v.classical_fallback      # pipeline.LOW_PERFUSION_PI
        n_fallback += v.classical_fallback
        assert bool(c["finger"]) == sensor.finger_detected
        assert c["sat"] == pytest.approx(sensor.saturated_fraction, abs=1e-12)
        assert c["pi_in"] == pytest.approx(v.pi_in, rel=1e-9, abs=1e-12)
        support = [x for s in (v.support_ir, v.support_red) for x in ((s.corr, s.gain) if s else (0.0, 0.0))]
        assert c["support"] == pytest.approx(support, rel=1e-9, abs=1e-12)
        n_mismatch += "denoiser_mismatch" in v.reasons or (v.support_red is not None and not v.support_red.ok)
        if v.hr_bpm is not None:
            assert c["hr"] == pytest.approx(v.hr_bpm, abs=1e-6)
        if v.spo2 is not None:
            assert c["spo2"] == pytest.approx(v.spo2, abs=1e-6)
        if v.sp.r_ratio is not None:
            assert c["r"] == pytest.approx(v.sp.r_ratio, abs=1e-8)
        assert c["sqi"] == pytest.approx(v.quality.sqi, abs=2e-4)
        assert c["motion"] == pytest.approx(v.quality.motion_fraction, abs=1e-12)
        n_reliable += v.reliable
    assert n_reliable > 60                                    # the comparison is not vacuous
    assert (n_mismatch >= 10) == use_nn                       # the input-support check was exercised
    assert (n_fallback >= 2) == use_nn                        # and the low-perfusion decision
