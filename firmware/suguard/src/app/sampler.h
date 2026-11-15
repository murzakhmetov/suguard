// PPG acquisition: drains the MAX30102 FIFO into contiguous 10.24-s windows.
//
// One window = SG_WINDOW (512) samples at 50 Hz of raw red and IR counts.
// The sampler guarantees that every delivered window is gap-free and was
// recorded at constant LED currents:
//   * if the chip reports lost samples (FIFO overflow), the partial window is
//     discarded and a new one is started
//   * LED currents (automatic gain control) only change between windows and
//     are followed by a short settling time
//   * when nothing reflects the IR light (bracelet not worn) the sensor is
//     shut down and probed every few seconds
//   * a sensor that resets itself (brown-out) or stops answering is
//     re-initialised
//
// poll() must be called from one task only, every 40-100 ms (the FIFO holds
// 32 samples = 640 ms at 50 Hz). The request_*() calls may come from a lower
// priority task on the same core.
#pragma once

#include <stdint.h>

#include "../core/sg_core.h"
#include "../drivers/max30102.h"

enum SgWindowFlag : uint16_t {
  SG_WF_AMBIENT_OVERFLOW = 1u << 0,   // ambient-light cancellation overflowed during the window
};

struct SgWindow {
  uint32_t red[SG_WINDOW];
  uint32_t ir[SG_WINDOW];
  uint32_t seq;             // 1, 2, 3, ... since boot
  uint32_t end_ms;          // clock when the last sample was read
  float fs_hz;              // measured output rate of the sensor, 0 until known
  float temperature_c;      // MAX30102 die temperature, NAN if not available
  uint8_t led_red;          // LED current register values during the window (0.2 mA per LSB)
  uint8_t led_ir;
  uint16_t flags;           // SgWindowFlag
};

struct SgSamplerConfig {
  max30102::Config sensor;            // led1/led2 are ignored: the sampler owns the LED currents
  bool swap_red_ir = false;           // clone modules with exchanged LEDs
  uint8_t led_init = 0x3F;            // 12.6 mA: start value and wear-probe current
  uint8_t led_min = 0x08;             // 1.6 mA
  uint8_t led_max = 0x7F;             // 25.4 mA
  float dc_min = SG_FINGER_IR_DC_MIN; // IR level (counts) below which nothing is in front of the sensor
  float agc_low = 0.15f;              // act when the mean DC leaves [low, high] x full scale ...
  float agc_high = 0.70f;
  float agc_target = 0.45f;           // ... and steer it to target x full scale
  uint16_t settle_samples = 25;       // discarded after any LED change (0.5 s)
  uint32_t standby_period_ms = 3000;  // not worn: probe this often
  uint32_t standby_probe_ms = 300;    // LEDs on for this long per probe
  uint8_t not_worn_windows = 2;       // consecutive dark windows before standby
};

enum class SgSamplerState : uint8_t {
  kNoSensor,        // MAX30102 not answering (retrying)
  kResetting,
  kSettling,        // waiting after a LED/config change
  kActive,          // filling windows
  kStandbySleep,    // not worn, sensor shut down
  kStandbyProbe,    // not worn, checking for skin
  kLedTest,
};

struct SgSamplerStats {
  uint32_t windows = 0;
  uint32_t lost_samples = 0;      // dropped by the chip (FIFO overflow)
  uint32_t window_restarts = 0;
  uint32_t i2c_errors = 0;
  uint32_t sensor_resets = 0;     // unexpected power-on resets of the MAX30102
  float last_ir_dc = 0;           // mean counts of the last completed window
  float last_red_dc = 0;
  float fs_hz = 0;                // measured output rate (0 = not yet known)
  uint8_t part_id = 0;
  uint8_t rev_id = 0;
};

typedef void (*SgWindowFn)(void* ctx, const SgWindow* window);

class SgSampler {
 public:
  // `on_window` is called from poll() for every completed window; the window
  // memory belongs to the sampler, so copy what you need.
  void begin(const SgI2c& bus, const SgSamplerConfig& cfg, SgWindowFn on_window, void* ctx);
  void poll(uint32_t now_ms);

  // Re-initialise the sensor with new settings (returns false if a previous
  // request is still pending).
  bool request_config(const SgSamplerConfig& cfg);
  // Drive the LEDs for a visual check: mode bit0 = red, bit1 = IR, 0 = both off.
  bool request_led_test(uint8_t mode, uint32_t duration_ms);

  SgSamplerState state() const { return state_; }
  const SgSamplerStats& stats() const { return stats_; }
  bool worn() const { return state_ == SgSamplerState::kActive || state_ == SgSamplerState::kSettling; }
  uint8_t led_red() const { return led_red_; }
  uint8_t led_ir() const { return led_ir_; }
  int fill() const { return idx_; }

 private:
  void enter_no_sensor(uint32_t now, uint32_t retry_ms);
  void begin_settle(uint32_t now);
  void start_window(uint32_t now);
  void enter_standby(uint32_t now);
  void poll_active(uint32_t now);
  void poll_temperature();
  void finish_window(uint32_t now);
  bool write_leds(uint8_t red, uint8_t ir);
  uint8_t agc(uint8_t current, float mean, uint32_t peak) const;
  bool bus_failed(uint32_t now);

  max30102::Device dev_;
  SgSamplerConfig cfg_;
  SgWindowFn on_window_ = nullptr;
  void* ctx_ = nullptr;

  SgSamplerState state_ = SgSamplerState::kNoSensor;
  uint32_t next_ms_ = 0;            // time of the next action in timed states
  uint32_t reset_started_ms_ = 0;
  int settle_left_ = 0;
  uint8_t consecutive_errors_ = 0;
  uint8_t dark_windows_ = 0;
  uint8_t led_red_ = 0;
  uint8_t led_ir_ = 0;

  SgWindow win_{};
  int idx_ = 0;
  uint64_t sum_red_ = 0;
  uint64_t sum_ir_ = 0;
  uint32_t max_red_ = 0;
  uint32_t max_ir_ = 0;
  uint32_t seq_ = 0;

  uint8_t temp_phase_ = 0;          // 0 = not started this window, 1 = converting, 2 = done
  float temp_c_ = 0;

  uint32_t rate_t0_ms_ = 0;         // contiguous sampling since ...
  uint32_t rate_samples_ = 0;       // ... samples read since then

  volatile bool pending_cfg_ = false;
  SgSamplerConfig pending_cfg_value_;
  volatile bool pending_led_test_ = false;
  uint8_t led_test_mode_ = 0;
  uint32_t led_test_ms_ = 0;

  SgSamplerStats stats_;
};
