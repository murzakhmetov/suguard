#pragma once
#include "Arduino.h"

class Preferences {
 public:
  bool begin(const char* name, bool read_only = false);
  size_t getBytesLength(const char* key);
  size_t getBytes(const char* key, void* buf, size_t max_len);
  size_t putBytes(const char* key, const void* value, size_t len);
};
