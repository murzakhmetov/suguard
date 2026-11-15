"""Fixed-point form of the edge denoiser (EdgeUNet) for the ESP32-C3 firmware.

The ESP32-C3 has no FPU, so the firmware runs the network in integers:

* activations: int16 with a per-tensor number of fractional bits ``fb``
  (real value = q / 2**fb), chosen from calibration data
* weights: int8, symmetric, one scale per output channel
* accumulators: int32, proven overflow-free at export time
* re-quantisation: per-channel 31-bit multiplier and right shift,
  ``y = (acc * m0 + 2**(shift-1)) >> shift``, then saturation to int16, then ReLU

Three operations only: CONV (1 or 2 inputs = channel concatenation, kernel k,
dilation d, zero "same" padding), AVGPOOL2 ``(a + b + 1) >> 1`` and UPSAMPLE2
(sample repetition).

This module (1) folds batch-norm and quantises a trained EdgeUNet, (2) is the
bit-exact NumPy reference of the firmware engine (firmware/suguard/src/core/
sg_nn.cpp is tested against it), (3) writes the C header with the weights and
(4) wraps the integer model as a drop-in ``Denoiser`` for the Python pipeline,
so that every accuracy number reported for the device comes from the same
arithmetic the device executes.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from ..config import FS, WINDOW
from .denoiser import INPUT_CLIP, Denoised

FORMAT_VERSION = 1
IN_FB = 11                      # input: +-12 clip -> +-24576 in Q4.11
MAX_FB = 14
CALIB_MARGIN = 1.25             # headroom over the largest calibration activation

OP_CONV, OP_AVGPOOL2, OP_UPSAMPLE2 = 0, 1, 2


# ---------------------------------------------------------------------------
# Graph description
# ---------------------------------------------------------------------------

@dataclass
class Tensor:
    channels: int
    length: int
    fb: int = 0                 # fractional bits (set by quantisation)
    offset: int = -1            # position in the int16 arena (set by the planner)

    @property
    def size(self) -> int:
        return self.channels * self.length


@dataclass
class Op:
    kind: int
    inputs: list[int]
    out: int
    k: int = 1
    dil: int = 1
    relu: bool = False
    w: np.ndarray | None = None          # float (O, I, K) before quantisation, int8 after
    b: np.ndarray | None = None          # float (O,) / int32
    m0: np.ndarray | None = None         # int32 (O,)
    shift: np.ndarray | None = None      # uint8 (O,)


@dataclass
class IntModel:
    tensors: list[Tensor]
    ops: list[Op]
    arena_size: int = 0                  # int16 elements
    meta: dict = field(default_factory=dict)

    @property
    def out_tensor(self) -> Tensor:
        return self.tensors[self.ops[-1].out]

    @property
    def n_params(self) -> int:
        return int(sum(op.w.size + op.b.size for op in self.ops if op.kind == OP_CONV))

    @property
    def macs(self) -> int:
        return int(sum(op.w.size * self.tensors[op.out].length for op in self.ops if op.kind == OP_CONV))


# ---------------------------------------------------------------------------
# EdgeUNet -> float graph with batch-norm folded
# ---------------------------------------------------------------------------

def _fold(conv, bn) -> tuple[np.ndarray, np.ndarray]:
    w = conv.weight.detach().cpu().numpy().astype(np.float64)
    b = conv.bias.detach().cpu().numpy().astype(np.float64)
    if bn is not None:
        g = bn.weight.detach().cpu().numpy().astype(np.float64)
        beta = bn.bias.detach().cpu().numpy().astype(np.float64)
        mu = bn.running_mean.detach().cpu().numpy().astype(np.float64)
        var = bn.running_var.detach().cpu().numpy().astype(np.float64)
        s = g / np.sqrt(var + bn.eps)
        w = w * s[:, None, None]
        b = (b - mu) * s + beta
    return w, b


def graph_from_edge_unet(model, length: int = WINDOW) -> tuple[list[Tensor], list[Op]]:
    """Float graph (weights float64) equivalent to ``EdgeUNet.eval()``."""
    model = model.eval()
    tensors: list[Tensor] = [Tensor(model.enc[0].body[0].in_channels, length)]
    ops: list[Op] = []

    def new(c, n):
        tensors.append(Tensor(c, n))
        return len(tensors) - 1

    def block(body, inputs, n):
        x = inputs
        for i in range(0, len(body), 3):
            conv, bn = body[i], body[i + 1]
            w, b = _fold(conv, bn)
            out = new(conv.out_channels, n)
            ops.append(Op(OP_CONV, list(x), out, k=conv.kernel_size[0], dil=conv.dilation[0], relu=True, w=w, b=b))
            x = [out]
        return x[0]

    x, n, skips = 0, length, []
    for enc in model.enc:
        x = block(enc.body, [x], n)
        skips.append(x)
        n //= 2
        p = new(tensors[x].channels, n)
        ops.append(Op(OP_AVGPOOL2, [x], p))
        x = p
    x = block(model.mid.body, [x], n)
    for dec, s in zip(model.dec, reversed(skips)):
        n *= 2
        u = new(tensors[x].channels, n)
        ops.append(Op(OP_UPSAMPLE2, [x], u))
        x = block(dec.body, [u, s], n)           # order [upsampled, skip], as in EdgeUNet.forward
    w, b = _fold(model.head, None)
    out = new(model.head.out_channels, n)
    ops.append(Op(OP_CONV, [x], out, k=1, dil=1, relu=False, w=w, b=b))
    return tensors, ops


# ---------------------------------------------------------------------------
# Execution (shared by the float and the integer graph)
# ---------------------------------------------------------------------------

def _windows(x: np.ndarray, k: int, dil: int) -> np.ndarray:
    """(B, C, L) -> (B, C, K, L): the K dilated taps of a zero-padded 'same' convolution."""
    half = (k - 1) // 2 * dil
    xp = np.pad(x, ((0, 0), (0, 0), (half, half)))
    n = x.shape[-1]
    return np.stack([xp[..., j * dil: j * dil + n] for j in range(k)], axis=2)


def run_float(tensors: list[Tensor], ops: list[Op], x: np.ndarray, keep_all: bool = False):
    """Float execution of the folded graph. ``x``: (B, C, L) float64."""
    vals: dict[int, np.ndarray] = {0: np.asarray(x, dtype=np.float64)}
    for op in ops:
        a = vals[op.inputs[0]] if len(op.inputs) == 1 else np.concatenate([vals[i] for i in op.inputs], axis=1)
        if op.kind == OP_CONV:
            y = np.einsum("oik,bikl->bol", op.w, _windows(a, op.k, op.dil), optimize=True) + op.b[None, :, None]
            if op.relu:
                y = np.maximum(y, 0.0)
        elif op.kind == OP_AVGPOOL2:
            y = 0.5 * (a[..., 0::2] + a[..., 1::2])
        else:
            y = np.repeat(a, 2, axis=-1)
        vals[op.out] = y
    return vals if keep_all else vals[ops[-1].out]


def run_int(model: IntModel, xq: np.ndarray) -> np.ndarray:
    """Bit-exact reference of the firmware engine. ``xq``: (B, C, L) int16 -> (B, C_out, L) int16."""
    vals: dict[int, np.ndarray] = {0: np.asarray(xq, dtype=np.int64)}
    for op in model.ops:
        a = vals[op.inputs[0]] if len(op.inputs) == 1 else np.concatenate([vals[i] for i in op.inputs], axis=1)
        if op.kind == OP_CONV:
            acc = np.einsum("oik,bikl->bol", op.w.astype(np.int64), _windows(a, op.k, op.dil), optimize=True)
            acc = acc + op.b.astype(np.int64)[None, :, None]
            if np.abs(acc).max(initial=0) >= 2**31:
                raise OverflowError("int32 accumulator overflow (export-time bound violated)")
            sh = op.shift.astype(np.int64)[None, :, None]
            y = (acc * op.m0.astype(np.int64)[None, :, None] + (np.int64(1) << (sh - 1))) >> sh
            y = np.clip(y, -32768, 32767)
            if op.relu:
                y = np.maximum(y, 0)
        elif op.kind == OP_AVGPOOL2:
            y = (a[..., 0::2] + a[..., 1::2] + 1) >> 1
        else:
            y = np.repeat(a, 2, axis=-1)
        vals[op.out] = y
    return vals[model.ops[-1].out].astype(np.int16)


# ---------------------------------------------------------------------------
# Quantisation
# ---------------------------------------------------------------------------

def _quantize_multiplier(m: float) -> tuple[int, int]:
    """m = m0 * 2**-shift with m0 in [2**30, 2**31)."""
    if not (m > 0 and np.isfinite(m)):
        raise ValueError(f"bad multiplier {m}")
    e = int(np.floor(np.log2(m)))
    m0 = int(round(m * 2.0 ** (30 - e)))
    if m0 >= 2**31:
        m0 //= 2
        e += 1
    shift = 30 - e
    if not 1 <= shift <= 62:
        raise ValueError(f"multiplier {m} out of range (shift {shift})")
    return m0, shift


def _plan_arena(tensors: list[Tensor], ops: list[Op]) -> int:
    """Place tensors in one arena by lifetime (largest first, lowest free offset).

    A tensor lives from the op that produces it to its last consumer. Inputs
    and output of an op are alive together, so no op reads memory it is
    writing. Returns the arena size in int16 elements.
    """
    birth = {0: -1}
    last = {0: -1}
    for i, op in enumerate(ops):
        birth[op.out] = i
        last.setdefault(op.out, i)
        for t in op.inputs:
            last[t] = i
    last[ops[-1].out] = len(ops)                      # the output must survive the run
    placed: list[tuple[int, int, int, int]] = []      # (offset, size, birth, last)
    for t in sorted(birth, key=lambda t: (-tensors[t].size, birth[t])):
        size = tensors[t].size
        busy = sorted((o, s) for o, s, b, l in placed if not (l < birth[t] or b > last[t]))
        off = 0
        for o, s in busy:
            if off + size <= o:
                break
            off = max(off, o + s)
        tensors[t].offset = off
        placed.append((off, size, birth[t], last[t]))
    return max(o + s for o, s, _, _ in placed)


def quantize(tensors: list[Tensor], ops: list[Op], calib_x: np.ndarray, meta: dict | None = None) -> IntModel:
    """Post-training quantisation of the folded float graph.

    ``calib_x``: (N, 2, L) float network inputs (already normalised/clipped).
    """
    vals = run_float(tensors, ops, calib_x, keep_all=True)
    absmax = {t: float(np.abs(v).max()) for t, v in vals.items()}

    # Tensors that must share a scale: pool/upsample outputs with their input,
    # and the two inputs of a concatenating convolution.
    parent = list(range(len(tensors)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for op in ops:
        if op.kind != OP_CONV:
            parent[find(op.out)] = find(op.inputs[0])
        elif len(op.inputs) == 2:
            parent[find(op.inputs[1])] = find(op.inputs[0])
    group_max: dict[int, float] = {}
    for t in range(len(tensors)):
        g = find(t)
        group_max[g] = max(group_max.get(g, 0.0), absmax[t])
    qt = [Tensor(t.channels, t.length) for t in tensors]
    for t in range(len(tensors)):
        if find(t) == find(0):
            qt[t].fb = IN_FB                                   # fixed input format
        else:
            m = max(group_max[find(t)] * CALIB_MARGIN, 1e-6)
            qt[t].fb = int(min(MAX_FB, np.floor(np.log2(32767.0 / m))))
    if any(find(t) == find(0) for t in range(1, len(tensors))):
        raise ValueError("the input tensor must not share a scale with another tensor")

    qops: list[Op] = []
    for op in ops:
        if op.kind != OP_CONV:
            qops.append(Op(op.kind, list(op.inputs), op.out))
            continue
        fb_in, fb_out = qt[op.inputs[0]].fb, qt[op.out].fb
        if any(qt[i].fb != fb_in for i in op.inputs):
            raise AssertionError("concatenated inputs must share fractional bits")
        o = op.w.shape[0]
        s_w = np.abs(op.w).reshape(o, -1).max(axis=1) / 127.0
        s_w[s_w == 0] = 1.0
        wq = np.clip(np.rint(op.w / s_w[:, None, None]), -127, 127).astype(np.int8)
        bq = np.rint(op.b / (s_w * 2.0 ** -fb_in))
        bound = np.abs(wq.astype(np.int64)).reshape(o, -1).sum(axis=1) * 32768 + np.abs(bq)
        if bound.max() >= 2**31 - 1:
            raise OverflowError(f"int32 accumulator could overflow in op -> tensor {op.out} (bound {bound.max():.3g})")
        m0, sh = zip(*[_quantize_multiplier(float(s) * 2.0 ** (fb_out - fb_in)) for s in s_w])
        qops.append(Op(OP_CONV, list(op.inputs), op.out, k=op.k, dil=op.dil, relu=op.relu, w=wq,
                       b=bq.astype(np.int32), m0=np.array(m0, dtype=np.int32), shift=np.array(sh, dtype=np.uint8)))
    arena = _plan_arena(qt, qops)
    model = IntModel(qt, qops, arena_size=int(arena), meta=dict(meta or {}))
    model.meta.update(format=FORMAT_VERSION, in_fb=IN_FB, out_fb=model.out_tensor.fb,
                      calib_windows=int(calib_x.shape[0]), n_params=model.n_params, macs=model.macs)
    return model


# ---------------------------------------------------------------------------
# Serialisation
# ---------------------------------------------------------------------------

def save(model: IntModel, path: str | Path) -> None:
    arrays, ops = {}, []
    for i, op in enumerate(model.ops):
        d = {"kind": op.kind, "inputs": op.inputs, "out": op.out, "k": op.k, "dil": op.dil, "relu": bool(op.relu)}
        if op.kind == OP_CONV:
            for name in ("w", "b", "m0", "shift"):
                arrays[f"op{i}_{name}"] = getattr(op, name)
        ops.append(d)
    spec = {"tensors": [[t.channels, t.length, t.fb, t.offset] for t in model.tensors], "ops": ops,
            "arena_size": model.arena_size, "meta": model.meta}
    np.savez_compressed(path, spec=np.array(json.dumps(spec)), **arrays)


def load(path: str | Path) -> IntModel:
    z = np.load(path)
    spec = json.loads(str(z["spec"]))
    tensors = [Tensor(c, n, fb, off) for c, n, fb, off in spec["tensors"]]
    ops = []
    for i, d in enumerate(spec["ops"]):
        op = Op(d["kind"], d["inputs"], d["out"], k=d["k"], dil=d["dil"], relu=d["relu"])
        if op.kind == OP_CONV:
            op.w, op.b, op.m0, op.shift = (z[f"op{i}_{n}"] for n in ("w", "b", "m0", "shift"))
        ops.append(op)
    return IntModel(tensors, ops, arena_size=spec["arena_size"], meta=spec["meta"])


def _c_array(ctype: str, name: str, values: np.ndarray, per_line: int = 24) -> str:
    flat = [str(int(v)) for v in np.asarray(values).reshape(-1)]
    lines = [", ".join(flat[i:i + per_line]) for i in range(0, len(flat), per_line)]
    return f"static const {ctype} {name}[{len(flat)}] = {{\n  " + ",\n  ".join(lines) + "\n};\n"


def write_c_header(model: IntModel, path: str | Path) -> None:
    """Weights + op table for firmware/suguard/src/core/sg_nn.cpp."""
    out = ["// GENERATED by ml/scripts/export_edge_model.py - do not edit.",
           "// Edge denoiser (integer form). See ml/suguard_ml/models/edge_int.py for the format.",
           "#pragma once", "", '#include "sg_nn.h"', "",
           f"#define SG_MODEL_FORMAT {model.meta['format']}",
           f"#define SG_MODEL_IN_FB {model.meta['in_fb']}",
           f"#define SG_MODEL_OUT_FB {model.meta['out_fb']}",
           f"#define SG_MODEL_ARENA {model.arena_size}        // int16 elements",
           f"#define SG_MODEL_N_OPS {len(model.ops)}",
           f"#define SG_MODEL_IN_OFFSET {model.tensors[0].offset}",
           f"#define SG_MODEL_OUT_OFFSET {model.out_tensor.offset}",
           f"#define SG_MODEL_OUT_CHANNELS {model.out_tensor.channels}",
           f"#define SG_MODEL_PARAMS {model.n_params}",
           f"#define SG_MODEL_MACS {model.macs}",
           f"// {json.dumps({k: v for k, v in model.meta.items() if k in ('name', 'trained_steps', 'chans')})}", ""]
    rows = []
    for i, op in enumerate(model.ops):
        ta = model.tensors[op.inputs[0]]
        tb = model.tensors[op.inputs[1]] if len(op.inputs) == 2 else None
        to = model.tensors[op.out]
        if op.kind == OP_CONV:
            out += [_c_array("int8_t", f"SG_W{i}", op.w), _c_array("int32_t", f"SG_B{i}", op.b),
                    _c_array("int32_t", f"SG_M{i}", op.m0), _c_array("uint8_t", f"SG_S{i}", op.shift)]
            ptrs = f"SG_W{i}, SG_B{i}, SG_M{i}, SG_S{i}"
        else:
            ptrs = "nullptr, nullptr, nullptr, nullptr"
        rows.append(f"  {{{op.kind}, {int(op.relu)}, {op.k}, {op.dil}, {ta.channels}, {tb.channels if tb else 0}, "
                    f"{to.channels}, {to.length}, {ta.offset}, {tb.offset if tb else 0}, {to.offset}, {ptrs}}},")
    out += ["static const SgNnOp SG_MODEL_OPS[SG_MODEL_N_OPS] = {", *rows, "};", ""]
    Path(path).write_text("\n".join(out))


# ---------------------------------------------------------------------------
# Runtime wrapper (drop-in for models.denoiser.Denoiser)
# ---------------------------------------------------------------------------

def quantize_input(ir_bv: np.ndarray, red_bv: np.ndarray) -> tuple[np.ndarray, float]:
    """Exactly what the firmware does (sg_pipeline.cpp): float64 throughout."""
    scale = float(np.std(ir_bv))
    if not np.isfinite(scale) or scale < 1e-9:
        scale = 1e-9
    x = np.clip(np.stack([ir_bv, red_bv]) / scale, -INPUT_CLIP, INPUT_CLIP)
    return np.floor(x * (1 << IN_FB) + 0.5).astype(np.int16), scale


class EdgeDenoiserInt:
    """Integer edge denoiser with the interface of ``Denoiser``.

    For full 10.24-s windows the result is bit-identical to the firmware.
    Other lengths are split into full windows with 50 % overlap (the firmware
    never does this; it is only for analysing longer recordings in Python).
    """

    def __init__(self, model: IntModel | str | Path):
        self.model = model if isinstance(model, IntModel) else load(model)
        self.out_fb = self.model.out_tensor.fb

    @classmethod
    def load(cls, models_dir: str | Path | None = None) -> "EdgeDenoiserInt":
        d = Path(models_dir) if models_dir else Path(__file__).resolve().parents[2] / "models"
        return cls(d / "denoiser_edge_int.npz")

    def run(self, x: np.ndarray) -> np.ndarray:
        """Same contract as ``Denoiser.run``: normalised input (B, 2, WINDOW) ->
        (B, 3, WINDOW) float (clean IR, clean red, artefact logit)."""
        xq = np.floor(np.clip(np.asarray(x, dtype=np.float64), -INPUT_CLIP, INPUT_CLIP) * (1 << IN_FB) + 0.5)
        return (run_int(self.model, xq.astype(np.int16)).astype(np.float64) / (1 << self.out_fb)).astype(np.float32)

    def _window(self, ir_bv: np.ndarray, red_bv: np.ndarray):
        xq, scale = quantize_input(ir_bv, red_bv)
        y = run_int(self.model, xq[None])[0].astype(np.float64) / (1 << self.out_fb)
        return y[0] * scale, y[1] * scale, 1.0 / (1.0 + np.exp(-y[2]))

    def denoise_bv(self, ir_bv: np.ndarray, red_bv: np.ndarray, fs: float = FS) -> Denoised:
        if abs(fs - FS) > 1e-6:
            raise ValueError(f"denoiser expects {FS} Hz input, got {fs}")
        ir_bv = np.asarray(ir_bv, dtype=np.float64)
        red_bv = np.asarray(red_bv, dtype=np.float64)
        n = ir_bv.size
        if n == WINDOW:
            ir, red, p = self._window(ir_bv, red_bv)
            return Denoised(ir_bv=ir, red_bv=red, artifact_prob=p, fs=fs)
        if n < WINDOW:
            def ext(v):
                return np.resize(np.concatenate([v, v[::-1]]), WINDOW)
            ir, red, p = self._window(ext(ir_bv), ext(red_bv))
            return Denoised(ir_bv=ir[:n], red_bv=red[:n], artifact_prob=p[:n], fs=fs)
        hop = WINDOW // 2
        starts = list(range(0, n - WINDOW + 1, hop))
        if starts[-1] != n - WINDOW:
            starts.append(n - WINDOW)
        taper = np.hanning(WINDOW + 2)[1:-1]
        acc, wsum = np.zeros((3, n)), np.zeros(n)
        for s in starts:
            ir, red, p = self._window(ir_bv[s:s + WINDOW], red_bv[s:s + WINDOW])
            acc[0, s:s + WINDOW] += taper * ir
            acc[1, s:s + WINDOW] += taper * red
            acc[2, s:s + WINDOW] += taper * p
            wsum[s:s + WINDOW] += taper
        acc /= np.maximum(wsum, 1e-9)
        return Denoised(ir_bv=acc[0], red_bv=acc[1], artifact_prob=acc[2], fs=fs)
