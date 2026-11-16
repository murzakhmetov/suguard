"""End-to-end analysis of raw MAX30102 recordings.

    from suguard_ml.pipeline import SuGuardPipeline
    pipe = SuGuardPipeline.load()                 # bundled models in ml/models
    res = pipe.analyze(red, ir, fs=100)           # raw 18-bit counts
    res["heart_rate"], res["spo2"], res["quality"], res["features"]

Steps: resample to 50 Hz -> sensor checks (contact, saturation) -> DC
normalisation and band-pass -> motion-artefact denoiser (falls back to the
classical path if no model is available or the window is shorter than
``MIN_DENOISER_S``) -> beats, heart rate, HRV, SpO2 -> quality index -> PPG
features for the glucose model.

Values are reported only when the window is reliable: sensor checks pass,
the measured pulse is strong enough, the denoiser flags at most
``MAX_ARTIFACT_FRACTION`` of the window as motion, its output is supported
by the measurement (a denoiser can draw a pulse that is not there, so its
output cannot vouch for itself), the red/IR ratio is physiological, and
every quality component passes; SpO2 also needs the measured and the denoised
signals to agree on it (``SPO2_AGREEMENT``). Where the denoiser flags (almost) nothing
(``CLEAN_MAX_MOTION``), the measured signals are the reference: SpO2 and the
red/IR checks (the arterial-ratio rule, which withholds the heart rate too,
the red/IR correlation and the ratio stability) use them, and so does the
spectral cross-check of the heart rate, with the few flagged samples taken
from the denoiser's output for the checks. Otherwise the values are None
with reasons, never a guess. That a shown value is right is still not guaranteed: steady
rhythmic motion can pass for a pulse (scripts/eval_denoiser.py, hard_cases).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .config import FS
from .models.denoiser import Denoiser
from .signal.beats import Beats, detect_beats, hrv_metrics
from .signal.features import extract_features
from .signal.filters import preprocess, resample
from .signal.quality import Quality, SensorState, assess_quality, sensor_state
from .signal.spo2 import SpO2Estimate, estimate_spo2

MODELS_DIR = Path(__file__).resolve().parents[1] / "models"

# Share of the window the denoiser may flag as motion-dominated before the
# window is rejected. Tuned for denoiser v2 on simulated windows (seeds
# 5,000,000+, separate from the evaluation seeds): 0.5 / 0.6 / 0.7 gave HR
# coverage 51 / 55 / 59 % with the same accuracy (MAE 0.50-0.51 bpm, no error
# > 10 bpm) and SpO2 MAE 0.16-0.17, no error > 4 points.
MAX_ARTIFACT_FRACTION = 0.7
# Minimum peak-to-peak IR perfusion (%) of the *measured* signal.
MIN_INPUT_PI = 0.03
# A denoiser can draw a pulse that is not in the measurement (into noise, or
# a red pulse copied from the IR one), so its output must be supported by its
# input: over the samples it calls clean, the measured signal has to correlate
# with the denoised one and contain it at about the same size. On 1731
# reliable simulated windows (seeds 5,000,000+, both models) the correlation
# was >= 0.90 and the gain 0.75-1.16; a red channel without a pulse gives
# gain ~0.1 and correlation < 0.5.
MIN_SUPPORT_CORR = 0.7
SUPPORT_GAIN_RANGE = (0.7, 1.4)
MIN_SUPPORT_SAMPLES = 10
# Where the denoiser flags at most this share of the window as motion, the
# measured signals are the reference: SpO2 comes from the measured red/IR
# (weighted by the mask) and the spectral rate the beats must agree with from
# the measured IR. A network can otherwise make a clean measurement look
# different from what it is: it attenuated red at fast rates (SpO2 read high,
# hiding a desaturation) and suppressed the fundamental of slow, double-humped
# pulses, so the denoised spectrum agreed with a doubled beat count. With the
# v5 networks, scripts/eval_denoiser.py hard_cases, 150 windows each, rule on /
# off: wrong heart rates at 35-45 bpm 2 / 4 (server) and 2 / 3 (bracelet). At
# 150-210 bpm and 82-90 % the rule halved the bracelet's SpO2 errors on an
# earlier draw of that set (7 / 14) before SPO2_AGREEMENT existed; with the
# agreement check the errors are the same either way (2 and 1). It covers
# only windows flagged up to this share: slow pulses the network flags more
# heavily keep the denoised reference. No change in reported values or errors
# above 4 points on the standard sets. The price: a non-arterial component
# locked to the heartbeat (venous pulsation, a cadence locked to the pulse)
# that the network partly removes stays in the measured red/IR and pulls SpO2
# down (red team, previous server network: 69 vs 50 of ~195 windows off by
# more than 4 points with strong venous pulsation); SPO2_AGREEMENT withholds
# most of those where the network disagrees. Measured SpO2 in every
# window was worse under motion (server, 600 gated windows: mean error 0.20 ->
# 0.28 points), so the network's red/IR are kept there.
CLEAN_MAX_MOTION = 0.2
# Wherever the denoiser is used, SpO2 is shown only if the measured red/IR (weighted by its mask)
# and its output give SpO2 values within this many points of each other: where they disagree,
# one of them carries something the other does not (red amplified or attenuated by the network,
# a non-arterial component locked to the heartbeat), and it cannot be told which. v5 networks,
# server / bracelet, values off by more than 4 points without / with this check: venous pulsation
# 65 / 58 and 59 / 58, a cadence locked to the pulse 17 / 14 and 15 / 12, 150-210 bpm at low SpO2
# 0 / 0 and 7 / 1; SpO2 values on the 600 gated windows 318 -> 316 and 296 -> 293.
SPO2_AGREEMENT = 2.0
# Shorter windows go through the classical path (the denoiser saw 10.24 s).
MIN_DENOISER_S = 6.0
MAX_NONFINITE_FRACTION = 0.02


@dataclass
class InputSupport:
    """How well a measured signal supports its denoised version."""
    corr: float     # correlation over the samples the denoiser calls clean
    gain: float     # regression slope of measured on denoised (1 = same size)

    @property
    def ok(self) -> bool:
        return bool(self.corr >= MIN_SUPPORT_CORR and SUPPORT_GAIN_RANGE[0] <= self.gain <= SUPPORT_GAIN_RANGE[1])


def input_support(measured: np.ndarray, denoised: np.ndarray, p_art: np.ndarray) -> InputSupport:
    """Correlation and gain of ``measured`` against ``denoised`` over the
    samples with artefact probability <= 0.5 (0, 0 if that cannot be computed)."""
    keep = np.asarray(p_art) <= 0.5
    if keep.sum() < MIN_SUPPORT_SAMPLES:
        return InputSupport(0.0, 0.0)
    x = np.asarray(measured, dtype=np.float64)[keep]
    y = np.asarray(denoised, dtype=np.float64)[keep]
    if not (np.isfinite(x).all() and np.isfinite(y).all()):
        return InputSupport(0.0, 0.0)
    x, y = x - x.mean(), y - y.mean()
    sxx, syy, sxy = float(np.sum(x * x)), float(np.sum(y * y)), float(np.sum(x * y))
    if sxx <= 0 or syy <= 0:
        return InputSupport(0.0, 0.0)
    return InputSupport(corr=sxy / np.sqrt(sxx * syy), gain=sxy / syy)


@dataclass
class SignalVitals:
    """Result of :func:`vitals_from_signals` (also the contract of the C++ port
    in firmware/suguard/src/core, function ``sg_vitals_from_signals``)."""
    reliable: bool
    reasons: list
    hr_bpm: float | None          # from the detected beats; never None when reliable
    spo2_ok: bool                 # SpO2-grade window with a value: ``spo2`` is not None
    spo2: float | None
    spo2_reason: str | None       # why there is no SpO2 although the window is reliable
    pi_in: float                  # peak-to-peak IR perfusion (%) of the measured signal
    support_ir: InputSupport | None    # None on the classical path
    support_red: InputSupport | None
    beats: Beats
    sp: SpO2Estimate
    quality: Quality


def vitals_from_signals(ir_bv: np.ndarray, red_bv: np.ndarray, sensor: SensorState,
                        c_ir: np.ndarray | None = None, c_red: np.ndarray | None = None,
                        p_art: np.ndarray | None = None, spo2_coeffs=None) -> SignalVitals:
    """Heart rate, SpO2 and the reliability decision for one window at FS.

    ``ir_bv``, ``red_bv``: the measured (band-passed) blood-volume signals.
    ``c_ir``, ``c_red``, ``p_art``: the denoiser's output and per-sample
    artefact probability; all None on the classical path, where the measured
    signals are analysed directly. Everything downstream of the denoiser
    lives here so that the firmware port and the Python pipeline share one
    definition.

    A window is reliable when the sensor checks and every quality component
    pass, the measured pulse is strong enough, at most
    ``MAX_ARTIFACT_FRACTION`` of it is flagged as motion, the denoised IR
    pulse is supported by the measurement, and the red/IR ratio is one that
    arterial blood can produce. SpO2 additionally needs both wavelengths to
    agree and the denoised red pulse to be supported by the measurement. In
    a window with at most ``CLEAN_MAX_MOTION`` flagged, SpO2 and with it the
    arterial-ratio rule and the red/IR correlation come from the measured
    red/IR, and the beat rate must agree with the spectrum, and the red/IR
    ratio be stable in, the measured signals with the flagged samples taken
    from the denoiser's output.
    """
    denoised = p_art is not None
    if not denoised:
        c_ir, c_red = ir_bv, red_bv
    pi_in = float(np.percentile(ir_bv, 97) - np.percentile(ir_bv, 3)) * 100.0
    beats = detect_beats(c_ir, FS)
    coeffs = {"coeffs": spo2_coeffs} if spo2_coeffs else {}
    # The network sees (almost) no motion: the measured signals are the reference (CLEAN_MAX_MOTION).
    clean = denoised and float(np.mean(p_art > 0.5)) <= CLEAN_MAX_MOTION
    ratio_reference = None
    if clean:
        # For the stability of the red/IR ratio: the measured signals, with the samples the network
        # flags taken from its output (the clipped weight of the SpO2 fit), so that a short burst it
        # removed does not withhold SpO2. The rate check uses the measured IR as it is: trusting the
        # mask there let a window through whose flagged part held the true pulse.
        w = np.clip(1.0 - p_art, 0.0, 1.0)
        ratio_reference = (w * ir_bv + (1.0 - w) * c_ir, w * red_bv + (1.0 - w) * c_red)
    sp_red, sp_ir = (red_bv, ir_bv) if clean else (c_red, c_ir)
    sp = estimate_spo2(sp_red, sp_ir, weights=1 - p_art if denoised else None, **coeffs)
    q = assess_quality(c_ir, c_red, beats, FS, artifact_prob=p_art, sensor=sensor, red_ir_corr=sp.red_ir_corr,
                       rate_reference=ir_bv if clean else None, ratio_reference=ratio_reference)
    support_ir = input_support(ir_bv, c_ir, p_art) if denoised else None
    support_red = input_support(red_bv, c_red, p_art) if denoised else None
    # The SpO2 of the other source (SPO2_AGREEMENT): the denoised one in a clean window, else the measured one.
    agree = True
    if denoised:
        other = estimate_spo2(*((c_red, c_ir) if clean else (red_bv, ir_bv)), weights=1 - p_art, **coeffs)
        agree = sp.spo2 is not None and other.spo2 is not None and abs(sp.spo2 - other.spo2) <= SPO2_AGREEMENT

    weak = not (pi_in >= MIN_INPUT_PI)      # also when the measured signal is not finite
    mismatch = denoised and not support_ir.ok
    # Both wavelengths carry the same waveform, but in a ratio no arterial
    # blood produces: motion or ambient light common to both LEDs (or the two
    # LED channels are swapped). The "pulse" is then not a pulse.
    non_arterial = sp.reason == "r_out_of_calibration_range"
    reasons = set(q.reasons)
    if weak:
        reasons.add("weak_pulse")
    if mismatch:
        reasons.add("denoiser_mismatch")
    if non_arterial:
        reasons.add("red_ir_inconsistent")
    reliable = bool(q.usable and q.motion_fraction <= MAX_ARTIFACT_FRACTION
                    and not (weak or mismatch or non_arterial))

    red_supported = not denoised or (support_red.ok and agree)
    spo2_ok = bool(reliable and q.usable_spo2 and red_supported and sp.spo2 is not None)
    spo2_reason = None
    if reliable and not spo2_ok:
        spo2_reason = sp.reason or ("red_denoiser_mismatch" if not red_supported else "red_ir_inconsistent")
    return SignalVitals(reliable=reliable, reasons=sorted(reasons), hr_bpm=beats.hr_bpm, spo2_ok=spo2_ok,
                        spo2=sp.spo2 if spo2_ok else None, spo2_reason=spo2_reason, pi_in=pi_in,
                        support_ir=support_ir, support_red=support_red, beats=beats, sp=sp, quality=q)


def _clean_input(red_raw, ir_raw) -> tuple[np.ndarray, np.ndarray, int]:
    red = np.asarray(red_raw, dtype=np.float64).ravel()
    ir = np.asarray(ir_raw, dtype=np.float64).ravel()
    if red.shape != ir.shape:
        raise ValueError("red and ir must be 1-D arrays of equal length")
    bad = ~(np.isfinite(red) & np.isfinite(ir))
    if bad.any():
        if bad.mean() > MAX_NONFINITE_FRACTION or bad.all():
            raise ValueError(f"{int(bad.sum())} non-finite samples in the window")
        idx = np.arange(red.size)
        red = np.interp(idx, idx[~bad], red[~bad])
        ir = np.interp(idx, idx[~bad], ir[~bad])
    return red, ir, int(bad.sum())


class SuGuardPipeline:
    def __init__(self, denoiser: Denoiser | None = None, spo2_coeffs=None):
        self.denoiser = denoiser
        self.spo2_coeffs = spo2_coeffs

    @classmethod
    def load(cls, models_dir: str | Path | None = None) -> "SuGuardPipeline":
        d = Path(models_dir) if models_dir else MODELS_DIR
        den = Denoiser(d / "denoiser.onnx") if (d / "denoiser.onnx").exists() else None
        return cls(denoiser=den)

    def analyze(self, red_raw, ir_raw, fs: float = 100.0, temperature_c: float | None = None,
                include_signals: bool = False) -> dict:
        red_in, ir_in, n_bad = _clean_input(red_raw, ir_raw)
        red = resample(red_in, fs, FS)
        ir = resample(ir_in, fs, FS)
        if ir.size < 2 * FS:
            raise ValueError("need at least 2 s of data")
        duration = ir.size / FS
        sensor = sensor_state(red, ir)
        ir_bv, ir_dc = preprocess(ir, FS)
        red_bv, red_dc = preprocess(red, FS)

        if self.denoiser is not None and duration >= MIN_DENOISER_S:
            dn = self.denoiser.denoise_bv(ir_bv, red_bv, FS)
            c_ir, c_red, p_art = dn.ir_bv, dn.red_bv, dn.artifact_prob
            method = "denoiser"
        else:
            c_ir, c_red, p_art = ir_bv, red_bv, None
            method = "classical"

        v = vitals_from_signals(ir_bv, red_bv, sensor, c_ir if p_art is not None else None,
                                c_red if p_art is not None else None, p_art, spo2_coeffs=self.spo2_coeffs)
        beats, sp, q = v.beats, v.sp, v.quality
        reliable = v.reliable
        out = {
            "method": method,
            "duration_s": round(duration, 2),
            "interpolated_samples": n_bad,
            "sensor": {"finger_detected": sensor.finger_detected,
                       "saturated_fraction": round(sensor.saturated_fraction, 4),
                       "ir_dc": round(sensor.ir_dc), "red_dc": round(sensor.red_dc)},
            "quality": {k: (round(x, 4) if isinstance(x, float) and np.isfinite(x) else x)
                        for k, x in q.to_dict().items()},
            "reliable": reliable,
            "heart_rate": {"bpm": round(v.hr_bpm, 1) if reliable else None, "beats": int(beats.peaks.size)},
            "spo2": {"percent": round(v.spo2, 1) if v.spo2_ok else None,
                     "r_ratio": round(sp.r_ratio, 4) if v.spo2_ok else None,
                     "reason": None if v.spo2_ok else (v.spo2_reason if reliable else "unreliable_window"),
                     "calibration": "device" if self.spo2_coeffs else "maxim_reference_curve_uncalibrated"},
            "hrv": hrv_metrics(beats.ibi_s, beats.valid_ibi) if (reliable and duration >= 60) else None,
            "features": None,
        }
        if v.spo2_ok:
            # Features include red/IR ratios, so they need the SpO2-grade gate.
            feats = extract_features(c_ir, c_red, FS, artifact_prob=p_art, ir_dc=float(np.median(ir_dc)),
                                     red_dc=float(np.median(red_dc)), temperature_c=temperature_c)
            out["features"] = {k: (None if (isinstance(x, float) and not np.isfinite(x)) else x)
                               for k, x in feats.items()}
            out["feature_span_s"] = round(duration, 2)
        if not reliable:
            out["reason"] = v.reasons or ["unreliable"]
        if include_signals:
            out["signals"] = {"fs": FS, "ir_clean": c_ir.tolist(), "red_clean": c_red.tolist(),
                              "artifact_prob": None if p_art is None else p_art.tolist()}
        return out
