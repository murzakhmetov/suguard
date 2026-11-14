"""Signal quality: sensor state checks and a PPG signal quality index (SQI)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

import numpy as np
from scipy import stats

from ..config import ADC_MAX, FINGER_IR_DC_MIN, FS, SATURATION_LEVEL
from .beats import Beats, beat_template, spectral_hr


@dataclass
class SensorState:
    finger_detected: bool
    saturated_fraction: float
    ir_dc: float
    red_dc: float
    reasons: list[str] = field(default_factory=list)


def sensor_state(red_raw: np.ndarray, ir_raw: np.ndarray, ir_dc_min: float = FINGER_IR_DC_MIN) -> SensorState:
    """Checks on the raw counts that make a window unusable no matter what."""
    red = np.asarray(red_raw, dtype=np.float64)
    ir = np.asarray(ir_raw, dtype=np.float64)
    ir_dc, red_dc = float(np.median(ir)), float(np.median(red))
    sat = float(np.mean((ir >= SATURATION_LEVEL) | (red >= SATURATION_LEVEL) | (ir <= 0) | (red <= 0)))
    reasons = []
    finger = ir_dc >= ir_dc_min and red_dc >= 0.2 * ir_dc_min
    if not finger:
        reasons.append("no_contact")
    if sat > 0.05:
        reasons.append("adc_saturated")
    if ir_dc > 0.9 * ADC_MAX:
        reasons.append("led_current_too_high")
    return SensorState(finger_detected=finger, saturated_fraction=sat, ir_dc=ir_dc, red_dc=red_dc, reasons=reasons)


@dataclass
class Quality:
    perfusion_index: float          # % (IR AC/DC, peak-to-peak)
    skewness: float
    template_corr: float
    spectral_purity: float
    red_ir_corr: float
    beat_amp_cv: float
    valid_ibi_fraction: float
    hr_agreement_bpm: float         # |HR from beats - HR from spectrum|
    r_spread: float                 # spread of the ratio of ratios across sub-windows
    motion_fraction: float          # share of samples flagged as artefact by the denoiser
    sqi: float                      # 0..1
    usable: bool                    # pulse timing trustworthy (heart rate)
    usable_spo2: bool = False       # additionally both wavelengths trustworthy (SpO2, features)
    components: dict = field(default_factory=dict)
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def _ramp(x: float, lo: float, hi: float) -> float:
    if not np.isfinite(x):
        return 0.0
    return float(np.clip((x - lo) / (hi - lo), 0.0, 1.0))


def _r_spread(ir: np.ndarray, red: np.ndarray, fs: float = FS, parts: int = 3) -> float:
    """Relative spread (max-min over median) of the red/IR slope over
    sub-windows, in the cardiac band.

    Arterial R is constant over 10 s; motion mixes in its own ratio and makes
    R wander. The cardiac band (0.7-4 Hz) excludes respiratory/venous baseline
    modulation, whose red/IR ratio legitimately differs from the arterial one.
    On simulated windows: clean p97 ~0.07, motion-dominated median ~0.15;
    the overlap means this can only veto large spreads (> ~0.2), otherwise it
    lowers the combined score.
    """
    from .filters import bandpass
    from .spo2 import ratio_of_ratios

    if ir.size < 3 * fs:
        return np.inf
    ir, red = bandpass(ir, fs, 0.7, 4.0), bandpass(red, fs, 0.7, 4.0)
    n = ir.size // parts
    rs = []
    for k in range(parts):
        r, _ = ratio_of_ratios(red[k * n:(k + 1) * n], ir[k * n:(k + 1) * n])
        if r is not None:
            rs.append(r)
    return float(np.ptp(rs) / np.median(rs)) if len(rs) >= 2 and np.median(rs) > 0 else np.inf


# Minimum score every component must reach (a single failing check cannot be
# averaged away by the others), and the threshold on the combined score.
COMPONENT_MIN = 0.25
USABLE_SQI = 0.5


def assess_quality(ir_bv: np.ndarray, red_bv: np.ndarray, beats: Beats, fs: float = FS,
                   artifact_prob: np.ndarray | None = None, sensor: SensorState | None = None,
                   red_ir_corr: float | None = None, usable_threshold: float = USABLE_SQI) -> Quality:
    """Quality of a (raw or denoised) window from complementary indices.

    * perfusion index, two-sided: < ~0.03 % no measurable pulse; > ~10 %
      is not a pulse but motion or contact change
    * template correlation (Li & Clifford 2012) and spectral purity
    * beat-to-beat amplitude CV and share of plausible inter-beat intervals
    * agreement between beat-based and spectral heart rate
    * stability of the red/IR ratio across sub-windows (motion makes it drift)
    * red/IR correlation as a lower bound only: motion common to both LEDs
      *raises* it, so it cannot certify a motion-free window
    * artefact fraction from the denoiser's mask head, when available
    Skewness (Elgendi 2016) is reported, not scored.
    """
    ir = np.asarray(ir_bv, dtype=np.float64)
    red = np.asarray(red_bv, dtype=np.float64)
    pi = float(np.percentile(ir, 97) - np.percentile(ir, 3)) * 100.0
    skew = float(stats.skew(ir)) if ir.size > 3 and np.std(ir) > 0 else 0.0
    _, tcorr = beat_template(ir, beats)
    hr_spec, purity = spectral_hr(ir, fs)
    if red_ir_corr is None:
        a, b = ir - ir.mean(), red - red.mean()
        den = np.sqrt(np.sum(a * a) * np.sum(b * b))
        red_ir_corr = float(np.sum(a * b) / den) if den > 0 else 0.0

    pk = np.round(beats.peaks).astype(int)
    on = beats.onsets
    amps = np.array([ir[p] - ir[int(round(o))] for p, o in zip(pk, on)
                     if np.isfinite(o) and 0 <= p < ir.size and 0 <= int(round(o)) < ir.size])
    amps = amps[amps > 0]
    amp_cv = float(np.std(amps) / np.mean(amps)) if amps.size >= 3 else np.inf
    valid_frac = float(np.mean(beats.valid_ibi)) if beats.valid_ibi.size else 0.0
    hr_b = beats.hr_bpm
    hr_diff = abs(hr_b - hr_spec) if (hr_b is not None and hr_spec is not None) else np.inf
    r_spread = _r_spread(ir, red, fs)
    motion = float(np.mean(artifact_prob > 0.5)) if artifact_prob is not None else 0.0

    comp = {
        "perfusion": _ramp(pi, 0.03, 0.12) * (1.0 - _ramp(pi, 10.0, 20.0)),
        "template": _ramp(tcorr, 0.5, 0.9),
        "purity": _ramp(purity, 0.15, 0.5),
        "amplitude": 1.0 - _ramp(amp_cv, 0.2, 0.4),
        "rhythm": _ramp(valid_frac, 0.85, 0.95),
        "hr_agreement": 1.0 - _ramp(hr_diff, 5.0, 15.0),
        "r_stability": 1.0 - _ramp(r_spread, 0.08, 0.25),
        "red_ir": _ramp(red_ir_corr, 0.5, 0.8),
        "motion": 1.0 - motion,
    }
    parts = np.array(list(comp.values()))
    sqi = float(np.exp(np.mean(np.log(np.clip(parts, 1e-3, 1.0)))))  # geometric mean
    failing = [k for k, v in comp.items() if v < COMPONENT_MIN]
    # Heart rate needs a clean pulse train; SpO2 (and the red/IR features used
    # for glucose) additionally needs both wavelengths to agree. A quiet but
    # noisy, weakly perfused window can give a good HR and no SpO2.
    hr_parts = [k for k in comp if k not in ("r_stability", "red_ir")]
    sqi_hr = float(np.exp(np.mean(np.log(np.clip([comp[k] for k in hr_parts], 1e-3, 1.0)))))
    fail_hr = [k for k in failing if k in hr_parts]

    reasons = []
    if sensor is not None:
        reasons += sensor.reasons
        if not sensor.finger_detected or sensor.saturated_fraction > 0.05:
            sqi = 0.0
    if comp["perfusion"] < COMPONENT_MIN:
        reasons.append("weak_pulse" if pi < 1.0 else "implausible_amplitude")
    if motion > 0.5 or {"hr_agreement", "amplitude"} & set(failing):
        reasons.append("motion")
    if {"template", "purity", "rhythm"} & set(failing):
        reasons.append("irregular_or_noisy")
    if {"r_stability", "red_ir"} & set(failing):
        reasons.append("red_ir_inconsistent")
    usable = sqi_hr >= usable_threshold and not fail_hr
    usable_spo2 = usable and sqi >= usable_threshold and not failing
    return Quality(perfusion_index=pi, skewness=skew, template_corr=tcorr, spectral_purity=purity,
                   red_ir_corr=float(red_ir_corr), beat_amp_cv=amp_cv, valid_ibi_fraction=valid_frac,
                   hr_agreement_bpm=float(hr_diff), r_spread=r_spread, motion_fraction=motion, sqi=sqi,
                   usable=bool(usable), usable_spo2=bool(usable_spo2),
                   components={k: round(v, 3) for k, v in comp.items()},
                   reasons=sorted(set(reasons)))
