// SuGuard bracelet firmware
// Board: SuGuard PCB (ESP32-C3-WROOM-02 + MH-ET LIVE MAX30102 module, TP4056 charger)
//
// What it does
//   * samples raw red/IR PPG at 50 Hz in gap-free 10.24-s windows
//   * runs the on-device pipeline (integer neural denoiser + signal quality
//     gates) and reports heart rate and SpO2 only for windows that pass
//   * USB serial console (115200): live JSON lines, settings, raw streaming
//   * optional Wi-Fi upload of averaged records to Firebase (users/<uid>/vitals)
//
// It does NOT report glucose: there is no validated glucose model for this
// sensor (see ml/README.md). Not a medical device.
//
// Build (Arduino IDE 2.x, "esp32 by Espressif" core 3.x):
//   Board "ESP32C3 Dev Module", USB CDC On Boot: Enabled, CPU 160 MHz,
//   Flash 4MB, Partition Scheme "Minimal SPIFFS (1.9MB APP with OTA)".
// or PlatformIO: see platformio.ini. Details: firmware/README.md.

#include <Arduino.h>
#include <HTTPClient.h>
#include <Preferences.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <Wire.h>
#include <esp_sleep.h>
#include <math.h>
#include <time.h>

#include "src/app/aggregate.h"
#include "src/app/battery.h"
#include "src/app/cli.h"
#include "src/app/cloud_fmt.h"
#include "src/app/config.h"
#include "src/app/sampler.h"
#include "src/board.h"
#include "src/certs.h"
#include "src/core/sg_pipeline.h"

#define SG_FW_VERSION "1.0.0"

// ----------------------------------------------------------------------------
// State
// ----------------------------------------------------------------------------

static SgConfig g_cfg;
static Preferences g_prefs;
static SgSampler g_sampler;
static SgBatteryMonitor g_battery;
static SgAggregator g_agg;

// Window hand-over from the sampler task to loop(): 0 = empty, 1 = ready, 2 = being processed.
static SgWindow g_window;
static volatile uint8_t g_window_state = 0;
static volatile uint32_t g_windows_dropped = 0;
static SemaphoreHandle_t g_window_lock;

static uint32_t g_last_report_ms = 0;
static uint32_t g_last_battery_ms = 0;
static uint32_t g_low_battery_since_ms = 0;
static uint32_t g_wifi_last_try_ms = 0;
static bool g_time_started = false;
static bool g_wifi_dirty = false;         // credentials changed on the console
static bool g_button_down = false;
static uint32_t g_button_ms = 0;

// Records that could not be uploaded yet (kept in RAM, oldest dropped first).
#define SG_QUEUE_LEN 6
#define SG_RECORD_MAX 448
struct QueuedRecord {
  char key[24];
  char node[8];                           // "vitals" or "events"
  char json[SG_RECORD_MAX];
};
static QueuedRecord g_queue[SG_QUEUE_LEN];
static int g_queue_count = 0;
static uint32_t g_upload_ok = 0, g_upload_fail = 0;

static char g_line[200];
static size_t g_line_len = 0;
static char g_json[SG_RAW_JSON_MAX];      // shared scratch for the big raw-window JSON

// ----------------------------------------------------------------------------
// Small helpers
// ----------------------------------------------------------------------------

// Print only if the USB buffer has room: never stall the firmware when no PC is listening.
static bool serialWrite(const char* s, size_t n) {
  if ((size_t)Serial.availableForWrite() < n) return false;
  Serial.write((const uint8_t*)s, n);
  return true;
}

static void serialPrint(const char* s) { serialWrite(s, strlen(s)); }

static bool timeValid() { return time(nullptr) > 1700000000; }

static bool cloudConfigured(char* uid, size_t uid_len) {
  return g_cfg.cloud && g_cfg.wifi_ssid[0] && sg_email_to_uid(g_cfg.user_email, uid, uid_len);
}

static SgSamplerConfig samplerConfig() {
  SgSamplerConfig c;
  c.sensor.avg_code = 3;                  // 400 sps / 8 = 50 Hz output
  c.sensor.rate_code = 3;
  c.sensor.pw_code = 3;                   // 411 us, 18 bit
  c.sensor.range_code = g_cfg.adc_range;
  c.swap_red_ir = g_cfg.swap_red_ir != 0;
  c.led_init = g_cfg.led_init;
  c.led_max = g_cfg.led_max < g_cfg.led_init ? g_cfg.led_init : g_cfg.led_max;
  c.dc_min = g_cfg.ir_dc_min;
  return c;
}

// ----------------------------------------------------------------------------
// I2C (used by the sampler task only)
// ----------------------------------------------------------------------------

static bool i2cWrite(void*, uint8_t addr, uint8_t reg, const uint8_t* data, size_t n) {
  Wire.beginTransmission(addr);
  Wire.write(reg);
  Wire.write(data, n);
  return Wire.endTransmission() == 0;
}

static bool i2cRead(void*, uint8_t addr, uint8_t reg, uint8_t* data, size_t n) {
  Wire.beginTransmission(addr);
  Wire.write(reg);
  if (Wire.endTransmission(false) != 0) return false;            // repeated start
  const size_t got = Wire.requestFrom((int)addr, (int)n);        // n <= 96, below the Wire buffer size
  if (got != n) {
    while (Wire.available()) Wire.read();
    return false;
  }
  for (size_t i = 0; i < n; i++) data[i] = (uint8_t)Wire.read();
  return true;
}

// ----------------------------------------------------------------------------
// Sampler task: the only code that talks to the sensor. Higher priority than
// loop(), so slow work there (neural network, HTTPS) never loses samples.
// ----------------------------------------------------------------------------

static void onWindow(void*, const SgWindow* w) {
  if (xSemaphoreTake(g_window_lock, 0) == pdTRUE) {              // never block the sampler
    if (g_window_state == 0) {
      memcpy(&g_window, w, sizeof(SgWindow));
      g_window_state = 1;
    } else {
      g_windows_dropped++;                                       // loop() is still busy with the previous one
    }
    xSemaphoreGive(g_window_lock);
  } else {
    g_windows_dropped++;
  }
}

void samplerStep() { g_sampler.poll(millis()); }                 // not static: the host simulation calls it

static void samplerTask(void*) {
  TickType_t last = xTaskGetTickCount();
  for (;;) {
    samplerStep();
    vTaskDelayUntil(&last, pdMS_TO_TICKS(50));
  }
}

// ----------------------------------------------------------------------------
// Settings
// ----------------------------------------------------------------------------

static void loadConfig() {
  sg_config_defaults(&g_cfg);
  g_prefs.begin("suguard", false);
  if (g_prefs.getBytesLength("cfg") == sizeof(SgConfig)) {
    SgConfig stored;
    g_prefs.getBytes("cfg", &stored, sizeof stored);
    if (stored.version == SG_CONFIG_VERSION) g_cfg = stored;
  }
}

static void saveConfig() {
  const bool ok = g_prefs.putBytes("cfg", &g_cfg, sizeof g_cfg) == sizeof g_cfg;
  serialPrint(ok ? "saved\n" : "error: could not write settings\n");
}

static void applyConfig() {
  g_sampler.request_config(samplerConfig());
  SgBatteryConfig b;
  b.cal = g_cfg.bat_cal;
  g_battery.set_config(b);
  g_wifi_dirty = true;
}

// ----------------------------------------------------------------------------
// Cloud
// ----------------------------------------------------------------------------

static bool httpPut(const char* url, const char* body, size_t len) {
  WiFiClientSecure client;
  if (g_cfg.tls_insecure) client.setInsecure();
  else client.setCACert(SG_ROOT_CAS);
  HTTPClient http;
  http.setConnectTimeout(8000);
  http.setTimeout(8000);
  if (!http.begin(client, url)) return false;
  http.addHeader("Content-Type", "application/json");
  const int code = http.PUT((uint8_t*)body, len);
  http.end();
  if (code >= 200 && code < 300) {
    g_upload_ok++;
    return true;
  }
  g_upload_fail++;
  return false;
}

static void enqueue(const char* node, const char* key, const char* json) {
  if (g_queue_count == SG_QUEUE_LEN) {                           // full: drop the oldest
    memmove(&g_queue[0], &g_queue[1], sizeof(QueuedRecord) * (SG_QUEUE_LEN - 1));
    g_queue_count--;
  }
  QueuedRecord& q = g_queue[g_queue_count++];
  snprintf(q.node, sizeof q.node, "%s", node);
  snprintf(q.key, sizeof q.key, "%s", key);
  snprintf(q.json, sizeof q.json, "%s", json);
}

// Sends at most one queued record per call so that loop() stays responsive.
static void flushQueue() {
  char uid[160], url[400];
  if (g_queue_count == 0 || WiFi.status() != WL_CONNECTED || !cloudConfigured(uid, sizeof uid)) return;
  const QueuedRecord& q = g_queue[0];
  if (sg_db_url(url, sizeof url, g_cfg.db_url, "users", uid, q.node, q.key, g_cfg.db_auth) < 0) return;
  if (httpPut(url, q.json, strlen(q.json))) {
    memmove(&g_queue[0], &g_queue[1], sizeof(QueuedRecord) * (SG_QUEUE_LEN - 1));
    g_queue_count--;
  }
}

static void uploadRawWindow(const SgWindow& w) {
  char uid[160], url[400], key[24];
  if (WiFi.status() != WL_CONNECTED || !timeValid() || !cloudConfigured(uid, sizeof uid)) return;
  const int64_t now_s = (int64_t)time(nullptr);
  sg_record_key(now_s * 1000 + (int64_t)(millis() % 1000), key, sizeof key);
  const int n = sg_raw_window_json(g_json, sizeof g_json, &w, now_s, g_cfg.device_id);
  if (n < 0 || sg_db_url(url, sizeof url, g_cfg.db_url, "rawPpg", uid, nullptr, key, g_cfg.db_auth) < 0) return;
  httpPut(url, g_json, (size_t)n);                               // best effort: raw windows are not queued
}

static void wifiService(uint32_t now) {
  if (!g_cfg.wifi_ssid[0] || !g_cfg.cloud) return;
  if (g_wifi_dirty) {
    g_wifi_dirty = false;
    WiFi.disconnect();
    g_wifi_last_try_ms = now - 60000;
  }
  if (WiFi.status() == WL_CONNECTED) {
    if (!g_time_started) {
      configTime(0, 0, "pool.ntp.org", "time.google.com");       // UTC; the offset is applied when formatting
      g_time_started = true;
    }
    return;
  }
  if (now - g_wifi_last_try_ms >= 20000) {
    g_wifi_last_try_ms = now;
    WiFi.mode(WIFI_STA);
    WiFi.begin(g_cfg.wifi_ssid, g_cfg.wifi_pass);
  }
}

// ----------------------------------------------------------------------------
// Reporting
// ----------------------------------------------------------------------------

static void markEvent(const char* note) {
  char line[320], key[24];
  const int64_t now_s = timeValid() ? (int64_t)time(nullptr) : 0;
  const int n = sg_event_json(line, sizeof line - 3, now_s, g_cfg.tz_offset_min, "mark", note);
  if (n < 0) return;
  if (now_s) {
    sg_record_key(now_s * 1000 + (int64_t)(millis() % 1000), key, sizeof key);
    enqueue("events", key, line);
  }
  memcpy(line + n, "}\n", 3);                                   // closes the {"t":"event","e":... wrapper
  serialPrint("{\"t\":\"event\",\"e\":");
  serialPrint(line);
}

static void printWindowLine(const SgWindow& w, const SgPipelineOutput& o, double hr_scale, uint32_t proc_ms) {
  char reasons[160], line[512];
  sg_reason_names(o.vitals.reliable ? 0 : o.vitals.reasons, reasons, sizeof reasons);   // reasons explain a rejection
  char hr[16] = "null", spo2[16] = "null", temp[16] = "null";
  if (o.vitals.reliable && o.vitals.has_hr) snprintf(hr, sizeof hr, "%.1f", o.vitals.hr_bpm * hr_scale);
  if (o.vitals.has_spo2) snprintf(spo2, sizeof spo2, "%.1f", o.vitals.spo2);
  if (!isnan(w.temperature_c)) snprintf(temp, sizeof temp, "%.2f", (double)w.temperature_c);
  const int n = snprintf(
      line, sizeof line,
      "{\"t\":\"vitals\",\"seq\":%lu,\"reliable\":%s,\"hr\":%s,\"spo2\":%s,\"sqi\":%.2f,\"pi\":%.3f,"
      "\"motion\":%.2f,\"reasons\":\"%s\",\"nn\":%s,\"dc\":[%.0f,%.0f],\"led\":[%u,%u],\"temp\":%s,"
      "\"fs\":%.3f,\"proc_ms\":%lu,\"bat\":%d,\"usb\":%s}\n",
      (unsigned long)w.seq, o.vitals.reliable ? "true" : "false", hr, spo2, o.vitals.quality.sqi, o.vitals.pi_in,
      o.vitals.quality.motion_fraction, reasons, o.used_nn ? "true" : "false", o.sensor.red_dc, o.sensor.ir_dc,
      (unsigned)w.led_red, (unsigned)w.led_ir, temp, (double)w.fs_hz, (unsigned long)proc_ms,
      g_battery.state().percent, g_battery.state().usb_present ? "true" : "false");
  if (n > 0 && n < (int)sizeof line) serialWrite(line, (size_t)n);
}

static void printRawWindow(const SgWindow& w) {
  const int64_t now_s = timeValid() ? (int64_t)time(nullptr) : (int64_t)(millis() / 1000);
  const int n = sg_raw_window_json(g_json, sizeof g_json - 16, &w, now_s, g_cfg.device_id);
  if (n < 0 || (size_t)Serial.availableForWrite() < (size_t)n + 16) return;    // PC not reading: skip
  Serial.print("{\"t\":\"raw\",\"w\":");
  Serial.write((const uint8_t*)g_json, (size_t)n);
  Serial.print("}\n");
}

// Every report interval: one record from the reliable windows, if there is any.
static void reportService(uint32_t now) {
  if (now - g_last_report_ms < (uint32_t)g_cfg.report_interval_s * 1000u) return;
  g_last_report_ms = now;
  SgVitalsRecord rec;
  memset(&rec, 0, sizeof rec);
  const bool any = g_agg.summary(&rec.pulse_bpm, &rec.has_spo2, &rec.spo2, &rec.sqi, &rec.spo2_windows,
                                 &rec.has_temperature, &rec.temperature_c);
  rec.windows = g_agg.windows();
  rec.reliable_windows = g_agg.reliable();
  g_agg.reset();
  if (!any) return;                                              // nothing trustworthy: report nothing
  rec.unix_s = timeValid() ? (int64_t)time(nullptr) : 0;
  rec.tz_offset_min = g_cfg.tz_offset_min;
  rec.battery_percent = g_battery.state().percent;
  rec.charging = g_battery.state().charging;
  rec.device_id = g_cfg.device_id;
  rec.firmware = SG_FW_VERSION;
  rec.model = g_cfg.use_nn ? "edge-nn" : "classical";
  char key[24], json[SG_RECORD_MAX];
  sg_record_key(rec.unix_s * 1000, key, sizeof key);
  const int n = sg_vitals_json(json, sizeof json - 3, &rec, key);
  if (n < 0) return;
  char uid[160];
  if (rec.unix_s && cloudConfigured(uid, sizeof uid)) enqueue("vitals", key, json);
  memcpy(json + n, "}\n", 3);                                   // closes the {"t":"record","r":... wrapper
  serialPrint("{\"t\":\"record\",\"r\":");
  serialPrint(json);
}

static void processPendingWindow() {
  if (g_window_state != 1) return;
  xSemaphoreTake(g_window_lock, portMAX_DELAY);
  g_window_state = 2;
  xSemaphoreGive(g_window_lock);

  const SgWindow& w = g_window;
  static SgPipelineOutput out;
  const uint32_t t0 = millis();
  sg_process_window(w.red, w.ir, g_cfg.use_nn != 0, &out);
  const uint32_t proc_ms = millis() - t0;
  if (w.flags & SG_WF_AMBIENT_OVERFLOW) {                        // sunlight overwhelmed the sensor
    out.vitals.reliable = false;
    out.vitals.has_spo2 = false;
    out.vitals.reasons |= SG_R_ADC_SATURATED;
  }
  const double hr_scale = w.fs_hz > 0 ? (double)w.fs_hz / SG_FS : 1.0;   // sensor clock tolerance
  g_agg.add(out.vitals, hr_scale, (double)w.temperature_c);
  printWindowLine(w, out, hr_scale, proc_ms);
  if (g_cfg.stream_raw) printRawWindow(w);
  if (g_cfg.upload_raw) uploadRawWindow(w);

  xSemaphoreTake(g_window_lock, portMAX_DELAY);
  g_window_state = 0;
  xSemaphoreGive(g_window_lock);
}

// ----------------------------------------------------------------------------
// Battery, button, console
// ----------------------------------------------------------------------------

static float readPinMv(int pin) {
  uint32_t sum = 0;
  for (int i = 0; i < 8; i++) sum += analogReadMilliVolts(pin);
  return (float)sum / 8.0f;
}

// Deep sleep for 10 minutes, then start again and look at the battery once more.
static void sleepOnEmptyBattery() {
  serialPrint("{\"t\":\"log\",\"msg\":\"battery empty, sleeping\"}\n");
  WiFi.disconnect(true);
  delay(100);
  esp_sleep_enable_timer_wakeup(600ULL * 1000000ULL);
  esp_deep_sleep_start();
}

// Empty = at or below 3.45 V without USB power. Readings under 3.0 V cannot be
// a running system (the regulator needs more), so they are treated as a
// measurement fault, not as an empty battery.
static bool batteryEmpty(float volts, bool usb_present) {
  return !usb_present && volts > 3.0f && volts <= 3.45f;
}

static void batteryService(uint32_t now) {
  if (now - g_last_battery_ms < 1000) return;
  g_last_battery_ms = now;
  g_battery.update(readPinMv(board::kPinBatAdc), readPinMv(board::kPinVbusAdc));
  const SgBattery& b = g_battery.state();
  // Protect the cell (the board has no under-voltage cut-off of its own).
  if (batteryEmpty(b.volts, b.usb_present)) {
    if (g_low_battery_since_ms == 0) g_low_battery_since_ms = now | 1;
    if (now - g_low_battery_since_ms > 60000) sleepOnEmptyBattery();
  } else {
    g_low_battery_since_ms = 0;
  }
}

static void buttonService(uint32_t now) {
  const bool down = digitalRead(board::kPinButton) == LOW;
  if (down && !g_button_down && now - g_button_ms > 300) markEvent("button");
  if (down != g_button_down) g_button_ms = now;
  g_button_down = down;
}

static void printStatus(void*) {
  static const char* const kStates[] = {"no_sensor", "resetting", "settling", "active",
                                        "standby", "standby_probe", "led_test"};
  const SgSamplerStats& s = g_sampler.stats();
  const SgBattery& b = g_battery.state();
  char uid[160], line[512];
  const bool cloud = cloudConfigured(uid, sizeof uid);
  snprintf(line, sizeof line,
           "SuGuard fw %s\n sensor: %s part 0x%02X rev 0x%02X  led red/ir %u/%u (x0.2 mA)  dc red/ir %.0f/%.0f\n"
           " windows %lu (dropped %lu, restarts %lu)  lost samples %lu  i2c errors %lu  sensor resets %lu  fs %.3f Hz\n",
           SG_FW_VERSION, kStates[(int)g_sampler.state()], s.part_id, s.rev_id, g_sampler.led_red(), g_sampler.led_ir(),
           (double)s.last_red_dc, (double)s.last_ir_dc, (unsigned long)s.windows, (unsigned long)g_windows_dropped,
           (unsigned long)s.window_restarts, (unsigned long)s.lost_samples, (unsigned long)s.i2c_errors,
           (unsigned long)s.sensor_resets, (double)s.fs_hz);
  serialPrint(line);
  snprintf(line, sizeof line,
           " battery: %.2f V %d%%%s%s\n wifi: %s  time %s  cloud %s  uploads ok/failed %lu/%lu  queued %d\n"
           " free heap %lu B  pipeline memory %lu B\n",
           (double)b.volts, b.percent, b.usb_present ? " usb" : "", b.charging ? " charging" : "",
           WiFi.status() == WL_CONNECTED ? "connected" : (g_cfg.wifi_ssid[0] ? "not connected" : "not configured"),
           timeValid() ? "ok" : "not set", cloud ? uid : "off (set wifi + user)", (unsigned long)g_upload_ok,
           (unsigned long)g_upload_fail, g_queue_count, (unsigned long)ESP.getFreeHeap(),
           (unsigned long)sg_pipeline_static_bytes());
  serialPrint(line);
}

static void consoleService() {
  static SgCliHooks hooks = {
      nullptr,
      [](void*, const char* s) { serialPrint(s); },
      printStatus,
      [](void*) { saveConfig(); },
      [](void*) { applyConfig(); },
      [](void*) { serialPrint("rebooting\n"); delay(200); ESP.restart(); },
      [](void*, uint8_t mode) { return g_sampler.request_led_test(mode, 5000); },
      [](void*, const char* note) { markEvent(note); },
  };
  while (Serial.available()) {
    const char c = (char)Serial.read();
    if (c == '\n' || c == '\r') {
      if (g_line_len) {
        g_line[g_line_len] = '\0';
        sg_cli_handle(g_line, &g_cfg, &hooks);
        g_line_len = 0;
      }
    } else if (g_line_len + 1 < sizeof g_line) {
      g_line[g_line_len++] = c;
    }
  }
}

// ----------------------------------------------------------------------------
// Arduino entry points
// ----------------------------------------------------------------------------

void setup() {
  Serial.setTxBufferSize(16384);          // a raw window (8 kB JSON) must fit without blocking
  Serial.begin(115200);
  pinMode(board::kPinButton, INPUT_PULLUP);
  loadConfig();

  SgBatteryConfig bat;
  bat.cal = g_cfg.bat_cal;
  g_battery.set_config(bat);
  delay(50);
  g_battery.update(readPinMv(board::kPinBatAdc), readPinMv(board::kPinVbusAdc));
  if (batteryEmpty(g_battery.state().volts, g_battery.state().usb_present)) sleepOnEmptyBattery();

  Wire.begin(board::kPinI2cSda, board::kPinI2cScl, board::kI2cHz);
  Wire.setTimeOut(50);

  sg_pipeline_init();
  g_window_lock = xSemaphoreCreateMutex();
  const SgI2c bus = {nullptr, i2cWrite, i2cRead};
  g_sampler.begin(bus, samplerConfig(), onWindow, nullptr);
  xTaskCreate(samplerTask, "sampler", 4096, nullptr, 3, nullptr);

  g_last_report_ms = millis();
  serialPrint("{\"t\":\"log\",\"msg\":\"SuGuard fw " SG_FW_VERSION " started, type 'help'\"}\n");
}

void loop() {
  const uint32_t now = millis();
  consoleService();
  processPendingWindow();
  batteryService(now);
  buttonService(now);
  wifiService(now);
  reportService(now);
  flushQueue();
  delay(10);
}
