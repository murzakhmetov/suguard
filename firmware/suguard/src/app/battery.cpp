#include "battery.h"

namespace {

struct Point { float v; float pct; };
// Typical open-circuit curve; below 3.61 V it is cut to reach 0 % at 3.45 V.
const Point kCurve[] = {
    {4.20f, 100}, {4.15f, 95}, {4.11f, 90}, {4.08f, 85}, {4.02f, 80}, {3.98f, 75}, {3.95f, 70},
    {3.91f, 65},  {3.87f, 60}, {3.85f, 55}, {3.84f, 50}, {3.82f, 45}, {3.80f, 40}, {3.79f, 35},
    {3.77f, 30},  {3.75f, 25}, {3.73f, 20}, {3.71f, 15}, {3.69f, 10}, {3.61f, 5},  {3.45f, 0},
};
const int kCurveN = (int)(sizeof(kCurve) / sizeof(kCurve[0]));

}  // namespace

int sg_battery_percent(float volts) {
  if (volts >= kCurve[0].v) return 100;
  for (int i = 1; i < kCurveN; i++) {
    if (volts >= kCurve[i].v) {
      const float f = (volts - kCurve[i].v) / (kCurve[i - 1].v - kCurve[i].v);
      return (int)(kCurve[i].pct + f * (kCurve[i - 1].pct - kCurve[i].pct) + 0.5f);
    }
  }
  return 0;
}

void SgBatteryMonitor::update(float bat_pin_mv, float vbus_pin_mv) {
  const float v = bat_pin_mv * 0.001f * cfg_.bat_divider * cfg_.cal;
  // The 32 kOhm divider gives noisy readings: smooth them (time constant ~10 updates).
  state_.volts = state_.percent < 0 ? v : state_.volts + 0.1f * (v - state_.volts);
  state_.percent = sg_battery_percent(state_.volts);
  state_.usb_present = vbus_pin_mv * 0.001f * cfg_.vbus_divider > 3.0f;
  state_.charging = state_.usb_present && state_.volts < 4.15f;
}
