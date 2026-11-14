"""Shared constants for the SuGuard ML pipeline.

The wearable uses a Maxim/Analog Devices MAX30102: two LEDs (red 660 nm,
infrared 880 nm), one photodiode and an 18-bit ADC. Raw samples are photon
counts, so *more* arterial blood means *less* light and a *lower* count.
Everything downstream works on the inverted, DC-normalised "blood volume"
signal  bv = -(raw - DC) / DC, whose systolic peaks point up.
"""

from __future__ import annotations

# Canonical sampling rate of the ML pipeline. PPG content lies below ~12 Hz,
# so 50 Hz keeps the full waveform while halving the denoiser cost compared
# with the 100 Hz the MAX30102 is usually configured for. Inputs at any other
# rate are resampled with an anti-aliasing filter (see signal.filters).
FS: float = 50.0

# Analysis window fed to the denoiser: 512 samples = 10.24 s at 50 Hz.
WINDOW: int = 512
WINDOW_S: float = WINDOW / FS

# MAX30102 ADC: 18-bit unsigned counts.
ADC_BITS: int = 18
ADC_MAX: int = 2**ADC_BITS - 1
SATURATION_LEVEL: float = 0.98 * ADC_MAX

# No-finger / not-worn detection on the IR DC level (counts). The SparkFun and
# Maxim examples use ~50 000 at their default LED current; the threshold is a
# per-device setting because it scales with LED current and ADC range.
FINGER_IR_DC_MIN: float = 20_000.0

# Physiological limits.
HR_MIN_BPM: float = 35.0
HR_MAX_BPM: float = 210.0
HR_BAND_HZ: tuple[float, float] = (HR_MIN_BPM / 60.0, HR_MAX_BPM / 60.0)

# Band of the pulsatile component kept by the preprocessing filter.
PPG_BAND_HZ: tuple[float, float] = (0.4, 12.0)

# Default SpO2 calibration: Maxim's reference design (RD117 / MAXREFDES117)
# quadratic in the ratio of ratios R = (AC_red/DC_red) / (AC_ir/DC_ir).
# A device-specific curve must be fitted against a reference oximeter
# (see models.spo2_calibration) before SpO2 values are used clinically.
SPO2_COEFFS: tuple[float, float, float] = (-45.060, 30.354, 94.845)  # a*R^2 + b*R + c

# Glucose units.
MGDL_PER_MMOL: float = 18.0
