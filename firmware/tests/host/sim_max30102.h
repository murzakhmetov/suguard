// Register-level model of a MAX30102 for host tests (not part of the firmware).
//
// Implements what the driver relies on: register read/write with address
// auto-increment (except on FIFO_DATA), soft reset, shutdown, the 32-sample
// FIFO with write/read pointers and the overflow counter (roll-over off),
// SpO2-mode sample packing (2 x 3 bytes), interrupt status with clear-on-read
// (PWR_RDY, ALC_OVF), LED currents, the die-temperature conversion, and
// injected faults (absent chip, bus errors, brown-out reset).
#pragma once

#include <cstdint>
#include <cstring>
#include <functional>

#include "../../suguard/src/drivers/max30102.h"

struct SimMax30102 {
  using Source = std::function<void(uint64_t n, uint8_t led1, uint8_t led2, uint32_t* s1, uint32_t* s2)>;

  uint8_t reg[256];
  uint32_t fifo1[32], fifo2[32];
  int wr = 0, rd = 0, count = 0, ovf = 0;
  int byte_pos = 0;                 // position inside the sample being read (0..5)
  double now_ms = 0;
  double next_sample_ms = 0;
  double temp_ready_ms = -1;
  double output_rate_scale = 1.0;   // oscillator error: 1.02 = 2 % fast
  uint64_t n_generated = 0;
  bool present = true;
  int fail_transactions = 0;        // fail this many following bus transactions
  uint64_t transactions = 0;
  float die_temp = 31.5f;
  Source source;

  SimMax30102() { power_on_reset(); }

  void power_on_reset() {
    memset(reg, 0, sizeof reg);
    reg[max30102::kPartIdReg] = max30102::kPartId;
    reg[max30102::kRevId] = 0x03;
    reg[max30102::kIntStatus1] = max30102::kStatusPwrRdy;
    wr = rd = count = ovf = byte_pos = 0;
    temp_ready_ms = -1;
  }

  bool running() const {
    const uint8_t m = reg[max30102::kModeConfig];
    return !(m & max30102::kModeShutdown) && (m & 0x07) == max30102::kModeSpo2;
  }

  double period_ms() const {
    max30102::Config c;
    c.avg_code = reg[max30102::kFifoConfig] >> 5;
    c.rate_code = (reg[max30102::kSpo2Config] >> 2) & 7;
    return 1000.0 / (max30102::output_rate_hz(c) * output_rate_scale);
  }

  void advance(double ms) {
    const double end = now_ms + ms;
    if (!running()) {
      now_ms = end;
      next_sample_ms = end + period_ms();
    } else {
      if (next_sample_ms < now_ms) next_sample_ms = now_ms + period_ms();
      while (next_sample_ms <= end) {
        push_sample();
        next_sample_ms += period_ms();
      }
      now_ms = end;
    }
    if (temp_ready_ms >= 0 && now_ms >= temp_ready_ms) {
      reg[max30102::kTempConfig] &= ~0x01;
      reg[max30102::kTempInt] = (uint8_t)(int8_t)die_temp;
      reg[max30102::kTempFrac] = (uint8_t)((die_temp - (int)die_temp) / 0.0625f);
      temp_ready_ms = -1;
    }
  }

  void push_sample() {
    uint32_t s1 = 0, s2 = 0;
    if (source) source(n_generated, reg[max30102::kLed1Pa], reg[max30102::kLed2Pa], &s1, &s2);
    n_generated++;
    if (count == 32) {                       // roll-over disabled: the new sample is lost
      if (ovf < 31) ovf++;
      return;
    }
    fifo1[wr] = s1 & 0x3FFFF;
    fifo2[wr] = s2 & 0x3FFFF;
    wr = (wr + 1) & 31;
    count++;
  }

  uint8_t read_byte(uint8_t r) {
    switch (r) {
      case max30102::kFifoWrPtr: return (uint8_t)wr;
      case max30102::kOvfCounter: return (uint8_t)ovf;
      case max30102::kFifoRdPtr: return (uint8_t)rd;
      case max30102::kIntStatus1: {
        const uint8_t v = reg[r];
        reg[r] = 0;
        return v;
      }
      case max30102::kFifoData: {
        if (count == 0) return 0;
        const uint32_t s = byte_pos < 3 ? fifo1[rd] : fifo2[rd];
        const int shift = 16 - 8 * (byte_pos % 3);
        const uint8_t v = (uint8_t)(s >> shift);
        if (++byte_pos == 6) {               // a complete sample has been popped
          byte_pos = 0;
          rd = (rd + 1) & 31;
          count--;
          ovf = 0;
        }
        return v;
      }
      default: return reg[r];
    }
  }

  void write_byte(uint8_t r, uint8_t v) {
    switch (r) {
      case max30102::kModeConfig:
        if (v & max30102::kModeReset) {
          power_on_reset();                  // reset bit clears itself; PWR_RDY is set again
          return;
        }
        reg[r] = v;
        return;
      case max30102::kFifoWrPtr: wr = v & 31; count = (wr - rd) & 31; return;
      case max30102::kFifoRdPtr: rd = v & 31; count = (wr - rd) & 31; byte_pos = 0; return;
      case max30102::kOvfCounter: ovf = v & 31; return;
      case max30102::kTempConfig:
        reg[r] = v;
        if (v & 1) temp_ready_ms = now_ms + 29.0;
        return;
      default: reg[r] = v;
    }
  }

  static bool bus_write(void* ctx, uint8_t addr, uint8_t r, const uint8_t* data, size_t n) {
    auto* s = (SimMax30102*)ctx;
    s->transactions++;
    if (!s->present || addr != max30102::kI2cAddr) return false;
    if (s->fail_transactions > 0) { s->fail_transactions--; return false; }
    for (size_t i = 0; i < n; i++) s->write_byte((uint8_t)(r + i), data[i]);
    return true;
  }

  static bool bus_read(void* ctx, uint8_t addr, uint8_t r, uint8_t* data, size_t n) {
    auto* s = (SimMax30102*)ctx;
    s->transactions++;
    if (!s->present || addr != max30102::kI2cAddr) return false;
    if (s->fail_transactions > 0) { s->fail_transactions--; return false; }
    for (size_t i = 0; i < n; i++) {
      data[i] = s->read_byte(r);
      if (r != max30102::kFifoData) r++;     // FIFO_DATA does not auto-increment
    }
    return true;
  }

  SgI2c bus() { return SgI2c{this, bus_write, bus_read}; }
};
