// SuGuard signal core: sensor checks, preprocessing, beat detection, spectral
// heart rate, SpO2, signal quality and the reliability decision.
//
// A line-by-line port of ml/suguard_ml (signal/filters.py, beats.py, spo2.py,
// quality.py and pipeline.vitals_from_signals); every function names its
// Python twin. Sums, filters and order statistics go through sg_dsp, which
// reproduces numpy/scipy bit for bit; only the spectrum is single precision.
#include <math.h>
#include <string.h>

#include "sg_core.h"
#include "sg_dsp.h"
#include "sg_tables.h"
#include "sg_work.h"

static_assert(sizeof(SgWork) <= 64 * 1024, "SgWork must stay within 64 KiB");

// Spectral heart rate: the (bpm, purity) pair of beats.spectral_hr.
struct SpectralHr {
  bool valid;      // bpm is not None
  double bpm;
  double purity;   // 0 if not valid
};

// Result of spo2.ratio_of_ratios.
struct Ratio {
  bool valid;      // r is not None
  double r;
  double corr;
};

// Result of spo2.estimate_spo2 (SpO2Estimate).
struct Spo2 {
  Ratio ratio;
  bool has_spo2;
  double spo2;
  uint8_t reason;  // SgSpo2Reason
};

void sg_work_init(SgWork* w, float* fft_scratch) { w->fft = fft_scratch; }

size_t sg_work_size(void) { return sizeof(SgWork); }

// Window lengths the core accepts; anything else yields an empty, unreliable result.
static bool valid_length(int n) { return n >= SG_MIN_SAMPLES && n <= SG_WINDOW; }

// round() / np.round(): nearest integer, ties to even.
static int nearest(double v) { return (int)rint(v); }

// np.median(x); `tmp` receives the sorted copy.
static double median_of(const double* x, int n, double* tmp) {
  memcpy(tmp, x, (size_t)n * sizeof(double));
  sg_sort(tmp, n);
  return sg_median_sorted(tmp, n);
}

// ---------------------------------------------------------------------------
// Sensor state and preprocessing
// ---------------------------------------------------------------------------

// quality.sensor_state
void sg_sensor_state(const double* red_raw, const double* ir_raw, int n, double ir_dc_min,
                     SgSensorState* out, SgWork* w) {
  memset(out, 0, sizeof(*out));
  if (!valid_length(n)) {
    out->reasons = SG_R_NO_CONTACT;
    return;
  }
  out->ir_dc = median_of(ir_raw, n, w->c);
  out->red_dc = median_of(red_raw, n, w->c);
  int saturated = 0;
  for (int i = 0; i < n; ++i) {
    saturated += ir_raw[i] >= SG_SATURATION_LEVEL || red_raw[i] >= SG_SATURATION_LEVEL ||
                 ir_raw[i] <= 0 || red_raw[i] <= 0;
  }
  out->saturated_fraction = (double)saturated / n;
  out->finger_detected = out->ir_dc >= ir_dc_min && out->red_dc >= 0.2 * ir_dc_min;
  if (!out->finger_detected) out->reasons |= SG_R_NO_CONTACT;
  if (out->saturated_fraction > SG_MAX_SATURATED_FRACTION) out->reasons |= SG_R_ADC_SATURATED;
  if (out->ir_dc > 0.9 * SG_ADC_MAX) out->reasons |= SG_R_LED_CURRENT_TOO_HIGH;
}

// filters.preprocess: blood_volume (estimate_dc, -(raw - dc) / dc) and the 0.4-12 Hz band-pass
void sg_preprocess(const double* raw, int n, double* bv_out, SgWork* w) {
  if (!valid_length(n)) {
    for (int i = 0; i < n; ++i) bv_out[i] = 0.0;
    return;
  }
  for (int i = 0; i < n; ++i) w->c[i] = fabs(raw[i]);
  sg_sort(w->c, n);
  const double scaled = 1e-3 * sg_median_sorted(w->c, n);
  const double dc_floor = scaled > 1.0 ? scaled : 1.0;
  sg_filtfilt(&SG_FILTER_DC, raw, n, bv_out, w->ext);
  for (int i = 0; i < n; ++i) {
    const double dc = bv_out[i] > dc_floor ? bv_out[i] : dc_floor;
    bv_out[i] = -(raw[i] - dc) / dc;
  }
  sg_filtfilt(&SG_FILTER_PPG, bv_out, n, bv_out, w->ext);
}

// (np.percentile(bv, 97) - np.percentile(bv, 3)) * 100
double sg_perfusion_index(const double* bv, int n, SgWork* w) {
  if (!valid_length(n)) return 0.0;
  memcpy(w->c, bv, (size_t)n * sizeof(double));
  sg_sort(w->c, n);
  return (sg_percentile_sorted(w->c, n, 97) - sg_percentile_sorted(w->c, n, 3)) * 100.0;
}

// ---------------------------------------------------------------------------
// Beats (beats.detect_beats)
// ---------------------------------------------------------------------------

// beats._parabolic: sub-sample position of the extremum at sample i. The sign
// of x does not matter, so this also serves _parabolic(-x, i).
static double parabolic(const double* x, int n, int i) {
  if (i > 0 && i < n - 1) {
    const double a = x[i - 1], b = x[i], c = x[i + 1];
    const double den = a - 2 * b + c;
    if (den != 0) {
      const double off = 0.5 * (a - c) / den;
      if (fabs(off) <= 0.5) return i + off;
    }
  }
  return i;
}

// Refractory period of detect_beats: of two peaks closer than the maximum
// heart rate allows, keep the larger one.
static void add_peak(SgBeats* b, const double* x, double peak) {
  const double min_dist = SG_FS * 60.0 / SG_HR_MAX_BPM;
  if (b->n > 0 && peak - b->peak[b->n - 1] < min_dist) {
    if (x[nearest(peak)] > x[nearest(b->peak[b->n - 1])]) b->peak[b->n - 1] = peak;
  } else if (b->n < SG_MAX_BEATS) {  // always true: kept peaks are >= min_dist apart
    b->peak[b->n++] = peak;
  }
}

// Peak search of detect_beats (Elgendi 2013): a block is a run of samples where
// the short moving average of the clipped, squared signal exceeds the long one.
static void find_peaks_in_blocks(const double* x, int n, SgWork* w) {
  double* y = w->c;
  double* ma_peak = w->a;
  double* ma_beat = w->b;
  for (int i = 0; i < n; ++i) {
    const double v = x[i] > 0 ? x[i] : 0.0;
    y[i] = v * v;
  }
  sg_uniform_filter(y, n, SG_MA_PEAK_LEN, ma_peak);
  sg_uniform_filter(y, n, SG_MA_BEAT_LEN, ma_beat);
  const double offset = 0.02 * sg_mean(y, n);

  SgBeats* b = &w->beats;
  b->n = 0;
  int start = -1;  // first sample of the block being scanned, -1 between blocks
  for (int i = 0; i <= n; ++i) {
    const bool in_block = i < n && ma_peak[i] > ma_beat[i] + offset;
    if (in_block && start < 0) start = i;
    if (!in_block && start >= 0) {
      if (i - start >= SG_MA_PEAK_LEN) {
        add_peak(b, x, parabolic(x, n, start + sg_argmax(x + start, i - start)));
      }
      start = -1;
    }
  }
}

// Inter-beat intervals of detect_beats, their validity and Beats.hr_bpm.
static void validate_intervals(SgBeats* b, double* tmp) {
  const double ibi_min = 60.0 / SG_HR_MAX_BPM, ibi_max = 60.0 / SG_HR_MIN_BPM;
  const int n_ibi = b->n > 1 ? b->n - 1 : 0;
  int plausible = 0;
  for (int k = 0; k < n_ibi; ++k) {
    b->ibi[k] = (b->peak[k + 1] - b->peak[k]) / SG_FS;
    b->valid[k] = b->ibi[k] >= ibi_min && b->ibi[k] <= ibi_max;
    if (b->valid[k]) tmp[plausible++] = b->ibi[k];
  }
  b->n_valid = 0;
  if (plausible > 0) {
    sg_sort(tmp, plausible);
    const double med = sg_median_sorted(tmp, plausible);
    for (int k = 0; k < n_ibi; ++k) {
      b->valid[k] = b->valid[k] && fabs(b->ibi[k] - med) <= 0.3 * med;
      if (b->valid[k]) tmp[b->n_valid++] = b->ibi[k];
    }
  }
  b->has_hr = b->n_valid >= 2;
  b->hr_bpm = 0.0;
  if (b->has_hr) b->hr_bpm = 60.0 / sg_mean(tmp, b->n_valid);   // the valid intervals, in order (np.mean)
}

// beats._find_onsets: the beat foot is the minimum within 0.6 s before each peak.
static void find_onsets(const double* x, int n, SgBeats* b) {
  int prev = 0;
  for (int k = 0; k < b->n; ++k) {
    const int peak = nearest(b->peak[k]);
    const int from = peak - SG_ONSET_LOOKBACK > prev ? peak - SG_ONSET_LOOKBACK : prev;
    b->onset[k] = peak - from < 2 ? (double)NAN : parabolic(x, n, from + sg_argmin(x + from, peak - from));
    prev = peak;
  }
}

// beats.detect_beats on the 0.5-8 Hz pulse signal x; fills w->beats.
static void detect_beats(const double* x, int n, SgWork* w) {
  find_peaks_in_blocks(x, n, w);
  validate_intervals(&w->beats, w->per_beat);
  find_onsets(x, n, &w->beats);
}

// ---------------------------------------------------------------------------
// Spectral heart rate (beats.spectral_hr)
// ---------------------------------------------------------------------------

// Sum of the spectrum over bins lo..hi.
static double band_power(const float* p, int lo, int hi) {
  double sum = 0.0;
  for (int k = lo; k <= hi; ++k) sum += p[k];
  return sum;
}

// First half of spectral_hr: |rfft((x - mean) * hann, SG_FFT_N)|^2 of the pulse
// signal into w->fft. Returns false where the reference returns (None, 0.0).
// The FFT input is scaled to unit peak, which keeps the single-precision
// spectrum in range for any signal level; every later use is a ratio or a
// comparison of spectral values, so the scale cancels.
static bool pulse_spectrum(const double* x, int n, SgWork* w) {
  double* windowed = w->c;
  const double mean = sg_mean(x, n);
  double peak = 0.0;
  for (int i = 0; i < n; ++i) {
    windowed[i] = (x[i] - mean) * sg_hann(i, n);
    if (fabs(windowed[i]) > peak) peak = fabs(windowed[i]);
  }
  if (peak == 0) return false;  // all-zero signal ("not np.any(x)") or all-zero spectrum
  memset(w->fft, 0, 2 * SG_FFT_N * sizeof(float));
  for (int i = 0; i < n; ++i) w->fft[2 * i] = (float)(windowed[i] / peak);
  sg_fft_power(w->fft);
  return band_power(w->fft, SG_K_HR_LO, SG_K_HR_HI) > 0;
}

// beats._harmonic_power: the strongest bin within SG_K_HARMONIC_SPAN bins of h * k
// (gen_tables.py checks that these bins never leave the spectrum).
static double harmonic_power(const float* p, int k, int h) {
  double best = p[h * k - SG_K_HARMONIC_SPAN];
  for (int j = h * k - SG_K_HARMONIC_SPAN + 1; j <= h * k + SG_K_HARMONIC_SPAN; ++j) {
    if (p[j] > best) best = p[j];
  }
  return best;
}

// Second half of spectral_hr (without a prior) on the spectrum p: among the
// peaks of the cardiac band with at least SG_HARMONIC_MIN_SHARE of the
// strongest one's power, the one with the most power in itself and its 2nd
// and 3rd harmonic; and its purity.
static SpectralHr spectral_peak(const float* p) {
  const float* band = p + SG_K_HR_LO;
  const int n_band = SG_K_HR_HI - SG_K_HR_LO + 1;
  double strongest = -1.0;
  int scan = 1;
  for (int c = sg_next_peak(band, n_band, &scan); c >= 0; c = sg_next_peak(band, n_band, &scan)) {
    if (band[c] > strongest) strongest = band[c];
  }
  int best = -1;
  if (strongest >= 0) {
    double best_score = 0.0;
    scan = 1;
    for (int c = sg_next_peak(band, n_band, &scan); c >= 0; c = sg_next_peak(band, n_band, &scan)) {
      if (!(band[c] >= SG_HARMONIC_MIN_SHARE * strongest)) continue;
      const int k = SG_K_HR_LO + c;
      const double score = (double)band[c] + harmonic_power(p, k, 2) + harmonic_power(p, k, 3);
      if (best < 0 || score > best_score) {
        best = c;
        best_score = score;
      }
    }
  } else {  // no local maximum in the band: take the largest bin
    best = 0;
    for (int j = 1; j < n_band; ++j) {
      if (band[j] > band[best]) best = j;
    }
  }
  const int k = SG_K_HR_LO + best;

  // Share of the 0.5-8 Hz power within 0.1 Hz of the peak and of its 2nd harmonic. The
  // total is > 0 because it includes the cardiac band, which pulse_spectrum() checked.
  SpectralHr out;
  out.valid = true;
  out.bpm = k * SG_FFT_DF * 60.0;
  out.purity = (band_power(p, k - SG_K_NEAR, k + SG_K_NEAR) + band_power(p, 2 * k - SG_K_NEAR, 2 * k + SG_K_NEAR)) /
               band_power(p, SG_K_TOTAL_LO, SG_K_TOTAL_HI);
  return out;
}

// ---------------------------------------------------------------------------
// Beat template (beats.beat_template)
// ---------------------------------------------------------------------------

// One row of S: np.interp(np.linspace(a, b, SG_TEMPLATE_LEN), np.arange(n), x) minus its mean.
static void resample_beat(const double* x, int n, double a, double b, double* row) {
  const int last = SG_TEMPLATE_LEN - 1;
  const double step = (b - a) / last;
  for (int j = 0; j <= last; ++j) row[j] = sg_interp(x, n, j == last ? b : j * step + a);
  const double mean = sg_mean(row, SG_TEMPLATE_LEN);
  for (int j = 0; j <= last; ++j) row[j] -= mean;
}

// np.corrcoef(a, b)[0, 1]
static double correlation(const double* a, const double* b, int n) {
  const double mean_a = sg_mean(a, n), mean_b = sg_mean(b, n);
  double saa = 0.0, sbb = 0.0, sab = 0.0;
  for (int i = 0; i < n; ++i) {
    const double da = a[i] - mean_a, db = b[i] - mean_b;
    saa += da * da;
    sbb += db * db;
    sab += da * db;
  }
  const double r = sab / sqrt(saa) / sqrt(sbb);
  return r > 1.0 ? 1.0 : (r < -1.0 ? -1.0 : r);
}

// beat_template: mean correlation of the onset-to-onset beats of x with their
// median (0 where the reference has no template).
static double template_correlation(const double* x, int n, const SgBeats* b, SgWork* w) {
  int rows = 0;
  double prev = NAN;  // previous finite onset; NaN fails the length test below
  for (int k = 0; k < b->n; ++k) {
    const double onset = b->onset[k];
    if (!isfinite(onset)) continue;
    const double length = onset - prev;
    if (length >= 0.28 * SG_FS && length <= 1.75 * SG_FS) resample_beat(x, n, prev, onset, w->seg[rows++]);
    prev = onset;
  }
  if (rows < 2) return 0.0;  // also covers "fewer than 3 onsets"

  for (int j = 0; j < SG_TEMPLATE_LEN; ++j) {  // tmpl = np.median(S, axis=0)
    for (int i = 0; i < rows; ++i) w->per_beat[i] = w->seg[i][j];
    sg_sort(w->per_beat, rows);
    w->tmpl[j] = sg_median_sorted(w->per_beat, rows);
  }
  if (sg_std(w->tmpl, SG_TEMPLATE_LEN, w->c) == 0) return 0.0;

  int counted = 0;  // np.nanmean of the per-beat correlations
  for (int i = 0; i < rows; ++i) {
    const bool flat = !(sg_std(w->seg[i], SG_TEMPLATE_LEN, w->c) > 0);
    const double r = flat ? 0.0 : correlation(w->seg[i], w->tmpl, SG_TEMPLATE_LEN);
    w->per_beat[i] = isnan(r) ? 0.0 : r;
    counted += !isnan(r);
  }
  return sg_sum(w->per_beat, rows) / counted;
}

// ---------------------------------------------------------------------------
// SpO2 (spo2.py)
// ---------------------------------------------------------------------------

// Weight of sample i in ratio_of_ratios: clip(1 - p_art, 0, 1), or 1 without artefact probabilities.
static double sample_weight(const double* p_art, int i) {
  if (!p_art) return 1.0;
  const double v = 1.0 - p_art[i];
  return v < 0.0 ? 0.0 : (v > 1.0 ? 1.0 : v);
}

// np.sum(w * a * b) over the sample weights w; a NULL factor stands for ones.
static double weighted_sum(const double* p_art, const double* a, const double* b, int n, double* tmp) {
  for (int i = 0; i < n; ++i) {
    double v = sample_weight(p_art, i);
    if (a) v *= a[i];
    if (b) v *= b[i];
    tmp[i] = v;
  }
  return sg_sum(tmp, n);
}

static bool all_finite(const double* x, int n) {
  for (int i = 0; i < n; ++i) {
    if (!isfinite(x[i])) return false;
  }
  return true;
}

// spo2.ratio_of_ratios: total-least-squares slope of red against IR. Both
// signals are centred in place.
static Ratio ratio_of_ratios(double* red, double* ir, const double* p_art, int n, double* tmp) {
  Ratio out = {false, 0.0, 0.0};
  const double weight_total = weighted_sum(p_art, NULL, NULL, n, tmp);
  if (weight_total < 10 || !all_finite(red, n) || !all_finite(ir, n)) return out;
  const double red_mean = weighted_sum(p_art, red, NULL, n, tmp) / weight_total;
  const double ir_mean = weighted_sum(p_art, ir, NULL, n, tmp) / weight_total;
  for (int i = 0; i < n; ++i) {
    red[i] -= red_mean;
    ir[i] -= ir_mean;
  }
  const double sxx = weighted_sum(p_art, ir, ir, n, tmp);
  const double syy = weighted_sum(p_art, red, red, n, tmp);
  const double sxy = weighted_sum(p_art, red, ir, n, tmp);
  if (sxx <= 0 || syy <= 0) return out;
  out.corr = sxy / sqrt(sxx * syy);
  if (sxy <= 0) return out;
  const double d = syy - sxx;
  out.r = (d + sqrt(d * d + 4.0 * sxy * sxy)) / (2.0 * sxy);
  out.valid = true;
  return out;
}

// spo2.spo2_from_ratio with the default calibration; false where Python returns None.
static bool spo2_from_ratio(double r, double* spo2) {
  if (!(r >= SG_R_MIN_PLAUSIBLE && r <= SG_R_MAX_CALIBRATED)) return false;  // also inf and NaN
  if (SG_SPO2_A < 0) {  // never use the ascending, non-physiological branch
    const double vertex = -SG_SPO2_B / (2 * SG_SPO2_A);
    if (vertex > r) r = vertex;
  }
  const double s = SG_SPO2_A * r * r + SG_SPO2_B * r + SG_SPO2_C;
  *spo2 = s < 100.0 ? s : 100.0;
  return true;
}

// spo2.cardiac_band: 0.7-5 Hz band-pass; windows shorter than 3 s are used as they are.
static void cardiac_band(const double* x, int n, double* y, SgWork* w) {
  if (n >= SG_BAND_MIN_SAMPLES) {
    sg_filtfilt(&SG_FILTER_CARDIAC, x, n, y, w->ext);
  } else {
    memcpy(y, x, (size_t)n * sizeof(double));
  }
}

// spo2.estimate_spo2
static Spo2 estimate_spo2(const double* c_red, const double* c_ir, const double* p_art, int n, SgWork* w) {
  double* ir = w->a;
  double* red = w->b;
  cardiac_band(c_red, n, red, w);
  cardiac_band(c_ir, n, ir, w);
  Spo2 out;
  out.ratio = ratio_of_ratios(red, ir, p_art, n, w->c);
  out.has_spo2 = false;
  out.spo2 = 0.0;
  if (!out.ratio.valid) {
    out.reason = SG_SPO2_NO_COMMON_PULSE;
  } else if (out.ratio.corr < SG_MIN_RED_IR_CORR) {
    out.reason = SG_SPO2_LOW_RED_IR_AGREEMENT;
  } else {
    out.has_spo2 = spo2_from_ratio(out.ratio.r, &out.spo2);
    out.reason = out.has_spo2 ? SG_SPO2_OK : SG_SPO2_R_OUT_OF_RANGE;
  }
  return out;
}

// ---------------------------------------------------------------------------
// Quality (quality.py)
// ---------------------------------------------------------------------------

// quality._r_spread: (max - min) / median of R over three sub-windows of the 0.7-4 Hz band.
static double r_spread(const double* c_ir, const double* c_red, int n, SgWork* w) {
  if (n < SG_BAND_MIN_SAMPLES) return INFINITY;
  double* ir = w->a;
  double* red = w->b;
  sg_filtfilt(&SG_FILTER_RSPREAD, c_ir, n, ir, w->ext);
  sg_filtfilt(&SG_FILTER_RSPREAD, c_red, n, red, w->ext);
  const int parts = 3, len = n / parts;
  double rs[parts];
  int found = 0;
  for (int k = 0; k < parts; ++k) {
    const Ratio part = ratio_of_ratios(red + k * len, ir + k * len, NULL, len, w->c);
    if (part.valid) rs[found++] = part.r;
  }
  if (found < 2) return INFINITY;
  sg_sort(rs, found);
  const double med = sg_median_sorted(rs, found);
  return med > 0 ? (rs[found - 1] - rs[0]) / med : INFINITY;
}

// Beat-to-beat amplitude CV of assess_quality: std / mean of the positive
// foot-to-peak amplitudes, infinite with fewer than 3 of them.
static double amplitude_cv(const double* ir, int n, const SgBeats* b, SgWork* w) {
  double* amps = w->per_beat;
  int count = 0;
  for (int k = 0; k < b->n; ++k) {
    if (!isfinite(b->onset[k])) continue;
    const int peak = nearest(b->peak[k]), onset = nearest(b->onset[k]);
    if (peak < 0 || peak >= n || onset < 0 || onset >= n) continue;
    const double amp = ir[peak] - ir[onset];
    if (amp > 0) amps[count++] = amp;
  }
  return count >= 3 ? sg_std(amps, count, w->c) / sg_mean(amps, count) : INFINITY;
}

// Share of samples the denoiser flags as artefact (0 on the classical path).
static double motion_fraction(const double* p_art, int n) {
  if (!p_art) return 0.0;
  int flagged = 0;
  for (int i = 0; i < n; ++i) flagged += p_art[i] > 0.5;
  return (double)flagged / n;
}

// quality._ramp: rises from 0 at lo to 1 at hi; an undefined metric scores 0.
static double ramp(double x, double lo, double hi) {
  if (!isfinite(x)) return 0.0;
  const double t = (x - lo) / (hi - lo);
  return t < 0.0 ? 0.0 : (t > 1.0 ? 1.0 : t);
}

// quality._ramp_down: falls from 1 at lo to 0 at hi; an undefined metric scores 0 as well.
static double ramp_down(double x, double lo, double hi) { return isfinite(x) ? 1.0 - ramp(x, lo, hi) : 0.0; }

// Bit of quality component k in a component mask.
static unsigned bit(int k) { return 1u << k; }

// Geometric mean of the components selected by `mask`, each clipped to [1e-3, 1].
static double geometric_mean(const double* comp, unsigned mask) {
  double logs[SG_Q_COUNT];
  int count = 0;
  for (int k = 0; k < SG_Q_COUNT; ++k) {
    if (!(mask & bit(k))) continue;
    const double v = comp[k] < 1e-3 ? 1e-3 : (comp[k] > 1.0 ? 1.0 : comp[k]);
    logs[count++] = log(v);
  }
  return exp(sg_mean(logs, count));
}

// quality.assess_quality. `spec` is spectral_hr(ir); the beats are in w->beats.
static void assess_quality(const double* ir, const double* red, const double* p_art, int n,
                           const SgSensorState* sensor, double red_ir_corr, const SpectralHr* spec,
                           SgQuality* q, SgWork* w) {
  const SgBeats* b = &w->beats;
  q->perfusion_index = sg_perfusion_index(ir, n, w);
  q->template_corr = template_correlation(ir, n, b, w);
  q->spectral_purity = spec->purity;
  q->red_ir_corr = red_ir_corr;
  q->beat_amp_cv = amplitude_cv(ir, n, b, w);
  q->valid_ibi_fraction = b->n > 1 ? (double)b->n_valid / (b->n - 1) : 0.0;
  q->hr_agreement_bpm = b->has_hr && spec->valid ? fabs(b->hr_bpm - spec->bpm) : INFINITY;
  q->r_spread = r_spread(ir, red, n, w);
  q->motion_fraction = motion_fraction(p_art, n);

  const double pi = q->perfusion_index;
  q->comp[SG_Q_PERFUSION] = ramp(pi, 0.03, 0.12) * (1.0 - ramp(pi, 10.0, 20.0));
  q->comp[SG_Q_TEMPLATE] = ramp(q->template_corr, 0.5, 0.9);
  q->comp[SG_Q_PURITY] = ramp(q->spectral_purity, 0.15, 0.5);
  q->comp[SG_Q_AMPLITUDE] = ramp_down(q->beat_amp_cv, 0.2, 0.4);
  q->comp[SG_Q_RHYTHM] = ramp(q->valid_ibi_fraction, 0.85, 0.95);
  q->comp[SG_Q_HR_AGREEMENT] = ramp_down(q->hr_agreement_bpm, 5.0, 15.0);
  q->comp[SG_Q_R_STABILITY] = ramp_down(q->r_spread, 0.08, 0.25);
  q->comp[SG_Q_RED_IR] = ramp(q->red_ir_corr, 0.5, 0.8);
  q->comp[SG_Q_MOTION] = 1.0 - q->motion_fraction;

  // Heart rate needs a clean pulse train; SpO2 additionally needs both wavelengths to agree.
  const unsigned all = (1u << SG_Q_COUNT) - 1;
  const unsigned hr_parts = all & ~(bit(SG_Q_R_STABILITY) | bit(SG_Q_RED_IR));
  unsigned failing = 0;
  for (int k = 0; k < SG_Q_COUNT; ++k) {
    if (q->comp[k] < SG_COMPONENT_MIN) failing |= bit(k);
  }
  q->sqi = geometric_mean(q->comp, all);
  const double sqi_hr = geometric_mean(q->comp, hr_parts);

  const bool sensor_ok = sensor->finger_detected && sensor->saturated_fraction <= SG_MAX_SATURATED_FRACTION;
  q->reasons = sensor->reasons;
  if (!sensor_ok) q->sqi = 0.0;
  if (failing & bit(SG_Q_PERFUSION)) q->reasons |= pi < 1.0 ? SG_R_WEAK_PULSE : SG_R_IMPLAUSIBLE_AMPLITUDE;
  // Too few beats to measure (undefined amplitude spread / heart-rate agreement) is "noisy", not "motion".
  unsigned undefined = 0;
  if (!isfinite(q->beat_amp_cv)) undefined |= bit(SG_Q_AMPLITUDE);
  if (!isfinite(q->hr_agreement_bpm)) undefined |= bit(SG_Q_HR_AGREEMENT);
  const unsigned motion_parts = bit(SG_Q_HR_AGREEMENT) | bit(SG_Q_AMPLITUDE);
  if (q->motion_fraction > 0.5 || (failing & motion_parts & ~undefined)) q->reasons |= SG_R_MOTION;
  if (failing & (bit(SG_Q_TEMPLATE) | bit(SG_Q_PURITY) | bit(SG_Q_RHYTHM) | undefined)) {
    q->reasons |= SG_R_IRREGULAR_OR_NOISY;
  }
  if (failing & (bit(SG_Q_R_STABILITY) | bit(SG_Q_RED_IR))) q->reasons |= SG_R_RED_IR_INCONSISTENT;
  q->usable = sensor_ok && sqi_hr >= SG_USABLE_SQI && !(failing & hr_parts);
  q->usable_spo2 = q->usable && q->sqi >= SG_USABLE_SQI && !failing;
}

// ---------------------------------------------------------------------------
// pipeline.input_support and pipeline.vitals_from_signals
// ---------------------------------------------------------------------------

// pipeline.InputSupport
struct Support {
  double corr;
  double gain;
};

// InputSupport.ok
static bool supported(Support s) {
  return s.corr >= SG_MIN_SUPPORT_CORR && s.gain >= SG_SUPPORT_GAIN_MIN && s.gain <= SG_SUPPORT_GAIN_MAX;
}

// pipeline.input_support: correlation and gain of the measured signal against the denoised
// one over the samples with artefact probability <= 0.5 (0, 0 if that cannot be computed).
static Support input_support(const double* measured, const double* denoised, const double* p_art, int n, SgWork* w) {
  Support out = {0.0, 0.0};
  double* x = w->a;
  double* y = w->b;
  int kept = 0;
  for (int i = 0; i < n; ++i) {
    if (!(p_art[i] <= 0.5)) continue;
    x[kept] = measured[i];
    y[kept] = denoised[i];
    ++kept;
  }
  if (kept < SG_MIN_SUPPORT_SAMPLES || !all_finite(x, kept) || !all_finite(y, kept)) return out;
  const double mean_x = sg_mean(x, kept), mean_y = sg_mean(y, kept);
  for (int i = 0; i < kept; ++i) {
    x[i] -= mean_x;
    y[i] -= mean_y;
  }
  const double sxx = weighted_sum(NULL, x, x, kept, w->c);
  const double syy = weighted_sum(NULL, y, y, kept, w->c);
  const double sxy = weighted_sum(NULL, x, y, kept, w->c);
  if (sxx <= 0 || syy <= 0) return out;
  out.corr = sxy / sqrt(sxx * syy);
  out.gain = sxy / syy;
  return out;
}

void sg_vitals_from_signals(const double* ir_bv, const double* red_bv, const double* c_ir, const double* c_red,
                            const double* p_art, int n, const SgSensorState* sensor, SgVitals* out, SgWork* w) {
  memset(out, 0, sizeof(*out));
  out->spo2_reason = SG_SPO2_NO_COMMON_PULSE;
  if (!valid_length(n)) return;
  const bool denoised = p_art != NULL;
  if (!denoised) {
    c_ir = ir_bv;
    c_red = red_bv;
  }
  out->pi_in = sg_perfusion_index(ir_bv, n, w);

  // detect_beats and spectral_hr band-pass the IR signal identically (0.5-8 Hz): filter once.
  sg_filtfilt(&SG_FILTER_PULSE, c_ir, n, w->pulse, w->ext);
  detect_beats(w->pulse, n, w);
  const SgBeats* beats = &w->beats;
  SpectralHr spec = {false, 0.0, 0.0};
  if (pulse_spectrum(w->pulse, n, w)) spec = spectral_peak(w->fft);

  // pipeline.CLEAN_MAX_MOTION: where the network flags (almost) no motion, the measured signals are
  // the reference. The spectral rate the beats must agree with comes from the measured IR (the
  // purity stays that of the denoised signal), and SpO2 from the measured red/IR.
  const bool clean = denoised && motion_fraction(p_art, n) <= SG_CLEAN_MAX_MOTION;
  if (clean) {
    sg_filtfilt(&SG_FILTER_PULSE, ir_bv, n, w->pulse, w->ext);   // the beats are already detected
    SpectralHr ref = {false, 0.0, 0.0};
    if (pulse_spectrum(w->pulse, n, w)) ref = spectral_peak(w->fft);
    spec.valid = ref.valid;
    spec.bpm = ref.bpm;
  }

  const Spo2 sp = clean ? estimate_spo2(red_bv, ir_bv, p_art, n, w) : estimate_spo2(c_red, c_ir, p_art, n, w);
  SgQuality* q = &out->quality;
  assess_quality(c_ir, c_red, p_art, n, sensor, sp.ratio.corr, &spec, q, w);

  bool mismatch = false, red_supported = true;
  if (denoised) {
    const Support ir = input_support(ir_bv, c_ir, p_art, n, w);
    const Support red = input_support(red_bv, c_red, p_art, n, w);
    out->support_ir_corr = ir.corr;
    out->support_ir_gain = ir.gain;
    out->support_red_corr = red.corr;
    out->support_red_gain = red.gain;
    mismatch = !supported(ir);
    red_supported = supported(red);
  }
  const bool weak = out->pi_in < SG_MIN_INPUT_PI;
  // Both wavelengths carry the same waveform, but in a ratio no arterial blood produces.
  const bool non_arterial = sp.reason == SG_SPO2_R_OUT_OF_RANGE;

  out->reasons = q->reasons;
  if (weak) out->reasons |= SG_R_WEAK_PULSE;
  if (mismatch) out->reasons |= SG_R_DENOISER_MISMATCH;
  if (non_arterial) out->reasons |= SG_R_RED_IR_INCONSISTENT;
  out->reliable = q->usable && q->motion_fraction <= SG_MAX_ARTIFACT_FRACTION && !(weak || mismatch || non_arterial);

  out->has_hr = beats->has_hr;   // a usable window always has it: without it the HR agreement is undefined
  out->hr_bpm = beats->has_hr ? beats->hr_bpm : 0.0;
  out->n_beats = beats->n;
  out->n_valid_ibi = beats->n_valid;

  out->has_spo2 = out->reliable && q->usable_spo2 && red_supported && sp.has_spo2;
  out->spo2 = out->has_spo2 ? sp.spo2 : 0.0;
  out->has_r = sp.ratio.valid;
  out->r_ratio = sp.ratio.r;
  out->spo2_reason = sp.reason;
  if (out->reliable && !out->has_spo2) {
    if (sp.reason != SG_SPO2_OK) {
      out->spo2_withheld = sp.reason;
    } else {
      out->spo2_withheld = red_supported ? SG_SPO2_RED_IR_INCONSISTENT : SG_SPO2_RED_DENOISER_MISMATCH;
    }
  }
}
