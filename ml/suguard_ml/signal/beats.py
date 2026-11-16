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
        """Rate from the mean of the valid intervals. The validity band
        (within 30 % of the median) keeps missed and extra beats out; among
        the rest, a peak found a little late lengthens one interval and
        shortens the next, so the mean cancels that jitter where the median
        does not (simulated clean windows: mean error 0.55 -> 0.32 bpm,
        95th percentile 1.44 -> 0.82 bpm)."""
        good = self.ibi_s[self.valid_ibi]
        if good.size < 2:
            return None
        return float(60.0 / np.mean(good))


def _parabolic(x: np.ndarray, i: int) -> float:
    """Sub-sample extremum position; the vertex of a parabola through three
    samples around a true local extremum lies within +-0.5 sample, so larger
    offsets (flat or non-extremal neighbourhoods) are rejected."""
    if 0 < i < x.size - 1:
        a, b, c = x[i - 1], x[i], x[i + 1]
        den = a - 2 * b + c
        if den != 0:
            off = 0.5 * (a - c) / den
            if abs(off) <= 0.5:
                return i + off
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


def pulse_polarity(x: np.ndarray, fs: float = FS, ref_bpm: np.ndarray | None = None, window: int = 512) -> int:
    """+1 if the systolic peaks of the recording ``x`` point up, -1 if it is
    upside down. For recordings of unknown polarity (other devices).

    ``ref_bpm``: optional reference heart rate of each consecutive window of
    ``window`` samples (NaN where unknown).

    The slopes do not decide it: behind an analog filter or the low-pass of
    the tissue a real pulse rises about as fast as it falls (three public
    recordings: steepest rise / steepest fall = 0.92-0.99; "the rise is the
    short flank" turned two of them upside down, and the beat detector then
    found 170 instead of 59 beats per minute in one). Two things do:

    * with a reference, the way up in which the beat detector agrees with it
      in more windows (a clear majority: more than a tenth of the windows);
    * else the shape of the amplitude distribution: an upright pulse spends a
      short time at its peak and a long time near its foot (positive
      skewness, +0.9 to +1.5 in those recordings). A pulse so smooth that the
      skewness is about zero reads the same either way up.
    """
    x = bandpass(np.asarray(x, dtype=np.float64), fs, 0.4, 12.0)
    n = x.size // window
    if n == 0:
        return 1
    segs = x[:n * window].reshape(n, window)
    if ref_bpm is not None:
        ref = np.asarray(ref_bpm, dtype=np.float64).ravel()[:n]
        agree = {1: 0, -1: 0}
        for seg, r in zip(segs, ref):
            if not np.isfinite(r):
                continue
            for sign in (1, -1):
                hr = detect_beats(sign * seg, fs).hr_bpm
                agree[sign] += int(hr is not None and abs(hr - r) <= 10.0)
        if abs(agree[1] - agree[-1]) > 0.1 * n:
            return 1 if agree[1] > agree[-1] else -1
    sd = segs.std(axis=1)
    ok = sd > 0
    if not ok.any():
        return 1
    z = (segs[ok] - segs[ok].mean(axis=1, keepdims=True)) / sd[ok, None]
    return 1 if float(np.median(np.mean(z ** 3, axis=1))) >= 0 else -1


# Spectral heart rate by harmonic summation: a peak of the cardiac band is
# scored by its own power plus the strongest power within HARMONIC_SPAN bins
# of its 2nd and 3rd harmonic. A real pulse often has a 2nd harmonic stronger
# than its fundamental (a pronounced dicrotic notch or reflected wave); the
# strongest peak alone then reads double the rate. Only peaks with at least
# HARMONIC_MIN_SHARE of the strongest peak's power compete: a component at
# half the rate (arm swing while walking) would otherwise win with the
# pulse's own fundamental as its "2nd harmonic" (a sinusoidal pulse with arm
# swing at half its rate, 0.35 of its size: 6 of 40 windows got a heart rate
# on the classical path with 0.1, 40 of 40 with 0.25, all correct). 0.25 still
# admits a fundamental whose 2nd harmonic is twice as strong (power ratio
# 0.25: an amplitude ratio of 2; the real recordings reach 1.6, power 0.39).
HARMONIC_MIN_SHARE = 0.25
HARMONIC_SPAN = 2


def _harmonic_power(spec: np.ndarray, k: int, h: int) -> float:
    lo, hi = h * k - HARMONIC_SPAN, h * k + HARMONIC_SPAN
    if lo > spec.size - 1:
        return 0.0
    return float(spec[max(lo, 0):min(hi, spec.size - 1) + 1].max())


def spectral_hr(bv: np.ndarray, fs: float = FS, prior_bpm: float | None = None,
                nfft: int = 4096) -> tuple[float | None, float]:
    """Heart rate from the cardiac-band peak with the most power in it and
    its 2nd and 3rd harmonic (see HARMONIC_MIN_SHARE).

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
    k_lo = int(np.flatnonzero(band)[0])
    fb, pb = f[band], spec[band]
    cand, _ = signal.find_peaks(pb)
    if cand.size == 0:
        cand = np.array([int(np.argmax(pb))])
    cand = cand[pb[cand] >= HARMONIC_MIN_SHARE * pb[cand].max()]
    score = np.array([pb[c] + _harmonic_power(spec, k_lo + c, 2) + _harmonic_power(spec, k_lo + c, 3)
                      for c in cand], dtype=np.float64)
    if prior_bpm is not None:
        d = np.abs(fb[cand] * 60.0 - prior_bpm)
        score = score * np.exp(-0.5 * (d / 15.0) ** 2)
    k = cand[int(np.argmax(score))]
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


# Detection of premature beats in the interval series, with the decision rule
# of Lipponen & Tarvainen (2019): a successive difference far larger than the
# typical one, flanked by differences of the opposite sign, is the short-long
# (or long-short) signature of a premature beat with its compensatory pause,
# or of one misplaced peak. "Far larger" is ECTOPIC_ALPHA x the median
# |difference| (about 3 SD for normal rhythm; the median stays robust in
# short recordings). On simulated rhythms 4.5 removes < 0.5 % of normal
# intervals and brings RMSSD back to within a few per cent of the ectopy-free
# value; a premature beat smaller than the rhythm's own variability cannot be
# told apart and stays in. C1, C2 are the constants of the published rule.
ECTOPIC_ALPHA = 4.5
ECTOPIC_C1, ECTOPIC_C2 = 0.13, 0.17


def _premature_pairs(ibi_ms: np.ndarray, nn: np.ndarray) -> np.ndarray:
    """Mask of the intervals that form short-long / long-short pairs."""
    bad = np.zeros(ibi_ms.size, dtype=bool)
    d = np.diff(ibi_ms)                       # d[j]: change from interval j to j + 1
    pair = nn[1:] & nn[:-1]
    if pair.sum() < 4:
        return bad
    th = ECTOPIC_ALPHA * float(np.median(np.abs(d[pair])))
    if th <= 0:
        return bad
    s = d / th
    for j in np.flatnonzero(pair & (np.abs(s) > 1.0)):
        neighbours = [s[k] for k in (j - 1, j + 1) if 0 <= k < s.size and pair[k]]
        if not neighbours:
            continue
        if s[j] > 0:
            hit = max(neighbours) < -ECTOPIC_C1 * s[j] - ECTOPIC_C2
        else:
            hit = min(neighbours) > -ECTOPIC_C1 * s[j] + ECTOPIC_C2
        if hit:
            bad[j] = bad[j + 1] = True
    return bad


def hrv_metrics(ibi_s: np.ndarray, valid: np.ndarray | None = None) -> dict[str, float | None]:
    """Time-domain HRV from inter-beat intervals (needs >= ~60 s).

    ``valid`` marks plausible intervals (Beats.valid_ibi). NN editing is done
    on the full series: the intervals next to a rejected one are dropped too
    (the other half of an ectopic beat's short-long pair), premature beats that stay
    within the detector's plausibility band are found by their short-long
    pattern, and successive differences are taken only between truly adjacent
    normal intervals, so removed beats cannot create spurious jumps in
    RMSSD / pNN50. ``excluded_intervals`` counts everything left out.
    """
    ibi = np.asarray(ibi_s, dtype=np.float64) * 1000.0
    empty = {"sdnn_ms": None, "rmssd_ms": None, "pnn50": None, "mean_ibi_ms": None, "excluded_intervals": None}
    if ibi.size == 0:
        return empty
    v = np.ones(ibi.size, dtype=bool) if valid is None else np.asarray(valid, dtype=bool).copy()
    nn = v.copy()
    nn[1:] &= v[:-1]      # a rejected interval takes its neighbours with it: the other half of a
    nn[:-1] &= v[1:]      # premature beat / compensatory pause pair may itself look plausible
    nn &= ~_premature_pairs(ibi, nn)
    if nn.sum() < 5:
        return empty
    d = np.diff(ibi)
    pair = nn[1:] & nn[:-1]
    return {
        "sdnn_ms": float(np.std(ibi[nn], ddof=1)),
        "rmssd_ms": float(np.sqrt(np.mean(d[pair] ** 2))) if pair.sum() >= 3 else None,
        "pnn50": float(np.mean(np.abs(d[pair]) > 50.0)) if pair.sum() >= 3 else None,
        "mean_ibi_ms": float(np.mean(ibi[nn])),
        "excluded_intervals": int(ibi.size - nn.sum()),
    }
