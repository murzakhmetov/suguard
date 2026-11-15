// Firmware-in-the-loop on a PC: builds the real sketch (suguard.ino) against
// the Arduino mock and the simulated MAX30102, plays recorded/simulated PPG
// through the sensor model and prints what the firmware prints on USB serial.
//
//   fw_sim <samples.bin> <seconds> [options...]
//     samples.bin : little-endian uint32 pairs (red, ir) at the sensor output rate, looped
//     options     : cmd=<console line>   typed on the serial console after start-up (repeatable)
//                   wifi=1               Wi-Fi reports "connected"; HTTP PUTs are logged
//                   vbat=<volts>  usb=1  battery / USB state
//                   rate=<scale>         sensor oscillator error (1.02 = 2 % fast)
//                   unplug=<s>           sensor stops answering at this time (seconds)
// Output: the firmware's serial lines, plus "HTTP PUT <url> <body>" for uploads
// and "SIM ..." lines from this harness.
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <ctime>
#include <string>
#include <vector>

#include "Arduino.h"
#include "HTTPClient.h"
#include "Preferences.h"
#include "WiFi.h"
#include "WiFiClientSecure.h"
#include "Wire.h"
#include "esp_sleep.h"
#include "sim_max30102.h"

// ---- simulation state -------------------------------------------------------

static uint32_t g_ms = 0;
static SimMax30102 g_sim;
static bool g_task_started = false;
static bool g_wifi = false;
static double g_vbat = 3.9;
static bool g_usb = true;
static std::string g_serial_in;
static size_t g_serial_pos = 0;
static std::vector<uint8_t> g_prefs_blob;
static std::vector<uint32_t> g_samples;     // red, ir, red, ir, ...

void samplerStep();                          // defined by the sketch

// Wall clock of the simulated device: starts at a fixed date and follows simulated time,
// so that test output is reproducible.
static const time_t kSimEpoch = 1794700000;  // 2026-11-14T23:46:40Z
static time_t sim_time(time_t* out) {
  const time_t t = kSimEpoch + (time_t)(g_ms / 1000);
  if (out) *out = t;
  return t;
}

uint32_t millis() { return g_ms; }

void delay(uint32_t ms) {
  for (uint32_t i = 0; i < ms; i++) {
    g_ms++;
    g_sim.advance(1.0);
    if (g_task_started && g_ms % 50 == 0) samplerStep();   // the 50 ms sampler task
  }
}

void pinMode(int, int) {}
int digitalRead(int) { return HIGH; }
uint32_t analogReadMilliVolts(int pin) {
  if (pin == 2) return (uint32_t)(g_vbat * 1000.0 * 47.0 / 147.0);
  if (pin == 4) return g_usb ? 2500 : 0;
  return 0;
}
void configTime(long, int, const char*, const char*) {}

SemaphoreHandle_t xSemaphoreCreateMutex() { return (SemaphoreHandle_t)1; }
int xSemaphoreTake(SemaphoreHandle_t, TickType_t) { return pdTRUE; }
int xSemaphoreGive(SemaphoreHandle_t) { return pdTRUE; }
int xTaskCreate(TaskFunction_t, const char*, uint32_t, void*, int, TaskHandle_t*) {
  g_task_started = true;                     // the task body is driven from delay()
  return pdTRUE;
}
TickType_t xTaskGetTickCount() { return g_ms; }
void vTaskDelayUntil(TickType_t*, TickType_t) {}

HWCDC Serial;
size_t HWCDC::setTxBufferSize(size_t n) { return n; }
void HWCDC::begin(unsigned long) {}
int HWCDC::availableForWrite() { return 16384; }
size_t HWCDC::write(const uint8_t* data, size_t n) { return fwrite(data, 1, n, stdout); }
size_t HWCDC::print(const char* s) { return fwrite(s, 1, strlen(s), stdout); }
int HWCDC::available() { return (int)(g_serial_in.size() - g_serial_pos); }
int HWCDC::read() { return g_serial_pos < g_serial_in.size() ? (uint8_t)g_serial_in[g_serial_pos++] : -1; }

EspClass ESP;
uint32_t EspClass::getFreeHeap() { return 200000; }
void EspClass::restart() {
  printf("SIM restart requested\n");
  exit(0);
}

int esp_sleep_enable_timer_wakeup(uint64_t us) {
  printf("SIM deep sleep timer %llu s\n", (unsigned long long)(us / 1000000ULL));
  return 0;
}
void esp_deep_sleep_start() {
  printf("SIM deep sleep at %u ms\n", (unsigned)g_ms);
  exit(0);
}

// Wire: a register write is [reg, data...]; a read is [reg] + repeated start + requestFrom.
static uint8_t g_tx[64];
static size_t g_tx_len = 0;
static uint8_t g_tx_addr = 0;
static uint8_t g_rx[128];
static size_t g_rx_len = 0, g_rx_pos = 0;
static bool g_reg_valid = false;
static uint8_t g_reg = 0;

TwoWire Wire;
bool TwoWire::begin(int sda, int scl, uint32_t hz) {
  printf("SIM Wire.begin sda=%d scl=%d hz=%u\n", sda, scl, (unsigned)hz);
  return true;
}
void TwoWire::setTimeOut(uint16_t) {}
void TwoWire::beginTransmission(uint8_t addr) {
  g_tx_addr = addr;
  g_tx_len = 0;
}
size_t TwoWire::write(uint8_t b) {
  if (g_tx_len < sizeof g_tx) g_tx[g_tx_len++] = b;
  return 1;
}
size_t TwoWire::write(const uint8_t* data, size_t n) {
  for (size_t i = 0; i < n; i++) write(data[i]);
  return n;
}
uint8_t TwoWire::endTransmission(bool) {
  if (g_tx_len == 0) return 4;
  g_reg = g_tx[0];
  g_reg_valid = true;
  if (g_tx_len == 1) {                       // register pointer only (a read follows)
    return (g_sim.present && g_tx_addr == max30102::kI2cAddr) ? 0 : 2;
  }
  return SimMax30102::bus_write(&g_sim, g_tx_addr, g_reg, g_tx + 1, g_tx_len - 1) ? 0 : 2;
}
size_t TwoWire::requestFrom(int addr, int n) {
  g_rx_len = g_rx_pos = 0;
  if (!g_reg_valid || n > (int)sizeof g_rx) return 0;
  if (!SimMax30102::bus_read(&g_sim, (uint8_t)addr, g_reg, g_rx, (size_t)n)) return 0;
  g_rx_len = (size_t)n;
  return g_rx_len;
}
int TwoWire::available() { return (int)(g_rx_len - g_rx_pos); }
int TwoWire::read() { return g_rx_pos < g_rx_len ? g_rx[g_rx_pos++] : -1; }

WiFiClass WiFi;
wl_status_t WiFiClass::status() { return g_wifi ? WL_CONNECTED : WL_DISCONNECTED; }
bool WiFiClass::mode(wifi_mode_t) { return true; }
wl_status_t WiFiClass::begin(const char* ssid, const char*) {
  printf("SIM WiFi.begin ssid=%s\n", ssid);
  return status();
}
bool WiFiClass::disconnect(bool) { return true; }

static bool g_ca_set = false;
void WiFiClientSecure::setInsecure() { g_ca_set = false; }
void WiFiClientSecure::setCACert(const char* pem) { g_ca_set = pem && strstr(pem, "BEGIN CERTIFICATE"); }

static std::string g_url;
void HTTPClient::setConnectTimeout(int32_t) {}
void HTTPClient::setTimeout(uint16_t) {}
bool HTTPClient::begin(WiFiClient&, String url) {
  g_url = url.c_str();
  return true;
}
void HTTPClient::addHeader(const String&, const String&) {}
int HTTPClient::PUT(uint8_t* payload, size_t size) {
  printf("HTTP PUT %s ca=%d %.*s\n", g_url.c_str(), g_ca_set ? 1 : 0, (int)(size > 600 ? 600 : size), (const char*)payload);
  delay(300);                                // a request takes time; sampling must continue meanwhile
  return 200;
}
void HTTPClient::end() {}

bool Preferences::begin(const char*, bool) { return true; }
size_t Preferences::getBytesLength(const char*) { return g_prefs_blob.size(); }
size_t Preferences::getBytes(const char*, void* buf, size_t max_len) {
  const size_t n = g_prefs_blob.size() < max_len ? g_prefs_blob.size() : max_len;
  memcpy(buf, g_prefs_blob.data(), n);
  return n;
}
size_t Preferences::putBytes(const char*, const void* value, size_t len) {
  g_prefs_blob.assign((const uint8_t*)value, (const uint8_t*)value + len);
  return len;
}

// ---- the firmware itself -------------------------------------------------------
#define time(x) sim_time(x)
#include "../../suguard/suguard.ino"
#undef time

int main(int argc, char** argv) {
  if (argc < 3) {
    fprintf(stderr, "usage: fw_sim <samples.bin> <seconds> [cmd=...] [wifi=1] [vbat=V] [usb=0|1] [rate=x] [unplug=s]\n");
    return 2;
  }
  FILE* f = fopen(argv[1], "rb");
  if (!f) return 3;
  uint32_t pair[2];
  while (fread(pair, sizeof(uint32_t), 2, f) == 2) {
    g_samples.push_back(pair[0]);
    g_samples.push_back(pair[1]);
  }
  fclose(f);
  const double seconds = atof(argv[2]);
  std::vector<std::string> cmds;
  double unplug_s = -1;
  for (int i = 3; i < argc; i++) {
    const std::string a = argv[i];
    if (a.rfind("cmd=", 0) == 0) cmds.push_back(a.substr(4));
    else if (a == "wifi=1") g_wifi = true;
    else if (a.rfind("vbat=", 0) == 0) g_vbat = atof(a.c_str() + 5);
    else if (a.rfind("usb=", 0) == 0) g_usb = a[4] == '1';
    else if (a.rfind("rate=", 0) == 0) g_sim.output_rate_scale = atof(a.c_str() + 5);
    else if (a.rfind("unplug=", 0) == 0) unplug_s = atof(a.c_str() + 7);
  }
  const size_t n = g_samples.size() / 2;
  // The recording was made at the default LED current (0x3F); the detected light scales with it.
  g_sim.source = [n](uint64_t i, uint8_t led1, uint8_t led2, uint32_t* s1, uint32_t* s2) {
    const double red = n ? g_samples[2 * (i % n)] * (led1 / 63.0) : 0;       // slot 1 = red (genuine MAX30102)
    const double ir = n ? g_samples[2 * (i % n) + 1] * (led2 / 63.0) : 0;    // slot 2 = IR
    *s1 = red > 262143 ? 262143u : (uint32_t)(red + 0.5);
    *s2 = ir > 262143 ? 262143u : (uint32_t)(ir + 0.5);
  };

  setup();
  for (const auto& c : cmds) g_serial_in += c + "\n";
  while (g_ms < (uint32_t)(seconds * 1000.0)) {
    if (unplug_s >= 0 && g_ms >= (uint32_t)(unplug_s * 1000.0)) g_sim.present = false;
    loop();
  }
  printf("SIM done at %u ms, %llu samples generated\n", (unsigned)g_ms, (unsigned long long)g_sim.n_generated);
  return 0;
}
