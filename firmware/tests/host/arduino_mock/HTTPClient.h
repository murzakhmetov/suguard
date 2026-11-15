#pragma once
#include "WiFi.h"

class HTTPClient {
 public:
  void setConnectTimeout(int32_t ms);
  void setTimeout(uint16_t ms);
  bool begin(WiFiClient& client, String url);
  void addHeader(const String& name, const String& value);
  int PUT(uint8_t* payload, size_t size);
  void end();
};
