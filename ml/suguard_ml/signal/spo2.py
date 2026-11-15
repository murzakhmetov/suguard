"""SpO2 from the ratio of ratios of the red and IR blood-volume signals."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..config import FS, SPO2_COEFFS

# Accept R only on the descending (physiological) branch of the calibration
# curve and below the curve's validated range (Maxim curve: R 1.1 ~ 74 %).
# Ratios a little under the vertex (-b/2a ~ 0.34) are well-perfused, ~100 %
# readings; much lower or higher ratios are noise, not physiology. The floor
# keeps 11 % of margin below the vertex for noise at full saturation (genuine
# simulated windows up to 99.5 %, R 0.44, never estimate below 0.43). It was
# 0.25, and a red pulse attenuated to a fifth (R 0.26-0.28) then read 100 %.
R_MIN_PLAUSIBLE = 0.30
R_MAX_CALIBRATED = 1.1
# Below this red/IR agreement the two channels do not see the same arterial
# pulse (noise, motion, ambient light) and the ratio is not trustworthy.
MIN_RED_IR_CORR = 0.9
# R is computed on the cardiac band only: respiratory/venous modulation below
# ~0.5 Hz has its own red/IR ratio and biases SpO2 (simulated clean windows:
# MAE 0.57 -> 0.16 points, p90 1.75 -> 0.30).
CARDIAC_BAND_HZ = (0.7, 5.0)


def cardiac_band(x: np.ndarray, fs: float = FS) -> np.ndarray:
    from .filters import bandpass

    x = np.asarray(x, dtype=np.float64)
    return bandpass(x, fs, *CARDIAC_BAND_HZ) if x.size >= 3 * fs else x


@dataclass
class SpO2Estimate:
    r_ratio: float | None
    spo2: float | None
    red_ir_corr: float       # 1.0 when red and IR carry the same pulse shape
    reason: str | None = None


def ratio_of_ratios(red_bv: np.ndarray, ir_bv: np.ndarray, weights: np.ndarray | None = None) -> tuple[float | None, float]:
    """Slope of red vs IR (both DC-normalised, band-passed) by total least squares.

    Because both signals are already divided by their DC, the slope equals
    (AC_red/DC_red) / (AC_ir/DC_ir). An ordinary least-squares slope of red on
    IR is biased towards zero when IR is noisy (errors in variables), which
    would read SpO2 too *high* exactly when the pulse is weak; the symmetric
    total-least-squares (Deming, noise ratio 1) slope is not. Both signals
    carry sensor noise of similar relative size, so a ratio of 1 is used.
    ``weights`` (e.g. 1 - artefact probability) down-weights motion.
    """
    red = np.asarray(red_bv, dtype=np.float64)
    ir = np.asarray(ir_bv, dtype=np.float64)
    w = np.ones_like(ir) if weights is None else np.clip(np.asarray(weights, dtype=np.float64), 0, 1)
    if w.sum() < 10 or not (np.isfinite(red).all() and np.isfinite(ir).all()):
        return None, 0.0
    red = red - np.average(red, weights=w)
    ir = ir - np.average(ir, weights=w)
    sxx = float(np.sum(w * ir * ir))
    syy = float(np.sum(w * red * red))
    sxy = float(np.sum(w * red * ir))
    if sxx <= 0 or syy <= 0:
        return None, 0.0
    corr = sxy / np.sqrt(sxx * syy)
    if sxy <= 0:
        return None, float(corr)
    r = (syy - sxx + np.sqrt((syy - sxx) ** 2 + 4.0 * sxy * sxy)) / (2.0 * sxy)
    return float(r), float(corr)


def spo2_from_ratio(r: float | None, coeffs=SPO2_COEFFS,
                    r_range: tuple[float, float] = (R_MIN_PLAUSIBLE, R_MAX_CALIBRATED)) -> float | None:
    """SpO2 (%) from R, or None if R is outside the calibrated range."""
    if r is None or not np.isfinite(r) or not (r_range[0] <= r <= r_range[1]):
        return None
    a, b, c = coeffs
    if a < 0:
        r = max(r, -b / (2 * a))  # never use the ascending, non-physiological branch
    return float(min(a * r * r + b * r + c, 100.0))


def estimate_spo2(red_bv: np.ndarray, ir_bv: np.ndarray, weights: np.ndarray | None = None,
                  coeffs=SPO2_COEFFS, min_corr: float = MIN_RED_IR_CORR, fs: float = FS) -> SpO2Estimate:
    r, corr = ratio_of_ratios(cardiac_band(red_bv, fs), cardiac_band(ir_bv, fs), weights)
    if r is None:
        return SpO2Estimate(r_ratio=None, spo2=None, red_ir_corr=corr, reason="no_common_pulse")
    if corr < min_corr:
        return SpO2Estimate(r_ratio=r, spo2=None, red_ir_corr=corr, reason="spo2_low_red_ir_agreement")
    s = spo2_from_ratio(r, coeffs)
    return SpO2Estimate(r_ratio=r, spo2=s, red_ir_corr=corr,
                        reason=None if s is not None else "r_out_of_calibration_range")


def fit_spo2_calibration(r_values: np.ndarray, ref_spo2: np.ndarray, quadratic: bool = True) -> tuple[float, float, float]:
    """Fit a device-specific SpO2(R) curve against a reference oximeter.

    Returns coefficients ``(a, b, c)`` for ``a*R^2 + b*R + c`` (``a = 0`` for
    a linear fit). Needs paired readings that span the SpO2 range of interest
    (a hypoxia study, or at least a wide range of normal values).
    """
    r = np.asarray(r_values, dtype=np.float64)
    y = np.asarray(ref_spo2, dtype=np.float64)
    if quadratic:
        a, b, c = np.polyfit(r, y, 2)
        return float(a), float(b), float(c)
    b, c = np.polyfit(r, y, 1)
    return 0.0, float(b), float(c)
