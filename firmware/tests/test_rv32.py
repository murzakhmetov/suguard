"""The portable core on the ESP32-C3's instruction set (RV32IMC, soft-float).

Cross-compiles the complete pipeline (signal processing + integer network)
with the distro RISC-V GCC, runs it bare-metal under QEMU and checks that it
produces the same results as the host build and the Python reference. Also
counts executed instructions per window, the basis of the timing estimate in
firmware/README.md (written to firmware/docs/rv32_benchmark.json when
SG_WRITE_BENCH=1).

This is NOT the ESP32 toolchain or the real chip: it proves that the code is
correct for a 32-bit RISC-V target without FPU, not that the Arduino build
links.
"""
import json
import os
import shutil
import subprocess

import numpy as np
import pytest

from conftest import CORE, FW, ML, build_host

from suguard_ml.pipeline import SuGuardPipeline  # noqa: E402
from suguard_ml.synth.ppg import simulate_window  # noqa: E402

RV_GXX = shutil.which("riscv64-unknown-elf-g++")
QEMU = shutil.which("qemu-system-riscv32")
pytestmark = pytest.mark.skipif(not (RV_GXX and QEMU), reason="RISC-V toolchain or QEMU not installed")

RV_FLAGS = ["-march=rv32imc_zicsr", "-mabi=ilp32", "-O2", "-Wall", "-Wextra", "-Werror", "-fno-exceptions",
            "-fno-rtti", "-fno-threadsafe-statics", "-nostdlib++", "--specs=picolibc.specs", "--oslib=semihost",
            "--crt0=hosted", "-Wl,--defsym=__flash=0x80000000", "-Wl,--defsym=__flash_size=0x00800000",
            "-Wl,--defsym=__ram=0x80800000", "-Wl,--defsym=__ram_size=0x00800000"]

# (seed, kwargs): clean, light motion, heavy motion, weak pulse, not worn is added separately
CASES = [(11, dict(kinds=[])), (12, dict(kinds=[], pi_ir=0.002)), (13, dict(kinds=["burst"], artifact_level=1.5)),
         (14, dict(kinds=["periodic"], artifact_level=4.0)), (15, dict(kinds=["periodic", "step"], artifact_level=10.0))]


def windows():
    ws = [(simulate_window(seed, **kw).red_raw, simulate_window(seed, **kw).ir_raw) for seed, kw in CASES]
    dark = np.random.default_rng(0).normal(900, 4, (2, 512)).round()
    ws.append((dark[0], dark[1]))
    return [(np.asarray(r, dtype=np.uint32), np.asarray(i, dtype=np.uint32)) for r, i in ws]


def write_header(path, ws):
    def arr(name, rows):
        body = ",\n".join("  {" + ",".join(map(str, row)) + "}" for row in rows)
        return f"static const uint32_t {name}[BENCH_N][512] = {{\n{body}\n}};\n"
    path.write_text("#pragma once\n#include <stdint.h>\n"
                    f"#define BENCH_N {len(ws)}\n" + arr("bench_red", [w[0] for w in ws]) + arr("bench_ir", [w[1] for w in ws]))


def parse(stdout):
    return [json.loads(line) for line in stdout.splitlines() if line.startswith("{")]


def test_rv32_matches_host_and_python(build_dir):
    if not (CORE / "sg_model.h").exists():
        pytest.skip("edge model not exported yet")
    ws = windows()
    write_header(build_dir / "bench_windows.h", ws)
    sources = [FW / "tests" / "host" / "rv32_bench.cpp", *sorted(CORE.glob("*.cpp"))]

    host = build_host(sources, build_dir / "rv32_bench_host", extra=["-I", str(build_dir)])
    host_rows = parse(subprocess.run([str(host)], capture_output=True, text=True, check=True).stdout)

    elf = build_dir / "rv32_bench.elf"
    build = subprocess.run([RV_GXX, *RV_FLAGS, "-I", str(CORE), "-I", str(build_dir), *map(str, sources), "-lm",
                            "-o", str(elf)], capture_output=True, text=True)
    assert build.returncode == 0, build.stderr[-4000:]
    run = subprocess.run([QEMU, "-M", "virt", "-bios", "none", "-nographic", "-icount", "shift=0",
                          "-semihosting-config", "enable=on,target=native", "-kernel", str(elf)],
                         capture_output=True, text=True, timeout=1800)
    rv_rows = parse(run.stdout + "\n" + run.stderr)       # QEMU routes semihosting output to its stderr
    assert len(rv_rows) == len(host_rows) == 1 + 2 * len(ws), run.stdout[-2000:] + run.stderr[-2000:]

    # RV32 soft-float == host: same decisions, same numbers.
    for h, r in zip(host_rows[1:], rv_rows[1:]):
        for key in ("i", "nn", "reliable", "has_hr", "has_spo2", "reasons", "n_beats"):
            assert h[key] == r[key], (key, h, r)
        for key, tol in (("hr", 1e-6), ("spo2", 1e-6), ("sqi", 1e-4), ("pi_in", 1e-9), ("motion", 1e-6)):
            assert r[key] == pytest.approx(h[key], abs=tol), (key, h, r)

    # Host == Python reference (the full parity suites are test_core_parity.py / test_pipeline_parity.py).
    from suguard_ml.models.edge_int import EdgeDenoiserInt
    pipes = {0: SuGuardPipeline(denoiser=None), 1: SuGuardPipeline(denoiser=EdgeDenoiserInt.load())}
    for h in host_rows[1:]:
        red, ir = ws[h["i"]]
        ref = pipes[h["nn"]].analyze(red, ir, fs=50.0)
        assert bool(h["reliable"]) == ref["reliable"]
        if ref["heart_rate"]["bpm"] is not None:
            assert h["hr"] == pytest.approx(ref["heart_rate"]["bpm"], abs=0.051)
        if ref["spo2"]["percent"] is not None:
            assert h["spo2"] == pytest.approx(ref["spo2"]["percent"], abs=0.051)

    # Timing basis: executed instructions per window on RV32IMC.
    nn = [r["instr"] for r in rv_rows[1:] if r["nn"] == 1]
    classical = [r["instr"] for r in rv_rows[1:] if r["nn"] == 0]
    size = subprocess.run(["riscv64-unknown-elf-size", str(elf)], capture_output=True, text=True).stdout.splitlines()[-1].split()
    # The signal core alone (network weights included): its object files, without the benchmark
    # harness, picolibc and the test windows that the program above also contains.
    objs = []
    for src in sorted(CORE.glob("*.cpp")):
        obj = build_dir / f"{src.stem}.rv32.o"
        cc = subprocess.run([RV_GXX, *[f for f in RV_FLAGS if not f.startswith(("-Wl,", "--oslib", "--crt0"))],
                             "-I", str(CORE), "-c", str(src), "-o", str(obj)], capture_output=True, text=True)
        assert cc.returncode == 0, cc.stderr[-2000:]
        objs.append(str(obj))
    rows = subprocess.run(["riscv64-unknown-elf-size", *objs], capture_output=True, text=True).stdout.splitlines()[1:]
    core_bytes = sum(int(r.split()[0]) + int(r.split()[1]) for r in rows)
    bench = {"instructions_per_window": {"with_nn": {"median": int(np.median(nn)), "max": int(max(nn))},
                                         "classical": {"median": int(np.median(classical)), "max": int(max(classical))}},
             "static_ram_bytes": rv_rows[0]["static_bytes"],
             "signal_core_code_and_constants_bytes": core_bytes,
             "benchmark_program_code_and_constants_bytes": int(size[0]) + int(size[1]),
             "note": "QEMU instruction counts for -march=rv32imc -O2 with picolibc soft-float; "
                     "not a measurement on the ESP32-C3"}
    print(json.dumps(bench))
    assert max(nn) < 400e6            # must stay far below real time (10.24 s at 160 MHz = 1.6e9 cycles)
    if os.environ.get("SG_WRITE_BENCH") == "1":
        (FW / "docs" / "rv32_benchmark.json").write_text(json.dumps(bench, indent=2) + "\n")
