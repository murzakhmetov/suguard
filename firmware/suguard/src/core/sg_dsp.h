// SuGuard signal core - numeric building blocks.
//
// Each function is the twin of the numpy/scipy routine named in its comment
// and performs the same floating-point operations in the same order, so that
// on an IEEE-754 target the double results are bit-identical to Python. This
// needs a build without fused multiply-add contraction (-ffp-contract=off on
// CPUs that have FMA; the ESP32-C3 has no FPU at all).
//
// No heap, no STL; scratch memory is passed in by the caller.
#pragma once

#include <stddef.h>
#include <stdint.h>

// One second-order section (a0 = 1) and its scipy.signal.sosfilt_zi state.
struct SgBiquad {
  double b0, b1, b2, a1, a2;
  double zi0, zi1;
};

// A zero-phase filter: Butterworth sections plus the padding of filters._filtfilt.
struct SgFilter {
  const SgBiquad* sections;
  int n_sections;
  int padlen;
};

// filters._filtfilt: scipy.signal.sosfiltfilt(sos, x, padtype="odd", padlen=f->padlen).
// Needs n > f->padlen. `ext` is scratch for n + 2 * f->padlen doubles; y may alias x.
void sg_filtfilt(const SgFilter* f, const double* x, int n, double* y, double* ext);

// np.sum / np.mean of a double array (numpy's pairwise summation).
double sg_sum(const double* x, int n);
double sg_mean(const double* x, int n);

// np.std (population). `tmp` is scratch for n doubles and may alias x.
double sg_std(const double* x, int n, double* tmp);

// Ascending in-place sort; with it, np.median and np.percentile (linear
// interpolation, q in percent) of the sorted array.
void sg_sort(double* x, int n);
double sg_median_sorted(const double* sorted, int n);
double sg_percentile_sorted(const double* sorted, int n, double q);

// Index of the first maximum / minimum (np.argmax, np.argmin).
int sg_argmax(const double* x, int n);
int sg_argmin(const double* x, int n);

// np.interp(pos, np.arange(n), y).
double sg_interp(const double* y, int n, double pos);

// scipy.ndimage.uniform_filter1d(y, size, mode="nearest"). out may not alias y.
void sg_uniform_filter(const double* y, int n, int size, double* out);

// scipy.signal.windows.hann(n)[i] (symmetric window).
double sg_hann(int i, int n);

// scipy.signal.find_peaks(x) with default arguments, one peak per call: returns
// the index of the next local maximum (the middle of a flat top) or -1 when
// there is none left. Start with *scan = 1; *scan carries the search position.
int sg_next_peak(const float* x, int n, int* scan);

// Power spectrum by a single-precision radix-2 FFT. On entry `buf` holds
// SG_FFT_N complex samples (re, im interleaved); on return buf[k] = |X[k]|^2
// for k = 0 .. SG_FFT_N / 2 (the rest of the buffer is undefined).
void sg_fft_power(float* buf);
