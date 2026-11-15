#include "max30102.h"

namespace max30102 {

double output_rate_hz(const Config& c) {
  static const double kRates[8] = {50, 100, 200, 400, 800, 1000, 1600, 3200};
  static const double kAvg[8] = {1, 2, 4, 8, 16, 32, 32, 32};
  return kRates[c.rate_code & 7] / kAvg[c.avg_code & 7];
}

bool Device::wr(uint8_t reg, uint8_t v) { return bus_.write && bus_.write(bus_.ctx, kI2cAddr, reg, &v, 1); }

bool Device::rd(uint8_t reg, uint8_t* v, size_t n) { return bus_.read && bus_.read(bus_.ctx, kI2cAddr, reg, v, n); }

bool Device::probe(uint8_t* part, uint8_t* rev) {
  uint8_t p = 0, r = 0;
  if (!rd(kPartIdReg, &p) || !rd(kRevId, &r)) return false;
  if (part) *part = p;
  if (rev) *rev = r;
  return true;
}

bool Device::start_reset() { return wr(kModeConfig, kModeReset); }

bool Device::reset_done(bool* done) {
  uint8_t m = 0;
  if (!rd(kModeConfig, &m)) return false;
  *done = (m & kModeReset) == 0;
  return true;
}

bool Device::configure(const Config& c) {
  mode_ = kModeSpo2;
  const uint8_t fifo = (uint8_t)((c.avg_code & 7) << 5);            // roll-over off, A_FULL unused
  const uint8_t spo2 = (uint8_t)(((c.range_code & 3) << 5) | ((c.rate_code & 7) << 2) | (c.pw_code & 3));
  // The INT pin is not used (the FIFO is polled), but the ambient-light overflow flag is read from
  // the status register, and status flags of this chip family are only latched while enabled.
  return wr(kIntEnable1, kStatusAlcOvf) && wr(kIntEnable2, 0x00) && wr(kFifoConfig, fifo) && wr(kSpo2Config, spo2) &&
         set_led(c.led1, c.led2) && wr(kModeConfig, mode_) && clear_fifo();
}

bool Device::set_led(uint8_t led1, uint8_t led2) { return wr(kLed1Pa, led1) && wr(kLed2Pa, led2); }

bool Device::set_shutdown(bool on) { return wr(kModeConfig, (uint8_t)(mode_ | (on ? kModeShutdown : 0))); }

bool Device::clear_fifo() { return wr(kFifoWrPtr, 0) && wr(kOvfCounter, 0) && wr(kFifoRdPtr, 0); }

bool Device::read_status1(uint8_t* status) { return rd(kIntStatus1, status); }

int Device::read_fifo(uint32_t* slot1, uint32_t* slot2, int max_samples, int* lost) {
  uint8_t p[3];
  if (!rd(kFifoWrPtr, p, 3)) return -1;                              // WR_PTR, OVF_COUNTER, RD_PTR
  const int ovf = p[1] & 0x1F;
  int n = (p[0] - p[2]) & 0x1F;
  if (n == 0 && ovf > 0) n = kFifoDepth;                             // equal pointers + overflow = full
  if (lost) *lost = ovf;
  if (n > max_samples) n = max_samples;
  int done = 0;
  while (done < n) {
    uint8_t buf[6 * 16];                                             // 16 samples per transfer fits any Wire buffer
    const int m = (n - done) < 16 ? (n - done) : 16;
    if (!rd(kFifoData, buf, (size_t)(6 * m))) return -1;
    for (int i = 0; i < m; i++) {
      const uint8_t* b = buf + 6 * i;
      slot1[done + i] = ((uint32_t)(b[0] & 0x03) << 16) | ((uint32_t)b[1] << 8) | b[2];
      slot2[done + i] = ((uint32_t)(b[3] & 0x03) << 16) | ((uint32_t)b[4] << 8) | b[5];
    }
    done += m;
  }
  return n;
}

bool Device::start_temperature() { return wr(kTempConfig, 0x01); }

bool Device::read_temperature(float* celsius, bool* ready) {
  uint8_t cfg = 0;
  if (!rd(kTempConfig, &cfg)) return false;
  *ready = (cfg & 0x01) == 0;                                        // TEMP_EN clears itself when done
  if (!*ready) return true;
  uint8_t t[2];
  if (!rd(kTempInt, t, 2)) return false;
  *celsius = (float)(int8_t)t[0] + 0.0625f * (float)(t[1] & 0x0F);
  return true;
}

}  // namespace max30102
