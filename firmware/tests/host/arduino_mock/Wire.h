#pragma once
#include "Arduino.h"

class TwoWire {
 public:
  bool begin(int sda, int scl, uint32_t frequency);
  void setTimeOut(uint16_t ms);
  void beginTransmission(uint8_t addr);
  size_t write(uint8_t b);
  size_t write(const uint8_t* data, size_t n);
  uint8_t endTransmission(bool send_stop = true);
  size_t requestFrom(int addr, int n);
  int available();
  int read();
};
extern TwoWire Wire;
