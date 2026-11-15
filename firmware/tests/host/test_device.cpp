// Host tests of the device layer (sampler, driver, battery, config, console,
// cloud formatting) against the simulated MAX30102. Run by test_device_layer.py.
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>

#include "../../suguard/src/app/aggregate.h"
#include "../../suguard/src/app/battery.h"
#include "../../suguard/src/app/cli.h"
#include "../../suguard/src/app/cloud_fmt.h"
#include "../../suguard/src/app/config.h"
#include "../../suguard/src/app/power.h"
#include "../../suguard/src/app/sampler.h"
#include "../../suguard/src/app/store.h"
#include "../../suguard/src/app/uplink.h"
#include "sim_max30102.h"

#define CHECK(cond)                                                                 \
  do {                                                                              \
    if (!(cond)) {                                                                  \
      printf("FAIL %s:%d: %s\n", __FILE__, __LINE__, #cond);                        \
      exit(1);                                                                      \
    }                                                                               \
  } while (0)
#define CHECK_NEAR(a, b, tol) CHECK(std::fabs((double)(a) - (double)(b)) <= (tol))

namespace {

struct Rig {
  SimMax30102 sim;
  SgSampler sampler;
  std::vector<SgWindow> windows;
  uint32_t now = 1000;
  double dc_per_step = 2000.0;     // counts per LED current step (0x3F -> 126 000)
  bool worn = true;
  long spike_every = 0;            // every Nth sample is at full scale

  static void on_window(void* ctx, const SgWindow* w) { ((Rig*)ctx)->windows.push_back(*w); }

  // Slot 1 (red on a genuine part): LED-proportional DC + sample counter in the low digits,
  // so that contiguity and channel mapping can be checked exactly. Slot 2: different DC ratio.
  void install_source() {
    sim.source = [this](uint64_t n, uint8_t led1, uint8_t led2, uint32_t* s1, uint32_t* s2) {
      const double k = worn ? dc_per_step : 30.0;
      double a = k * 0.7 * led1, b = k * led2;
      if (a > 262143) a = 262143;
      if (b > 262143) b = 262143;
      *s1 = (uint32_t)a / 1000 * 1000 + (uint32_t)(n % 1000);
      *s2 = (uint32_t)b / 1000 * 1000 + (uint32_t)((n + 500) % 1000);
      if (*s1 > 262143 || (spike_every && n % spike_every == 0)) *s1 = 262143;
      if (*s2 > 262143 || (spike_every && n % spike_every == 0)) *s2 = 262143;
    };
  }

  void begin(const SgSamplerConfig& cfg = SgSamplerConfig()) {
    install_source();
    sampler.begin(sim.bus(), cfg, on_window, this);
  }

  // Advance simulated time, polling every `step` ms.
  void run(double ms, double step = 50) {
    for (double t = 0; t < ms; t += step) {
      sim.advance(step);
      now += (uint32_t)step;
      sampler.poll(now);
    }
  }
};

// Samples inside a window must be consecutive sensor samples.
void check_contiguous(const SgWindow& w, bool swapped) {
  const uint32_t* a = swapped ? w.ir : w.red;      // slot 1 carries n % 1000
  for (int i = 1; i < SG_WINDOW; i++) CHECK((a[i] % 1000) == (a[i - 1] % 1000 + 1) % 1000);
  const uint32_t* b = swapped ? w.red : w.ir;      // slot 2 carries (n + 500) % 1000
  CHECK((b[0] % 1000) == (a[0] % 1000 + 500) % 1000);
}

void test_bringup_and_windows() {
  Rig r;
  r.begin();
  r.run(200);
  CHECK(r.sampler.stats().part_id == max30102::kPartId);
  CHECK(r.sim.reg[max30102::kModeConfig] == max30102::kModeSpo2);
  CHECK(r.sim.reg[max30102::kFifoConfig] == (3 << 5));                 // 8x averaging, roll-over off
  CHECK(r.sim.reg[max30102::kSpo2Config] == ((1 << 5) | (3 << 2) | 3)); // 4096 nA, 400 sps, 411 us
  CHECK(r.sim.reg[max30102::kIntEnable1] == max30102::kStatusAlcOvf);   // only the ambient-overflow flag
  r.run(35000);
  CHECK(r.windows.size() == 3);                                         // 0.5 s settle + 3 x 10.24 s
  for (size_t i = 0; i < r.windows.size(); i++) {
    check_contiguous(r.windows[i], false);
    CHECK(r.windows[i].seq == i + 1);
    CHECK(r.windows[i].flags == 0);
    CHECK(r.windows[i].led_red == 0x3F && r.windows[i].led_ir == 0x3F);
    CHECK_NEAR(r.windows[i].temperature_c, 31.5, 0.07);
  }
  // Consecutive windows are gap-free too (no LED change in between).
  CHECK((r.windows[1].red[0] % 1000) == (r.windows[0].red[SG_WINDOW - 1] % 1000 + 1) % 1000);
  CHECK(r.windows[0].red[0] / 1000 == 88 && r.windows[0].ir[0] / 1000 == 126);   // DC: 0.7*2000*63, 2000*63
  CHECK(r.sampler.stats().lost_samples == 0 && r.sampler.stats().i2c_errors == 0);
  printf("PASS bringup_and_windows\n");
}

void test_swapped_leds() {
  Rig r;
  SgSamplerConfig cfg;
  cfg.swap_red_ir = true;
  r.begin(cfg);
  r.run(12000);
  CHECK(r.windows.size() == 1);
  check_contiguous(r.windows[0], true);
  CHECK(r.windows[0].ir[0] / 1000 == 88 && r.windows[0].red[0] / 1000 == 126);   // channels exchanged
  printf("PASS swapped_leds\n");
}

void test_fifo_overflow_restarts_window() {
  Rig r;
  r.begin();
  r.run(5000);
  r.sim.advance(1500);            // nobody polls for 1.5 s: 75 samples, FIFO holds 32
  r.now += 1500;
  r.run(25000);
  CHECK(r.sampler.stats().lost_samples > 0);
  CHECK(r.sampler.stats().window_restarts == 1);
  CHECK(!r.windows.empty());
  for (const auto& w : r.windows) check_contiguous(w, false);
  printf("PASS fifo_overflow_restarts_window (lost %u)\n", (unsigned)r.sampler.stats().lost_samples);
}

void test_agc_reduces_and_raises() {
  {
    Rig r;
    r.dc_per_step = 6000.0;        // 0x3F -> 378 000: both channels clip
    r.begin();
    r.run(60000);
    CHECK(r.sampler.led_ir() < 0x3F);
    const float dc = r.sampler.stats().last_ir_dc;
    CHECK(dc > 0.15f * 262143 && dc < 0.70f * 262143);
    const SgWindow& last = r.windows.back();
    uint32_t peak = 0;
    for (int i = 0; i < SG_WINDOW; i++) peak = last.ir[i] > peak ? last.ir[i] : peak;
    CHECK(peak < 0.95 * 262143);
    printf("PASS agc_reduces (led_ir %u, dc %.0f)\n", r.sampler.led_ir(), dc);
  }
  {
    Rig r;
    r.dc_per_step = 420.0;         // 0x3F -> 26 460 (worn but dim): raise the current
    r.begin();
    r.run(60000);
    CHECK(r.sampler.led_ir() > 0x3F && r.sampler.led_ir() <= 0x7F);
    CHECK(r.sampler.stats().last_ir_dc > 0.15f * 262143);
    printf("PASS agc_raises (led_ir %u, dc %.0f)\n", r.sampler.led_ir(), r.sampler.stats().last_ir_dc);
  }
}

void test_not_worn_standby_and_wake() {
  Rig r;
  r.begin();
  r.run(12000);
  CHECK(r.sampler.worn());
  r.worn = false;                  // bracelet taken off
  r.run(40000);
  CHECK(!r.sampler.worn());
  CHECK(r.sampler.state() == SgSamplerState::kStandbySleep || r.sampler.state() == SgSamplerState::kStandbyProbe);
  // In standby the LEDs are off except during the short probes: duty well below 20 %.
  int shut = 0, total = 0;
  for (int i = 0; i < 400; i++) {
    r.run(50);
    total++;
    shut += (r.sim.reg[max30102::kModeConfig] & max30102::kModeShutdown) ? 1 : 0;
  }
  CHECK(shut > total * 8 / 10);
  const size_t before = r.windows.size();
  r.worn = true;                   // put on again
  r.run(20000);
  CHECK(r.sampler.worn());
  CHECK(r.windows.size() > before);
  check_contiguous(r.windows.back(), false);
  printf("PASS not_worn_standby_and_wake\n");
}

void test_sensor_brownout_recovers() {
  Rig r;
  r.begin();
  r.run(5000);
  r.sim.power_on_reset();          // MAX30102 lost power for a moment: registers back to defaults
  r.run(30000);
  CHECK(r.sampler.stats().sensor_resets == 1);
  CHECK(r.sim.reg[max30102::kModeConfig] == max30102::kModeSpo2);
  CHECK(!r.windows.empty());
  check_contiguous(r.windows.back(), false);
  printf("PASS sensor_brownout_recovers\n");
}

void test_absent_then_present_and_bus_errors() {
  Rig r;
  r.sim.present = false;
  r.begin();
  r.run(7000);
  CHECK(r.sampler.state() == SgSamplerState::kNoSensor);
  CHECK(r.sampler.stats().i2c_errors >= 2);
  r.sim.present = true;
  r.run(15000);
  CHECK(r.sampler.state() == SgSamplerState::kActive);
  CHECK(r.windows.size() == 1);
  r.sim.fail_transactions = 3;     // a short glitch must not end the measurement...
  r.run(1000);
  CHECK(r.sampler.state() == SgSamplerState::kActive);
  r.sim.present = false;           // ...a dead bus must
  r.run(3000);
  CHECK(r.sampler.state() == SgSamplerState::kNoSensor);
  r.sim.present = true;
  r.run(15000);
  CHECK(r.sampler.state() == SgSamplerState::kActive);
  printf("PASS absent_then_present_and_bus_errors\n");
}

void test_sample_rate_estimate() {
  Rig r;
  r.sim.output_rate_scale = 1.02;  // oscillator 2 % fast
  r.begin();
  r.run(45000, 40);
  CHECK(r.sampler.stats().fs_hz > 0);
  CHECK_NEAR(r.sampler.stats().fs_hz, 51.0, 0.1);
  CHECK(r.windows.front().fs_hz == 0.0f);          // not known yet for the first window
  CHECK_NEAR(r.windows.back().fs_hz, 51.0, 0.1);
  printf("PASS sample_rate_estimate (%.3f Hz)\n", r.sampler.stats().fs_hz);
}

void test_led_test_request() {
  Rig r;
  r.begin();
  r.run(3000);
  CHECK(r.sampler.request_led_test(1, 5000));      // red only
  r.run(200);
  CHECK(r.sim.reg[max30102::kLed1Pa] == 0x3F && r.sim.reg[max30102::kLed2Pa] == 0);
  r.run(6000);
  CHECK(r.sim.reg[max30102::kLed1Pa] == 0x3F && r.sim.reg[max30102::kLed2Pa] == 0x3F);
  r.run(12000);
  CHECK(r.sampler.state() == SgSamplerState::kActive && !r.windows.empty());
  printf("PASS led_test_request\n");
}

void test_ambient_overflow_flag() {
  Rig r;
  r.begin();
  r.run(3000);
  r.sim.reg[max30102::kIntStatus1] |= max30102::kStatusAlcOvf;
  r.run(9000);
  CHECK(r.windows.size() == 1 && (r.windows[0].flags & SG_WF_AMBIENT_OVERFLOW));
  r.run(10300);
  CHECK(r.windows.size() == 2 && r.windows[1].flags == 0);
  printf("PASS ambient_overflow_flag\n");
}

void test_battery() {
  CHECK(sg_battery_percent(4.25f) == 100);
  CHECK(sg_battery_percent(3.84f) == 50);
  CHECK(sg_battery_percent(3.45f) == 0 && sg_battery_percent(3.0f) == 0);
  int prev = 0;
  for (float v = 3.3f; v <= 4.3f; v += 0.01f) {    // monotonic
    const int p = sg_battery_percent(v);
    CHECK(p >= prev);
    prev = p;
  }
  SgBatteryMonitor m;
  for (int i = 0; i < 100; i++) m.update(3.9f * 1000.0f * 47.0f / 147.0f, 0.0f);
  CHECK_NEAR(m.state().volts, 3.9, 0.01);
  CHECK(!m.state().usb_present && !m.state().charging);
  const int resting = m.state().percent;
  // On USB power the charger is active; the higher charging voltage must not jump the percentage.
  for (int i = 0; i < 100; i++) m.update(3.98f * 1000.0f * 47.0f / 147.0f, 2500.0f);
  CHECK(m.state().usb_present && m.state().charging && m.state().percent == resting);
  for (int i = 0; i < 100; i++) m.update(4.2f * 1000.0f * 47.0f / 147.0f, 2500.0f);
  CHECK(m.state().usb_present && m.state().charging);          // the firmware cannot see "charge finished"
  CHECK(m.state().percent > resting && m.state().percent < 100);
  for (int i = 0; i < 100; i++) m.update(4.18f * 1000.0f * 47.0f / 147.0f, 0.0f);
  CHECK(!m.state().charging && m.state().percent >= 95);
  printf("PASS battery\n");
}

std::string g_out;
void cli_print(void*, const char* s) { g_out += s; }
int g_saved = 0, g_applied = 0, g_led = -1;
std::string g_mark;

void test_config_and_cli() {
  SgConfig cfg;
  sg_config_defaults(&cfg);
  char err[64], val[160];
  CHECK(sg_config_set(&cfg, "report_interval_s", "30", err, sizeof err) && cfg.report_interval_s == 30);
  CHECK(!sg_config_set(&cfg, "report_interval_s", "5", err, sizeof err));        // below range
  CHECK(!sg_config_set(&cfg, "report_interval_s", "abc", err, sizeof err));
  CHECK(!sg_config_set(&cfg, "nope", "1", err, sizeof err));
  CHECK(sg_config_set(&cfg, "use_nn", "off", err, sizeof err) && cfg.use_nn == 0);
  CHECK(sg_config_set(&cfg, "bat_cal", "1.03", err, sizeof err));
  CHECK_NEAR(cfg.bat_cal, 1.03, 1e-6);
  std::string too_long(80, 'x');
  CHECK(!sg_config_set(&cfg, "wifi_ssid", too_long.c_str(), err, sizeof err));   // 32 chars max
  CHECK(sg_config_set(&cfg, "wifi_pass", "s3cret pass", err, sizeof err));
  CHECK(sg_config_get(&cfg, "wifi_pass", val, sizeof val, false) && strcmp(val, "(set)") == 0);   // masked
  CHECK(sg_config_get(&cfg, "wifi_pass", val, sizeof val, true) && strcmp(val, "s3cret pass") == 0);

  SgCliHooks h = {};
  h.print = cli_print;
  h.save = [](void*) { g_saved++; };
  h.apply = [](void*) { g_applied++; };
  h.led_test = [](void*, uint8_t mode) { g_led = mode; return true; };
  h.mark = [](void*, const char* note) {
    g_mark = note;
    return (int)strlen(note) % 3;                    // 0 / 1 / 2: the three outcomes
  };
  auto run = [&](const char* line) {
    char buf[256];
    snprintf(buf, sizeof buf, "%s", line);
    g_out.clear();
    sg_cli_handle(buf, &cfg, &h);
    return g_out;
  };
  CHECK(run("help").find("status") != std::string::npos);
  run("wifi HomeNet my pass word");
  CHECK(strcmp(cfg.wifi_ssid, "HomeNet") == 0 && strcmp(cfg.wifi_pass, "my pass word") == 0);
  CHECK(g_out.find("my pass word") == std::string::npos);                        // never echo secrets
  run("user  Aigerim.K@Example.com ");
  CHECK(strcmp(cfg.user_email, "Aigerim.K@Example.com") == 0);
  run("stream on");
  CHECK(cfg.stream_raw == 1);
  run("set tz_offset_min 300");
  CHECK(cfg.tz_offset_min == 300 && g_applied > 0);
  CHECK(run("set led_init 999").find("error") != std::string::npos);
  run("led red");
  CHECK(g_led == 1);
  CHECK(run("mark fingerstick 5.4 mmol").find("queued") != std::string::npos);   // 20 characters -> 2
  CHECK(g_mark == "fingerstick 5.4 mmol");
  CHECK(run("mark abcd").find("USB only") != std::string::npos);                 // -> 1
  CHECK(run("mark abc").find("error") != std::string::npos);                     // -> 0
  // Values that would silently misconfigure the sensor or the CPU are refused.
  CHECK(run("set sensor_sps 300").find("error") != std::string::npos && cfg.sensor_sps == 400);
  CHECK(run("set sensor_sps 100").find("ok") != std::string::npos && cfg.sensor_sps == 100);
  CHECK(run("set cpu_mhz 120").find("error") != std::string::npos && cfg.cpu_mhz == 160);
  CHECK(run("set report_interval_s 3600").find("error") != std::string::npos);   // the record holds <= 64 windows
  CHECK(run("set upload_interval_s 0").find("ok") != std::string::npos && cfg.upload_interval_s == 0);
  run("save");
  CHECK(g_saved == 1);
  CHECK(run("bogus").find("unknown command") != std::string::npos);
  CHECK(run("get").find("wifi_ssid") != std::string::npos);
  CHECK(run("   ").empty());
  printf("PASS config_and_cli\n");
}

void test_cloud_formatting() {
  char uid[160];
  CHECK(sg_email_to_uid("  Aigerim.K@Example.com ", uid, sizeof uid));
  CHECK(strcmp(uid, "aigerim_dot_k_at_example_dot_com") == 0);                   // = Dart _emailToUid
  CHECK(!sg_email_to_uid("no-at-sign", uid, sizeof uid));
  CHECK(!sg_email_to_uid("a/b@x.com", uid, sizeof uid));                         // would break the path
  CHECK(!sg_email_to_uid("", uid, sizeof uid));
  char small[8];
  CHECK(!sg_email_to_uid("someone@example.com", small, sizeof small));
  CHECK(uid[0] == '\0' && small[0] == '\0');                                    // failures leave no partial uid
  CHECK(sg_email_to_uid("Aigerim.K@Example.com", uid, sizeof uid));

  char iso[24];
  sg_local_iso8601(1763215390, 300, iso, sizeof iso);                            // 2025-11-15 14:03:10 UTC
  CHECK(strcmp(iso, "2025-11-15T19:03:10") == 0);
  sg_local_iso8601(951782400, 0, iso, sizeof iso);                               // leap day
  CHECK(strcmp(iso, "2000-02-29T00:00:00") == 0);
  sg_local_iso8601(1767225599, 300, iso, sizeof iso);                            // year roll-over in local time
  CHECK(strcmp(iso, "2026-01-01T04:59:59") == 0);

  char key[24];
  sg_record_key(1763215390123LL, key, sizeof key);
  CHECK(strcmp(key, "hd_1763215390123") == 0);

  SgVitalsRecord rec = {};
  rec.unix_s = 1763215390;
  rec.tz_offset_min = 300;
  rec.pulse_bpm = 71.94;
  rec.has_spo2 = false;
  rec.sqi = 0.914;
  rec.windows = 6;
  rec.reliable_windows = 4;
  rec.battery_percent = 87;
  rec.device_id = "SG-\"001\"";                                                  // needs escaping
  rec.firmware = "1.0.0";
  rec.model = "edge-nn";
  char json[512];
  const int n = sg_vitals_json(json, sizeof json, &rec, key);
  CHECK(n > 0 && (size_t)n == strlen(json));
  CHECK(strstr(json, "\"pulse\":71.9") && strstr(json, "\"spo2\":null") && strstr(json, "\"battery\":87"));
  CHECK(strstr(json, "\"timestamp\":\"2025-11-15T19:03:10\"") && strstr(json, "SG-\\\"001\\\""));
  CHECK(!strstr(json, "glucose"));
  CHECK(sg_vitals_json(json, 40, &rec, key) == -1);                              // too small: reported, not truncated
  rec.unix_s = 0;                                                                // clock not set: no invented time
  CHECK(sg_vitals_json(json, sizeof json, &rec, key) > 0);
  CHECK(strstr(json, "\"timestamp\":null,\"ts\":null") && !strstr(json, "1970"));
  char line[600];
  const int ln = sg_console_line(line, sizeof line, "record", "r", json);
  CHECK(ln > 0 && strncmp(line, "{\"t\":\"record\",\"r\":{\"id\":", 24) == 0 && line[ln - 2] == '}' && line[ln - 1] == '\n');
  CHECK(sg_console_line(line, 30, "record", "r", json) == -1);

  static SgWindow w;
  for (int i = 0; i < SG_WINDOW; i++) {
    w.red[i] = 262143;
    w.ir[i] = 262143;
  }
  w.seq = 7;
  w.fs_hz = 50.2f;
  w.temperature_c = NAN;
  static char raw[SG_RAW_JSON_MAX];
  const int m = sg_raw_window_json(raw, sizeof raw, &w, 1763215390123LL, 2345, "SG-001");
  CHECK(m > 0 && m < SG_RAW_JSON_MAX);                                           // worst case fits
  CHECK(strstr(raw, "\"temp_c\":null") && strstr(raw, "\"fs\":50.200"));
  // Time of the FIRST sample: end - 512 / 50.2 s; the age lets a PC without the device clock date it.
  CHECK(strstr(raw, "{\"ts\":1763215379.924,\"age_ms\":2345,"));
  int commas = 0;
  for (int i = 0; i < m; i++) commas += raw[i] == ',';
  CHECK(commas == 2 * (SG_WINDOW - 1) + 10);
  CHECK(sg_raw_window_json(raw, sizeof raw, &w, -1, 2345, "SG-001") > 0);
  CHECK(strstr(raw, "{\"ts\":null,\"age_ms\":2345,"));                           // clock not set: no invented time

  char url[320];
  CHECK(sg_db_url(url, sizeof url, "https://db.example", "users", uid, "vitals", key, "") > 0);
  CHECK(strcmp(url, "https://db.example/users/aigerim_dot_k_at_example_dot_com/vitals/hd_1763215390123.json") == 0);
  CHECK(sg_db_url(url, sizeof url, "https://db.example", "rawPpg", uid, nullptr, key, "TOKEN") > 0);
  CHECK(strstr(url, "/rawPpg/aigerim_dot_k_at_example_dot_com/hd_1763215390123.json?auth=TOKEN"));
  printf("PASS cloud_formatting\n");
}

void test_aggregator() {
  SgAggregator agg;
  double pulse, spo2, sqi, temp;
  bool has_spo2, has_temp;
  int nspo2;
  CHECK(!agg.summary(&pulse, &has_spo2, &spo2, &sqi, &nspo2, &has_temp, &temp));
  SgVitals v = {};
  const double hrs[] = {70, 72, 150, 71};          // one outlier: the median ignores it
  for (int i = 0; i < 4; i++) {
    v.reliable = true;
    v.has_hr = true;
    v.hr_bpm = hrs[i];
    v.has_spo2 = i < 2;
    v.spo2 = 96 + i;
    v.quality.sqi = 0.8;
    agg.add(v, 1.02, 31.0 + i);
  }
  v.reliable = false;                               // unreliable windows count but do not contribute
  agg.add(v, 1.0, NAN);
  CHECK(agg.windows() == 5 && agg.reliable() == 4);
  {
    SgAggregator many;                              // more reliable windows than are stored: all are counted
    SgVitals x = {};
    x.reliable = x.has_hr = true;
    for (int i = 0; i < SG_AGG_MAX + 20; i++) {
      x.hr_bpm = 60 + i % 5;
      many.add(x, 1.0, NAN);
    }
    CHECK(many.reliable() == SG_AGG_MAX + 20 && many.windows() == SG_AGG_MAX + 20);
  }
  CHECK(agg.summary(&pulse, &has_spo2, &spo2, &sqi, &nspo2, &has_temp, &temp));
  CHECK_NEAR(pulse, 71.5 * 1.02, 1e-9);
  CHECK(has_spo2 && nspo2 == 2);
  CHECK_NEAR(spo2, 96.5, 1e-9);
  CHECK_NEAR(sqi, 0.8, 1e-9);
  CHECK(has_temp);
  CHECK_NEAR(temp, 32.5, 1e-9);
  agg.reset();
  CHECK(agg.windows() == 0 && !agg.summary(&pulse, &has_spo2, &spo2, &sqi, &nspo2, &has_temp, &temp));
  printf("PASS aggregator\n");
}


// ---------------------------------------------------------------------------
// Sampler behaviour found by the independent review
// ---------------------------------------------------------------------------

void test_sensor_reset_while_settling_recovers() {
  for (int phase = 0; phase < 3; phase++) {
    Rig r;
    r.begin();
    if (phase == 0) {
      r.run(300);                                    // still settling after the first configuration
      CHECK(r.sampler.state() == SgSamplerState::kSettling);
    } else if (phase == 1) {
      r.run(3000);
      CHECK(r.sampler.request_led_test(3, 5000));
      r.run(1000);
      CHECK(r.sampler.state() == SgSamplerState::kLedTest);
    } else {
      r.dc_per_step = 6000.0;                        // the AGC changes the current after the first window
      r.run(10900);
      CHECK(r.sampler.state() == SgSamplerState::kSettling);
    }
    r.sim.power_on_reset();                          // brown-out: registers back to defaults, no conversions
    r.sim.reg[max30102::kIntStatus1] = 0;            // ... and a chip that does not even flag it
    r.run(30000);
    CHECK(r.sampler.state() == SgSamplerState::kActive);
    CHECK(r.sampler.stats().no_data_timeouts == 1);
    CHECK(r.sim.running() && !r.windows.empty());
  }
  printf("PASS sensor_reset_while_settling_recovers\n");
}

void test_dim_wrist_is_measured_and_wakes() {
  Rig r;
  r.dc_per_step = 308.0;                             // 19 400 counts at the start current: below "not worn"
  r.begin();
  r.run(45000);
  CHECK(r.sampler.worn() && r.sampler.led_ir() == 0x7F);   // full current: 39 000 counts
  CHECK(r.windows.size() >= 3 && r.windows.back().led_ir == 0x7F);
  r.worn = false;
  r.run(40000);
  CHECK(!r.sampler.worn());
  r.worn = true;                                     // the same dim wrist again: the probe must see it
  r.run(15000);
  CHECK(r.sampler.worn() && r.sampler.led_ir() == 0x7F);
  printf("PASS dim_wrist_is_measured_and_wakes\n");
}

void test_rest_and_wake_on_change() {
  SgSamplerConfig cfg;
  cfg.rest_recheck_ms = 60000;
  Rig r;
  r.dc_per_step = 800.0;                             // 101 600 counts at the probe current: room to change
  r.begin(cfg);
  r.run(12000);
  CHECK(r.sampler.worn() && !r.sampler.resting());
  r.sampler.request_rest();                          // what reflects the light has no pulse
  r.run(100);
  CHECK(!r.sampler.worn() && r.sampler.resting());
  int shut = 0, total = 0;
  for (int i = 0; i < 400; i++) {                    // 20 s: LEDs off except for the probes
    r.run(50);
    total++;
    shut += (r.sim.reg[max30102::kModeConfig] & max30102::kModeShutdown) ? 1 : 0;
  }
  CHECK(shut > total * 8 / 10 && r.sampler.resting());
  r.dc_per_step *= 1.3;                              // the bracelet is picked up / put on
  r.run(8000);
  CHECK(r.sampler.worn() && !r.sampler.resting());
  // Nothing changes: after the re-check time it measures again by itself.
  r.sampler.request_rest();
  r.run(30000);
  CHECK(r.sampler.resting());
  r.run(45000);
  CHECK(r.sampler.worn() && !r.sampler.resting());
  // Taken away while resting: plain "not worn", and putting it on wakes it.
  r.sampler.request_rest();
  r.run(5000);
  r.worn = false;
  r.run(10000);
  CHECK(!r.sampler.worn() && !r.sampler.resting());
  r.worn = true;
  r.run(10000);
  CHECK(r.sampler.worn());
  printf("PASS rest_and_wake_on_change\n");
}

void test_power_down_request() {
  Rig r;
  r.begin();
  r.run(5000);
  CHECK(r.sim.running() && r.sim.reg[max30102::kLed1Pa] != 0);
  r.sampler.request_power_down();
  r.run(100);
  CHECK(r.sampler.powered_down() && !r.sim.running());
  CHECK((r.sim.reg[max30102::kModeConfig] & max30102::kModeShutdown) && r.sim.reg[max30102::kLed1Pa] == 0 &&
        r.sim.reg[max30102::kLed2Pa] == 0);
  CHECK(!r.sampler.request_led_test(1, 1000));       // nothing wakes it by accident
  r.sampler.request_rest();
  r.run(20000);
  CHECK(r.sampler.powered_down() && !r.sim.running());
  CHECK(r.sampler.request_config(SgSamplerConfig()));
  r.run(15000);
  CHECK(r.sampler.state() == SgSamplerState::kActive && r.sim.running());
  printf("PASS power_down_request\n");
}

void test_agc_ignores_single_spikes() {
  Rig r;
  r.dc_per_step = 1016.0;                            // 64 000 counts at the start current: inside the band
  r.spike_every = 500;                               // about one full-scale sample per window
  r.begin();
  r.run(120000);
  CHECK(r.sampler.led_ir() == 0x3F && r.sampler.led_red() == 0x3F);    // was: a limit cycle down to "not worn"
  CHECK(r.sampler.worn() && r.windows.size() >= 10);
  for (const SgWindow& w : r.windows) CHECK(w.led_ir == 0x3F);
  printf("PASS agc_ignores_single_spikes\n");
}

void test_led_test_refused_without_sensor() {
  Rig r;
  r.sim.present = false;
  r.begin();
  r.run(3000);
  CHECK(r.sampler.state() == SgSamplerState::kNoSensor);
  CHECK(!r.sampler.request_led_test(1, 5000));       // was accepted and fired whenever the sensor appeared
  r.sim.present = true;
  r.run(5000);
  CHECK(r.sampler.state() == SgSamplerState::kActive);
  CHECK(r.sim.reg[max30102::kLed1Pa] == 0x3F && r.sim.reg[max30102::kLed2Pa] == 0x3F);
  printf("PASS led_test_refused_without_sensor\n");
}

// ---------------------------------------------------------------------------
// Offline store, upload scheduling, battery guard
// ---------------------------------------------------------------------------

void test_store() {
  static SgStore st;
  CHECK(st.next() == SgStoredKind::kNone && st.pending() == 0);
  SgStoredRecord r = {};
  for (int i = 0; i < 5; i++) {                      // before the clock is known: time since boot
    r.t_ms = 60000 * (i + 1);
    r.flags = 0;
    r.pulse_bpm = 60.0f + i;
    CHECK(st.add_record(r));
  }
  CHECK(st.add_marker(125000, false, "before sync"));
  st.set_boot_time(1763215000000LL);                 // clock set: boot was at this unix time
  r.t_ms = 1763215400000LL;
  r.flags = SG_SF_UNIX_TIME;
  r.pulse_bpm = 99.0f;
  CHECK(st.add_record(r));
  st.set_boot_time(1763215000000LL);                 // a second sync must not shift anything again
  CHECK(st.pending() == 7 && st.next() == SgStoredKind::kMarker);
  CHECK(st.marker().t_ms == 1763215125000LL && (st.marker().flags & SG_SF_UNIX_TIME));
  CHECK(strcmp(st.marker().note, "before sync") == 0);
  st.pop();
  for (int i = 0; i < 5; i++) {                      // oldest first
    CHECK(st.next() == SgStoredKind::kRecord && st.record().pulse_bpm == 60.0f + i);
    CHECK(st.record().t_ms == 1763215000000LL + 60000 * (i + 1) && (st.record().flags & SG_SF_UNIX_TIME));
    st.pop();
  }
  CHECK(st.record().pulse_bpm == 99.0f && st.record().t_ms == 1763215400000LL);
  st.pop();
  CHECK(st.pending() == 0 && st.dropped() == 0);
  st.pop();                                          // popping an empty store is harmless
  // Overflow: the oldest entries make room and are counted.
  for (int i = 0; i < SG_STORE_RECORDS + 10; i++) {
    r.pulse_bpm = (float)i;
    CHECK(st.add_record(r) == (i < SG_STORE_RECORDS));
  }
  CHECK(st.records() == SG_STORE_RECORDS && st.dropped() == 10 && st.record().pulse_bpm == 10.0f);
  const std::string long_note(200, 'x');
  for (int i = 0; i < SG_STORE_MARKERS + 3; i++) st.add_marker(i, true, i == 0 ? long_note.c_str() : "m");
  CHECK(st.markers() == SG_STORE_MARKERS && st.dropped() == 13);
  CHECK(st.add_marker(1, true, long_note.c_str()) == false);
  CHECK(st.add_marker(1, true, nullptr) == false);
  printf("PASS store\n");
}

// Drives SgUplink like the main loop does; `http` is the answer of the server to every send.
struct UplinkRig {
  SgUplink up;
  uint64_t now = 0;
  int pending = 0;
  bool ap_in_range = true, radio = false, connected = false, clock = false;
  int http = 200;
  uint64_t connect_at = 0, clock_at = 0, radio_on_ms = 0;
  int sends = 0, radio_ons = 0;

  void run(uint64_t ms, bool enabled = true) {
    for (uint64_t t = 0; t < ms; t += 10) {
      now += 10;
      if (radio) radio_on_ms += 10;
      connected = radio && ap_in_range && now >= connect_at;
      if (connected && clock_at && now >= clock_at) clock = true;
      switch (up.step(now, enabled, pending, connected, clock)) {
        case SgUplinkAction::kRadioOn:
          CHECK(!radio);
          radio = true;
          radio_ons++;
          connect_at = now + 2500;                   // association + DHCP
          break;
        case SgUplinkAction::kStartClock:
          clock_at = now + 1500;                     // SNTP answer
          break;
        case SgUplinkAction::kSend:
          sends++;
          now += 1500;                               // a TLS handshake blocks the loop
          radio_on_ms += 1500;
          if (up.sent(now, http)) pending--;
          break;
        case SgUplinkAction::kRadioOff:
          CHECK(radio);
          radio = connected = false;
          break;
        case SgUplinkAction::kNone:
          break;
      }
    }
  }
};

void test_uplink() {
  {  // Normal operation: one short session per interval, radio off in between.
    UplinkRig u;
    u.run(60000);
    CHECK(!u.radio && u.radio_ons == 0);             // nothing to send: the radio stays off
    for (int minute = 0; minute < 60; minute++) {
      u.pending++;                                   // one record per minute
      u.run(60000);
    }
    CHECK(u.pending <= 5 && u.sends >= 55);
    CHECK(u.radio_ons >= 11 && u.radio_ons <= 13);   // every 5 minutes
    CHECK(u.radio_on_ms < 3600000 / 8);              // on for a fraction of the time
    CHECK(u.up.stats().delivered == (uint32_t)u.sends && u.up.stats().failures == 0);
  }
  {  // No access point: attempts back off to one every 10 minutes; nothing is lost.
    UplinkRig u;
    u.ap_in_range = false;
    u.pending = 3;
    u.run(4 * 3600000);
    CHECK(u.pending == 3 && u.sends == 0);
    CHECK(u.radio_ons >= 20 && u.radio_ons <= 32);   // was: a new attempt every 20 s (720 in 4 h)
    CHECK(u.radio_on_ms < 4 * 3600000 / 15);
    u.ap_in_range = true;                            // back home: everything goes out
    u.run(700000);
    CHECK(u.pending == 0 && !u.radio);
  }
  {  // The server refuses everything (database rules): a few attempts per hour, items are kept.
    UplinkRig u;
    u.http = 401;
    u.pending = 4;
    u.run(2 * 3600000);
    CHECK(u.pending == 4 && u.sends >= 10 && u.sends <= 14);     // was: 3 per second
    CHECK(u.up.stats().last_code == 401 && u.up.stats().rejected == 0);
    u.http = 200;
    u.run(700000);
    CHECK(u.pending == 0);
  }
  {  // Server errors and time-outs are retried with growing pauses.
    UplinkRig u;
    u.http = 503;
    u.pending = 2;
    u.run(3600000);
    CHECK(u.pending == 2 && u.sends >= 8 && u.sends <= 14);
    UplinkRig v;
    v.http = -1;                                     // transport error
    v.pending = 2;
    v.run(3600000);
    CHECK(v.pending == 2 && v.sends >= 8 && v.sends <= 14);
  }
  {  // One record the server will never accept must not block the ones behind it.
    UplinkRig u;
    u.http = 400;
    u.pending = 3;
    u.run(60000);
    CHECK(u.pending == 0 && u.up.stats().rejected == 3 && u.up.stats().delivered == 0 && !u.radio);
  }
  {  // The clock never arrives (NTP blocked): the sessions end, the radio goes off in between.
    UplinkRig w;
    w.pending = 1;
    for (int i = 0; i < 7000; i++) {                 // 70 s with the clock answer suppressed
      w.run(10);
      w.clock_at = 0;
    }
    CHECK(w.sends == 0 && !w.radio && w.up.stats().failures == 2 && w.pending == 1);
  }
  {  // Data-collection mode: stays online; a failing extra upload still backs off.
    UplinkRig u;
    SgUplinkConfig cfg;
    cfg.keep_connected = true;
    u.up.configure(cfg);
    u.run(600000);
    CHECK(u.radio && u.up.online() && u.radio_ons == 1);
    u.up.extra_result(u.now, 200);
    u.run(1000);
    CHECK(u.up.online());
    u.up.extra_result(u.now, -1);
    u.run(1000);
    CHECK(!u.radio && !u.up.online() && u.up.wait_ms(u.now) > 0);
    u.run(60000);
    CHECK(u.up.online());
  }
  {  // Switched off in the settings while connected: the radio goes off at once.
    UplinkRig u;
    u.pending = 1;
    u.run(3000);
    CHECK(u.radio);
    u.run(100, false);
    CHECK(!u.radio && u.up.state() == SgUplinkState::kIdle);
    u.up.retry_now();
    u.run(10000);
    CHECK(u.pending == 0);
  }
  printf("PASS uplink\n");
}

void test_power_guard() {
  const SgPowerLimits lim;
  // Run time: empty only after a full minute below the threshold, whatever the clock value is
  // (the first version encoded "timer running" in the time stamp and slept at once on even values).
  for (uint32_t start : {1000u, 1001u, 0xFFFFFFF0u}) {
    SgPowerGuard g(lim);
    uint32_t t = start;
    CHECK(g.update(t, 3.80f, false) == SgPowerAction::kRun);
    for (int i = 0; i < 60; i++) {                   // 60 s from the first low reading
      t += 1000;
      CHECK(g.update(t, 3.44f, false) == SgPowerAction::kRun);
    }
    t += 1000;
    CHECK(g.update(t, 3.44f, false) == SgPowerAction::kSleep);
  }
  {
    SgPowerGuard g(lim);
    uint32_t t = 0;
    for (int i = 0; i < 50; i++) g.update(t += 1000, 3.40f, false);
    CHECK(g.update(t += 1000, 3.50f, false) == SgPowerAction::kRun);        // recovered: the timer restarts
    for (int i = 0; i < 60; i++) CHECK(g.update(t += 1000, 3.40f, false) == SgPowerAction::kRun);
    CHECK(g.update(t += 1000, 3.40f, false) == SgPowerAction::kSleep);
    SgPowerGuard usb(lim);
    for (int i = 0; i < 200; i++) CHECK(usb.update(t += 1000, 3.30f, true) == SgPowerAction::kRun);   // on USB: never
    SgPowerGuard deep(lim);                                                  // was: "below 3.0 V cannot be real"
    for (int i = 0; i < 60; i++) deep.update(t += 1000, 2.90f, false);
    CHECK(deep.update(t += 1000, 2.90f, false) == SgPowerAction::kSleepLong);
    SgPowerGuard none(lim);                                                  // no divider fitted: nothing to decide
    for (int i = 0; i < 200; i++) CHECK(none.update(t += 1000, 0.05f, false) == SgPowerAction::kRun);
  }
  // Start-up: a fresh start needs to be above empty; a wake-up from the empty sleep needs a recharge.
  CHECK(sg_power_at_boot(3.50f, false, false, lim) == SgPowerAction::kRun);
  CHECK(sg_power_at_boot(3.44f, false, false, lim) == SgPowerAction::kSleep);
  CHECK(sg_power_at_boot(3.50f, false, true, lim) == SgPowerAction::kSleep);       // rested, not recharged
  CHECK(sg_power_at_boot(3.60f, false, true, lim) == SgPowerAction::kRun);
  CHECK(sg_power_at_boot(3.10f, false, true, lim) == SgPowerAction::kSleepLong);
  CHECK(sg_power_at_boot(2.95f, false, false, lim) == SgPowerAction::kSleepLong);
  CHECK(sg_power_at_boot(3.10f, true, true, lim) == SgPowerAction::kRun);          // charger connected
  CHECK(sg_power_at_boot(0.0f, false, false, lim) == SgPowerAction::kRun);
  printf("PASS power_guard\n");
}

}  // namespace

int main() {
  test_bringup_and_windows();
  test_swapped_leds();
  test_fifo_overflow_restarts_window();
  test_agc_reduces_and_raises();
  test_not_worn_standby_and_wake();
  test_sensor_brownout_recovers();
  test_absent_then_present_and_bus_errors();
  test_sample_rate_estimate();
  test_led_test_request();
  test_ambient_overflow_flag();
  test_battery();
  test_config_and_cli();
  test_cloud_formatting();
  test_aggregator();
  test_sensor_reset_while_settling_recovers();
  test_dim_wrist_is_measured_and_wakes();
  test_rest_and_wake_on_change();
  test_power_down_request();
  test_agc_ignores_single_spikes();
  test_led_test_refused_without_sensor();
  test_store();
  test_uplink();
  test_power_guard();
  printf("ALL OK\n");
  return 0;
}
