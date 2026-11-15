"""The firmware sources against the real Arduino-ESP32 headers (front end only).

Runs tools/typecheck_arduino.sh if the packages are already unpacked in the
directory named by SG_ARDUINO_CACHE (the script downloads about 370 MB on
first use, which a test run should not do by itself):

    firmware/tools/typecheck_arduino.sh ~/.cache/suguard-typecheck
    SG_ARDUINO_CACHE=~/.cache/suguard-typecheck python -m pytest firmware/tests/test_typecheck.py
"""
import os
import shutil
import subprocess

import pytest

from conftest import FW


def test_sources_type_check_against_arduino_cores():
    cache = os.environ.get("SG_ARDUINO_CACHE")
    if not cache or not os.path.isdir(os.path.join(cache, "esp32c3-libs")):
        pytest.skip("set SG_ARDUINO_CACHE to a directory prepared by tools/typecheck_arduino.sh")
    if not shutil.which("arm-none-eabi-g++"):
        pytest.skip("needs arm-none-eabi-g++ with newlib and libstdc++")
    run = subprocess.run(["bash", str(FW / "tools" / "typecheck_arduino.sh"), cache], capture_output=True, text=True,
                         timeout=900)
    assert run.returncode == 0, run.stdout[-3000:] + run.stderr[-2000:]
    assert "type-check passed for Arduino core 2.0.17 and 3.3.12" in run.stdout
