// Combines the per-window results of one report interval into a single record.
#pragma once

#include "../core/sg_core.h"

#define SG_AGG_MAX 64   // reliable windows kept per interval; the longest interval (600 s) has 59 windows

class SgAggregator {
 public:
  // `hr_scale` = measured sample rate / 50 Hz: corrects the heart rate for the
  // tolerance of the sensor's oscillator (1.0 if unknown).
  void add(const SgVitals& v, double hr_scale, double temperature_c);
  int windows() const { return windows_; }
  int reliable() const { return n_reliable_; }

  // Medians over the reliable windows. Returns false if there is none.
  bool summary(double* pulse, bool* has_spo2, double* spo2, double* sqi, int* spo2_windows,
               bool* has_temperature, double* temperature_c);
  void reset();

 private:
  double hr_[SG_AGG_MAX];
  double spo2_[SG_AGG_MAX];
  int n_hr_ = 0;
  int n_reliable_ = 0;
  int n_spo2_ = 0;
  int windows_ = 0;
  double sqi_sum_ = 0;
  double temp_sum_ = 0;
  int n_temp_ = 0;
};
