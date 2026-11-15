"""The C++ integer engine (sg_nn.cpp) must be bit-identical to edge_int.run_int."""
import subprocess

import numpy as np
import pytest

from conftest import CORE, FW, ML, build_host

torch = pytest.importorskip("torch")

from suguard_ml.models import edge_int as E  # noqa: E402
from suguard_ml.models.denoiser_net import EdgeUNet  # noqa: E402


def _run_cli(build_dir, header, xq, tag):
    exe = build_host([FW / "tests" / "host" / "nn_cli.cpp", CORE / "sg_nn.cpp"], build_dir / f"nn_cli_{tag}",
                     extra=[f'-DSG_MODEL_HEADER="{header}"'])
    fin, fout = build_dir / f"nn_in_{tag}.bin", build_dir / f"nn_out_{tag}.bin"
    xq.astype("<i2").tofile(fin)
    subprocess.run([str(exe), str(fin), str(fout)], check=True, capture_output=True)
    return np.fromfile(fout, dtype="<i2").reshape(xq.shape[0], -1, xq.shape[-1])


def _inputs(n, seed):
    """Realistic inputs (pulse-like + noise) plus extreme ones that exercise saturation."""
    rng = np.random.default_rng(seed)
    t = np.arange(512) / 50.0
    x = np.zeros((n, 2, 512))
    for i in range(n):
        f = rng.uniform(0.8, 2.5)
        x[i, 0] = np.sin(2 * np.pi * f * t + rng.uniform(0, 6)) + rng.normal(0, rng.uniform(0, 3), 512)
        x[i, 1] = 0.6 * x[i, 0] + rng.normal(0, 0.2, 512)
    x[-1] = 12.0                      # stuck at the clip
    x[-2] = -12.0
    x[-3] = rng.choice([-12.0, 12.0], size=(2, 512))
    x[-4] = 0.0
    return np.floor(np.clip(x, -12, 12) * (1 << E.IN_FB) + 0.5).astype(np.int16)


def test_random_models_bit_exact(build_dir):
    """Fresh random networks: exporter, header writer and engine agree exactly."""
    for seed, chans in ((0, (8, 16, 24, 32)), (1, (4, 6, 8, 10))):
        torch.manual_seed(seed)
        model = EdgeUNet(chans=chans)
        model.train()
        with torch.no_grad():                    # give batch-norm non-trivial statistics
            for _ in range(4):
                model(torch.randn(16, 2, 512) * 2)
        tensors, ops = E.graph_from_edge_unet(model)
        calib = np.random.default_rng(seed).normal(0, 1.5, (32, 2, 512)).clip(-12, 12)
        im = E.quantize(tensors, ops, calib, meta={"name": f"random{seed}"})
        header = build_dir / f"model_random{seed}.h"
        E.write_c_header(im, header)
        xq = _inputs(12, seed)
        assert np.array_equal(_run_cli(build_dir, header, xq, f"r{seed}"), E.run_int(im, xq))


def test_committed_model_matches_reference(build_dir):
    """The header compiled into the firmware is the model stored in ml/models."""
    header = CORE / "sg_model.h"
    npz = ML / "models" / "denoiser_edge_int.npz"
    if not (header.exists() and npz.exists()):
        pytest.skip("edge model not exported yet")
    im = E.load(npz)
    regenerated = build_dir / "sg_model_regen.h"
    E.write_c_header(im, regenerated)
    assert regenerated.read_text() == header.read_text(), "run ml/scripts/export_edge_model.py"
    xq = _inputs(16, 7)
    assert np.array_equal(_run_cli(build_dir, header, xq, "committed"), E.run_int(im, xq))


def test_arena_plan_has_no_live_overlap():
    torch.manual_seed(3)
    tensors, ops = E.graph_from_edge_unet(EdgeUNet().eval())
    im = E.quantize(tensors, ops, np.zeros((2, 2, 512)))
    birth, last = {0: -1}, {0: -1}
    for i, op in enumerate(im.ops):
        birth[op.out] = i
        last.setdefault(op.out, i)
        for t in op.inputs:
            last[t] = i
    last[im.ops[-1].out] = len(im.ops)
    ids = list(birth)
    for a in ids:
        for b in ids:
            if a < b and not (last[a] < birth[b] or birth[a] > last[b]):
                ta, tb = im.tensors[a], im.tensors[b]
                assert ta.offset + ta.size <= tb.offset or tb.offset + tb.size <= ta.offset
    assert max(t.offset + t.size for t in im.tensors) == im.arena_size
