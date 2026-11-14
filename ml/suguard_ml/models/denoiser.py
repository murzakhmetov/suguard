"""Runtime for the motion-artefact denoiser (NumPy + ONNX Runtime, no PyTorch)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from ..config import FS, WINDOW
from ..signal.filters import preprocess

INPUT_CLIP = 12.0


def model_input(red_raw: np.ndarray, ir_raw: np.ndarray, fs: float = FS) -> tuple[np.ndarray, float, np.ndarray, np.ndarray]:
    """Raw counts -> network input ``(2, n)`` plus the scale and both DCs.

    Both channels are divided by the same factor (the IR std) so the red/IR
    amplitude ratio survives normalisation.
    """
    ir_bv, ir_dc = preprocess(ir_raw, fs)
    red_bv, red_dc = preprocess(red_raw, fs)
    return normalise(ir_bv, red_bv) + (ir_dc, red_dc)


def normalise(ir_bv: np.ndarray, red_bv: np.ndarray) -> tuple[np.ndarray, float]:
    scale = float(np.std(ir_bv))
    if not np.isfinite(scale) or scale < 1e-9:
        scale = 1e-9
    x = np.stack([ir_bv, red_bv]).astype(np.float32) / scale
    return np.clip(x, -INPUT_CLIP, INPUT_CLIP), scale


@dataclass
class Denoised:
    ir_bv: np.ndarray            # clean IR blood-volume signal (AC/DC units)
    red_bv: np.ndarray           # clean red blood-volume signal
    artifact_prob: np.ndarray    # per-sample probability that motion dominated
    fs: float


def _sigmoid(x):
    return 1.0 / (1.0 + np.exp(-x))


class Denoiser:
    """ONNX Runtime wrapper. ``Denoiser.load()`` uses the bundled model."""

    def __init__(self, onnx_path: str | Path):
        import onnxruntime as ort

        opts = ort.SessionOptions()
        opts.intra_op_num_threads = 1
        opts.inter_op_num_threads = 1
        self.session = ort.InferenceSession(str(onnx_path), sess_options=opts, providers=["CPUExecutionProvider"])
        self.input_name = self.session.get_inputs()[0].name
        self.path = Path(onnx_path)

    @classmethod
    def load(cls, models_dir: str | Path | None = None) -> "Denoiser":
        d = Path(models_dir) if models_dir else Path(__file__).resolve().parents[2] / "models"
        return cls(d / "denoiser.onnx")

    def run(self, x: np.ndarray) -> np.ndarray:
        """``x``: (B, 2, WINDOW) float32 -> (B, 3, WINDOW)."""
        return self.session.run(None, {self.input_name: np.ascontiguousarray(x, dtype=np.float32)})[0]

    def denoise_bv(self, ir_bv: np.ndarray, red_bv: np.ndarray, fs: float = FS) -> Denoised:
        """Denoise pre-processed blood-volume signals of any length >= 1 s.

        Signals longer than one window are processed in 50 %-overlapping
        windows and recombined with a Hann taper (overlap-add). Shorter ones
        are extended by mirror-periodic repetition (zeros never occur in the
        training data and make the network flag everything as artefact),
        with the scale taken from the real samples only; quality still drops
        for very short inputs, so the pipeline uses the classical path below
        ~6 s.
        """
        if abs(fs - FS) > 1e-6:
            raise ValueError(f"denoiser expects {FS} Hz input, got {fs}")
        ir_bv = np.asarray(ir_bv, dtype=np.float64)
        red_bv = np.asarray(red_bv, dtype=np.float64)
        n = ir_bv.size
        if n <= WINDOW:
            def ext(v):
                return np.resize(np.concatenate([v, v[::-1]]), WINDOW)
            scale = max(float(np.std(ir_bv)), 1e-9)
            x = np.clip(np.stack([ext(ir_bv), ext(red_bv)]).astype(np.float32) / scale, -INPUT_CLIP, INPUT_CLIP)
            y = self.run(x[None])[0]
            return Denoised(ir_bv=y[0, :n] * scale, red_bv=y[1, :n] * scale,
                            artifact_prob=_sigmoid(y[2, :n]), fs=fs)

        hop = WINDOW // 2
        starts = list(range(0, n - WINDOW + 1, hop))
        if starts[-1] != n - WINDOW:
            starts.append(n - WINDOW)
        xs, scales = [], []
        for s in starts:
            x, sc = normalise(ir_bv[s:s + WINDOW], red_bv[s:s + WINDOW])
            xs.append(x)
            scales.append(sc)
        ys = self.run(np.stack(xs))
        taper = np.hanning(WINDOW + 2)[1:-1]
        acc = np.zeros((3, n))
        wsum = np.zeros(n)
        for s, y, sc in zip(starts, ys, scales):
            acc[0, s:s + WINDOW] += taper * y[0] * sc
            acc[1, s:s + WINDOW] += taper * y[1] * sc
            acc[2, s:s + WINDOW] += taper * _sigmoid(y[2])
            wsum[s:s + WINDOW] += taper
        acc /= np.maximum(wsum, 1e-9)
        return Denoised(ir_bv=acc[0], red_bv=acc[1], artifact_prob=acc[2], fs=fs)
