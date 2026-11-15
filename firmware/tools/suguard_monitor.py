#!/usr/bin/env python3
"""Live monitor and data recorder for the SuGuard bracelet over USB.

    pip install pyserial
    python firmware/tools/suguard_monitor.py --port /dev/ttyACM0 --record session1 --user u01

What it does
  * shows the bracelet's own results (heart rate, SpO2, signal quality, why a
    window was rejected) as they arrive, one line per 10.24-s window
  * with --record DIR it switches raw streaming on and stores everything
    needed to train and validate models later (formats of ml/docs/DATA_COLLECTION.md):
        DIR/windows.jsonl      raw red/IR windows
        DIR/vitals.jsonl       what the firmware computed for each window
        DIR/fingersticks.csv   reference glucose values you type in
        DIR/events.jsonl       markers
  * with --check it re-computes every raw window on the PC with the Python
    reference pipeline (same integer model as the firmware) and reports any
    difference - a quick way to prove the device and the PC agree

While it runs, type and press Enter:
    g 5.6            reference glucose 5.6 mmol/L   (values > 30 are taken as mg/dL)
    m <text>         marker (meal, exercise, ...)
    <anything else>  sent to the bracelet console (try: status, help)
    q                quit

Replay a saved serial log instead of a live port (no hardware needed):
    python firmware/tools/suguard_monitor.py --replay log.txt --check
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def parse_line(line: str):
    """One line from the bracelet -> (kind, payload) or (None, text)."""
    line = line.strip()
    if not line.startswith("{"):
        return None, line
    try:
        msg = json.loads(line)
    except json.JSONDecodeError:
        return None, line
    return msg.get("t"), msg


def format_vitals(v: dict) -> str:
    hr = f"{v['hr']:5.1f}" if v.get("hr") is not None else "  --"
    spo2 = f"{v['spo2']:5.1f}" if v.get("spo2") is not None else "  --"
    temp = f"{v['temp']:.1f}" if v.get("temp") is not None else "--"
    state = "ok " if v.get("reliable") else "-- "
    why = v.get("reasons") or ""
    return (f"#{v.get('seq', 0):<5d} {state} HR {hr} bpm  SpO2 {spo2} %  SQI {v.get('sqi', 0):.2f}  "
            f"PI {v.get('pi', 0):.2f}%  motion {v.get('motion', 0):.2f}  DC {v.get('dc', [0, 0])[1]:.0f}  "
            f"T {temp}C  bat {v.get('bat', -1)}%  {v.get('proc_ms', 0)} ms  {why}")


def window_record(raw: dict, user: str) -> dict:
    """Firmware raw window -> record of windows.jsonl (see ml/suguard_ml/data/paired.py)."""
    w = raw["w"]
    return {"user_id": user, "device_id": w.get("device"), "ts": w["ts"], "fs": w["fs"], "seq": w.get("seq"),
            "temp_c": w.get("temp_c"), "led_red": w.get("ledRed"), "led_ir": w.get("ledIr"),
            "flags": w.get("flags", 0), "red": w["red"], "ir": w["ir"]}


class Checker:
    """Re-computes windows on the PC with the Python reference of the firmware."""

    def __init__(self):
        sys.path.insert(0, str(ROOT / "ml"))
        from suguard_ml.models.edge_int import EdgeDenoiserInt
        from suguard_ml.pipeline import SuGuardPipeline

        self.pipe = SuGuardPipeline(denoiser=EdgeDenoiserInt.load())
        self.prior = None
        self.prior_seq = 0
        self.n = self.n_bad = 0

    def analyze(self, raw: dict) -> dict:
        w = raw["w"]
        if self.prior is not None and self.prior_seq + 3 < w.get("seq", 0):
            self.prior = None                              # same staleness rule as the firmware
        res = self.pipe.analyze(w["red"], w["ir"], fs=50.0, prior_hr=self.prior)
        scale = w["fs"] / 50.0 if w.get("fs") else 1.0     # the firmware reports HR on the measured clock
        hr = res["heart_rate"]["bpm"]
        if res["reliable"] and hr is not None:
            self.prior, self.prior_seq = hr, w.get("seq", 0)   # in 50 Hz units, like the firmware's prior
        return {"reliable": res["reliable"], "hr": None if hr is None else hr * scale,
                "spo2": res["spo2"]["percent"], "sqi": res["quality"]["sqi"]}

    def compare(self, fw: dict, pc: dict) -> str | None:
        self.n += 1
        problems = []
        if bool(fw.get("reliable")) != bool(pc["reliable"]):
            problems.append(f"reliable fw={fw.get('reliable')} pc={pc['reliable']}")
        for key, tol in (("hr", 0.15), ("spo2", 0.15)):
            a, b = fw.get(key), pc[key]
            if (a is None) != (b is None) or (a is not None and abs(a - b) > tol):
                problems.append(f"{key} fw={a} pc={b}")
        if problems:
            self.n_bad += 1
            return "; ".join(problems)
        return None


class Recorder:
    def __init__(self, folder: Path, user: str):
        folder.mkdir(parents=True, exist_ok=True)
        self.user = user
        self.windows = open(folder / "windows.jsonl", "a")
        self.vitals = open(folder / "vitals.jsonl", "a")
        self.events = open(folder / "events.jsonl", "a")
        sticks = folder / "fingersticks.csv"
        new = not sticks.exists()
        self.sticks = open(sticks, "a")
        if new:
            self.sticks.write("user_id,ts,glucose_mgdl,source\n")

    def write(self, fh, obj):
        fh.write(json.dumps(obj) + "\n")
        fh.flush()

    def fingerstick(self, mgdl: float):
        stamp = time.strftime("%Y-%m-%dT%H:%M:%S%z")
        stamp = stamp[:-2] + ":" + stamp[-2:]                  # +0500 -> +05:00
        self.sticks.write(f"{self.user},{stamp},{mgdl:.1f},meter\n")
        self.sticks.flush()


def parse_glucose(text: str) -> float | None:
    """'5.6' / '5,6' (mmol/L) or '101' / '101 mg' (mg/dL) -> mg/dL."""
    parts = text.replace(",", ".").split()
    if not parts:
        return None
    try:
        value = float(parts[0])
    except ValueError:
        return None
    unit = parts[1].lower() if len(parts) > 1 else ""
    if unit.startswith("mmol") or (not unit and value <= 30):
        value *= 18.0
    return value if 20 <= value <= 600 else None


def run(lines, send, recorder: Recorder | None, checker: Checker | None, user: str, out=print):
    """Process bracelet output. ``lines`` yields text lines; ``send(text)`` writes to the console."""
    pending_vitals = {}
    stats = {"windows": 0, "reliable": 0, "raw": 0, "mismatch": 0}
    for line in lines:
        kind, msg = parse_line(line)
        if kind == "vitals":
            stats["windows"] += 1
            stats["reliable"] += bool(msg.get("reliable"))
            out(format_vitals(msg))
            pending_vitals[msg.get("seq")] = msg
            if recorder:
                recorder.write(recorder.vitals, msg)
        elif kind == "raw":
            stats["raw"] += 1
            if recorder:
                recorder.write(recorder.windows, window_record(msg, user))
            if checker:
                fw = pending_vitals.pop(msg["w"].get("seq"), None)
                pc = checker.analyze(msg)
                diff = checker.compare(fw, pc) if fw else None
                if diff:
                    stats["mismatch"] += 1
                    out(f"   !! firmware and PC disagree on window {msg['w'].get('seq')}: {diff}")
        elif kind == "record":
            r = msg["r"]
            out(f"== record {r.get('timestamp')}: pulse {r.get('pulse')} bpm, SpO2 {r.get('spo2')} %, "
                f"{r.get('reliableWindows')}/{r.get('windows')} windows, battery {r.get('battery')} %")
        elif kind == "event":
            out(f"== event: {msg['e'].get('note')}")
            if recorder:
                recorder.write(recorder.events, msg["e"])
        elif kind == "log":
            out(f"-- {msg.get('msg')}")
        elif msg:
            out(msg)
        while len(pending_vitals) > 8:
            pending_vitals.pop(next(iter(pending_vitals)))
    return stats


def keyboard_thread(send, recorder: Recorder | None, stop: threading.Event):
    for text in sys.stdin:
        text = text.strip()
        if text == "q":
            stop.set()
            return
        if text.startswith("g "):
            mgdl = parse_glucose(text[2:])
            if mgdl is None:
                print("   ?? not a glucose value (examples: g 5.6   g 101 mg)")
                continue
            if recorder:
                recorder.fingerstick(mgdl)
            send(f"mark fingerstick {mgdl:.0f} mg/dL")
            print(f"   reference glucose {mgdl:.0f} mg/dL ({mgdl / 18:.1f} mmol/L) stored")
        elif text.startswith("m "):
            send(f"mark {text[2:]}")
        elif text:
            send(text)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", help="serial port of the bracelet, e.g. /dev/ttyACM0 or COM5")
    ap.add_argument("--replay", help="read a saved serial log instead of a port")
    ap.add_argument("--record", help="folder to store raw windows, vitals and fingersticks")
    ap.add_argument("--user", default="u00", help="participant id written to the recorded files")
    ap.add_argument("--check", action="store_true", help="recompute every raw window on the PC and compare")
    a = ap.parse_args()
    if not a.port and not a.replay:
        ap.error("give --port or --replay")

    recorder = Recorder(Path(a.record), a.user) if a.record else None
    checker = Checker() if a.check else None

    if a.replay:
        with open(a.replay, errors="replace") as fh:
            stats = run(fh, lambda s: None, recorder, checker, a.user)
    else:
        import serial  # pyserial

        port = serial.Serial(a.port, 115200, timeout=1)
        stop = threading.Event()

        def send(text: str):
            port.write((text + "\n").encode())

        def lines():
            while not stop.is_set():
                raw = port.readline()
                if raw:
                    yield raw.decode(errors="replace")

        time.sleep(0.5)
        if recorder or checker:
            send("stream on")
        threading.Thread(target=keyboard_thread, args=(send, recorder, stop), daemon=True).start()
        try:
            stats = run(lines(), send, recorder, checker, a.user)
        except KeyboardInterrupt:
            stats = {}
        finally:
            if recorder or checker:
                send("stream off")
            port.close()
    if stats:
        print(f"\n{stats['windows']} windows, {stats['reliable']} reliable, {stats['raw']} raw windows"
              + (f", {stats['mismatch']} firmware/PC mismatches" if checker else ""))
    return 1 if stats and stats.get("mismatch") else 0


if __name__ == "__main__":
    sys.exit(main())
