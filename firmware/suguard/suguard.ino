// SuGuard bracelet firmware
// Board: SuGuard PCB (ESP32-C3-WROOM-02 + MH-ET LIVE MAX30102 module, TP4056 charger)
//
// What it does
//   * samples raw red/IR PPG at 50 Hz in gap-free 10.24-s windows
//   * runs the on-device pipeline (integer neural denoiser + signal quality
//     gates) and reports heart rate and SpO2 only for windows that pass
//   * USB serial console (115200): live JSON lines, settings, raw streaming
//   * optional Wi-Fi upload of averaged records to Firebase (users/<uid>/vitals):
//     the radio is switched on for a short session every few minutes
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
#include <sys/time.h>
#include <time.h>

#include "src/app/aggregate.h"
#include "src/app/battery.h"
#include "src/app/cli.h"
#include "src/app/cloud_fmt.h"
#include "src/app/config.h"
#include "src/app/power.h"
#include "src/app/sampler.h"
#include "src/app/store.h"
#include "src/app/uplink.h"
#include "src/board.h"
#include "src/certs.h"
#include "src/core/sg_pipeline.h"

#define SG_FW_VERSION "1.1.0"

// ----------------------------------------------------------------------------
// State
// ----------------------------------------------------------------------------

static SgConfig g_cfg;
static SgConfig g_applied;                // the settings the services are running with
static Preferences g_prefs;
static SgSampler g_sampler;
static SgBatteryMonitor g_battery;
static SgPowerGuard g_power;
static SgAggregator g_agg;
static SgStore g_store;
static SgUplink g_uplink;

// Window hand-over from the sampler task to loop(): 0 = empty, 1 = ready, 2 = being processed.
static SgWindow g_window;
static volatile uint8_t g_window_state = 0;
static volatile uint32_t g_windows_dropped = 0;
static SemaphoreHandle_t g_window_lock;

// BOOT button, sampled by the sampler task so that a press during a long loop() pass is not lost.
static volatile uint32_t g_button_presses = 0;
static volatile uint32_t g_button_press_ms = 0;
static uint32_t g_button_seen = 0;

static uint64_t g_uptime_ms = 0;          // milliseconds since boot, without the 49-day wrap of millis()
static uint32_t g_uptime_last = 0;
static bool g_clock_known = false;        // the wall clock has been set at least once
static uint32_t g_last_report_ms = 0;
static uint32_t g_last_battery_ms = 0;
static bool g_sampler_dirty = false;      // sensor settings changed, not yet accepted by the sampler
static bool g_stopping = false;           // going to sleep: no new work
static int g_no_pulse_windows = 0;
static int g_odd_ratio_windows = 0;
static bool g_hinted = false;
static uint32_t g_hint_ms = 0;

static char g_line[200];
static size_t g_line_len = 0;

#define SG_RECORD_MAX 448
#define SG_NO_PULSE_WINDOWS 6             // a minute without any pulsation: nothing alive is in front of the sensor
#define SG_ODD_RATIO_WINDOWS 6

// ----------------------------------------------------------------------------
// Small helpers
// ----------------------------------------------------------------------------

// Never stall the firmware on the USB port. With a PC attached a line is
// written only if the buffer has room for all of it (the core's write() would
// otherwise wait for the PC); without one the core does not wait at all and
// keeps the newest data, so that a PC plugged in later sees current lines.
static bool serialWrite(const char* s, size_t n) {
  if (Serial && (size_t)Serial.availableForWrite() < n) return false;
  Serial.write((const uint8_t*)s, n);
  return true;
}

static void serialPrint(const char* s) { serialWrite(s, strlen(s)); }

// A long line (a raw window is 7 kB) through a small buffer: wait for the PC
// to take it, but only briefly; a PC that does not read gets a cut line.
static void serialWriteLong(const char* s, size_t n) {
  if (!Serial) return;
  const uint32_t t0 = millis();
  while (n > 0 && millis() - t0 < 250) {
    size_t room = (size_t)Serial.availableForWrite();
    if (room == 0) {
      delay(1);
      continue;
    }
    if (room > n) room = n;
    Serial.write((const uint8_t*)s, room);
    s += room;
    n -= room;
  }
  if (n > 0) serialWrite("\n", 1);        // resynchronise: the cut line is not valid JSON and is ignored
}

static void logLine(const char* msg) {
  char line[200];
  const int n = snprintf(line, sizeof line, "{\"t\":\"log\",\"msg\":\"%s\"}\n", msg);
  if (n > 0 && n < (int)sizeof line) serialWrite(line, (size_t)n);
}

static uint64_t uptimeMs() {              // loop() context only
  const uint32_t now = millis();
  g_uptime_ms += (uint32_t)(now - g_uptime_last);
  g_uptime_last = now;
  return g_uptime_ms;
}

static bool timeValid() { return time(nullptr) > 1700000000; }

static int64_t unixMs() {
  struct timeval tv;
  gettimeofday(&tv, nullptr);
  return (int64_t)tv.tv_sec * 1000 + (int64_t)(tv.tv_usec / 1000);
}

static bool cloudConfigured(char* uid, size_t uid_len) {
  return g_cfg.cloud && g_cfg.wifi_ssid[0] && sg_email_to_uid(g_cfg.user_email, uid, uid_len);
}

static SgSamplerConfig samplerConfig() {
  SgSamplerConfig c;
  // 400 / 200 / 100 / 50 conversions per second, averaged down to 50 Hz output.
  const uint8_t code = g_cfg.sensor_sps >= 400 ? 3 : g_cfg.sensor_sps >= 200 ? 2 : g_cfg.sensor_sps >= 100 ? 1 : 0;
  c.sensor.avg_code = code;
  c.sensor.rate_code = code;
  c.sensor.pw_code = 3;                   // 411 us, 18 bit
  c.sensor.range_code = g_cfg.adc_range;
  c.swap_red_ir = g_cfg.swap_red_ir != 0;
  c.led_init = g_cfg.led_init;
  c.led_max = g_cfg.led_max < g_cfg.led_init ? g_cfg.led_init : g_cfg.led_max;
  c.dc_min = g_cfg.ir_dc_min;
  return c;
}

static SgUplinkConfig uplinkConfig() {
  SgUplinkConfig c;
  c.interval_ms = (uint32_t)g_cfg.upload_interval_s * 1000u;
  c.keep_connected = g_cfg.upload_raw != 0 || g_cfg.upload_interval_s == 0;
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
      g_windows_dropped = g_windows_dropped + 1;                 // loop() is still busy with the previous one
    }
    xSemaphoreGive(g_window_lock);
  } else {
    g_windows_dropped = g_windows_dropped + 1;
  }
}

void samplerStep() {                                             // not static: the host simulation calls it
  const uint32_t now = millis();
  g_sampler.poll(now);
  // A press = the pin is low after having been high for at least 150 ms (contact bounce is shorter).
  static uint8_t released_polls = 3;
  if (digitalRead(board::kPinButton) == LOW) {
    if (released_polls >= 3) {
      g_button_press_ms = now;
      g_button_presses = g_button_presses + 1;
    }
    released_polls = 0;
  } else if (released_polls < 3) {
    released_polls++;
  }
}

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

// Called after every change on the console: restart only what the change affects.
static void applyConfig() {
  const SgConfig& a = g_applied;
  const SgConfig& b = g_cfg;
  if (a.sensor_sps != b.sensor_sps || a.adc_range != b.adc_range || a.swap_red_ir != b.swap_red_ir ||
      a.led_init != b.led_init || a.led_max != b.led_max || a.ir_dc_min != b.ir_dc_min) {
    g_sampler_dirty = true;
  }
  if (a.bat_cal != b.bat_cal) {
    SgBatteryConfig bat;
    bat.cal = b.bat_cal;
    g_battery.set_config(bat);
  }
  const bool link_changed = strcmp(a.wifi_ssid, b.wifi_ssid) || strcmp(a.wifi_pass, b.wifi_pass) ||
                            strcmp(a.user_email, b.user_email) || strcmp(a.db_url, b.db_url) ||
                            strcmp(a.db_auth, b.db_auth) || a.cloud != b.cloud || a.tls_insecure != b.tls_insecure;
  if (link_changed || a.upload_raw != b.upload_raw || a.upload_interval_s != b.upload_interval_s) {
    g_uplink.configure(uplinkConfig());
    g_uplink.retry_now();
  }
  if (link_changed && g_uplink.radio_on()) g_uplink.restart();    // reconnect with the new settings
  g_applied = g_cfg;
}

// The sampler takes one request at a time: keep asking until it has taken this one.
static void samplerConfigService() {
  if (g_sampler_dirty && g_sampler.request_config(samplerConfig())) g_sampler_dirty = false;
}

// ----------------------------------------------------------------------------
// Cloud
// ----------------------------------------------------------------------------

// Returns the HTTP status, or a value <= 0 if the request did not get through.
static int httpPut(const char* url, const char* body, size_t len) {
  WiFiClientSecure client;
  if (g_cfg.tls_insecure) client.setInsecure();
  else client.setCACert(SG_ROOT_CAS);
  client.setHandshakeTimeout(8);                                 // seconds (the default is two minutes)
  HTTPClient http;
  http.setConnectTimeout(6000);
  http.setTimeout(6000);
  if (!http.begin(client, url)) return -1;
  http.addHeader("Content-Type", "application/json");
  const int code = http.PUT((uint8_t*)body, len);
  http.end();
  return code;
}

static void recordFromStored(const SgStoredRecord& s, SgVitalsRecord* r) {
  memset(r, 0, sizeof(*r));
  r->unix_s = (s.flags & SG_SF_UNIX_TIME) ? s.t_ms / 1000 : 0;
  r->tz_offset_min = g_cfg.tz_offset_min;
  r->pulse_bpm = s.pulse_bpm;
  r->has_spo2 = (s.flags & SG_SF_HAS_SPO2) != 0;
  r->spo2 = s.spo2;
  r->sqi = s.sqi;
  r->windows = s.windows;
  r->reliable_windows = s.reliable_windows;
  r->spo2_windows = s.spo2_windows;
  r->battery_percent = s.battery_percent;
  r->charging = (s.flags & SG_SF_CHARGING) != 0;
  r->has_temperature = (s.flags & SG_SF_HAS_TEMPERATURE) != 0;
  r->temperature_c = s.temperature_c;
  r->device_id = g_cfg.device_id;
  r->firmware = SG_FW_VERSION;
  r->model = (s.flags & SG_SF_NEURAL) ? "edge-nn" : "classical";
}

// Uploads the oldest stored item; the uplink decides what its result means.
static void sendOldest(const char* uid) {
  char url[400], key[24], json[SG_RECORD_MAX];
  const char* node;
  int n;
  if (g_store.next() == SgStoredKind::kMarker) {
    const SgStoredMarker& m = g_store.marker();
    sg_record_key(m.t_ms, key, sizeof key);
    n = sg_event_json(json, sizeof json, m.t_ms / 1000, g_cfg.tz_offset_min, "mark", m.note);
    node = "events";
  } else {
    SgVitalsRecord rec;
    recordFromStored(g_store.record(), &rec);
    sg_record_key(g_store.record().t_ms, key, sizeof key);
    n = sg_vitals_json(json, sizeof json, &rec, key);
    node = "vitals";
  }
  // 400 = "cannot be sent": the item is dropped instead of blocking the queue forever.
  const int code = n < 0 || sg_db_url(url, sizeof url, g_cfg.db_url, "users", uid, node, key, g_cfg.db_auth) < 0
                       ? 400
                       : httpPut(url, json, (size_t)n);
  if (g_uplink.sent(uptimeMs(), code)) g_store.pop();
}

static void uplinkService() {
  char uid[160];
  const bool enabled = !g_stopping && cloudConfigured(uid, sizeof uid);
  const SgUplinkAction action =
      g_uplink.step(uptimeMs(), enabled, g_store.pending(), WiFi.status() == WL_CONNECTED, timeValid());
  switch (action) {
    case SgUplinkAction::kRadioOn:
      WiFi.mode(WIFI_STA);
      WiFi.begin(g_cfg.wifi_ssid, g_cfg.wifi_pass);
      break;
    case SgUplinkAction::kStartClock:
      configTime(0, 0, "pool.ntp.org", "time.google.com");       // UTC; the offset is applied when formatting
      break;
    case SgUplinkAction::kSend:
      sendOldest(uid);
      break;
    case SgUplinkAction::kRadioOff:
      WiFi.disconnect(true);
      WiFi.mode(WIFI_OFF);
      break;
    case SgUplinkAction::kNone:
      break;
  }
}

// The first time the wall clock is known: date everything that was stored with the time since boot.
static void clockService() {
  if (g_clock_known || !timeValid()) return;
  g_clock_known = true;
  g_store.set_boot_time(unixMs() - (int64_t)uptimeMs());
}

// ----------------------------------------------------------------------------
// Reporting
// ----------------------------------------------------------------------------

// Stores a marker that happened `age_ms` ago. Returns 0 = not stored, 1 = USB only, 2 = queued for upload.
static int markEvent(const char* note, uint32_t age_ms) {
  char json[320], line[360], uid[160];
  const int64_t t_ms = (g_clock_known ? unixMs() : (int64_t)uptimeMs()) - (int64_t)age_ms;
  const int n = sg_event_json(json, sizeof json, g_clock_known ? t_ms / 1000 : 0, g_cfg.tz_offset_min, "mark", note);
  if (n < 0) return 0;
  const int m = sg_console_line(line, sizeof line, "event", "e", json);
  if (m > 0) serialWrite(line, (size_t)m);
  if (!cloudConfigured(uid, sizeof uid)) return 1;
  g_store.add_marker(t_ms, g_clock_known, note);
  return 2;
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

// The raw window as text, in the pipeline's scratch memory (free between two windows).
// Its time comes from the window itself, not from the moment loop() got round to it.
static void outputRawWindow(const SgWindow& w) {
  size_t cap = 0;
  char* buf = sg_pipeline_scratch(&cap);
  const uint32_t age_ms = millis() - w.end_ms;
  const int64_t end_unix_ms = g_clock_known ? unixMs() - (int64_t)age_ms : -1;
  static const char kHead[] = "{\"t\":\"raw\",\"w\":";
  const size_t head = sizeof kHead - 1;
  memcpy(buf, kHead, head);
  const int n = sg_raw_window_json(buf + head, cap - head - 3, &w, end_unix_ms, age_ms, g_cfg.device_id);
  if (n < 0) return;
  if (g_cfg.stream_raw) {
    memcpy(buf + head + n, "}\n", 3);
    serialWriteLong(buf, head + (size_t)n + 2);
  }
  char uid[160], url[400], key[24];
  if (g_cfg.upload_raw && g_clock_known && g_uplink.online() && cloudConfigured(uid, sizeof uid)) {
    sg_record_key(end_unix_ms, key, sizeof key);
    if (sg_db_url(url, sizeof url, g_cfg.db_url, "rawPpg", uid, nullptr, key, g_cfg.db_auth) >= 0) {
      // Best effort: raw windows are not stored; a failure makes the uplink pause like any other.
      g_uplink.extra_result(uptimeMs(), httpPut(url, buf + head, (size_t)n));
    }
  }
}

// Every report interval: one record from the reliable windows, if there is any.
static void reportService(uint32_t now) {
  if (now - g_last_report_ms < (uint32_t)g_cfg.report_interval_s * 1000u) return;
  g_last_report_ms = now;
  double pulse, spo2, sqi, temperature;
  bool has_spo2, has_temperature;
  int spo2_windows;
  const bool any = g_agg.summary(&pulse, &has_spo2, &spo2, &sqi, &spo2_windows, &has_temperature, &temperature);
  SgStoredRecord rec;
  memset(&rec, 0, sizeof rec);
  rec.windows = (uint16_t)g_agg.windows();
  rec.reliable_windows = (uint16_t)g_agg.reliable();
  g_agg.reset();
  if (!any) return;                                              // nothing trustworthy: report nothing
  rec.t_ms = g_clock_known ? unixMs() : (int64_t)uptimeMs();
  rec.pulse_bpm = (float)pulse;
  rec.spo2 = (float)spo2;
  rec.sqi = (float)sqi;
  rec.temperature_c = (float)temperature;
  rec.spo2_windows = (uint16_t)spo2_windows;
  rec.battery_percent = (int8_t)g_battery.state().percent;
  rec.flags = (uint8_t)((g_clock_known ? SG_SF_UNIX_TIME : 0) | (g_battery.state().charging ? SG_SF_CHARGING : 0) |
                        (g_cfg.use_nn ? SG_SF_NEURAL : 0) | (has_spo2 ? SG_SF_HAS_SPO2 : 0) |
                        (has_temperature ? SG_SF_HAS_TEMPERATURE : 0));

  SgVitalsRecord shown;
  recordFromStored(rec, &shown);
  char key[24], json[SG_RECORD_MAX], line[SG_RECORD_MAX + 32], uid[160];
  sg_record_key(g_clock_known ? rec.t_ms : 0, key, sizeof key);
  const int n = sg_vitals_json(json, sizeof json, &shown, key);
  if (n > 0) {
    const int m = sg_console_line(line, sizeof line, "record", "r", json);
    if (m > 0) serialWrite(line, (size_t)m);
  }
  if (cloudConfigured(uid, sizeof uid)) g_store.add_record(rec);
}

// What the windows say about the set-up, beyond the vital signs.
static void watchWindows(const SgPipelineOutput& out, uint32_t now) {
  // Light comes back but nothing pulsates: the bracelet lies on a table or in a bag.
  if (out.sensor.finger_detected && out.vitals.pi_in < SG_MIN_INPUT_PI) g_no_pulse_windows++;
  else g_no_pulse_windows = 0;
  if (g_no_pulse_windows >= SG_NO_PULSE_WINDOWS) {
    g_no_pulse_windows = 0;
    g_sampler.request_rest();
    logLine("no pulse for a minute: sensor resting until the bracelet is moved");
  }
  // A clear pulse that is much stronger in the "red" channel than in the "IR" one, window after
  // window: blood does the opposite (down to SpO2 ~70 %), so the two LEDs are probably exchanged,
  // as on some clone sensor modules.
  if (out.sensor.finger_detected && out.vitals.pi_in >= 0.1 && out.pi_red > 1.3 * out.vitals.pi_in) g_odd_ratio_windows++;
  else g_odd_ratio_windows = 0;
  if (g_odd_ratio_windows >= SG_ODD_RATIO_WINDOWS && (!g_hinted || now - g_hint_ms > 300000)) {
    g_hinted = true;
    g_hint_ms = now;
    logLine("the pulse is stronger in the red channel than in the IR one: if 'led red' is not "
            "visibly red, type 'set swap_red_ir 1' and 'save'");
  }
}

static void processPendingWindow() {
  if (g_window_state != 1) return;
  xSemaphoreTake(g_window_lock, portMAX_DELAY);
  g_window_state = 2;
  xSemaphoreGive(g_window_lock);

  const SgWindow& w = g_window;
  static SgPipelineOutput out;
  const uint32_t t0 = millis();
  sg_process_window(w.red, w.ir, g_cfg.use_nn != 0, (double)g_cfg.ir_dc_min, &out);
  const uint32_t proc_ms = millis() - t0;
  if (w.flags & SG_WF_AMBIENT_OVERFLOW) {                        // sunlight overwhelmed the sensor
    out.vitals.reliable = false;
    out.vitals.has_spo2 = false;
    out.vitals.reasons |= SG_R_ADC_SATURATED;
  }
  const double hr_scale = w.fs_hz > 0 ? (double)w.fs_hz / SG_FS : 1.0;   // sensor clock tolerance
  g_agg.add(out.vitals, hr_scale, (double)w.temperature_c);
  printWindowLine(w, out, hr_scale, proc_ms);
  watchWindows(out, millis());
  if (g_cfg.stream_raw || g_cfg.upload_raw) outputRawWindow(w);

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

// Deep sleep; the caller has shut the sensor down. Wakes every 10 minutes to
// look at the battery again (a wake-up costs far less than the board's own
// sleep current). USB power cannot wake the chip on this board: the VBUS
// divider gives 2.5 V at best, and the pull-down the core adds to a wake-up
// pin halves that. After plugging in the charger the bracelet therefore
// starts within 10 minutes, or at once with the reset button (S1).
static void deepSleep() {
  esp_sleep_enable_timer_wakeup(600ULL * 1000000ULL);
  esp_deep_sleep_start();
}

static void sleepOnEmptyBattery() {
  logLine("battery empty, sleeping");
  g_stopping = true;
  g_sampler.request_power_down();                                // LEDs off, sensor in shutdown (it stays powered)
  for (int i = 0; i < 30 && !g_sampler.powered_down(); i++) delay(10);
  WiFi.disconnect(true);
  WiFi.mode(WIFI_OFF);
  delay(50);
  deepSleep();
}

static void batteryService(uint32_t now) {
  if (now - g_last_battery_ms < 1000) return;
  g_last_battery_ms = now;
  g_battery.update(readPinMv(board::kPinBatAdc), readPinMv(board::kPinVbusAdc));
  const SgBattery& b = g_battery.state();
  // Protect the cell (the board has no under-voltage cut-off of its own).
  if (g_power.update(now, b.volts, b.usb_present) == SgPowerAction::kSleep) sleepOnEmptyBattery();
}

static void buttonService() {
  const uint32_t presses = g_button_presses;
  if (presses == g_button_seen) return;
  g_button_seen = presses;                                       // several presses in one pass count as one
  markEvent("button", millis() - g_button_press_ms);
}

static void printStatus(void*) {
  static const char* const kStates[] = {"no_sensor", "resetting", "settling", "active",
                                        "standby", "standby_probe", "led_test", "off"};
  static const char* const kLink[] = {"idle", "connecting", "waiting for the clock", "online"};
  const SgSamplerStats& s = g_sampler.stats();
  const SgBattery& b = g_battery.state();
  const SgUplinkStats& u = g_uplink.stats();
  char uid[160], line[700];
  const bool cloud = cloudConfigured(uid, sizeof uid);
  snprintf(line, sizeof line,
           "SuGuard fw %s  up %lu s\n sensor: %s%s part 0x%02X rev 0x%02X  led red/ir %u/%u (x0.2 mA)  dc red/ir %.0f/%.0f\n"
           " windows %lu (dropped %lu, restarts %lu)  lost samples %lu  i2c errors %lu  sensor resets %lu\n"
           " no-data timeouts %lu  fs %.3f Hz\n",
           SG_FW_VERSION, (unsigned long)(uptimeMs() / 1000), kStates[(int)g_sampler.state()],
           g_sampler.resting() ? " (resting: no pulse)" : "", s.part_id, s.rev_id, g_sampler.led_red(),
           g_sampler.led_ir(), (double)s.last_red_dc, (double)s.last_ir_dc, (unsigned long)s.windows,
           (unsigned long)g_windows_dropped, (unsigned long)s.window_restarts, (unsigned long)s.lost_samples,
           (unsigned long)s.i2c_errors, (unsigned long)s.sensor_resets, (unsigned long)s.no_data_timeouts,
           (double)s.fs_hz);
  serialPrint(line);
  snprintf(line, sizeof line,
           " battery: %.2f V %d%%%s%s\n wifi: %s (%s, next try in %lu s)  time %s  cloud %s\n"
           " uploads: delivered %lu  rejected %lu  failed sessions %lu  last http %d  waiting %d records + %d markers"
           " (dropped %lu)\n",
           (double)b.volts, b.percent, b.usb_present ? " usb" : "", b.charging ? " charging" : "",
           !g_cfg.wifi_ssid[0] ? "not configured" : WiFi.status() == WL_CONNECTED ? "connected" : "off",
           kLink[(int)g_uplink.state()], (unsigned long)(g_uplink.wait_ms(uptimeMs()) / 1000),
           timeValid() ? "ok" : "not set", cloud ? uid : "off (set wifi + user)", (unsigned long)u.delivered,
           (unsigned long)u.rejected, (unsigned long)u.failures, u.last_code, g_store.records(), g_store.markers(),
           (unsigned long)g_store.dropped());
  serialPrint(line);
  snprintf(line, sizeof line, " heap: free %lu B, lowest %lu B, largest block %lu B  pipeline memory %lu B\n",
           (unsigned long)ESP.getFreeHeap(), (unsigned long)ESP.getMinFreeHeap(),
           (unsigned long)ESP.getMaxAllocHeap(), (unsigned long)sg_pipeline_static_bytes());
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
      [](void*, const char* note) { return markEvent(note, 0); },
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
  loadConfig();
  g_applied = g_cfg;
  if (g_cfg.cpu_mhz == 80) setCpuFrequencyMhz(80);
  // A raw window (7 kB of text) fits the large buffer in one piece; otherwise it is sent in parts.
  Serial.setTxBufferSize(g_cfg.stream_raw ? 16384 : 4096);
  Serial.begin(115200);
  pinMode(board::kPinButton, INPUT_PULLUP);
  Wire.begin(board::kPinI2cSda, board::kPinI2cScl, board::kI2cHz);
  Wire.setTimeOut(50);
  const SgI2c bus = {nullptr, i2cWrite, i2cRead};

  SgBatteryConfig bat;
  bat.cal = g_cfg.bat_cal;
  g_battery.set_config(bat);
  delay(50);
  g_battery.update(readPinMv(board::kPinBatAdc), readPinMv(board::kPinVbusAdc));
  // Any wake-up from deep sleep is a wake-up from the empty-battery sleep: nothing else sleeps.
  const bool after_sleep = esp_sleep_get_wakeup_cause() != ESP_SLEEP_WAKEUP_UNDEFINED;
  const SgPowerAction boot =
      sg_power_at_boot(g_battery.state().volts, g_battery.state().usb_present, after_sleep, SgPowerLimits());
  if (boot != SgPowerAction::kRun) {
    max30102::Device sensor;                                     // make sure the sensor draws nothing
    sensor.attach(bus);
    sensor.set_led(0, 0);
    sensor.set_shutdown(true);
    deepSleep();
  }

  sg_pipeline_init();
  g_uplink.configure(uplinkConfig());
  g_window_lock = xSemaphoreCreateMutex();
  g_sampler.begin(bus, samplerConfig(), onWindow, nullptr);
  xTaskCreate(samplerTask, "sampler", 4096, nullptr, 3, nullptr);

  g_uptime_last = g_last_report_ms = millis();
  logLine("SuGuard fw " SG_FW_VERSION " started, type 'help'");
}

void loop() {
  const uint32_t now = millis();
  consoleService();
  clockService();
  processPendingWindow();
  batteryService(now);
  buttonService();
  samplerConfigService();
  reportService(now);
  uplinkService();
  delay(10);
}
