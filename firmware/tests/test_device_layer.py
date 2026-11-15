"""Device layer (MAX30102 driver, sampler, battery, config, console, cloud
formatting) against a register-level sensor simulator, built with sanitizers."""
import subprocess

from conftest import FW

SRC = FW / "suguard" / "src"
SOURCES = [FW / "tests" / "host" / "test_device.cpp", SRC / "app" / "sampler.cpp", SRC / "app" / "battery.cpp",
           SRC / "app" / "config.cpp", SRC / "app" / "cloud_fmt.cpp", SRC / "app" / "cli.cpp",
           SRC / "app" / "aggregate.cpp", SRC / "app" / "store.cpp", SRC / "app" / "uplink.cpp",
           SRC / "app" / "power.cpp", SRC / "drivers" / "max30102.cpp"]


def test_device_layer(build_dir):
    exe = build_dir / "test_device"
    cmd = ["g++", "-std=gnu++17", "-O1", "-g", "-Wall", "-Wextra", "-Werror",
           "-fsanitize=address,undefined", "-fno-sanitize-recover=all", *map(str, SOURCES), "-o", str(exe)]
    build = subprocess.run(cmd, capture_output=True, text=True)
    assert build.returncode == 0, build.stderr[-3000:]
    run = subprocess.run([str(exe)], capture_output=True, text=True, timeout=300)
    assert run.returncode == 0, run.stdout[-3000:] + run.stderr[-3000:]
    assert "ALL OK" in run.stdout
    assert run.stdout.count("PASS ") >= 24
