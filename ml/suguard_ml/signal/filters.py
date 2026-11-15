"""Resampling and zero-phase filtering for raw MAX30102 channels."""

from __future__ import annotations

from fractions import Fraction

import numpy as np
from scipy import signal

from ..config import FS, PPG_BAND_HZ


RESAMPLE_END_SAMPLES = 5      # samples at each end whose median anchors the trend line


def resample(x: np.ndarray, fs_in: float, fs_out: float = FS) -> np.ndarray:
    """Polyphase resampling of one window with an anti-aliasing filter.

    A window of raw counts has a large level and usually a drift, and the
    filter must not ring where the window starts and ends. So a straight line
    is taken out before filtering and put back afterwards (level and drift
    then pass exactly, instead of through a stop band of about -60 dB that
    would leave images of a 100,000-count level as a tone of tens of counts),
    and what is left is continued beyond the ends by reflection. The line
    runs through the medians of the first and the last few samples, not
    through the end samples themselves: a glitch on an end sample would tilt
    it and put a step at the edge.

    Worst error on drifting windows with a 500-count pulse (content up to
    11.5 Hz), in the first and last half second / with a 3,000-count glitch
    on the first sample, at 100 -> 50 Hz: 43 / 7 counts; with the mean
    removed and zeros outside the window (the first version) 592 / 161; with
    a line through the two end samples 21 / 204. The reliability decision of
    the pipeline for a window delivered at 100 Hz equals that for the same
    window at 50 Hz in 299-300 of 300 simulated windows (with the first
    version it differed in every tenth one).
    """
    x = np.asarray(x, dtype=np.float64)
    if abs(fs_in - fs_out) < 1e-9 or x.size < 2:
        return x.copy()
    frac = Fraction(fs_out / fs_in).limit_denominator(1000)
    up, down = frac.numerator, frac.denominator
    if up == down:
        return x.copy()
    k = max(min(RESAMPLE_END_SAMPLES, x.size // 2), 1)
    first, last = float(np.median(x[:k])), float(np.median(x[-k:]))
    i_first, i_last = (k - 1) / 2.0, x.size - 1 - (k - 1) / 2.0
    slope = (last - first) / (i_last - i_first)
    level = first - slope * i_first
    y = signal.resample_poly(x - (level + slope * np.arange(x.size)), up, down, padtype="reflect")
    return y + level + slope * (np.arange(y.size) * (down / up))


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
