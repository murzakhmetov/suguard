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
    motion_fraction: float          # share of samples flagged as artefact
    sqi: float                      # 0..1
    usable: bool
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def _ramp(x: float, lo: float, hi: float) -> float:
    return float(np.clip((x - lo) / (hi - lo), 0.0, 1.0))


def assess_quality(ir_bv: np.ndarray, red_bv: np.ndarray, beats: Beats, fs: float = FS,
                   artifact_prob: np.ndarray | None = None, sensor: SensorState | None = None,
                   red_ir_corr: float | None = None, usable_threshold: float = 0.5) -> Quality:
    """Combine standard PPG quality indices into one score.

    * perfusion index - pulse too weak to measure below ~0.05 %
    * template correlation - beats look alike (Li & Clifford 2012)
    * spectral purity - power concentrated at the heart rate and harmonic
    * red/IR correlation - both wavelengths see the same arterial pulse;
      motion lowers it because it affects them with a different ratio
    * artefact fraction - from the denoiser's mask head, when available
    Skewness (Elgendi 2016) is reported but not used in the score: it depends
    on morphology as much as on quality.
    """
    ir = np.asarray(ir_bv, dtype=np.float64)
    pi = float(np.percentile(ir, 97) - np.percentile(ir, 3)) * 100.0
    skew = float(stats.skew(ir)) if ir.size > 3 and np.std(ir) > 0 else 0.0
    _, tcorr = beat_template(ir, beats)
    _, purity = spectral_hr(ir, fs)
    if red_ir_corr is None:
        a, b = ir - ir.mean(), np.asarray(red_bv) - np.mean(red_bv)
        den = np.sqrt(np.sum(a * a) * np.sum(b * b))
        red_ir_corr = float(np.sum(a * b) / den) if den > 0 else 0.0
    motion = float(np.mean(artifact_prob > 0.5)) if artifact_prob is not None else 0.0

    s_pi = _ramp(pi, 0.03, 0.12)
    s_t = _ramp(tcorr, 0.5, 0.9)
    s_p = _ramp(purity, 0.15, 0.5)
    s_c = _ramp(red_ir_corr, 0.5, 0.95)
    s_m = 1.0 - motion
    parts = np.array([s_pi, s_t, s_p, s_c, s_m])
    sqi = float(np.exp(np.mean(np.log(np.clip(parts, 1e-3, 1.0)))))  # geometric mean

    reasons = []
    if sensor is not None:
        reasons += sensor.reasons
        if not sensor.finger_detected or sensor.saturated_fraction > 0.05:
            sqi = 0.0
    if s_pi == 0:
        reasons.append("weak_pulse")
    if motion > 0.5:
        reasons.append("motion")
    elif s_t < 0.3 or s_p < 0.3:
        reasons.append("irregular_or_noisy")
    return Quality(perfusion_index=pi, skewness=skew, template_corr=tcorr, spectral_purity=purity,
                   red_ir_corr=float(red_ir_corr), motion_fraction=motion, sqi=sqi,
                   usable=sqi >= usable_threshold, reasons=reasons)
