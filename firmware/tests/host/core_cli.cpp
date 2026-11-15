// Test harness for the signal core (firmware/tests/test_core_parity.py).
// Runs on the host and, through semihosting, on RV32 under QEMU.
//
//   core_cli <in.bin> <out.bin>         run whole windows through the core
//   core_cli --fields                   print the names of the scalar outputs of a window
//   core_cli --dsp <in.bin> <out.bin>   call single sg_dsp building blocks
//
// All files are streams of little-endian doubles.
//
// Windows
//   in :  n_cases, then for each case
//           n, mode, ir_dc_min, red_raw[n], ir_raw[n]
//           and for mode 1 also c_ir[n], c_red[n], p_art[n]
//   out:  n_cases, n_fields, sg_work_size(), then for each case
//           the scalar outputs in --fields order, ir_bv[n], red_bv[n]
//   Every case computes the sensor state and both preprocessed signals from
//   the raw counts. The vitals then come from
//     mode 0 (classical): the preprocessed signals alone
//     mode 1 (denoised) : the preprocessed signals and the given c_ir, c_red and p_art
//
// Building blocks (--dsp)
//   in :  for each call  op (DspOp), n, m, param, a[n], b[m]
//   out:  for each call  count, values[count]
#include <stdio.h>
#include <string.h>

#include "sg_core.h"
#include "sg_dsp.h"
#include "sg_tables.h"
#include "sg_work.h"

// name, value: the scalar outputs of one case.
#define FIELDS(X)                                             \
  X(n, n)                                                     \
  X(finger_detected, sensor.finger_detected)                  \
  X(saturated_fraction, sensor.saturated_fraction)            \
  X(ir_dc, sensor.ir_dc)                                      \
  X(red_dc, sensor.red_dc)                                    \
  X(sensor_reasons, sensor.reasons)                           \
  X(pi_in, v.pi_in)                                           \
  X(reliable, v.reliable)                                     \
  X(reasons, v.reasons)                                       \
  X(has_hr, v.has_hr)                                         \
  X(hr_bpm, v.hr_bpm)                                         \
  X(n_beats, v.n_beats)                                       \
  X(n_valid_ibi, v.n_valid_ibi)                               \
  X(has_spo2, v.has_spo2)                                     \
  X(spo2, v.spo2)                                             \
  X(has_r, v.has_r)                                           \
  X(r_ratio, v.r_ratio)                                       \
  X(spo2_reason, v.spo2_reason)                               \
  X(spo2_withheld, v.spo2_withheld)                           \
  X(support_ir_corr, v.support_ir_corr)                       \
  X(support_ir_gain, v.support_ir_gain)                       \
  X(support_red_corr, v.support_red_corr)                     \
  X(support_red_gain, v.support_red_gain)                     \
  X(q_perfusion_index, v.quality.perfusion_index)             \
  X(q_template_corr, v.quality.template_corr)                 \
  X(q_spectral_purity, v.quality.spectral_purity)             \
  X(q_red_ir_corr, v.quality.red_ir_corr)                     \
  X(q_beat_amp_cv, v.quality.beat_amp_cv)                     \
  X(q_valid_ibi_fraction, v.quality.valid_ibi_fraction)       \
  X(q_hr_agreement_bpm, v.quality.hr_agreement_bpm)           \
  X(q_r_spread, v.quality.r_spread)                           \
  X(q_motion_fraction, v.quality.motion_fraction)             \
  X(q_sqi, v.quality.sqi)                                     \
  X(q_comp_perfusion, v.quality.comp[SG_Q_PERFUSION])         \
  X(q_comp_template, v.quality.comp[SG_Q_TEMPLATE])           \
  X(q_comp_purity, v.quality.comp[SG_Q_PURITY])               \
  X(q_comp_amplitude, v.quality.comp[SG_Q_AMPLITUDE])         \
  X(q_comp_rhythm, v.quality.comp[SG_Q_RHYTHM])               \
  X(q_comp_hr_agreement, v.quality.comp[SG_Q_HR_AGREEMENT])   \
  X(q_comp_r_stability, v.quality.comp[SG_Q_R_STABILITY])     \
  X(q_comp_red_ir, v.quality.comp[SG_Q_RED_IR])               \
  X(q_comp_motion, v.quality.comp[SG_Q_MOTION])               \
  X(q_usable, v.quality.usable)                               \
  X(q_usable_spo2, v.quality.usable_spo2)                     \
  X(q_reasons, v.quality.reasons)

#define NAME(name, value) #name,
static const char* const kFieldNames[] = {FIELDS(NAME)};
#undef NAME
static const int kFields = (int)(sizeof(kFieldNames) / sizeof(kFieldNames[0]));

// Longest test vector: beyond SG_WINDOW so that the range check of the core can be exercised.
#define MAX_N 1024

static SgWork work;
static float fft_scratch[2 * SG_FFT_N];
static double red_raw[MAX_N], ir_raw[MAX_N], c_ir[MAX_N], c_red[MAX_N], p_art[MAX_N];
static double ir_bv[MAX_N], red_bv[MAX_N];

static bool read_doubles(FILE* f, double* dst, int count) {
  return fread(dst, sizeof(double), (size_t)count, f) == (size_t)count;
}

static bool write_doubles(FILE* f, const double* src, int count) {
  return fwrite(src, sizeof(double), (size_t)count, f) == (size_t)count;
}

// Reads one case, runs the core and writes its outputs.
static bool run_case(FILE* in, FILE* out) {
  double head[3];
  if (!read_doubles(in, head, 3)) return false;
  const int n = (int)head[0];
  const int mode = (int)head[1];
  const double ir_dc_min = head[2];
  if (n < 0 || n > MAX_N || (mode != 0 && mode != 1)) return false;
  if (!read_doubles(in, red_raw, n) || !read_doubles(in, ir_raw, n)) return false;
  if (mode == 1 && !(read_doubles(in, c_ir, n) && read_doubles(in, c_red, n) && read_doubles(in, p_art, n))) {
    return false;
  }

  SgSensorState sensor;
  SgVitals v;
  sg_sensor_state(red_raw, ir_raw, n, ir_dc_min, &sensor, &work);
  sg_preprocess(ir_raw, n, ir_bv, &work);
  sg_preprocess(red_raw, n, red_bv, &work);
  if (mode == 0) {
    sg_vitals_from_signals(ir_bv, red_bv, NULL, NULL, NULL, n, &sensor, &v, &work);
  } else {
    sg_vitals_from_signals(ir_bv, red_bv, c_ir, c_red, p_art, n, &sensor, &v, &work);
  }

#define VALUE(name, value) (double)(value),
  const double fields[] = {FIELDS(VALUE)};
#undef VALUE
  return write_doubles(out, fields, kFields) && write_doubles(out, ir_bv, n) && write_doubles(out, red_bv, n);
}

// Runs all windows of `in`; returns false on a malformed or truncated file.
static bool run_windows(FILE* in, FILE* out) {
  double n_cases;
  if (!read_doubles(in, &n_cases, 1)) return false;
  const double header[3] = {n_cases, (double)kFields, (double)sg_work_size()};
  bool ok = write_doubles(out, header, 3);
  int done = 0;
  while (ok && done < (int)n_cases) {
    ok = run_case(in, out);
    done += ok;
  }
  printf("core_cli: %d of %d windows, sizeof(SgWork) = %u\n", done, (int)n_cases, (unsigned)sg_work_size());
  return ok;
}

// ---------------------------------------------------------------------------
// --dsp: single building blocks
// ---------------------------------------------------------------------------

enum DspOp {
  OP_SUM = 0,     // sg_sum(a)
  OP_STD,         // sg_std(a)
  OP_MEDIAN,      // sg_sort + sg_median_sorted(a)
  OP_PERCENTILE,  // sg_sort + sg_percentile_sorted(a, param)
  OP_ARG,         // sg_argmax(a), sg_argmin(a)
  OP_INTERP,      // sg_interp(a, b[i]) for each of the m positions
  OP_UNIFORM,     // sg_uniform_filter(a, size = param)
  OP_HANN,        // sg_hann(i, param) for i < param
  OP_PEAKS,       // every sg_next_peak of a (as float)
  OP_FFT,         // sg_fft_power of a (as float), zero-padded to SG_FFT_N
  OP_FILTFILT,    // sg_filtfilt with filter number param
};

static const SgFilter* const kFilters[] = {&SG_FILTER_DC, &SG_FILTER_PPG, &SG_FILTER_PULSE, &SG_FILTER_CARDIAC,
                                           &SG_FILTER_RSPREAD};

static double dsp_a[SG_FFT_N], dsp_b[SG_FFT_N], dsp_out[SG_FFT_N];

// Performs one call on dsp_a[n], dsp_b[m]; returns the number of values written to dsp_out, -1 if invalid.
static int run_dsp_op(int op, int n, int m, double param) {
  switch (op) {
    case OP_SUM:
      dsp_out[0] = sg_sum(dsp_a, n);
      return 1;
    case OP_STD:
      dsp_out[0] = sg_std(dsp_a, n, dsp_b);
      return 1;
    case OP_MEDIAN:
      sg_sort(dsp_a, n);
      dsp_out[0] = sg_median_sorted(dsp_a, n);
      return 1;
    case OP_PERCENTILE:
      sg_sort(dsp_a, n);
      dsp_out[0] = sg_percentile_sorted(dsp_a, n, param);
      return 1;
    case OP_ARG:
      dsp_out[0] = sg_argmax(dsp_a, n);
      dsp_out[1] = sg_argmin(dsp_a, n);
      return 2;
    case OP_INTERP:
      for (int i = 0; i < m; ++i) dsp_out[i] = sg_interp(dsp_a, n, dsp_b[i]);
      return m;
    case OP_UNIFORM:
      sg_uniform_filter(dsp_a, n, (int)param, dsp_out);
      return n;
    case OP_HANN: {
      const int len = (int)param;
      if (len < 2 || len > SG_FFT_N) return -1;
      for (int i = 0; i < len; ++i) dsp_out[i] = sg_hann(i, len);
      return len;
    }
    case OP_PEAKS: {
      for (int i = 0; i < n; ++i) fft_scratch[i] = (float)dsp_a[i];
      int count = 0, scan = 1;
      for (int k = sg_next_peak(fft_scratch, n, &scan); k >= 0; k = sg_next_peak(fft_scratch, n, &scan)) {
        dsp_out[count++] = k;
      }
      return count;
    }
    case OP_FFT:
      memset(fft_scratch, 0, sizeof(fft_scratch));
      for (int i = 0; i < n; ++i) fft_scratch[2 * i] = (float)dsp_a[i];
      sg_fft_power(fft_scratch);
      for (int k = 0; k <= SG_FFT_N / 2; ++k) dsp_out[k] = fft_scratch[k];
      return SG_FFT_N / 2 + 1;
    case OP_FILTFILT: {
      const int id = (int)param;
      if (id < 0 || id >= (int)(sizeof(kFilters) / sizeof(kFilters[0]))) return -1;
      if (n > SG_WINDOW || n <= kFilters[id]->padlen) return -1;
      sg_filtfilt(kFilters[id], dsp_a, n, dsp_out, work.ext);
      return n;
    }
    default:
      return -1;
  }
}

// Runs all calls of `in`; returns false on a malformed or truncated file.
static bool run_dsp(FILE* in, FILE* out) {
  double head[4];
  int done = 0;
  while (fread(head, sizeof(double), 4, in) == 4) {
    const int n = (int)head[1], m = (int)head[2];
    if (n < 0 || n > SG_FFT_N || m < 0 || m > SG_FFT_N) return false;
    if (!read_doubles(in, dsp_a, n) || !read_doubles(in, dsp_b, m)) return false;
    const int count = run_dsp_op((int)head[0], n, m, head[3]);
    const double count_out = count;
    if (count < 0 || !write_doubles(out, &count_out, 1) || !write_doubles(out, dsp_out, count)) return false;
    ++done;
  }
  printf("core_cli: %d building-block calls\n", done);
  return true;
}

int main(int argc, char** argv) {
  if (argc == 2 && strcmp(argv[1], "--fields") == 0) {
    for (int i = 0; i < kFields; ++i) puts(kFieldNames[i]);
    return 0;
  }
  const bool dsp = argc == 4 && strcmp(argv[1], "--dsp") == 0;
  if (argc != 3 && !dsp) {
    fprintf(stderr, "usage: core_cli [--dsp] <in.bin> <out.bin> | core_cli --fields\n");
    return 2;
  }
  FILE* in = fopen(argv[argc - 2], "rb");
  FILE* out = fopen(argv[argc - 1], "wb");
  if (!in || !out) {
    fprintf(stderr, "core_cli: cannot open %s\n", argv[in ? argc - 1 : argc - 2]);
    return 3;
  }
  sg_work_init(&work, fft_scratch);
  bool ok = dsp ? run_dsp(in, out) : run_windows(in, out);
  ok = fclose(out) == 0 && ok;
  fclose(in);
  return ok ? 0 : 4;
}
