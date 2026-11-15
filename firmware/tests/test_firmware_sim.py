"""Firmware-in-the-loop on the host.

The real sketch (suguard/suguard.ino) is compiled against a mock of the
Arduino API and a register-level MAX30102 simulator (tests/host/fw_sim.cpp).
Simulated PPG is played through the sensor model; everything the firmware
prints on USB serial and every HTTPS request is captured and checked: the
vital signs against the Python reference pipeline in ml/suguard_ml, the
behaviour over time (uploads, outages, battery, markers, wear detection)
against what the README promises.

Simulated time advances only while the sketch waits, and the sampler "task"
runs every 50 ms of it, also while loop() is blocked in a request or in the
signal pipeline (the harness can make both take as long as on the MCU).

This exercises the same code that runs on the board except for the drivers
below the Arduino API (Wire, Wi-Fi, flash), which are mocked.
"""
import json
import re
import subprocess

import numpy as np
import pytest

from conftest import FW, ML

from suguard_ml.pipeline import SuGuardPipeline  # noqa: E402
from suguard_ml.synth.ppg import simulate_window  # noqa: E402

SRC = FW / "suguard" / "src"
EDGE_NPZ = ML / "models" / "denoiser_edge_int.npz"
EPOCH = 1794700000            # wall clock of the simulation once it is set (fw_sim.cpp)
CLOUD = ("ap=1", "cmd=wifi HomeNet secret123", "cmd=user Test.User@example.com")
DB = "https://suguard-7f535-default-rtdb.asia-southeast1.firebasedatabase.app"
UID = "test_dot_user_at_example_dot_com"


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


@pytest.fixture(scope="session")
def clean(build_dir):
    """A resting signal: 72 bpm, SpO2 97 %, strong pulse, no motion."""
    path = build_dir / "rec_clean.bin"
    return path, recording(path, 42, 6000, kinds=[], hr_bpm=72.0, spo2=97.0, pi_ir=0.01)


def run_sim(exe, samples, seconds, *args):
    res = subprocess.run([str(exe), str(samples), str(seconds), *args], capture_output=True, text=True, timeout=900)
    assert res.returncode == 0, res.stdout[-2000:] + res.stderr[-4000:]
    out = {"vitals": {}, "raw": {}, "records": [], "events": [], "logs": [], "http": [], "sim": [], "text": [],
           "stdout": res.stdout}
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
            elif msg["t"] == "log":
                out["logs"].append(msg["msg"])
        elif line.startswith("HTTP PUT "):
            _, _, url, ca, code, body = line.split(" ", 5)
            out["http"].append((url, ca, int(code.split("=")[1]), json.loads(body)))
        elif line.startswith("SIM "):
            out["sim"].append(line)
        else:
            out["text"].append(line)
    return out


def radio_sessions(out):
    """[(on, off)] in seconds, from the harness log."""
    on = [float(m.group(1)) for m in (re.match(r"SIM ([\d.]+) radio on", s) for s in out["sim"]) if m]
    off = [float(m.group(1)) for m in (re.match(r"SIM ([\d.]+) radio off", s) for s in out["sim"]) if m]
    return list(zip(on, off + [None] * (len(on) - len(off))))


def radio_share(out):
    return float(re.search(r"radio on ([\d.]+) %", out["sim"][-1]).group(1)) / 100.0


def led_share(out):
    return float(re.search(r"leds on ([\d.]+) %", out["sim"][-1]).group(1)) / 100.0


def status_field(out, pattern):
    m = re.search(pattern, "\n".join(out["text"]))
    assert m, pattern
    return m.group(1)


def reference(windows, denoiser):
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


# ---------------------------------------------------------------------------
# Vital signs
# ---------------------------------------------------------------------------

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
    assert list(out["vitals"]) == list(range(1, len(out["vitals"]) + 1))   # 'set' and 'stream' restart nothing
    assert status_run(fw_sim, samples, "restarts (\\d+)") == "0"


def status_run(exe, samples, pattern):
    out = run_sim(exe, samples, 30, "cmd=stream on", "cmd=set tz_offset_min 360", "at=25:cmd:status")
    return status_field(out, pattern)


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


def test_swapped_led_channels_are_pointed_out(fw_sim, build_dir, clean):
    """A clone sensor with red and IR exchanged gives no values; the firmware says why."""
    path, w = clean
    swapped = build_dir / "rec_swapped.bin"
    np.stack([w.ir_raw, w.red_raw], axis=1).astype("<u4").tofile(swapped)
    out = run_sim(fw_sim, swapped, 100)
    assert not any(v["reliable"] for v in out["vitals"].values())
    assert all("red_ir_inconsistent" in v["reasons"] for v in out["vitals"].values())
    assert sum("swap_red_ir" in m for m in out["logs"]) == 1          # said once, not every window
    fixed = run_sim(fw_sim, swapped, 60, "cmd=set swap_red_ir 1")
    good = [v for v in fixed["vitals"].values() if v["reliable"]]
    assert len(good) >= 3 and np.median([v["hr"] for v in good]) == pytest.approx(w.hr_bpm, abs=1.5)
    assert not any("swap_red_ir" in m for m in fixed["logs"])


# ---------------------------------------------------------------------------
# Records and uploads
# ---------------------------------------------------------------------------

def test_clean_signal_accuracy_and_upload(fw_sim, clean):
    """Resting signal: correct numbers, one record per interval, uploaded to the right place."""
    path, w = clean
    out = run_sim(fw_sim, path, 135, *CLOUD, "cmd=set report_interval_s 30", "cmd=set upload_interval_s 30",
                  "cmd=mark after coffee")
    reliable = [v for v in out["vitals"].values() if v["reliable"]]
    assert len(reliable) >= 8
    assert np.median([v["hr"] for v in reliable]) == pytest.approx(w.hr_bpm, abs=1.5)
    assert np.median([v["spo2"] for v in reliable if v["spo2"] is not None]) == pytest.approx(97.0, abs=1.0)

    assert len(out["records"]) == 4
    for r in out["records"]:
        assert "glucose" not in r and r["spo2Calibrated"] is False
        assert r["reliableWindows"] >= 1 and r["pulse"] == pytest.approx(w.hr_bpm, abs=2.0)
    vitals = [x for x in out["http"] if "/vitals/" in x[0]]
    events = [x for x in out["http"] if "/events/" in x[0]]
    assert len(vitals) == 4 and len(events) == 1 and all(code == 200 for _, _, code, _ in out["http"])
    for url, ca, _, body in vitals:
        assert url.startswith(f"{DB}/users/{UID}/vitals/hd_") and url.endswith(f"{body['id']}.json")
        assert ca == "ca=1"                                           # TLS roots installed
        assert body["timestamp"].startswith("2026-11-15T04:4")         # local time, UTC+5
    # Each record carries the time it was made, 30 s apart, whenever it was uploaded.
    stamps = [body["ts"] for _, _, _, body in vitals]
    assert stamps == pytest.approx([EPOCH + 30 * k for k in (1, 2, 3, 4)], abs=2)
    # The marker was typed before the clock was set; it is dated by when it happened.
    assert events[0][3]["note"] == "after coffee" and events[0][3]["ts"] == pytest.approx(EPOCH, abs=2)
    assert "secret123" not in out["stdout"]                           # the console never echoes the password
    keys = [b["id"] for _, _, _, b in vitals]
    assert keys == sorted(keys) and len(set(keys)) == len(keys)
    # One session for the marker right after the start, then one per record; the radio is off in between.
    assert len(radio_sessions(out)) == 5 and radio_share(out) < 0.25


def test_radio_is_duty_cycled(fw_sim, clean):
    """Default settings: a short Wi-Fi session every five minutes, radio off in between."""
    path, _ = clean
    out = run_sim(fw_sim, path, 1260, *CLOUD)
    sessions = radio_sessions(out)
    assert 4 <= len(sessions) <= 5
    assert all(off is not None and off - on < 15 for on, off in sessions)
    assert np.diff([on for on, _ in sessions]) == pytest.approx(300, abs=5)
    assert radio_share(out) < 0.04
    assert len(out["records"]) == 20 and len(out["http"]) >= 16


@pytest.mark.parametrize("code, attempts, kept", [(401, (1, 2), True), (503, (4, 7), True), (-1, (4, 7), True),
                                                    (400, (10, 11), False)])
def test_failed_uploads_back_off(fw_sim, clean, code, attempts, kept):
    """A server that refuses or fails must not make the bracelet retry around the clock
    (the first version made a new TLS connection on every pass of the main loop)."""
    path, _ = clean
    args = [*CLOUD, "cmd=set report_interval_s 30", "cmd=set upload_interval_s 30", f"http_code={code}",
            "at=330:cmd:status"]
    out = run_sim(fw_sim, path, 335, *args)
    assert attempts[0] <= len(out["http"]) <= attempts[1], len(out["http"])
    assert radio_share(out) < 0.25
    waiting = int(status_field(out, r"waiting (\d+) records"))
    assert waiting >= 10 if kept else waiting <= 1                    # refused for good: dropped, not retried
    assert f"last http {code}" in "\n".join(out["text"])
    if kept:                                                          # the server recovers: everything arrives
        later = run_sim(fw_sim, path, 1100, *args, "at=340:http:200")
        ok = [b for _, _, c, b in later["http"] if c == 200]
        assert len(ok) == len(later["records"]) >= 35 and len({b["id"] for b in ok}) == len(ok)


def test_offline_records_are_kept_and_dated(fw_sim, clean):
    """An hour away from Wi-Fi: every record is uploaded on return, with the time it was made
    (the first version kept six, and nothing from before the first clock synchronisation)."""
    path, _ = clean
    out = run_sim(fw_sim, path, 3700, *CLOUD, "at=3600:ap:1", "ap=0", "at=1800:button:1", "at=1800.3:button:0")
    assert all(r["ts"] is None and r["timestamp"] is None for r in out["records"][:59])   # no invented time
    uploaded = [b for u, _, c, b in out["http"] if c == 200 and "/vitals/" in u]
    assert len(uploaded) >= 60                     # everything made while away (the newest waits for the next session)
    assert [b["ts"] for b in uploaded] == pytest.approx([EPOCH + 60 * k for k in range(1, len(uploaded) + 1)], abs=3)
    assert [b["pulse"] for b in uploaded] == [r["pulse"] for r in out["records"][:len(uploaded)]]
    marks = [b for u, _, c, b in out["http"] if c == 200 and "/events/" in u]
    assert len(marks) == 1 and marks[0]["ts"] == pytest.approx(EPOCH + 1800, abs=2)
    # While the access point was away the radio tried a few times an hour, not every 20 s.
    tries = [on for on, _ in radio_sessions(out) if on < 3600]
    assert 6 <= len(tries) <= 12 and radio_share(out) < 0.08


def test_raw_windows_carry_their_own_time(fw_sim, clean):
    """Raw windows are dated by their samples, not by when the firmware got round to them
    (slow processing and uploads shifted them by seconds), and never with an invented date."""
    path, _ = clean
    # No Wi-Fi (the usual USB recording session): no time, but the age lets the PC date the window.
    out = run_sim(fw_sim, path, 60, "cmd=stream on", "proc_ms=1500")
    assert len(out["raw"]) >= 4
    assert all(w["ts"] is None and 1500 <= w["age_ms"] <= 1700 for w in out["raw"].values())
    # With a clock, slow processing and slow uploads: consecutive windows are exactly one window apart.
    out = run_sim(fw_sim, path, 160, *CLOUD, "cmd=stream on", "cmd=set upload_raw 1", "proc_ms=1500", "http_ms=2500")
    stamped = [w["ts"] for w in out["raw"].values() if w["ts"] is not None]
    assert len(stamped) >= 10
    assert np.diff(stamped) == pytest.approx(10.24, abs=0.06)
    first_seq = min(s for s, w in out["raw"].items() if w["ts"] is not None)
    assert stamped[0] == pytest.approx(EPOCH + 0.55 + 10.24 * (first_seq - 1), abs=0.3)   # 0.55 s start-up + settling
    uploads = [b for u, _, c, b in out["http"] if "/rawPpg/" in u]
    assert len(uploads) >= 8 and all(u.startswith(f"{DB}/rawPpg/{UID}/hd_") for u, _, _, _ in out["http"] if "rawPpg" in u)
    assert list(out["vitals"]) == list(range(1, len(out["vitals"]) + 1))        # no window was dropped meanwhile


def test_markers_survive_a_busy_main_loop(fw_sim, clean):
    """Short presses of the button while the pipeline or an upload is running are not lost."""
    path, _ = clean
    presses = [f"at={10 + 7.3 * k:.1f}:button:1" for k in range(30)] + [f"at={10.2 + 7.3 * k:.1f}:button:0" for k in range(30)]
    out = run_sim(fw_sim, path, 240, *CLOUD, "cmd=set upload_raw 1", "proc_ms=1500", "http_ms=2500", *presses)
    assert len(out["events"]) == 30 and all(e["note"] == "button" for e in out["events"])
    held = run_sim(fw_sim, path, 30, "at=5:button:1", "at=25:button:0")          # holding it down is one press
    assert len(held["events"]) == 1


def test_console_reports_what_happened(fw_sim, clean):
    path, _ = clean
    out = run_sim(fw_sim, path, 12, "cmd=mark no account yet", "cmd=mark " + "x" * 190, "at=3:cmd:led red",
                  "unplug=5", "at=9:cmd:led red", "at=10:cmd:status")
    text = "\n".join(out["text"])
    assert "USB only" in text and "queued" not in text                 # nothing is queued without an account
    assert len(out["events"]) == 2
    assert text.count("ok (5 s)") == 1 and "error: sensor not running" in text
    assert "no_sensor" in text and "wifi: not configured" in text and "heap: free" in text


def test_settings_typed_in_one_burst_all_take_effect(fw_sim, clean):
    """The sampler accepts one request at a time; the others used to be dropped silently."""
    path, _ = clean
    out = run_sim(fw_sim, path, 30, "at=0:scale:0.3", "cmd=set led_init 100", "cmd=set adc_range 2",
                  "cmd=set led_max 110", "at=20:cmd:status", "at=21:cmd:get led_init")
    assert status_field(out, r"led red/ir (\d+/\d+)") == "100/100"
    assert out["vitals"] and all(v["led"] == [100, 100] for v in out["vitals"].values())


def test_stored_settings_are_loaded(fw_sim, clean):
    path, _ = clean
    out = run_sim(fw_sim, path, 45, "save=use_nn=0", "save=report_interval_s=20", "save=cpu_mhz=80", "save=sensor_sps=100")
    assert out["vitals"] and all(v["nn"] is False for v in out["vitals"].values())
    assert len(out["records"]) == 2 and any("cpu 80 MHz" in s for s in out["sim"])
    assert [v["reliable"] for v in out["vitals"].values()].count(True) >= 2   # 100 conversions/s still gives 50 Hz


def test_usb_port_never_stalls_the_firmware(fw_sim, clean):
    path, _ = clean
    # No PC attached: everything keeps running.
    out = run_sim(fw_sim, path, 60, "host=0", "at=30:button:1")
    assert len(out["vitals"]) >= 5
    # A PC that stops reading: lines are skipped whole, never cut in the middle (run_sim parses every line).
    out = run_sim(fw_sim, path, 90, "cmd=set report_interval_s 20", "at=35:room:70", "at=70:room:4096")
    assert len(out["vitals"]) >= 4 and len(out["records"]) >= 2


def test_clock_wrap_around(fw_sim, clean):
    """millis() wraps after 49.7 days: sampling, records and uploads continue across it."""
    path, _ = clean
    out = run_sim(fw_sim, path, 150, *CLOUD, "cmd=set report_interval_s 30", "cmd=set upload_interval_s 30",
                  f"start_ms={2**32 - 40_000}")
    assert list(out["vitals"]) == list(range(1, len(out["vitals"]) + 1)) and len(out["vitals"]) >= 14
    assert len(out["records"]) == 4 and len([1 for u, _, c, _ in out["http"] if c == 200 and "/vitals/" in u]) == 4


# ---------------------------------------------------------------------------
# Wear detection and the sensor
# ---------------------------------------------------------------------------

def test_not_worn_goes_to_standby_and_reports_nothing(fw_sim, build_dir):
    samples = build_dir / "rec_dark.bin"
    np.full((2000, 2), 900, dtype="<u4").tofile(samples)              # nothing reflects the light
    out = run_sim(fw_sim, samples, 120, *CLOUD, "cmd=set report_interval_s 20", "at=100:cmd:status")
    assert len(out["vitals"]) == 3                 # one at the start current, two at full current, then standby
    assert all(not v["reliable"] and "no_contact" in v["reasons"] for v in out["vitals"].values())
    assert [v["led"][1] for v in out["vitals"].values()] == [63, 127, 127]
    assert out["records"] == [] and out["http"] == [] and radio_sessions(out) == []
    assert "sensor: standby" in "\n".join(out["text"]) and led_share(out) < 0.4


def test_something_without_a_pulse_puts_the_sensor_to_rest(fw_sim, build_dir, clean):
    """Face down on a table the sensor sees light but no pulse: it must not measure for ever."""
    samples = build_dir / "rec_table.bin"
    rng = np.random.default_rng(3)
    np.stack([np.round(40_000 + rng.normal(0, 4, 6000)), np.round(60_000 + rng.normal(0, 4, 6000))],
             axis=1).astype("<u4").tofile(samples)
    out = run_sim(fw_sim, samples, 600, "at=590:cmd:status")
    # A minute of looking, five minutes of rest, another look: 2 x 6 windows instead of 58.
    assert len(out["vitals"]) == 12 and not any(v["reliable"] for v in out["vitals"].values())
    assert sum("resting" in m for m in out["logs"]) == 2
    assert "resting: no pulse" in "\n".join(out["text"]) and led_share(out) < 0.27
    # Moved (the reflected level changes): it looks again at once instead of after five minutes.
    out = run_sim(fw_sim, samples, 200, "at=120:scale:1.4")
    assert len(out["vitals"]) >= 11 and min(s for s in out["vitals"] if s > 6) == 7
    # A worn bracelet never rests.
    path, _ = clean
    out = run_sim(fw_sim, path, 300)
    assert sum(v["reliable"] for v in out["vitals"].values()) >= 20 and not any("resting" in m for m in out["logs"])


def test_missing_sensor_is_reported_not_fatal(fw_sim, clean):
    path, _ = clean
    out = run_sim(fw_sim, path, 40, "unplug=0", "cmd=status")
    assert out["vitals"] == {}
    assert any("no_sensor" in t for t in out["text"])


def test_sensor_reset_at_any_moment_recovers(fw_sim, clean):
    """A brown-out of the sensor during settling used to leave the sampler waiting for ever."""
    path, _ = clean
    for at in (0.3, 4.0, 10.9):
        out = run_sim(fw_sim, path, 60, f"at={at}:por:1", "at=55:cmd:status")
        assert len(out["vitals"]) >= 3, at
        assert "sensor: active" in "\n".join(out["text"])


# ---------------------------------------------------------------------------
# Battery
# ---------------------------------------------------------------------------

def sleep_line(out):
    lines = [s for s in out["sim"] if "deep sleep at" in s]
    return lines[0] if lines else None


def test_empty_battery_sleeps_with_everything_off(fw_sim, clean):
    """The sensor stays powered during deep sleep, so it has to be shut down first
    (it used to keep both LEDs on, draining the empty cell)."""
    path, _ = clean
    out = run_sim(fw_sim, path, 300, *CLOUD, "usb=0", "at=40:vbat:3.40")
    line = sleep_line(out)
    assert line and "shutdown=1 led1=0 led2=0 radio=0" in line
    t = float(line.split()[4])
    assert 105 < t < 140              # a minute after the filtered voltage crossed 3.45 V, not at once
    assert any("sleep timer 600 s" in s for s in out["sim"]) and any("gpio mask 0x10 level 1" in s for s in out["sim"])
    assert any("battery empty" in m for m in out["logs"])
    # A sag that recovers within the minute is ignored; on USB power nothing sleeps.
    assert sleep_line(run_sim(fw_sim, path, 200, "usb=0", "at=40:vbat:3.40", "at=75:vbat:3.80")) is None
    assert sleep_line(run_sim(fw_sim, path, 200, "usb=1", "at=40:vbat:3.40")) is None


@pytest.mark.parametrize("args, sleeps, timer", [
    (("vbat=3.40", "usb=0"), True, 600),                    # empty at power-on
    (("vbat=3.40", "usb=1"), False, None),                  # on the charger
    (("vbat=3.50", "usb=0"), False, None),
    (("vbat=3.50", "usb=0", "wake=timer"), True, 600),      # rested but not recharged: sleep on
    (("vbat=3.65", "usb=0", "wake=timer"), False, None),
    (("vbat=3.30", "usb=1", "wake=gpio"), False, None),     # woken by the charger
    (("vbat=2.95", "usb=0"), True, 3600),                   # deeply discharged (was taken for a measurement fault)
])
def test_start_up_with_a_low_battery(fw_sim, clean, args, sleeps, timer):
    path, _ = clean
    out = run_sim(fw_sim, path, 30, *args)
    line = sleep_line(out)
    assert (line is not None) == sleeps
    if sleeps:
        assert "shutdown=1 led1=0 led2=0" in line and float(line.split()[4]) < 0.5 and not out["vitals"]
        assert any(f"sleep timer {timer} s" in s for s in out["sim"])
    else:
        assert out["vitals"]
