#pragma once
#include "WiFi.h"

class WiFiClientSecure : public WiFiClient {
 public:
  void setInsecure();
  void setCACert(const char* root_ca);
  void setHandshakeTimeout(unsigned long seconds);
};
