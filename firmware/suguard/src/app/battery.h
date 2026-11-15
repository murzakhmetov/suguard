// Battery state from the two ADC inputs of the SuGuard board:
//   GPIO2 <- VBAT through R8 100k / R9 47k   (VBAT * 47/147)
//   GPIO4 <- VBUS through R11 100k / R13 100k (VBUS / 2)
// The charger (TP4056) status pins only drive LEDs, so "charging" is inferred.
#pragma once

#include <stdint.h>

struct SgBatteryConfig {
  float bat_divider = (100.0f + 47.0f) / 47.0f;
  float vbus_divider = 2.0f;
  float cal = 1.0f;               // multimeter voltage / reported voltage (resistor and ADC tolerance)
};

struct SgBattery {
  float volts = 0;                // filtered battery voltage
  int percent = -1;               // -1 until the first reading
  bool usb_present = false;
  bool charging = false;          // USB present and battery below the full level
};

// Resting-voltage to state-of-charge curve of a 1S LiPo. The 3.3 V regulator
// (AP2112K) needs about 3.45 V at the battery, which is taken as empty.
int sg_battery_percent(float volts);

class SgBatteryMonitor {
 public:
  explicit SgBatteryMonitor(const SgBatteryConfig& cfg = SgBatteryConfig()) : cfg_(cfg) {}
  void set_config(const SgBatteryConfig& cfg) { cfg_ = cfg; }
  // Feed calibrated ADC readings in millivolts (at the pin), e.g. once a second.
  void update(float bat_pin_mv, float vbus_pin_mv);
  const SgBattery& state() const { return state_; }

 private:
  SgBatteryConfig cfg_;
  SgBattery state_;
};
