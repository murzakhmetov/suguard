"""Resampling and zero-phase filtering for raw MAX30102 channels."""

from __future__ import annotations

from fractions import Fraction

import numpy as np
from scipy import signal

from ..config import FS, PPG_BAND_HZ


def resample(x: np.ndarray, fs_in: float, fs_out: float = FS) -> np.ndarray:
    """Polyphase resampling with an anti-aliasing filter."""
    x = np.asarray(x, dtype=np.float64)
    if abs(fs_in - fs_out) < 1e-9:
        return x.copy()
    frac = Fraction(fs_out / fs_in).limit_denominator(1000)
    # resample_poly treats samples outside the signal as zero, which rings at
    # the edges of a signal with a large DC (raw counts). Remove the mean first.
    mean = float(np.mean(x)) if x.size else 0.0
    y = signal.resample_poly(x - mean, frac.numerator, frac.denominator)
    return y + mean


def resample_irregular(t: np.ndarray, x: np.ndarray, fs_out: float = FS) -> tuple[np.ndarray, np.ndarray]:
    """Linear interpolation of jittered timestamps onto a uniform grid.

    ``t`` is in seconds. Returns ``(t_uniform, x_uniform)``.
    """
    t = np.asarray(t, dtype=np.float64)
    x = np.asarray(x, dtype=np.float64)
    order = np.argsort(t, kind="stable")
    t, x = t[order], x[order]
    keep = np.concatenate(([True], np.diff(t) > 0))
    t, x = t[keep], x[keep]
    tu = np.arange(t[0], t[-1], 1.0 / fs_out)
    return tu, np.interp(tu, t, x)


def _sos(kind: str, cutoff, fs: float, order: int) -> np.ndarray:
    nyq = fs / 2.0
    if kind == "bandpass":
        lo, hi = cutoff
        hi = min(hi, 0.95 * nyq)
        return signal.butter(order, [lo / nyq, hi / nyq], btype="bandpass", output="sos")
    fc = min(cutoff, 0.95 * nyq)
    return signal.butter(order, fc / nyq, btype=kind, output="sos")


def _filtfilt(sos: np.ndarray, x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=np.float64)
    padlen = min(3 * (2 * sos.shape[0] + 1) * 4, max(x.shape[-1] - 1, 0))
    if x.shape[-1] < 4:
        return x.copy()
    return signal.sosfiltfilt(sos, x, padtype="odd", padlen=padlen, axis=-1)


def bandpass(x: np.ndarray, fs: float = FS, lo: float = PPG_BAND_HZ[0],
             hi: float = PPG_BAND_HZ[1], order: int = 3) -> np.ndarray:
    return _filtfilt(_sos("bandpass", (lo, hi), fs, order), x)


def lowpass(x: np.ndarray, fs: float = FS, fc: float = 0.25, order: int = 2) -> np.ndarray:
    return _filtfilt(_sos("lowpass", fc, fs, order), x)


def highpass(x: np.ndarray, fs: float = FS, fc: float = 0.4, order: int = 2) -> np.ndarray:
    return _filtfilt(_sos("highpass", fc, fs, order), x)


def estimate_dc(raw: np.ndarray, fs: float = FS, fc: float = 0.25) -> np.ndarray:
    """Slowly varying DC level of a raw channel (counts)."""
    dc = lowpass(raw, fs, fc=fc, order=2)
    floor = max(1.0, 1e-3 * float(np.median(np.abs(raw))) if np.size(raw) else 1.0)
    return np.maximum(dc, floor)


def blood_volume(raw: np.ndarray, fs: float = FS, fc_dc: float = 0.25) -> tuple[np.ndarray, np.ndarray]:
    """Inverted, DC-normalised pulsatile signal ``-(raw - DC) / DC``.

    Returns ``(bv, dc)``. ``bv`` is dimensionless (a perfusion index of 1 %
    gives a peak-to-peak amplitude of about 0.01) and its systolic peaks point
    up, which is the convention every other module relies on.
    """
    raw = np.asarray(raw, dtype=np.float64)
    dc = estimate_dc(raw, fs, fc_dc)
    return -(raw - dc) / dc, dc


def preprocess(raw: np.ndarray, fs: float = FS) -> tuple[np.ndarray, np.ndarray]:
    """Blood-volume signal band-limited to the pulsatile band, plus the DC."""
    bv, dc = blood_volume(raw, fs)
    return bandpass(bv, fs), dc
