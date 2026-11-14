"""SpO2 from the ratio of ratios of the red and IR blood-volume signals."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..config import SPO2_COEFFS


@dataclass
class SpO2Estimate:
    r_ratio: float | None
    spo2: float | None
    red_ir_corr: float       # 1.0 when red and IR carry the same pulse shape


def ratio_of_ratios(red_bv: np.ndarray, ir_bv: np.ndarray, weights: np.ndarray | None = None) -> tuple[float | None, float]:
    """Least-squares slope of red vs IR (both DC-normalised, band-passed).

    Because both signals are already divided by their DC, the slope equals
    (AC_red/DC_red) / (AC_ir/DC_ir). Fitting over the whole window uses every
    sample instead of only peaks and troughs, which makes it robust to noise;
    ``weights`` (e.g. 1 - artefact probability) down-weights motion.
    """
    red = np.asarray(red_bv, dtype=np.float64)
    ir = np.asarray(ir_bv, dtype=np.float64)
    w = np.ones_like(ir) if weights is None else np.clip(np.asarray(weights, dtype=np.float64), 0, 1)
    if w.sum() < 10:
        return None, 0.0
    red = red - np.average(red, weights=w)
    ir = ir - np.average(ir, weights=w)
    den = np.sum(w * ir * ir)
    if den <= 0:
        return None, 0.0
    r = float(np.sum(w * red * ir) / den)
    num = np.sum(w * red * ir)
    corr = float(num / np.sqrt(den * np.sum(w * red * red))) if np.sum(w * red * red) > 0 else 0.0
    return r, corr


def spo2_from_ratio(r: float | None, coeffs=SPO2_COEFFS) -> float | None:
    if r is None or not np.isfinite(r) or r <= 0:
        return None
    a, b, c = coeffs
    return float(np.clip(a * r * r + b * r + c, 50.0, 100.0))


def estimate_spo2(red_bv: np.ndarray, ir_bv: np.ndarray, weights: np.ndarray | None = None,
                  coeffs=SPO2_COEFFS) -> SpO2Estimate:
    r, corr = ratio_of_ratios(red_bv, ir_bv, weights)
    return SpO2Estimate(r_ratio=r, spo2=spo2_from_ratio(r, coeffs), red_ir_corr=corr)


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
