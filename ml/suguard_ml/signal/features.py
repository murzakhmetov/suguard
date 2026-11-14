"""PPG features for glucose estimation.

Morphology is computed on an ensemble-averaged beat (onset to next onset,
time-normalised), which is far more stable than single beats at 50 Hz.
Feature families follow the PPG-glucose literature (e.g. Monte-Moreno 2011;
Zhang et al. 2020; Susana et al. 2023):

* rate/rhythm and HRV
* amplitude and optics: perfusion indices, ratio of ratios, DC levels
* waveform timing and shape: crest time, widths, notch, areas, reflection
* second derivative (SDPPG / APG) a-e waves and the ageing index
* harmonic content and per-harmonic red/IR ratios
None of these is a direct glucose measurement; whether any of them carries
glucose information must be established on real paired data with
subject-independent validation (see scripts/train_glucose.py).
"""

from __future__ import annotations

import numpy as np
from scipy import signal, stats

from ..config import FS
from .beats import Beats, detect_beats, hrv_metrics

N_T = 100  # samples per normalised beat


def _good_beat_spans(beats: Beats, artifact_prob: np.ndarray | None, n: int) -> list[tuple[float, float]]:
    on = beats.onsets[np.isfinite(beats.onsets)]
    spans = []
    for a, b in zip(on[:-1], on[1:]):
        dur = (b - a) / beats.fs
        if not (0.28 <= dur <= 1.75):
            continue
        if artifact_prob is not None:
            seg = artifact_prob[int(a): int(np.ceil(b)) + 1]
            if seg.size and float(np.mean(seg)) > 0.3:
                continue
        if b >= n - 1:
            continue
        spans.append((a, b))
    return spans


def ensemble_beat(x: np.ndarray, spans: list[tuple[float, float]], min_corr: float = 0.8) -> tuple[np.ndarray | None, np.ndarray]:
    """Median of time-normalised beats that correlate with the provisional template."""
    if len(spans) < 3:
        return None, np.array([])
    grid = np.arange(x.size)
    segs = np.array([np.interp(np.linspace(a, b, N_T), grid, x) for a, b in spans])
    segs = segs - segs[:, :1]  # foot at zero
    tmpl = np.median(segs, axis=0)
    corr = np.array([np.corrcoef(s, tmpl)[0, 1] if np.std(s) > 0 else 0 for s in segs])
    keep = corr >= min_corr
    if keep.sum() < 3:
        return None, corr
    return np.median(segs[keep], axis=0), corr


def _sdppg_waves(t2: np.ndarray, i_sys: int) -> dict:
    """a, b, c, d, e waves of the second derivative (normalised time)."""
    out = {k: np.nan for k in ("b_a", "c_a", "d_a", "e_a", "agi", "t_b", "t_e")}
    lim = min(int(0.6 * N_T), t2.size - 1)
    seg = t2[:lim]
    if seg.size < 10:
        return out
    ia = int(np.argmax(seg[: max(i_sys, 3)]))  # a: max acceleration before systolic peak
    a = seg[ia]
    if a <= 0:
        return out
    mins, _ = signal.find_peaks(-seg[ia:])
    maxs, _ = signal.find_peaks(seg[ia:])
    mins, maxs = mins + ia, maxs + ia
    if mins.size == 0:
        return out
    ib = mins[0]
    out["b_a"] = seg[ib] / a
    out["t_b"] = ib / N_T
    later_max = maxs[maxs > ib]
    if later_max.size:
        ic = later_max[0]
        out["c_a"] = seg[ic] / a
        later_min = mins[mins > ic]
        if later_min.size:
            id_ = later_min[0]
            out["d_a"] = seg[id_] / a
            later_max2 = maxs[maxs > id_]
            if later_max2.size:
                ie = later_max2[0]
                out["e_a"] = seg[ie] / a
                out["t_e"] = ie / N_T
                out["agi"] = out["b_a"] - out["c_a"] - out["d_a"] - out["e_a"]
    return out


def template_features(tmpl: np.ndarray, ibi_s: float, prefix: str = "") -> dict:
    """Shape features of a foot-aligned, time-normalised beat."""
    f: dict[str, float] = {}
    amp = float(tmpl.max() - tmpl.min())
    if amp <= 0 or not np.isfinite(amp):
        return f
    y = (tmpl - tmpl[0]) / amp
    t = np.linspace(0, 1, N_T)
    i_sys = int(np.argmax(y[: int(0.7 * N_T)]))
    d1 = np.gradient(y, t)
    d2 = np.gradient(signal.savgol_filter(d1, 9, 3), t)
    f["crest_time_ratio"] = i_sys / N_T
    f["crest_time_s"] = i_sys / N_T * ibi_s
    f["max_slope"] = float(d1[: i_sys + 1].max()) / ibi_s if i_sys > 0 else np.nan
    f["t_max_slope_ratio"] = float(np.argmax(d1[: i_sys + 1])) / N_T if i_sys > 0 else np.nan
    for lvl in (0.25, 0.5, 0.75):
        above = np.flatnonzero(y >= lvl * y[i_sys])
        f[f"width{int(lvl * 100)}_ratio"] = (above[-1] - above[0]) / N_T if above.size else np.nan

    # Dicrotic notch: first local minimum after the systolic peak, else the
    # flattest point of the descent (late-systolic inflection in stiff arteries).
    after = y[i_sys + 3: int(0.85 * N_T)]
    mins, _ = signal.find_peaks(-after)
    if mins.size:
        i_n = i_sys + 3 + mins[0]
        notch_type = 1.0
    else:
        d1a = d1[i_sys + 3: int(0.85 * N_T)]
        i_n = i_sys + 3 + int(np.argmax(d1a)) if d1a.size else i_sys
        notch_type = 0.0
    f["notch_present"] = notch_type
    f["notch_time_ratio"] = i_n / N_T
    f["notch_height"] = float(y[i_n])
    post = y[i_n:]
    i_d = i_n + int(np.argmax(post)) if post.size else i_n
    f["dia_height"] = float(y[i_d])                       # reflection index
    f["dia_time_ratio"] = i_d / N_T
    f["delta_t_s"] = (i_d - i_sys) / N_T * ibi_s           # stiffness index ~ height / delta_t
    a_sys = float(np.trapezoid(y[: i_n + 1], t[: i_n + 1]))
    a_dia = float(np.trapezoid(y[i_n:], t[i_n:]))
    f["area_total"] = a_sys + a_dia
    f["ipa"] = a_dia / a_sys if a_sys > 0 else np.nan     # inflection point area ratio
    f["skew"] = float(stats.skew(y))
    f["kurt"] = float(stats.kurtosis(y))
    f.update(_sdppg_waves(d2, i_sys))

    spec = np.fft.rfft(y - y.mean())
    mag = np.abs(spec[1:6])
    if mag[0] > 0:
        for h in range(1, 5):
            f[f"h{h + 1}_h1"] = float(mag[h] / mag[0])
        ph = np.angle(spec[1:4])
        f["phase_h2_h1"] = float(np.angle(np.exp(1j * (ph[1] - 2 * ph[0]))))
        f["phase_h3_h1"] = float(np.angle(np.exp(1j * (ph[2] - 3 * ph[0]))))
    return {prefix + k: v for k, v in f.items()}


def extract_features(ir_bv: np.ndarray, red_bv: np.ndarray | None = None, fs: float = FS,
                     artifact_prob: np.ndarray | None = None, ir_dc: float | None = None,
                     red_dc: float | None = None, temperature_c: float | None = None) -> dict:
    """All PPG features of a clean (denoised or artefact-free) recording.

    Works for any length >= ~10 s; HRV needs >= 60 s to be meaningful.
    ``red_bv`` may be None for single-wavelength devices (e.g. green-LED
    watches in public datasets); red features are then NaN.
    """
    ir_bv = np.asarray(ir_bv, dtype=np.float64)
    beats = detect_beats(ir_bv, fs)
    feats: dict[str, float] = {}
    good_ibi = beats.ibi_s[beats.valid_ibi]
    feats["hr_bpm"] = float(60.0 / np.median(good_ibi)) if good_ibi.size >= 2 else np.nan
    hrv = hrv_metrics(good_ibi)
    feats.update({k: (np.nan if v is None else v) for k, v in hrv.items()})
    feats["pi_ir"] = float(np.percentile(ir_bv, 97) - np.percentile(ir_bv, 3)) * 100
    feats["ir_dc"] = np.nan if ir_dc is None else float(ir_dc)
    feats["temperature_c"] = np.nan if temperature_c is None else float(temperature_c)

    spans = _good_beat_spans(beats, artifact_prob, ir_bv.size)
    tmpl_ir, corr = ensemble_beat(ir_bv, spans)
    feats["n_beats"] = float(len(spans))
    feats["beat_corr"] = float(np.nanmedian(corr)) if corr.size else np.nan
    ibi_s = float(np.median(good_ibi)) if good_ibi.size else np.nan
    if tmpl_ir is not None and np.isfinite(ibi_s):
        feats.update(template_features(tmpl_ir, ibi_s))

    if red_bv is not None:
        red_bv = np.asarray(red_bv, dtype=np.float64)
        w = None if artifact_prob is None else 1 - artifact_prob
        from .spo2 import ratio_of_ratios
        r, rc = ratio_of_ratios(red_bv, ir_bv, w)
        feats["r_ratio"] = np.nan if r is None else r
        feats["red_ir_corr"] = rc
        feats["pi_red"] = float(np.percentile(red_bv, 97) - np.percentile(red_bv, 3)) * 100
        feats["red_dc"] = np.nan if red_dc is None else float(red_dc)
        feats["dc_red_ir"] = (red_dc / ir_dc) if (red_dc and ir_dc) else np.nan
        tmpl_red, _ = ensemble_beat(red_bv, spans, min_corr=0.6)
        if tmpl_red is not None and tmpl_ir is not None:
            si = np.fft.rfft(tmpl_ir - tmpl_ir.mean())
            sr = np.fft.rfft(tmpl_red - tmpl_red.mean())
            for h in (1, 2, 3):
                feats[f"r_h{h}"] = float(np.abs(sr[h]) / np.abs(si[h])) if np.abs(si[h]) > 0 else np.nan
            feats["red_ir_tmpl_corr"] = float(np.corrcoef(tmpl_ir, tmpl_red)[0, 1])
            feats["red_ir_peak_lag_ratio"] = float(np.argmax(tmpl_red) - np.argmax(tmpl_ir)) / N_T
            feats.update(template_features(tmpl_red, ibi_s, prefix="red_") if np.isfinite(ibi_s) else {})
    return feats
