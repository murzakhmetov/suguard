"""Beat detection, heart rate, HRV and beat templates."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import ndimage, signal

from ..config import FS, HR_BAND_HZ, HR_MAX_BPM, HR_MIN_BPM
from .filters import bandpass


@dataclass
class Beats:
    peaks: np.ndarray        # sample index of systolic peaks (float, sub-sample)
    onsets: np.ndarray       # sample index of the beat feet (float)
    ibi_s: np.ndarray        # inter-beat intervals between consecutive peaks (s)
    valid_ibi: np.ndarray    # bool, IBI physiologically plausible and consistent
    fs: float

    @property
    def hr_bpm(self) -> float | None:
        good = self.ibi_s[self.valid_ibi]
        if good.size < 2:
            return None
        return float(60.0 / np.median(good))


def _parabolic(x: np.ndarray, i: int) -> float:
    if 0 < i < x.size - 1:
        a, b, c = x[i - 1], x[i], x[i + 1]
        den = a - 2 * b + c
        if den != 0:
            return i + 0.5 * (a - c) / den
    return float(i)


def detect_beats(bv: np.ndarray, fs: float = FS) -> Beats:
    """Systolic peaks with Elgendi's two-moving-average method (2013).

    ``bv`` is the blood-volume signal (systolic peaks pointing up).
    """
    x = bandpass(np.asarray(bv, dtype=np.float64), fs, 0.5, 8.0)
    y = np.clip(x, 0, None) ** 2
    w1 = max(int(round(0.111 * fs)), 1)
    w2 = max(int(round(0.667 * fs)), 1)
    ma_peak = ndimage.uniform_filter1d(y, w1, mode="nearest")
    ma_beat = ndimage.uniform_filter1d(y, w2, mode="nearest")
    blocks = ma_peak > ma_beat + 0.02 * np.mean(y)

    edges = np.diff(blocks.astype(np.int8), prepend=0, append=0)
    starts, ends = np.flatnonzero(edges == 1), np.flatnonzero(edges == -1)
    peaks: list[float] = []
    for s, e in zip(starts, ends):
        if e - s < w1:
            continue
        i = s + int(np.argmax(x[s:e]))
        peaks.append(_parabolic(x, i))
    peaks_arr = np.asarray(peaks)

    # Refractory period: two peaks closer than the maximum heart rate allows
    # -> keep the larger one.
    if peaks_arr.size > 1:
        min_dist = fs * 60.0 / HR_MAX_BPM
        keep = [0]
        for k in range(1, peaks_arr.size):
            if peaks_arr[k] - peaks_arr[keep[-1]] < min_dist:
                if x[int(round(peaks_arr[k]))] > x[int(round(peaks_arr[keep[-1]]))]:
                    keep[-1] = k
            else:
                keep.append(k)
        peaks_arr = peaks_arr[keep]

    ibi = np.diff(peaks_arr) / fs
    valid = np.zeros(ibi.size, dtype=bool)
    if ibi.size:
        plausible = (ibi >= 60.0 / HR_MAX_BPM) & (ibi <= 60.0 / HR_MIN_BPM)
        if plausible.any():
            med = np.median(ibi[plausible])
            valid = plausible & (np.abs(ibi - med) <= 0.3 * med)

    onsets = _find_onsets(x, peaks_arr, fs)
    return Beats(peaks=peaks_arr, onsets=onsets, ibi_s=ibi, valid_ibi=valid, fs=fs)


def _find_onsets(x: np.ndarray, peaks: np.ndarray, fs: float) -> np.ndarray:
    """Beat foot: minimum of the signal within the 0.6 s before each peak."""
    onsets = np.full(peaks.size, np.nan)
    look = int(0.6 * fs)
    prev = 0
    for k, p in enumerate(peaks):
        pi = int(round(p))
        a = max(prev, pi - look)
        if pi - a < 2:
            prev = pi
            continue
        i = a + int(np.argmin(x[a:pi]))
        onsets[k] = _parabolic(-x, i) if 0 < i < x.size - 1 else float(i)
        prev = pi
    return onsets


def spectral_hr(bv: np.ndarray, fs: float = FS, prior_bpm: float | None = None,
                nfft: int = 4096) -> tuple[float | None, float]:
    """Heart rate from the dominant spectral peak in the cardiac band.

    Returns ``(bpm, purity)`` where purity is the share of in-band power that
    lies within +-0.1 Hz of the chosen peak and its 2nd harmonic. With a prior
    (the previous window's HR), peaks far from it are penalised, which tracks
    the heart rate through short periods of motion.
    """
    x = bandpass(np.asarray(bv, dtype=np.float64), fs, 0.5, 8.0)
    if x.size < 8 or not np.any(x):
        return None, 0.0
    w = signal.windows.hann(x.size)
    spec = np.abs(np.fft.rfft((x - x.mean()) * w, n=max(nfft, x.size))) ** 2
    f = np.fft.rfftfreq(max(nfft, x.size), 1.0 / fs)
    band = (f >= HR_BAND_HZ[0]) & (f <= HR_BAND_HZ[1])
    if not band.any() or spec[band].sum() <= 0:
        return None, 0.0
    fb, pb = f[band], spec[band]
    cand, _ = signal.find_peaks(pb)
    if cand.size == 0:
        cand = np.array([int(np.argmax(pb))])
    score = pb[cand].astype(np.float64)
    if prior_bpm is not None:
        d = np.abs(fb[cand] * 60.0 - prior_bpm)
        score = score * np.exp(-0.5 * (d / 15.0) ** 2)
    k = cand[int(np.argmax(score))]
    f0 = fb[k]
    # Prefer the fundamental if the chosen peak looks like a 2nd harmonic.
    half = np.abs(fb - f0 / 2) <= 0.08
    if f0 / 2 >= HR_BAND_HZ[0] and half.any() and pb[half].max() >= 0.5 * pb[k] and prior_bpm is None:
        k = np.flatnonzero(half)[int(np.argmax(pb[half]))]
        f0 = fb[k]
    near = (np.abs(f - f0) <= 0.1) | (np.abs(f - 2 * f0) <= 0.1)
    total = spec[(f >= 0.5) & (f <= 8.0)].sum()
    purity = float(spec[near].sum() / total) if total > 0 else 0.0
    return float(f0 * 60.0), purity


def beat_template(x: np.ndarray, beats: Beats, length: int = 64) -> tuple[np.ndarray | None, float]:
    """Median onset-to-onset beat (resampled to ``length``) and the mean
    correlation of the individual beats with it (a standard PPG SQI)."""
    on = beats.onsets[np.isfinite(beats.onsets)]
    if on.size < 3:
        return None, 0.0
    segs = []
    for a, b in zip(on[:-1], on[1:]):
        if not (0.28 * beats.fs <= b - a <= 1.75 * beats.fs):
            continue
        idx = np.linspace(a, b, length)
        segs.append(np.interp(idx, np.arange(x.size), x))
    if len(segs) < 2:
        return None, 0.0
    S = np.asarray(segs)
    S = S - S.mean(axis=1, keepdims=True)
    tmpl = np.median(S, axis=0)
    if np.std(tmpl) == 0:
        return tmpl, 0.0
    corr = [np.corrcoef(s, tmpl)[0, 1] if np.std(s) > 0 else 0.0 for s in S]
    return tmpl, float(np.nanmean(corr))


def hrv_metrics(ibi_s: np.ndarray) -> dict[str, float | None]:
    """Time-domain HRV from clean inter-beat intervals (needs >= ~60 s)."""
    ibi = np.asarray(ibi_s, dtype=np.float64) * 1000.0
    if ibi.size < 5:
        return {"sdnn_ms": None, "rmssd_ms": None, "pnn50": None, "mean_ibi_ms": None}
    d = np.diff(ibi)
    return {
        "sdnn_ms": float(np.std(ibi, ddof=1)),
        "rmssd_ms": float(np.sqrt(np.mean(d**2))),
        "pnn50": float(np.mean(np.abs(d) > 50.0)),
        "mean_ibi_ms": float(np.mean(ibi)),
    }
