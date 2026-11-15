#include "aggregate.h"

#include <math.h>

namespace {

// Median by insertion sort (n <= SG_AGG_MAX); sorts in place.
double median(double* v, int n) {
  for (int i = 1; i < n; i++) {
    const double x = v[i];
    int j = i - 1;
    while (j >= 0 && v[j] > x) {
      v[j + 1] = v[j];
      j--;
    }
    v[j + 1] = x;
  }
  return n % 2 ? v[n / 2] : 0.5 * (v[n / 2 - 1] + v[n / 2]);
}

}  // namespace

void SgAggregator::add(const SgVitals& v, double hr_scale, double temperature_c) {
  windows_++;
  if (!isnan(temperature_c)) {
    temp_sum_ += temperature_c;
    n_temp_++;
  }
  if (!v.reliable || !v.has_hr) return;
  n_reliable_++;
  if (n_hr_ < SG_AGG_MAX) {
    hr_[n_hr_++] = v.hr_bpm * hr_scale;
    sqi_sum_ += v.quality.sqi;
  }
  if (v.has_spo2 && n_spo2_ < SG_AGG_MAX) spo2_[n_spo2_++] = v.spo2;
}

bool SgAggregator::summary(double* pulse, bool* has_spo2, double* spo2, double* sqi, int* spo2_windows,
                           bool* has_temperature, double* temperature_c) {
  if (n_hr_ == 0) return false;
  *sqi = sqi_sum_ / n_hr_;
  *pulse = median(hr_, n_hr_);
  *has_spo2 = n_spo2_ > 0;
  *spo2 = n_spo2_ > 0 ? median(spo2_, n_spo2_) : 0.0;
  *spo2_windows = n_spo2_;
  *has_temperature = n_temp_ > 0;
  *temperature_c = n_temp_ > 0 ? temp_sum_ / n_temp_ : 0.0;
  return true;
}

void SgAggregator::reset() {
  n_hr_ = n_reliable_ = n_spo2_ = windows_ = n_temp_ = 0;
  sqi_sum_ = temp_sum_ = 0;
}
