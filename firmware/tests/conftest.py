"""Shared fixtures for the firmware host tests.

The portable firmware core (firmware/suguard/src/core) is compiled with the
host g++ and compared against the Python reference in ml/suguard_ml.
"""
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
FW = ROOT / "firmware"
CORE = FW / "suguard" / "src" / "core"
ML = ROOT / "ml"
if str(ML) not in sys.path:
    sys.path.insert(0, str(ML))

CXXFLAGS = ["-std=gnu++17", "-O2", "-Wall", "-Wextra", "-Werror", "-fno-exceptions", "-fno-rtti"]


def build_host(sources, out: Path, extra=()):
    """Compile ``sources`` with the host g++ into ``out`` (rebuilt every time: it takes seconds)."""
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["g++", *CXXFLAGS, *extra, "-I", str(CORE), *map(str, sources), "-lm", "-o", str(out)]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError("host build failed:\n" + " ".join(cmd) + "\n" + res.stderr[-4000:])
    return out


@pytest.fixture(scope="session")
def build_dir(tmp_path_factory):
    return tmp_path_factory.mktemp("fwbuild")
