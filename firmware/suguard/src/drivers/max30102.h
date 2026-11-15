// Register-level driver for the MAX30102 pulse oximeter front end
// (Analog Devices / Maxim, datasheet rev. 1, 19-7740).
//
// Physical naming is used here: "LED1 / slot 1" is the first FIFO channel and
// register 0x0C, "LED2 / slot 2" the second and 0x0D. On a genuine MAX30102
// LED1 is red (660 nm) and LED2 infrared (880 nm); some clone modules have
// them swapped, which the sampler handles (config swap_red_ir).
#pragma once

#include <stddef.h>
#include <stdint.h>

#include "../hal/sg_hal.h"

namespace max30102 {

constexpr uint8_t kI2cAddr = 0x57;
constexpr uint8_t kPartId = 0x15;
constexpr int kFifoDepth = 32;

enum Reg : uint8_t {
  kIntStatus1 = 0x00,   // A_FULL[7] PPG_RDY[6] ALC_OVF[5] PWR_RDY[0]; cleared by reading
  kIntStatus2 = 0x01,   // DIE_TEMP_RDY[1]
  kIntEnable1 = 0x02,
  kIntEnable2 = 0x03,
  kFifoWrPtr = 0x04,
  kOvfCounter = 0x05,
  kFifoRdPtr = 0x06,
  kFifoData = 0x07,
  kFifoConfig = 0x08,   // SMP_AVE[7:5] FIFO_ROLLOVER_EN[4] FIFO_A_FULL[3:0]
  kModeConfig = 0x09,   // SHDN[7] RESET[6] MODE[2:0]
  kSpo2Config = 0x0A,   // ADC_RGE[6:5] SR[4:2] LED_PW[1:0]
  kLed1Pa = 0x0C,       // 0.2 mA per LSB
  kLed2Pa = 0x0D,
  kTempInt = 0x1F,
  kTempFrac = 0x20,     // 0.0625 degC per LSB
  kTempConfig = 0x21,   // TEMP_EN[0], self-clearing
  kRevId = 0xFE,
  kPartIdReg = 0xFF,
};

constexpr uint8_t kStatusAlcOvf = 0x20;
constexpr uint8_t kStatusPwrRdy = 0x01;
constexpr uint8_t kModeShutdown = 0x80;
constexpr uint8_t kModeReset = 0x40;
constexpr uint8_t kModeSpo2 = 0x03;        // red + IR

struct Config {
  uint8_t avg_code = 3;     // SMP_AVE: 0..5 -> 1, 2, 4, 8, 16, 32 samples
  uint8_t rate_code = 3;    // SR: 0..7 -> 50, 100, 200, 400, 800, 1000, 1600, 3200 sps
  uint8_t pw_code = 3;      // LED_PW: 0..3 -> 69, 118, 215, 411 us (15..18 bit)
  uint8_t range_code = 1;   // ADC_RGE: 0..3 -> 2048, 4096, 8192, 16384 nA full scale
  uint8_t led1 = 0x3F;      // 12.6 mA
  uint8_t led2 = 0x3F;
};

// Output sample rate in Hz for a configuration (sample rate / averaging).
double output_rate_hz(const Config& c);

class Device {
 public:
  void attach(const SgI2c& bus) { bus_ = bus; }

  // Reads PART_ID / REV_ID. Returns false on a bus error; `*part` must be kPartId.
  bool probe(uint8_t* part, uint8_t* rev);
  // Starts a soft reset (all registers to power-on values). Poll reset_done().
  bool start_reset();
  bool reset_done(bool* done);
  // SpO2 mode with the given settings, FIFO roll-over disabled, FIFO cleared,
  // interrupts disabled (the firmware polls the FIFO).
  bool configure(const Config& c);
  bool set_led(uint8_t led1, uint8_t led2);
  // Shutdown keeps the registers but stops the LEDs and the ADC (~0.7 uA).
  bool set_shutdown(bool on);
  bool clear_fifo();
  // Reads and clears the interrupt status (ALC overflow, power-ready).
  bool read_status1(uint8_t* status);

  // Drains up to `max_samples` samples. Returns the number read, or -1 on a
  // bus error. `*lost` = samples the chip dropped because the FIFO was full
  // (they were lost *after* the samples returned by this call).
  int read_fifo(uint32_t* slot1, uint32_t* slot2, int max_samples, int* lost);

  // Die temperature: start a conversion (~29 ms), then poll until `*ready`.
  bool start_temperature();
  bool read_temperature(float* celsius, bool* ready);

 private:
  bool wr(uint8_t reg, uint8_t v);
  bool rd(uint8_t reg, uint8_t* v, size_t n = 1);
  SgI2c bus_{};
  uint8_t mode_ = kModeSpo2;
};

}  // namespace max30102
