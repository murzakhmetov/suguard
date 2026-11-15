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
#include "../../suguard/src/app/sampler.h"
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
      if (*s1 > 262143) *s1 = 262143;
      if (*s2 > 262143) *s2 = 262143;
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
  CHECK(r.sim.reg[max30102::kIntEnable1] == 0);
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
  for (int i = 0; i < 100; i++) m.update(4.0f * 1000.0f * 47.0f / 147.0f, 2500.0f);
  CHECK(m.state().usb_present && m.state().charging);
  for (int i = 0; i < 100; i++) m.update(4.2f * 1000.0f * 47.0f / 147.0f, 2500.0f);
  CHECK(m.state().usb_present && !m.state().charging && m.state().percent == 100);
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
  h.mark = [](void*, const char* note) { g_mark = note; };
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
  run("mark fingerstick 5.4 mmol");
  CHECK(g_mark == "fingerstick 5.4 mmol");
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

  static SgWindow w;
  for (int i = 0; i < SG_WINDOW; i++) {
    w.red[i] = 262143;
    w.ir[i] = 262143;
  }
  w.seq = 7;
  w.fs_hz = 50.2f;
  w.temperature_c = NAN;
  static char raw[SG_RAW_JSON_MAX];
  const int m = sg_raw_window_json(raw, sizeof raw, &w, 1763215390, "SG-001");
  CHECK(m > 0 && m < SG_RAW_JSON_MAX);                                           // worst case fits
  CHECK(strstr(raw, "\"temp_c\":null") && strstr(raw, "\"fs\":50.200"));
  int commas = 0;
  for (int i = 0; i < m; i++) commas += raw[i] == ',';
  CHECK(commas == 2 * (SG_WINDOW - 1) + 9);

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
  printf("ALL OK\n");
  return 0;
}
