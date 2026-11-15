#pragma once
#include "Arduino.h"

enum wl_status_t { WL_IDLE_STATUS = 0, WL_CONNECTED = 3, WL_DISCONNECTED = 6 };
enum wifi_mode_t { WIFI_OFF = 0, WIFI_STA = 1 };

class WiFiClient {};

class WiFiClass {
 public:
  wl_status_t status();
  bool mode(wifi_mode_t m);
  wl_status_t begin(const char* ssid, const char* pass);
  bool disconnect(bool wifi_off = false);
};
extern WiFiClass WiFi;
