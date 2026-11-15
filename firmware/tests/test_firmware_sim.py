"""Firmware-in-the-loop on the host.

The real sketch (suguard/suguard.ino) is compiled against a mock of the
Arduino API and a register-level MAX30102 simulator (tests/host/fw_sim.cpp).
Simulated PPG is played through the sensor model; everything the firmware
prints on USB serial and every HTTP upload is captured and checked against the
Python reference pipeline in ml/suguard_ml.

This exercises the same code that runs on the board except for the hardware
drivers below the Arduino API (Wire, Wi-Fi, flash), which are mocked.
"""
import json
import subprocess

import numpy as np
import pytest

from conftest import FW, ML

from suguard_ml.pipeline import SuGuardPipeline  # noqa: E402
from suguard_ml.synth.ppg import simulate_window  # noqa: E402

SRC = FW / "suguard" / "src"
EDGE_NPZ = ML / "models" / "denoiser_edge_int.npz"


@pytest.fixture(scope="session")
def fw_sim(build_dir):
    exe = build_dir / "fw_sim"
    sources = [FW / "tests" / "host" / "fw_sim.cpp", *sorted((SRC / "app").glob("*.cpp")),
               *sorted((SRC / "drivers").glob("*.cpp")), *sorted((SRC / "core").glob("*.cpp"))]
    cmd = ["g++", "-std=gnu++17", "-O1", "-g", "-Wall", "-Wextra", "-Werror", "-fsanitize=address,undefined",
           "-fno-sanitize-recover=all", "-x", "c++", "-I", str(FW / "tests" / "host" / "arduino_mock"),
           "-I", str(FW / "tests" / "host"), *map(str, sources), "-lm", "-o", str(exe)]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 0, res.stderr[-4000:]
    return exe


def recording(path, seed, n, **kw):
    """Simulated raw recording (red, IR counts at 50 Hz) written as uint32 pairs."""
    w = simulate_window(seed, n=n, **kw)
    np.stack([w.red_raw, w.ir_raw], axis=1).astype("<u4").tofile(path)
    return w


def run_sim(exe, samples, seconds, *args):
    res = subprocess.run([str(exe), str(samples), str(seconds), *args], capture_output=True, text=True, timeout=600)
    assert res.returncode == 0, res.stdout[-2000:] + res.stderr[-4000:]
    out = {"vitals": {}, "raw": {}, "records": [], "events": [], "http": [], "text": []}
    for line in res.stdout.splitlines():
        if line.startswith("{"):
            msg = json.loads(line)                      # every JSON line the firmware prints must parse
            if msg["t"] == "vitals":
                out["vitals"][msg["seq"]] = msg
            elif msg["t"] == "raw":
                out["raw"][msg["w"]["seq"]] = msg["w"]
            elif msg["t"] == "record":
                out["records"].append(msg["r"])
            elif msg["t"] == "event":
                out["events"].append(msg["e"])
        elif line.startswith("HTTP PUT "):
            _, _, url, ca, body = line.split(" ", 4)
            out["http"].append((url, ca, body))
        else:
            out["text"].append(line)
    return out


def reference(windows, denoiser, hr_scale=1.0):
    """What the Python pipeline says for the raw windows the firmware streamed."""
    pipe = SuGuardPipeline(denoiser=denoiser)
    return {seq: pipe.analyze(w["red"], w["ir"], fs=50.0) for seq, w in windows.items()}


def assert_matches(fw, ref, hr_scale=1.0):
    assert fw["reliable"] == ref["reliable"], (fw, ref.get("reason"))
    hr = ref["heart_rate"]["bpm"]
    if hr is None:
        assert fw["hr"] is None
    else:
        assert fw["hr"] == pytest.approx(hr * hr_scale, abs=0.16)       # both sides round to 0.1
    spo2 = ref["spo2"]["percent"]
    assert (fw["spo2"] is None) == (spo2 is None)
    if spo2 is not None:
        assert fw["spo2"] == pytest.approx(spo2, abs=0.11)
    assert fw["sqi"] == pytest.approx(ref["quality"]["sqi"], abs=0.011)
    assert sorted(filter(None, fw["reasons"].split(","))) == sorted(ref.get("reason", []))


def edge_denoiser():
    if not EDGE_NPZ.exists():
        pytest.skip("edge model not exported yet")
    from suguard_ml.models.edge_int import EdgeDenoiserInt
    return EdgeDenoiserInt(EDGE_NPZ)


@pytest.mark.parametrize("use_nn", [False, True])
def test_vitals_match_python_reference(fw_sim, build_dir, use_nn):
    """Mixed clean / motion recording: every window the firmware analyses agrees with Python."""
    denoiser = edge_denoiser() if use_nn else None
    samples = build_dir / f"rec_mixed_{int(use_nn)}.bin"
    recording(samples, 2024, 9000)                                   # 3 min, random artefacts
    out = run_sim(fw_sim, samples, 185, f"cmd=set use_nn {int(use_nn)}", "cmd=stream on")
    assert len(out["raw"]) >= 15 and set(out["raw"]) == set(out["vitals"])
    ref = reference(out["raw"], denoiser)
    for seq, w in out["raw"].items():
        assert len(w["red"]) == len(w["ir"]) == 512
        assert_matches(out["vitals"][seq], ref[seq])
    assert all(v["nn"] == use_nn for v in out["vitals"].values())


def test_clean_signal_accuracy_and_upload(fw_sim, build_dir):
    """Resting signal: correct numbers, one record per interval, uploaded to the right place."""
    samples = build_dir / "rec_clean.bin"
    w = recording(samples, 42, 6000, kinds=[], hr_bpm=72.0, spo2=97.0, pi_ir=0.01)
    out = run_sim(fw_sim, samples, 125, "wifi=1", "cmd=wifi HomeNet secret123",
                  "cmd=user Test.User@example.com", "cmd=set report_interval_s 30", "cmd=mark after coffee")
    reliable = [v for v in out["vitals"].values() if v["reliable"]]
    assert len(reliable) >= 8
    assert np.median([v["hr"] for v in reliable]) == pytest.approx(w.hr_bpm, abs=1.5)
    assert np.median([v["spo2"] for v in reliable if v["spo2"] is not None]) == pytest.approx(97.0, abs=1.0)

    assert len(out["records"]) >= 3
    for r in out["records"]:
        assert "glucose" not in r and r["spo2Calibrated"] is False
        assert r["reliableWindows"] >= 1 and r["pulse"] == pytest.approx(w.hr_bpm, abs=2.0)
        assert r["timestamp"].startswith("2026-11-15T0")              # local time, UTC+5
    uploads = [(u, c, json.loads(b)) for u, c, b in out["http"]]
    vitals = [x for x in uploads if "/vitals/" in x[0]]
    events = [x for x in uploads if "/events/" in x[0]]
    assert len(vitals) == len(out["records"]) and len(events) == 1
    for url, ca, body in vitals:
        assert url.startswith("https://suguard-7f535-default-rtdb.asia-southeast1.firebasedatabase.app"
                              "/users/test_dot_user_at_example_dot_com/vitals/hd_")
        assert url.endswith(f"{body['id']}.json") and ca == "ca=1"    # TLS roots installed
    assert events[0][2]["note"] == "after coffee"
    assert "secret123" not in "\n".join(out["text"])                  # the console never echoes the password
    keys = [b["id"] for _, _, b in vitals]
    assert keys == sorted(keys) and len(set(keys)) == len(keys)       # chronological, unique


def test_sensor_clock_error_is_corrected(fw_sim, build_dir):
    """A sensor oscillator that runs 2 % fast must not shift the reported heart rate."""
    samples = build_dir / "rec_rate.bin"
    w = recording(samples, 7, 12000, kinds=[], hr_bpm=66.0, spo2=96.0, pi_ir=0.012)
    out = run_sim(fw_sim, samples, 120, "rate=1.02", "cmd=set use_nn 0")
    late = [v for v in out["vitals"].values() if v["fs"] > 0 and v["reliable"]]
    assert late and all(v["fs"] == pytest.approx(51.0, abs=0.15) for v in late)
    # The recording is played one sample per sensor tick, so in real time it runs 2 % fast and
    # the true heart rate is hr * 1.02. Analysed as 50 Hz data it would read hr; the firmware's
    # clock correction (measured fs / 50) restores the real-time value.
    assert np.median([v["hr"] for v in late]) == pytest.approx(w.hr_bpm * 1.02, rel=0.02)


def test_not_worn_goes_to_standby_and_reports_nothing(fw_sim, build_dir):
    samples = build_dir / "rec_dark.bin"
    np.full((2000, 2), 900, dtype="<u4").tofile(samples)              # nothing reflects the light
    out = run_sim(fw_sim, samples, 90, "wifi=1", "cmd=wifi HomeNet pw", "cmd=user a@b.kz",
                  "cmd=set report_interval_s 20", "cmd=status")
    assert len(out["vitals"]) == 2                                    # two dark windows, then standby
    assert all(not v["reliable"] and "no_contact" in v["reasons"] for v in out["vitals"].values())
    assert out["records"] == [] and out["http"] == []


def test_missing_sensor_is_reported_not_fatal(fw_sim, build_dir):
    samples = build_dir / "rec_none.bin"
    recording(samples, 3, 3000, kinds=[])
    out = run_sim(fw_sim, samples, 40, "unplug=0", "cmd=status")
    assert out["vitals"] == {}
    assert any("no_sensor" in t for t in out["text"])


def test_empty_battery_sleeps(fw_sim, build_dir):
    samples = build_dir / "rec_bat.bin"
    recording(samples, 3, 3000, kinds=[])
    res = subprocess.run([str(fw_sim), str(samples), "30", "vbat=3.40", "usb=0"], capture_output=True, text=True)
    assert "SIM deep sleep at" in res.stdout and '"t":"vitals"' not in res.stdout
    ok = subprocess.run([str(fw_sim), str(samples), "30", "vbat=3.40", "usb=1"], capture_output=True, text=True)
    assert "deep sleep" not in ok.stdout and '"t":"vitals"' in ok.stdout  # on USB power it keeps running
