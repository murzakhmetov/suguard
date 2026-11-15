#include "sampler.h"

#include <math.h>
#include <string.h>

namespace {

constexpr float kFullScale = 262143.0f;
constexpr uint32_t kRetryMs = 2000;          // sensor missing: try again this often
constexpr uint32_t kResetTimeoutMs = 500;
constexpr uint32_t kRateMinMs = 30000;       // measure the sample rate over at least this long

// true once `now` has reached `t` (wrap-safe for a 32-bit millisecond clock)
inline bool due(uint32_t now, uint32_t t) { return (int32_t)(now - t) >= 0; }

}  // namespace

void SgSampler::begin(const SgI2c& bus, const SgSamplerConfig& cfg, SgWindowFn on_window, void* ctx) {
  dev_.attach(bus);
  cfg_ = cfg;
  on_window_ = on_window;
  ctx_ = ctx;
  led_red_ = led_ir_ = cfg_.led_init;
  state_ = SgSamplerState::kNoSensor;
  next_ms_ = 0;
}

bool SgSampler::request_config(const SgSamplerConfig& cfg) {
  if (pending_cfg_) return false;
  pending_cfg_value_ = cfg;
  pending_cfg_ = true;               // set last: poll() only reads the value after seeing the flag
  return true;
}

bool SgSampler::request_led_test(uint8_t mode, uint32_t duration_ms) {
  if (pending_led_test_) return false;
  led_test_mode_ = mode;
  led_test_ms_ = duration_ms;
  pending_led_test_ = true;
  return true;
}

bool SgSampler::write_leds(uint8_t red, uint8_t ir) {
  return cfg_.swap_red_ir ? dev_.set_led(ir, red) : dev_.set_led(red, ir);
}

void SgSampler::enter_no_sensor(uint32_t now, uint32_t retry_ms) {
  state_ = SgSamplerState::kNoSensor;
  next_ms_ = now + retry_ms;
  consecutive_errors_ = 0;
  idx_ = 0;
}

// Counts a failed bus transaction; after several in a row the sensor is re-initialised.
bool SgSampler::bus_failed(uint32_t now) {
  stats_.i2c_errors++;
  if (++consecutive_errors_ >= 5) enter_no_sensor(now, kRetryMs);
  return false;
}

void SgSampler::begin_settle(uint32_t now) {
  settle_left_ = cfg_.settle_samples;
  idx_ = 0;
  state_ = SgSamplerState::kSettling;
  if (!dev_.clear_fifo()) bus_failed(now);
}

void SgSampler::start_window(uint32_t now) {
  idx_ = 0;
  sum_red_ = sum_ir_ = 0;
  max_red_ = max_ir_ = 0;
  win_.flags = 0;
  temp_phase_ = 0;
  rate_t0_ms_ = now;
  rate_samples_ = 0;
  state_ = SgSamplerState::kActive;
  if (!dev_.clear_fifo()) bus_failed(now);     // window and rate measurement start from an empty FIFO
}

void SgSampler::enter_standby(uint32_t now) {
  dev_.set_shutdown(true);
  dark_windows_ = 0;
  idx_ = 0;
  state_ = SgSamplerState::kStandbySleep;
  next_ms_ = now + cfg_.standby_period_ms;
}

uint8_t SgSampler::agc(uint8_t current, float mean, uint32_t peak) const {
  float scale;
  const float target = cfg_.agc_target * kFullScale;
  const float m = mean > 1.0f ? mean : 1.0f;
  if ((float)peak >= 0.95f * kFullScale) {
    scale = target / m < 0.8f ? target / m : 0.8f;      // clipping: always step down
  } else if (mean > cfg_.agc_high * kFullScale) {
    scale = target / m;
  } else if (mean < cfg_.agc_low * kFullScale) {
    scale = target / m;
  } else {
    return current;
  }
  if (scale < 0.5f) scale = 0.5f;                       // DC is only roughly proportional to the current
  if (scale > 2.0f) scale = 2.0f;
  float want = floorf((float)current * scale + 0.5f);
  if (want < (float)cfg_.led_min) want = (float)cfg_.led_min;
  if (want > (float)cfg_.led_max) want = (float)cfg_.led_max;
  return (uint8_t)want;
}

void SgSampler::poll_temperature() {
  if (temp_phase_ == 0 && idx_ >= SG_WINDOW / 2) {
    if (dev_.start_temperature()) temp_phase_ = 1;
  } else if (temp_phase_ == 1) {
    bool ready = false;
    float t = 0;
    if (dev_.read_temperature(&t, &ready) && ready) {
      temp_c_ = t;
      temp_phase_ = 2;
    }
  }
}

void SgSampler::finish_window(uint32_t now) {
  const float mean_red = (float)((double)sum_red_ / SG_WINDOW);
  const float mean_ir = (float)((double)sum_ir_ / SG_WINDOW);
  const uint32_t elapsed = now - rate_t0_ms_;
  if (elapsed >= kRateMinMs) stats_.fs_hz = (float)((double)rate_samples_ * 1000.0 / (double)elapsed);

  win_.seq = ++seq_;
  win_.end_ms = now;
  win_.fs_hz = stats_.fs_hz;
  win_.temperature_c = temp_phase_ == 2 ? temp_c_ : NAN;
  win_.led_red = led_red_;
  win_.led_ir = led_ir_;
  stats_.windows++;
  stats_.last_red_dc = mean_red;
  stats_.last_ir_dc = mean_ir;
  if (on_window_) on_window_(ctx_, &win_);

  // Next window: same buffers, continuing without a gap unless the LEDs change.
  idx_ = 0;
  const uint32_t peak_red = max_red_, peak_ir = max_ir_;
  sum_red_ = sum_ir_ = 0;
  max_red_ = max_ir_ = 0;
  win_.flags = 0;
  temp_phase_ = 0;

  uint8_t red = led_red_, ir = led_ir_;
  if (mean_ir < cfg_.dc_min) {
    // Nothing reflects the IR light. First make sure the LEDs are not simply
    // turned down too far, then conclude that the bracelet is not worn.
    if (led_ir_ < cfg_.led_init || led_red_ < cfg_.led_init) {
      if (ir < cfg_.led_init) ir = cfg_.led_init;
      if (red < cfg_.led_init) red = cfg_.led_init;
    } else if (++dark_windows_ >= cfg_.not_worn_windows) {
      enter_standby(now);
      return;
    }
  } else {
    dark_windows_ = 0;
    red = agc(led_red_, mean_red, peak_red);
    ir = agc(led_ir_, mean_ir, peak_ir);
  }
  if (red != led_red_ || ir != led_ir_) {
    if (write_leds(red, ir)) {
      led_red_ = red;
      led_ir_ = ir;
      begin_settle(now);
    } else {
      bus_failed(now);
    }
  }
}

void SgSampler::poll_active(uint32_t now) {
  uint32_t s1[max30102::kFifoDepth], s2[max30102::kFifoDepth];
  int lost = 0;
  const int n = dev_.read_fifo(s1, s2, max30102::kFifoDepth, &lost);
  if (n < 0) {
    bus_failed(now);
    return;
  }
  consecutive_errors_ = 0;

  uint8_t status = 0;
  if (dev_.read_status1(&status)) {
    if (status & max30102::kStatusPwrRdy) {             // the chip went through a power-on reset
      stats_.sensor_resets++;
      enter_no_sensor(now, 0);
      return;
    }
    if (status & max30102::kStatusAlcOvf) win_.flags |= SG_WF_AMBIENT_OVERFLOW;
  }

  if (lost > 0) {                                       // gap in the data: start over
    stats_.lost_samples += (uint32_t)lost;
    stats_.window_restarts++;
    start_window(now);
    return;
  }

  rate_samples_ += (uint32_t)n;
  const uint32_t* red = cfg_.swap_red_ir ? s2 : s1;
  const uint32_t* ir = cfg_.swap_red_ir ? s1 : s2;
  for (int i = 0; i < n; i++) {
    win_.red[idx_] = red[i];
    win_.ir[idx_] = ir[i];
    sum_red_ += red[i];
    sum_ir_ += ir[i];
    if (red[i] > max_red_) max_red_ = red[i];
    if (ir[i] > max_ir_) max_ir_ = ir[i];
    if (++idx_ == SG_WINDOW) {
      finish_window(now);
      if (state_ != SgSamplerState::kActive) return;    // LEDs changed or standby: drop the rest
    }
  }
  poll_temperature();
}

void SgSampler::poll(uint32_t now) {
  if (pending_cfg_) {
    cfg_ = pending_cfg_value_;
    pending_cfg_ = false;
    led_red_ = led_ir_ = cfg_.led_init;
    enter_no_sensor(now, 0);
  }
  if (pending_led_test_ && state_ != SgSamplerState::kNoSensor && state_ != SgSamplerState::kResetting) {
    pending_led_test_ = false;
    dev_.set_shutdown(false);
    write_leds((led_test_mode_ & 1) ? cfg_.led_init : 0, (led_test_mode_ & 2) ? cfg_.led_init : 0);
    state_ = SgSamplerState::kLedTest;
    next_ms_ = now + led_test_ms_;
    return;
  }

  switch (state_) {
    case SgSamplerState::kNoSensor: {
      if (!due(now, next_ms_)) return;
      uint8_t part = 0, rev = 0;
      if (!dev_.probe(&part, &rev) || part != max30102::kPartId || !dev_.start_reset()) {
        stats_.i2c_errors++;
        next_ms_ = now + kRetryMs;
        return;
      }
      stats_.part_id = part;
      stats_.rev_id = rev;
      reset_started_ms_ = now;
      next_ms_ = now + 10;
      state_ = SgSamplerState::kResetting;
      return;
    }
    case SgSamplerState::kResetting: {
      if (!due(now, next_ms_)) return;
      bool done = false;
      if (!dev_.reset_done(&done) || (!done && now - reset_started_ms_ > kResetTimeoutMs)) {
        stats_.i2c_errors++;
        enter_no_sensor(now, kRetryMs);
        return;
      }
      if (!done) return;
      max30102::Config c = cfg_.sensor;
      c.led1 = cfg_.swap_red_ir ? led_ir_ : led_red_;
      c.led2 = cfg_.swap_red_ir ? led_red_ : led_ir_;
      uint8_t status = 0;
      if (!dev_.configure(c) || !dev_.read_status1(&status)) {   // the read clears the power-ready flag
        stats_.i2c_errors++;
        enter_no_sensor(now, kRetryMs);
        return;
      }
      dark_windows_ = 0;
      begin_settle(now);
      return;
    }
    case SgSamplerState::kSettling: {
      uint32_t s1[max30102::kFifoDepth], s2[max30102::kFifoDepth];
      int lost = 0;
      const int n = dev_.read_fifo(s1, s2, max30102::kFifoDepth, &lost);
      if (n < 0) {
        bus_failed(now);
        return;
      }
      consecutive_errors_ = 0;
      settle_left_ -= n + lost;
      if (settle_left_ <= 0) start_window(now);
      return;
    }
    case SgSamplerState::kActive:
      poll_active(now);
      return;
    case SgSamplerState::kStandbySleep: {
      if (!due(now, next_ms_)) return;
      if (!dev_.set_shutdown(false) || !write_leds(cfg_.led_init, cfg_.led_init) || !dev_.clear_fifo()) {
        stats_.i2c_errors++;
        enter_no_sensor(now, kRetryMs);
        return;
      }
      led_red_ = led_ir_ = cfg_.led_init;
      state_ = SgSamplerState::kStandbyProbe;
      next_ms_ = now + cfg_.standby_probe_ms;
      return;
    }
    case SgSamplerState::kStandbyProbe: {
      if (!due(now, next_ms_)) return;
      uint32_t s1[max30102::kFifoDepth], s2[max30102::kFifoDepth];
      int lost = 0;
      const int n = dev_.read_fifo(s1, s2, max30102::kFifoDepth, &lost);
      if (n < 0) {
        stats_.i2c_errors++;
        enter_no_sensor(now, kRetryMs);
        return;
      }
      const uint32_t* ir = cfg_.swap_red_ir ? s1 : s2;
      const int use = n < 8 ? n : 8;                    // the newest samples: the LED level has settled
      uint64_t sum = 0;
      for (int i = n - use; i < n; i++) sum += ir[i];
      // 25 % above the not-worn level so that the state does not flip back and forth
      if (use >= 4 && (float)sum / (float)use >= 1.25f * cfg_.dc_min) {
        begin_settle(now);
      } else {
        enter_standby(now);
      }
      return;
    }
    case SgSamplerState::kLedTest:
      if (!due(now, next_ms_)) return;
      if (write_leds(led_red_, led_ir_)) begin_settle(now);
      else enter_no_sensor(now, kRetryMs);
      return;
  }
}
