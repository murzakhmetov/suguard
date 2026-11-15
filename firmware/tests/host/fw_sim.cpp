// Firmware-in-the-loop on a PC: builds the real sketch (suguard.ino) against
// the Arduino mock and the simulated MAX30102, plays recorded/simulated PPG
// through the sensor model and prints what the firmware prints on USB serial.
//
//   fw_sim <samples.bin> <seconds> [options...]
//     samples.bin : little-endian uint32 pairs (red, ir) at the sensor output rate, looped
//     cmd=<line>          typed on the serial console right after start-up (repeatable)
//     save=<key>=<value>  setting already stored in flash before the start (repeatable)
//     at=<s>:<kind>:<value>   timed event; kinds: cmd, ap, http, httpms, vbat, usb, button,
//                             present, por, scale, offset, spike, room, host
//     ap=1                the configured Wi-Fi access point is in range
//     ntp=<s>|never       seconds from "connected" to a valid clock (default 1.5)
//     http_code=<n>  http_ms=<ms>   answer and duration of every HTTPS request (200, 300)
//     proc_ms=<ms>        time the MCU needs per window (the PC needs none)
//     vbat=<V>  usb=0|1   battery voltage / USB power
//     wake=timer          this start is a wake-up from deep sleep
//     rate=<scale>        sensor oscillator error (1.02 = 2 % fast)
//     host=0              no PC is reading the USB port
//     start_ms=<n>        value of millis() at start (wrap-around tests)
//     unplug=<s>          the sensor stops answering at this time
//
// Simulated time only advances inside delay(): the sampler "task" runs every
// 50 ms of it, also while loop() is blocked in a request or in the pipeline,
// which is what the higher-priority task does on the device.
//
// Output: the firmware's serial lines, "HTTP PUT <url> ca=<0|1> code=<n> <body>"
// for every request and "SIM ..." lines from this harness.
#include <algorithm>
#include <cstdarg>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <ctime>
#include <string>
#include <sys/time.h>
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

static uint32_t g_ms = 0;                    // millis()
static uint64_t g_el = 0;                    // milliseconds since the start of the simulation
static SimMax30102 g_sim;
static bool g_task_started = false;
static std::string g_serial_in;
static size_t g_serial_pos = 0;
static std::vector<uint8_t> g_prefs_blob;
static std::vector<uint32_t> g_samples;      // red, ir, red, ir, ...

static double g_vbat = 3.9;
static bool g_usb = true;
static bool g_button = false;
static double g_scale = 1.0;                 // optical coupling
static double g_offset = 0.0;                // LED-independent counts (ambient light)
static long g_spike = 0;                     // every Nth sample saturates

static bool g_ap = false;                    // access point in range
static bool g_radio = false;
static uint64_t g_radio_since = 0, g_radio_on_ms = 0;
static double g_ntp_delay = 1.5;             // < 0: never
static bool g_sntp = false;
static uint64_t g_sntp_since = 0;
static bool g_clock_set = false;
static int g_http_code = 200;
static uint32_t g_http_ms = 300;
static uint32_t g_proc_ms = 0;

static bool g_host = true;                   // a PC reads the USB port
static int g_serial_room = -1;               // < 0: the whole transmit buffer
static size_t g_tx_buffer = 256;
static bool g_line_start = true;
static esp_sleep_wakeup_cause_t g_wake = ESP_SLEEP_WAKEUP_UNDEFINED;
static uint64_t g_led_on_ms = 0;

struct Event {
  double t;
  std::string kind, value;
};
static std::vector<Event> g_events;
static size_t g_event_pos = 0;

void samplerStep();                          // defined by the sketch

static void sim_line(const char* fmt, ...) {
  if (!g_line_start) {
    fputc('\n', stdout);
    g_line_start = true;
  }
  va_list ap;
  va_start(ap, fmt);
  vprintf(fmt, ap);
  va_end(ap);
}

// Wall clock of the simulated device: unset (1970 + up time) until SNTP has answered, then a
// fixed date plus the elapsed time, so that test output is reproducible.
static const time_t kSimEpoch = 1794700000;  // 2026-11-14T23:46:40Z
static bool wifi_connected() { return g_radio && g_ap && g_el - g_radio_since >= 2500; }
static time_t sim_time(time_t* out) {
  const time_t t = (g_clock_set ? kSimEpoch : 0) + (time_t)(g_el / 1000);
  if (out) *out = t;
  return t;
}
static int sim_gettimeofday(struct timeval* tv, void*) {
  tv->tv_sec = sim_time(nullptr);
  tv->tv_usec = (suseconds_t)(g_el % 1000) * 1000;
  return 0;
}

static void apply_events() {
  while (g_event_pos < g_events.size() && g_events[g_event_pos].t * 1000.0 <= (double)g_el) {
    const Event& e = g_events[g_event_pos++];
    const double v = atof(e.value.c_str());
    if (e.kind == "cmd") g_serial_in += e.value + "\n";
    else if (e.kind == "ap") g_ap = v != 0;
    else if (e.kind == "http") g_http_code = (int)v;
    else if (e.kind == "httpms") g_http_ms = (uint32_t)v;
    else if (e.kind == "vbat") g_vbat = v;
    else if (e.kind == "usb") g_usb = v != 0;
    else if (e.kind == "button") g_button = v != 0;
    else if (e.kind == "present") g_sim.present = v != 0;
    else if (e.kind == "por") g_sim.power_on_reset();
    else if (e.kind == "scale") g_scale = v;
    else if (e.kind == "offset") g_offset = v;
    else if (e.kind == "spike") g_spike = (long)v;
    else if (e.kind == "room") g_serial_room = (int)v;
    else if (e.kind == "host") g_host = v != 0;
  }
}

uint32_t millis() { return g_ms; }

void delay(uint32_t ms) {
  for (uint32_t i = 0; i < ms; i++) {
    g_ms++;
    g_el++;
    g_sim.advance(1.0);
    apply_events();
    if (g_radio) g_radio_on_ms++;
    if (g_sim.running() && (g_sim.reg[max30102::kLed1Pa] || g_sim.reg[max30102::kLed2Pa])) g_led_on_ms++;
    if (g_sntp && !g_clock_set && g_ntp_delay >= 0 && wifi_connected() &&
        (double)(g_el - g_sntp_since) >= g_ntp_delay * 1000.0) {
      g_clock_set = true;
    }
    if (g_task_started && g_el % 50 == 0) samplerStep();   // the 50 ms sampler task
  }
}

void pinMode(int, int) {}
int digitalRead(int pin) { return (pin == 9 && g_button) ? LOW : HIGH; }
uint32_t analogReadMilliVolts(int pin) {
  if (pin == 2) return (uint32_t)(g_vbat * 1000.0 * 47.0 / 147.0);   // BAT_VOLTAGE divider
  if (pin == 4) return g_usb ? 2500 : 0;                              // VBUS / 2
  return 0;
}
bool setCpuFrequencyMhz(uint32_t mhz) {
  sim_line("SIM cpu %u MHz\n", (unsigned)mhz);
  return true;
}
void configTime(long, int, const char*, const char*) {
  if (!g_sntp || !wifi_connected()) g_sntp_since = g_el;
  g_sntp = true;
}

SemaphoreHandle_t xSemaphoreCreateMutex() { return (SemaphoreHandle_t)1; }
int xSemaphoreTake(SemaphoreHandle_t, TickType_t) { return pdTRUE; }
int xSemaphoreGive(SemaphoreHandle_t) { return pdTRUE; }
int xTaskCreate(TaskFunction_t, const char*, uint32_t, void*, int, TaskHandle_t*) {
  g_task_started = true;
  return pdTRUE;
}
TickType_t xTaskGetTickCount() { return g_ms; }
void vTaskDelayUntil(TickType_t*, TickType_t) {}

static void out_bytes(const char* p, size_t n) {
  fwrite(p, 1, n, stdout);
  if (n) g_line_start = p[n - 1] == '\n';
}

HWCDC Serial;
size_t HWCDC::setTxBufferSize(size_t n) {
  g_tx_buffer = n;
  return n;
}
void HWCDC::setTxTimeoutMs(uint32_t) {}
void HWCDC::begin(unsigned long) {}
HWCDC::operator bool() const { return g_host; }
int HWCDC::availableForWrite() { return g_serial_room >= 0 ? g_serial_room : (int)g_tx_buffer; }
size_t HWCDC::write(const uint8_t* data, size_t n) {
  out_bytes((const char*)data, n);
  return n;
}
size_t HWCDC::print(const char* s) {
  out_bytes(s, strlen(s));
  return strlen(s);
}
int HWCDC::available() { return (int)(g_serial_in.size() - g_serial_pos); }
int HWCDC::read() { return g_serial_pos < g_serial_in.size() ? (uint8_t)g_serial_in[g_serial_pos++] : -1; }

EspClass ESP;
uint32_t EspClass::getFreeHeap() { return 150000; }
uint32_t EspClass::getMinFreeHeap() { return 90000; }
uint32_t EspClass::getMaxAllocHeap() { return 70000; }
void EspClass::restart() {
  sim_line("SIM restart requested\n");
  exit(0);
}

int esp_sleep_enable_timer_wakeup(uint64_t us) {
  sim_line("SIM sleep timer %llu s\n", (unsigned long long)(us / 1000000ULL));
  return 0;
}
esp_sleep_wakeup_cause_t esp_sleep_get_wakeup_cause() { return g_wake; }
void esp_deep_sleep_start() {
  sim_line("SIM deep sleep at %.2f s: sensor shutdown=%d led1=%u led2=%u radio=%d\n", (double)g_el / 1000.0,
           (g_sim.reg[max30102::kModeConfig] & max30102::kModeShutdown) ? 1 : 0, g_sim.reg[max30102::kLed1Pa],
           g_sim.reg[max30102::kLed2Pa], g_radio ? 1 : 0);
  exit(0);
}

// ---- Wire -> simulated sensor -------------------------------------------------
static uint8_t g_tx[64];
static size_t g_tx_len = 0;
static uint8_t g_tx_addr = 0;
static uint8_t g_rx[128];
static size_t g_rx_len = 0, g_rx_pos = 0;
static bool g_reg_valid = false;
static uint8_t g_reg = 0;

TwoWire Wire;
bool TwoWire::begin(int, int, uint32_t) { return true; }
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
  if (g_tx_len == 1) return (g_sim.present && g_tx_addr == max30102::kI2cAddr) ? 0 : 2;   // address NACK
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

// ---- Wi-Fi / HTTPS ------------------------------------------------------------
WiFiClass WiFi;
wl_status_t WiFiClass::status() { return wifi_connected() ? WL_CONNECTED : WL_DISCONNECTED; }
bool WiFiClass::mode(wifi_mode_t m) {
  if (m == WIFI_OFF && g_radio) {
    g_radio = false;
    sim_line("SIM %.2f radio off\n", (double)g_el / 1000.0);
  }
  return true;
}
wl_status_t WiFiClass::begin(const char* ssid, const char*) {
  g_radio = true;
  g_radio_since = g_el;
  sim_line("SIM %.2f radio on, joining %s\n", (double)g_el / 1000.0, ssid);
  return status();
}
bool WiFiClass::disconnect(bool wifi_off) {
  if (wifi_off && g_radio) {
    g_radio = false;
    sim_line("SIM %.2f radio off\n", (double)g_el / 1000.0);
  }
  return true;
}

static bool g_ca_set = false;
void WiFiClientSecure::setInsecure() { g_ca_set = false; }
void WiFiClientSecure::setCACert(const char* pem) { g_ca_set = pem && strstr(pem, "BEGIN CERTIFICATE"); }
void WiFiClientSecure::setHandshakeTimeout(unsigned long) {}

static std::string g_url;
void HTTPClient::setConnectTimeout(int32_t) {}
void HTTPClient::setTimeout(uint16_t) {}
bool HTTPClient::begin(WiFiClient&, String url) {
  g_url = url.c_str();
  return true;
}
void HTTPClient::addHeader(const String&, const String&) {}
int HTTPClient::PUT(uint8_t* payload, size_t size) {
  const int code = wifi_connected() ? g_http_code : -1;        // no connection: transport error
  sim_line("HTTP PUT %s ca=%d code=%d %.*s\n", g_url.c_str(), g_ca_set ? 1 : 0, code, (int)size,
           (const char*)payload);
  delay(g_http_ms);                                             // the request blocks loop(), not the sampler
  return code;
}
void HTTPClient::end() {}

// ---- Preferences (flash) --------------------------------------------------------
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

// ---- the firmware itself --------------------------------------------------------
#include "../../suguard/src/core/sg_pipeline.h"
static void sim_process_window(const uint32_t* red, const uint32_t* ir, bool nn, double ir_dc_min,
                               SgPipelineOutput* out) {
  sg_process_window(red, ir, nn, ir_dc_min, out);
  if (g_proc_ms) delay(g_proc_ms);           // the MCU needs 1-3 s; the sampler keeps running meanwhile
}
#define sg_process_window sim_process_window
#define time(x) sim_time(x)                  // the sketch's wall clock follows simulated time
#define gettimeofday(tv, tz) sim_gettimeofday(tv, tz)
#include "../../suguard/suguard.ino"
#undef gettimeofday
#undef time
#undef sg_process_window

int main(int argc, char** argv) {
  if (argc < 3) {
    fprintf(stderr, "usage: fw_sim <samples.bin> <seconds> [options]\n");
    return 2;
  }
  FILE* f = fopen(argv[1], "rb");
  if (!f) {
    fprintf(stderr, "cannot open %s\n", argv[1]);
    return 3;
  }
  uint32_t pair[2];
  while (fread(pair, sizeof(uint32_t), 2, f) == 2) {
    g_samples.push_back(pair[0]);
    g_samples.push_back(pair[1]);
  }
  fclose(f);
  const double seconds = atof(argv[2]);
  std::vector<std::string> cmds;
  SgConfig stored;
  sg_config_defaults(&stored);
  bool have_stored = false;
  for (int i = 3; i < argc; i++) {
    const std::string a = argv[i];
    const auto num = [&](size_t skip) { return atof(a.c_str() + skip); };
    if (a.rfind("cmd=", 0) == 0) cmds.push_back(a.substr(4));
    else if (a.rfind("save=", 0) == 0) {
      const size_t eq = a.find('=', 5);
      char err[64] = "";
      if (eq == std::string::npos ||
          !sg_config_set(&stored, a.substr(5, eq - 5).c_str(), a.substr(eq + 1).c_str(), err, sizeof err)) {
        fprintf(stderr, "bad option %s: %s\n", a.c_str(), err);
        return 2;
      }
      have_stored = true;
    } else if (a.rfind("at=", 0) == 0) {                  // at=<seconds>:<kind>:<value>
      const size_t c1 = a.find(':'), c2 = a.find(':', c1 + 1);
      if (c1 == std::string::npos || c2 == std::string::npos) return 2;
      g_events.push_back({atof(a.substr(3, c1 - 3).c_str()), a.substr(c1 + 1, c2 - c1 - 1), a.substr(c2 + 1)});
    } else if (a.rfind("ap=", 0) == 0) g_ap = a[3] == '1';
    else if (a == "ntp=never") g_ntp_delay = -1;
    else if (a.rfind("ntp=", 0) == 0) g_ntp_delay = num(4);
    else if (a.rfind("http_code=", 0) == 0) g_http_code = (int)num(10);
    else if (a.rfind("http_ms=", 0) == 0) g_http_ms = (uint32_t)num(8);
    else if (a.rfind("proc_ms=", 0) == 0) g_proc_ms = (uint32_t)num(8);
    else if (a.rfind("vbat=", 0) == 0) g_vbat = num(5);
    else if (a.rfind("usb=", 0) == 0) g_usb = a[4] == '1';
    else if (a == "wake=timer") g_wake = ESP_SLEEP_WAKEUP_TIMER;
    else if (a.rfind("rate=", 0) == 0) g_sim.output_rate_scale = num(5);
    else if (a.rfind("host=", 0) == 0) g_host = a[5] == '1';
    else if (a.rfind("start_ms=", 0) == 0) g_ms = (uint32_t)strtoul(a.c_str() + 9, nullptr, 10);
    else if (a.rfind("unplug=", 0) == 0) g_events.push_back({num(7), "present", "0"});
    else {
      fprintf(stderr, "unknown option %s\n", a.c_str());
      return 2;
    }
  }
  std::stable_sort(g_events.begin(), g_events.end(), [](const Event& a, const Event& b) { return a.t < b.t; });
  if (have_stored) g_prefs_blob.assign((const uint8_t*)&stored, (const uint8_t*)&stored + sizeof stored);

  // Light from the LEDs is proportional to their current (recorded at 0x3F); ambient light is not.
  const size_t n = g_samples.size() / 2;
  g_sim.source = [n](uint64_t i, uint8_t led1, uint8_t led2, uint32_t* s1, uint32_t* s2) {
    double red = n ? g_samples[2 * (i % n)] * (led1 / 63.0) * g_scale + g_offset : 0;
    double ir = n ? g_samples[2 * (i % n) + 1] * (led2 / 63.0) * g_scale + g_offset : 0;
    if (g_spike > 0 && i % (uint64_t)g_spike == 0) red = ir = 262143;
    *s1 = red > 262143 ? 262143u : (uint32_t)(red + 0.5);
    *s2 = ir > 262143 ? 262143u : (uint32_t)(ir + 0.5);
  };

  apply_events();
  setup();
  for (const auto& c : cmds) g_serial_in += c + "\n";
  while (g_el < (uint64_t)(seconds * 1000.0)) loop();
  sim_line("SIM done at %.2f s, %llu samples generated, leds on %.1f %% and radio on %.1f %% of the time\n",
           (double)g_el / 1000.0, (unsigned long long)g_sim.n_generated,
           100.0 * (double)g_led_on_ms / (double)(g_el ? g_el : 1), 100.0 * (double)g_radio_on_ms / (double)(g_el ? g_el : 1));
  return 0;
}
