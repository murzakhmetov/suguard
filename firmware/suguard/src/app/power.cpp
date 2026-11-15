#include "power.h"

SgPowerAction sg_power_at_boot(float volts, bool usb_present, bool after_empty_sleep, const SgPowerLimits& lim) {
  if (usb_present || volts < lim.min_valid_v) return SgPowerAction::kRun;
  // After a sleep the cell must have been recharged (>= resume_v); a fresh start only needs to be above empty.
  const bool enough = after_empty_sleep ? volts >= lim.resume_v : volts > lim.empty_v;
  return enough ? SgPowerAction::kRun : SgPowerAction::kSleep;
}

SgPowerAction SgPowerGuard::update(uint32_t now_ms, float volts, bool usb_present) {
  const bool low = !usb_present && volts >= lim_.min_valid_v && volts <= lim_.empty_v;
  if (!low) {
    low_ = false;
    return SgPowerAction::kRun;
  }
  if (!low_) {
    low_ = true;
    low_since_ms_ = now_ms;
  }
  return now_ms - low_since_ms_ >= lim_.confirm_ms ? SgPowerAction::kSleep : SgPowerAction::kRun;
}
