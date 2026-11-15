// Protection of the cell: the board has no under-voltage cut-off, so the
// firmware stops everything and sleeps when the battery is empty.
//
//   * empty = at or below `empty_v` without USB power for `confirm_ms`
//     (the filtered voltage sags under Wi-Fi bursts)
//   * after such a sleep the firmware only resumes above `resume_v` or on
//     USB power: a resting cell recovers a little, and starting again at the
//     same threshold would drain it in ever shorter cycles
//   * at or below `critical_v` the sleep is as long as the timer allows
//   * a reading below `min_valid_v` is no battery measurement at all
//     (divider not populated, ADC fault): nothing can be decided from it
//
// Pure logic; the board glue reads the voltage and performs the sleep.
#pragma once

#include <stdint.h>

struct SgPowerLimits {
  float empty_v = 3.45f;        // the 3.3 V regulator starts to drop out below this
  float resume_v = 3.60f;
  float critical_v = 3.20f;
  float min_valid_v = 1.0f;
  uint32_t confirm_ms = 60000;
};

enum class SgPowerAction : uint8_t {
  kRun,
  kSleep,          // battery empty: sleep and look again later
  kSleepLong,      // battery critically low: sleep as long as possible
};

// Decision right after start-up. `after_empty_sleep`: this start is a wake-up
// from an empty-battery sleep (not a power-on or a reset by the user).
SgPowerAction sg_power_at_boot(float volts, bool usb_present, bool after_empty_sleep, const SgPowerLimits& lim);

class SgPowerGuard {
 public:
  explicit SgPowerGuard(const SgPowerLimits& lim = SgPowerLimits()) : lim_(lim) {}
  // Feed the filtered battery voltage about once a second.
  SgPowerAction update(uint32_t now_ms, float volts, bool usb_present);
  bool low() const { return low_; }

 private:
  SgPowerLimits lim_;
  bool low_ = false;
  uint32_t low_since_ms_ = 0;
};
