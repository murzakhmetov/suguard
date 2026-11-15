// Numeric building blocks of the signal core - see sg_dsp.h.
#include "sg_dsp.h"

#include <math.h>
#include <string.h>

#include "sg_tables.h"

// ---------------------------------------------------------------------------
// Zero-phase IIR filtering
// ---------------------------------------------------------------------------

// scipy.signal.sosfilt (direct form II transposed) in place over x[0], x[step], ...
// with zi = sosfilt_zi(sos) * x[0], the steady state for a constant input x[0].
static void sos_run(const SgFilter* f, double* x, int n, int step) {
  double z0[SG_MAX_SECTIONS], z1[SG_MAX_SECTIONS];
  for (int s = 0; s < f->n_sections; ++s) {
    z0[s] = f->sections[s].zi0 * x[0];
    z1[s] = f->sections[s].zi1 * x[0];
  }
  for (int i = 0; i < n; ++i, x += step) {
    double v = *x;
    for (int s = 0; s < f->n_sections; ++s) {
      const SgBiquad* q = &f->sections[s];
      const double y = q->b0 * v + z0[s];
      z0[s] = (q->b1 * v - q->a1 * y) + z1[s];
      z1[s] = q->b2 * v - q->a2 * y;
      v = y;
    }
    *x = v;
  }
}

void sg_filtfilt(const SgFilter* f, const double* x, int n, double* y, double* ext) {
  const int pad = f->padlen;
  const int total = n + 2 * pad;
  for (int j = 0; j < pad; ++j) {  // scipy.signal._arraytools.odd_ext
    ext[j] = 2 * x[0] - x[pad - j];
    ext[pad + n + j] = 2 * x[n - 1] - x[n - 2 - j];
  }
  memcpy(ext + pad, x, (size_t)n * sizeof(double));
  sos_run(f, ext, total, 1);               // forward
  sos_run(f, ext + total - 1, total, -1);  // backward, from the last sample
  memcpy(y, ext + pad, (size_t)n * sizeof(double));
}

// ---------------------------------------------------------------------------
// Sums and statistics
// ---------------------------------------------------------------------------

// numpy's pairwise_sum: blocks of up to 128 values are added with 8
// accumulators, larger arrays are split in two (recursion depth <= 3 here).
double sg_sum(const double* x, int n) {
  if (n < 8) {
    double s = 0.0;
    for (int i = 0; i < n; ++i) s += x[i];
    return s;
  }
  if (n <= 128) {
    double r[8];
    for (int j = 0; j < 8; ++j) r[j] = x[j];
    int i = 8;
    for (; i < n - n % 8; i += 8) {
      for (int j = 0; j < 8; ++j) r[j] += x[i + j];
    }
    double s = ((r[0] + r[1]) + (r[2] + r[3])) + ((r[4] + r[5]) + (r[6] + r[7]));
    for (; i < n; ++i) s += x[i];
    return s;
  }
  int half = n / 2;
  half -= half % 8;
  return sg_sum(x, half) + sg_sum(x + half, n - half);
}

double sg_mean(const double* x, int n) { return sg_sum(x, n) / n; }

double sg_std(const double* x, int n, double* tmp) {
  const double mean = sg_mean(x, n);
  for (int i = 0; i < n; ++i) {
    const double d = x[i] - mean;
    tmp[i] = d * d;
  }
  return sqrt(sg_mean(tmp, n));
}

void sg_sort(double* x, int n) {  // Shell sort (Ciura gaps): in place, no recursion
  static const int gaps[] = {301, 132, 57, 23, 10, 4, 1};
  for (int gap : gaps) {
    for (int i = gap; i < n; ++i) {
      const double v = x[i];
      int j = i;
      for (; j >= gap && x[j - gap] > v; j -= gap) x[j] = x[j - gap];
      x[j] = v;
    }
  }
}

double sg_median_sorted(const double* sorted, int n) {
  return n % 2 ? sorted[n / 2] : (sorted[n / 2 - 1] + sorted[n / 2]) / 2;
}

// numpy's "linear" method: virtual index (n - 1) * q / 100 and _lerp().
double sg_percentile_sorted(const double* sorted, int n, double q) {
  const double pos = (n - 1) * (q / 100.0);
  const int lo = (int)pos;
  const int hi = lo + 1 < n ? lo + 1 : n - 1;
  const double t = pos - lo;
  const double diff = sorted[hi] - sorted[lo];
  return t >= 0.5 ? sorted[hi] - diff * (1 - t) : sorted[lo] + diff * t;
}

int sg_argmax(const double* x, int n) {
  int best = 0;
  for (int i = 1; i < n; ++i) {
    if (x[i] > x[best]) best = i;
  }
  return best;
}

int sg_argmin(const double* x, int n) {
  int best = 0;
  for (int i = 1; i < n; ++i) {
    if (x[i] < x[best]) best = i;
  }
  return best;
}

double sg_interp(const double* y, int n, double pos) {
  if (pos <= 0) return y[0];
  if (pos >= n - 1) return y[n - 1];
  const int j = (int)pos;
  return (y[j + 1] - y[j]) * (pos - j) + y[j];
}

// ---------------------------------------------------------------------------
// Moving average, window, peaks
// ---------------------------------------------------------------------------

static int clamp_index(int i, int n) { return i < 0 ? 0 : (i >= n ? n - 1 : i); }

// Like scipy: a running sum over samples i - size / 2 .. i + (size - 1) / 2,
// the signal being extended by its end values.
void sg_uniform_filter(const double* y, int n, int size, double* out) {
  const int before = size / 2;
  const int after = size - before - 1;
  double sum = 0.0;
  for (int k = -before; k <= after; ++k) sum += y[clamp_index(k, n)];
  out[0] = sum / size;
  for (int i = 1; i < n; ++i) {
    sum += y[clamp_index(i + after, n)] - y[clamp_index(i - before - 1, n)];
    out[i] = sum / size;
  }
}

// general_cosine(n, [0.5, 0.5]) over np.linspace(-pi, pi, n).
double sg_hann(int i, int n) {
  const double step = (SG_PI - -SG_PI) / (n - 1);
  const double phase = i == n - 1 ? SG_PI : i * step + -SG_PI;
  return 0.5 + 0.5 * cos(phase);
}

// scipy.signal._peak_finding_utils._local_maxima_1d.
int sg_next_peak(const float* x, int n, int* scan) {
  const int last = n - 1;  // the first and the last sample cannot be peaks
  int i = *scan;
  for (; i < last; ++i) {
    if (!(x[i - 1] < x[i])) continue;
    int ahead = i + 1;  // next sample that differs from x[i]
    while (ahead < last && x[ahead] == x[i]) ++ahead;
    if (x[ahead] < x[i]) {
      *scan = ahead + 1;
      return (i + ahead - 1) / 2;
    }
  }
  *scan = i;
  return -1;
}

// ---------------------------------------------------------------------------
// FFT
// ---------------------------------------------------------------------------

// exp(-2 pi i t / SG_FFT_N) for t in [0, SG_FFT_N / 2), from the quarter-wave table.
static void twiddle(int t, float* re, float* im) {
  const int quarter = SG_FFT_N / 4;
  if (t <= quarter) {
    *re = SG_FFT_SIN[quarter - t];
    *im = -SG_FFT_SIN[t];
  } else {
    *re = -SG_FFT_SIN[t - quarter];
    *im = -SG_FFT_SIN[2 * quarter - t];
  }
}

static void bit_reverse_permute(float* buf) {
  for (int i = 0, j = 0; i < SG_FFT_N; ++i) {
    if (i < j) {
      const float re = buf[2 * i], im = buf[2 * i + 1];
      buf[2 * i] = buf[2 * j];
      buf[2 * i + 1] = buf[2 * j + 1];
      buf[2 * j] = re;
      buf[2 * j + 1] = im;
    }
    int bit = SG_FFT_N >> 1;  // j = bit-reversed (i + 1)
    for (; bit && (j & bit); bit >>= 1) j ^= bit;
    j ^= bit;
  }
}

void sg_fft_power(float* buf) {
  bit_reverse_permute(buf);
  for (int half = 1, stride = SG_FFT_N / 2; half < SG_FFT_N; half *= 2, stride /= 2) {
    for (int j = 0; j < half; ++j) {
      float wr, wi;
      twiddle(j * stride, &wr, &wi);
      for (int k = j; k < SG_FFT_N; k += 2 * half) {
        float* p = buf + 2 * k;
        float* q = p + 2 * half;
        const float tr = wr * q[0] - wi * q[1];
        const float ti = wr * q[1] + wi * q[0];
        q[0] = p[0] - tr;
        q[1] = p[1] - ti;
        p[0] += tr;
        p[1] += ti;
      }
    }
  }
  for (int k = 0; k <= SG_FFT_N / 2; ++k) {
    buf[k] = buf[2 * k] * buf[2 * k] + buf[2 * k + 1] * buf[2 * k + 1];
  }
}
