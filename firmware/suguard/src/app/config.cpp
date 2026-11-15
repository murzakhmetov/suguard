#include "config.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

namespace {

enum Type : uint8_t { kStr, kU8, kBool, kU16, kI16, kFloat };

struct Field {
  const char* key;
  Type type;
  uint16_t offset;
  uint16_t size;        // strings: buffer size
  float lo, hi;         // numeric range
  bool secret;
  const char* help;
};

#define F(member) (uint16_t) offsetof(SgConfig, member), (uint16_t)sizeof(((SgConfig*)0)->member)

const Field kFields[] = {
    {"wifi_ssid", kStr, F(wifi_ssid), 0, 0, false, "Wi-Fi network name"},
    {"wifi_pass", kStr, F(wifi_pass), 0, 0, true, "Wi-Fi password"},
    {"user", kStr, F(user_email), 0, 0, false, "e-mail of the SuGuard app account that owns this bracelet"},
    {"device_id", kStr, F(device_id), 0, 0, false, "device label, e.g. SG-001"},
    {"db_url", kStr, F(db_url), 0, 0, false, "Firebase Realtime Database URL"},
    {"db_auth", kStr, F(db_auth), 0, 0, true, "optional Firebase auth token"},
    {"tz_offset_min", kI16, F(tz_offset_min), -720, 840, false, "local time zone, minutes east of UTC"},
    {"report_interval_s", kU16, F(report_interval_s), 20, 3600, false, "seconds between uploaded records"},
    {"cloud", kBool, F(cloud), 0, 1, false, "upload vitals to Firebase"},
    {"upload_raw", kBool, F(upload_raw), 0, 1, false, "upload raw windows too (data collection)"},
    {"stream_raw", kBool, F(stream_raw), 0, 1, false, "print raw windows on USB serial"},
    {"use_nn", kBool, F(use_nn), 0, 1, false, "on-device neural denoiser"},
    {"swap_red_ir", kBool, F(swap_red_ir), 0, 1, false, "red and IR LEDs are exchanged on the module"},
    {"tls_insecure", kBool, F(tls_insecure), 0, 1, false, "skip TLS certificate checks (debug only)"},
    {"led_init", kU8, F(led_init), 8, 255, false, "start LED current, 0.2 mA per step"},
    {"led_max", kU8, F(led_max), 8, 255, false, "maximum LED current, 0.2 mA per step"},
    {"adc_range", kU8, F(adc_range), 0, 3, false, "MAX30102 ADC range: 0=2048 1=4096 2=8192 3=16384 nA"},
    {"ir_dc_min", kFloat, F(ir_dc_min), 1000, 200000, false, "IR level (counts) below which the bracelet counts as not worn"},
    {"bat_cal", kFloat, F(bat_cal), 0.8f, 1.2f, false, "battery voltage calibration factor"},
};
const int kFieldN = (int)(sizeof(kFields) / sizeof(kFields[0]));

const Field* find(const char* key) {
  for (int i = 0; i < kFieldN; i++) {
    if (strcmp(kFields[i].key, key) == 0) return &kFields[i];
  }
  return nullptr;
}

void fail(char* err, size_t n, const char* msg) {
  if (err && n) snprintf(err, n, "%s", msg);
}

}  // namespace

void sg_config_defaults(SgConfig* c) {
  memset(c, 0, sizeof(*c));
  c->version = SG_CONFIG_VERSION;
  snprintf(c->device_id, sizeof(c->device_id), "SG-001");
  snprintf(c->db_url, sizeof(c->db_url), "https://suguard-7f535-default-rtdb.asia-southeast1.firebasedatabase.app");
  c->tz_offset_min = 300;
  c->report_interval_s = 60;
  c->cloud = 1;
  c->use_nn = 1;
  c->led_init = 0x3F;
  c->led_max = 0x7F;
  c->adc_range = 1;
  c->ir_dc_min = 20000.0f;
  c->bat_cal = 1.0f;
}

bool sg_config_set(SgConfig* c, const char* key, const char* value, char* err, size_t err_len) {
  const Field* f = find(key);
  if (!f) {
    fail(err, err_len, "unknown key");
    return false;
  }
  char* base = (char*)c + f->offset;
  if (f->type == kStr) {
    const size_t len = strlen(value);
    if (len >= f->size) {
      fail(err, err_len, "value too long");
      return false;
    }
    for (size_t i = 0; i < len; i++) {
      if ((unsigned char)value[i] < 0x20 || value[i] == 0x7F) {
        fail(err, err_len, "control characters are not allowed");
        return false;
      }
    }
    memset(base, 0, f->size);
    memcpy(base, value, len);
    return true;
  }
  char* end = nullptr;
  float v;
  if (f->type == kBool && (strcmp(value, "on") == 0 || strcmp(value, "true") == 0)) {
    v = 1;
  } else if (f->type == kBool && (strcmp(value, "off") == 0 || strcmp(value, "false") == 0)) {
    v = 0;
  } else {
    v = strtof(value, &end);
    if (end == value || *end != '\0' || v != v) {
      fail(err, err_len, "not a number");
      return false;
    }
  }
  if (v < f->lo || v > f->hi) {
    if (err && err_len) snprintf(err, err_len, "out of range (%g..%g)", (double)f->lo, (double)f->hi);
    return false;
  }
  switch (f->type) {
    case kU8:
    case kBool: *(uint8_t*)base = (uint8_t)v; break;
    case kU16: { uint16_t x = (uint16_t)v; memcpy(base, &x, sizeof x); break; }
    case kI16: { int16_t x = (int16_t)v; memcpy(base, &x, sizeof x); break; }
    default: memcpy(base, &v, sizeof v); break;
  }
  return true;
}

bool sg_config_get(const SgConfig* c, const char* key, char* out, size_t out_len, bool reveal) {
  const Field* f = find(key);
  if (!f || !out || !out_len) return false;
  const char* base = (const char*)c + f->offset;
  switch (f->type) {
    case kStr:
      if (f->secret && !reveal) snprintf(out, out_len, "%s", base[0] ? "(set)" : "(empty)");
      else snprintf(out, out_len, "%s", base);
      break;
    case kU8:
    case kBool: snprintf(out, out_len, "%u", (unsigned)*(const uint8_t*)base); break;
    case kU16: { uint16_t x; memcpy(&x, base, sizeof x); snprintf(out, out_len, "%u", (unsigned)x); break; }
    case kI16: { int16_t x; memcpy(&x, base, sizeof x); snprintf(out, out_len, "%d", (int)x); break; }
    default: { float x; memcpy(&x, base, sizeof x); snprintf(out, out_len, "%g", (double)x); break; }
  }
  return true;
}

const char* sg_config_key(int index) { return index >= 0 && index < kFieldN ? kFields[index].key : nullptr; }

const char* sg_config_help(int index) { return index >= 0 && index < kFieldN ? kFields[index].help : nullptr; }
