// SuGuard portable signal core - public API.
//
// This is the on-device twin of the Python reference in ml/suguard_ml:
//
//   sg_sensor_state()        <->  suguard_ml.signal.quality.sensor_state
//   sg_preprocess()          <->  suguard_ml.signal.filters.preprocess (first return value)
//   sg_perfusion_index()     <->  (percentile(bv, 97) - percentile(bv, 3)) * 100
//   sg_vitals_from_signals() <->  suguard_ml.pipeline.vitals_from_signals
//
// Rules for everything under src/core:
//   * portable C++17, no Arduino/ESP headers, so it builds on a PC for tests
//   * no STL, no exceptions, no RTTI, no heap: only <stdint.h>, <stddef.h>,
//     <math.h>, <string.h>, <float.h>; all scratch memory lives in SgWork
//   * the ESP32-C3 has no FPU: `double` is soft-float (slow but exact), which
//     is fine for a few hundred thousand operations per 10.24-s window
//
// Signals are sampled at SG_FS = 50 Hz; a window is SG_WINDOW = 512 samples.
#pragma once

#include <stddef.h>
#include <stdint.h>

#define SG_FS 50.0
#define SG_WINDOW 512
#define SG_ADC_MAX 262143.0             // MAX30102: 18-bit counts
#define SG_FINGER_IR_DC_MIN 20000.0     // default no-contact threshold on the IR DC level (counts)
#define SG_FFT_N 4096                   // zero-padded FFT length used by the spectral heart rate

// Thresholds of the reliability decision (suguard_ml.pipeline).
#define SG_MAX_ARTIFACT_FRACTION 0.7
#define SG_CLEAN_MAX_MOTION 0.2         // at most this share flagged: the measured signals are the reference
#define SG_SPO2_AGREEMENT 2.0           // measured and denoised SpO2 must agree within this many points
#define SG_MIN_INPUT_PI 0.03
#define SG_MIN_SUPPORT_CORR 0.7         // denoised signal vs measurement over the clean samples ...
#define SG_SUPPORT_GAIN_MIN 0.7         // ... and the size at which the measurement contains it
#define SG_SUPPORT_GAIN_MAX 1.4
#define SG_MIN_SUPPORT_SAMPLES 10

// Why a window is not reliable (bit mask; names follow the Python reason strings).
enum SgReason : uint16_t {
  SG_R_NO_CONTACT = 1u << 0,             // "no_contact"
  SG_R_ADC_SATURATED = 1u << 1,          // "adc_saturated"
  SG_R_LED_CURRENT_TOO_HIGH = 1u << 2,   // "led_current_too_high"
  SG_R_WEAK_PULSE = 1u << 3,             // "weak_pulse"
  SG_R_IMPLAUSIBLE_AMPLITUDE = 1u << 4,  // "implausible_amplitude"
  SG_R_MOTION = 1u << 5,                 // "motion"
  SG_R_IRREGULAR_OR_NOISY = 1u << 6,     // "irregular_or_noisy"
  SG_R_RED_IR_INCONSISTENT = 1u << 7,    // "red_ir_inconsistent"
  SG_R_DENOISER_MISMATCH = 1u << 8,      // "denoiser_mismatch": the denoised pulse is not in the measurement
};

// Outcome of the SpO2 estimate itself (SpO2Estimate.reason in Python: values 0-3), and why a
// reliable window carries no SpO2 value (SignalVitals.spo2_reason: all values but 3, because a
// ratio out of range rejects the whole window).
enum SgSpo2Reason : uint8_t {
  SG_SPO2_OK = 0,
  SG_SPO2_NO_COMMON_PULSE = 1,          // "no_common_pulse"
  SG_SPO2_LOW_RED_IR_AGREEMENT = 2,     // "spo2_low_red_ir_agreement"
  SG_SPO2_R_OUT_OF_RANGE = 3,           // "r_out_of_calibration_range"
  SG_SPO2_RED_DENOISER_MISMATCH = 4,    // "red_denoiser_mismatch": the denoised red pulse is not in the measurement
  SG_SPO2_RED_IR_INCONSISTENT = 5,      // "red_ir_inconsistent": the two wavelengths disagree (quality components)
};

// Order of SgQuality::comp[], identical to the `components` dict in assess_quality().
enum SgQualityComponent : uint8_t {
  SG_Q_PERFUSION = 0,
  SG_Q_TEMPLATE,
  SG_Q_PURITY,
  SG_Q_AMPLITUDE,
  SG_Q_RHYTHM,
  SG_Q_HR_AGREEMENT,
  SG_Q_R_STABILITY,
  SG_Q_RED_IR,
  SG_Q_MOTION,
  SG_Q_COUNT
};

struct SgSensorState {
  bool finger_detected;
  double saturated_fraction;
  double ir_dc;        // median of the raw IR counts
  double red_dc;       // median of the raw red counts
  uint16_t reasons;    // SG_R_NO_CONTACT | SG_R_ADC_SATURATED | SG_R_LED_CURRENT_TOO_HIGH
};

// Mirror of suguard_ml.signal.quality.Quality. Infinite values (e.g. beat_amp_cv
// with fewer than 3 beats) are represented as +INFINITY, as in Python.
struct SgQuality {
  double perfusion_index;      // % (IR, peak-to-peak, of the analysed signal)
  double template_corr;
  double spectral_purity;      // purity of the un-primed spectral HR (prior = none)
  double red_ir_corr;
  double beat_amp_cv;
  double valid_ibi_fraction;
  double hr_agreement_bpm;
  double r_spread;
  double motion_fraction;      // share of samples with artefact probability > 0.5 (0 if p_art == NULL)
  double sqi;                  // geometric mean of comp[] (0 if the sensor checks fail)
  double comp[SG_Q_COUNT];     // a metric that cannot be computed scores 0
  bool usable;                 // sensor checks pass and the pulse timing is trustworthy (heart rate)
  bool usable_spo2;            // additionally both wavelengths trustworthy
  uint16_t reasons;            // quality + sensor reasons, as in Quality.reasons
};

// Mirror of suguard_ml.pipeline.SignalVitals (+ SpO2Estimate details).
struct SgVitals {
  bool reliable;
  uint16_t reasons;            // union of all reasons, as in SignalVitals.reasons

  bool has_hr;                 // hr_bpm is not None in Python; always true when reliable
  double hr_bpm;               // from the detected beats (valid if has_hr)
  int n_beats;                 // number of detected systolic peaks
  int n_valid_ibi;             // number of inter-beat intervals accepted as valid

  bool has_spo2;               // SignalVitals.spo2_ok: SpO2-grade window with a value
  double spo2;                 // % (valid if has_spo2)
  bool has_r;                  // SpO2Estimate.r_ratio is not None
  double r_ratio;              // ratio of ratios (valid if has_r), reported regardless of gating
  uint8_t spo2_reason;         // SgSpo2Reason of the raw estimate
  uint8_t spo2_withheld;       // SgSpo2Reason: why a reliable window has no SpO2 (SG_SPO2_OK: it has one, or was rejected)

  double pi_in;                // peak-to-peak IR perfusion (%) of the measured signal
  // InputSupport of the IR and red signals; all zero on the classical path.
  double support_ir_corr, support_ir_gain;
  double support_red_corr, support_red_gain;

  SgQuality quality;
};

// Scratch memory for all core functions. Zero-initialise once (static storage)
// and call sg_work_init(). Not re-entrant: one SgWork per thread.
struct SgWork;

// `fft_scratch` must point to at least 2 * SG_FFT_N floats (32 KiB) that stay
// valid for every later call. The caller owns it so it can be shared with
// other buffers that are not in use at the same time (the NN arena).
void sg_work_init(SgWork* w, float* fft_scratch);

// Checks on raw counts that make a window unusable no matter what.
void sg_sensor_state(const double* red_raw, const double* ir_raw, int n, double ir_dc_min,
                     SgSensorState* out, SgWork* w);

// Raw counts -> inverted, DC-normalised, 0.4-12 Hz band-passed blood-volume
// signal (systolic peaks point up). n <= SG_WINDOW. bv_out may not alias raw.
void sg_preprocess(const double* raw, int n, double* bv_out, SgWork* w);

// Peak-to-peak perfusion (%) of a blood-volume signal: (p97 - p3) * 100.
double sg_perfusion_index(const double* bv, int n, SgWork* w);

// Heart rate, SpO2 and the reliability decision for one window of n <= SG_WINDOW samples.
//   ir_bv, red_bv : the measured (band-passed) blood-volume signals
//   c_ir, c_red   : the denoiser's output                      } all three NULL on the classical path,
//   p_art         : its per-sample artefact probability [0, 1] } where the measured signals are analysed
// A denoiser can draw a pulse that is not in the measurement, so with a denoiser the result is
// reliable only if the measured signals support the denoised ones (SG_R_DENOISER_MISMATCH).
void sg_vitals_from_signals(const double* ir_bv, const double* red_bv, const double* c_ir, const double* c_red,
                            const double* p_art, int n, const SgSensorState* sensor, SgVitals* out, SgWork* w);

// sizeof(SgWork), for tests and static allocation checks.
size_t sg_work_size(void);
