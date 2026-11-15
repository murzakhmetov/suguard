#include "cloud_fmt.h"

#include <math.h>
#include <stdio.h>
#include <string.h>

namespace {

// Bounded string builder: remembers overflow instead of writing past the end.
struct Out {
  char* p;
  size_t cap;
  size_t len;
  bool overflow;
};

void put(Out* o, const char* s) {
  const size_t n = strlen(s);
  if (o->overflow || o->len + n + 1 > o->cap) {
    o->overflow = true;
    return;
  }
  memcpy(o->p + o->len, s, n + 1);
  o->len += n;
}

void put_u32(Out* o, uint32_t v) {
  char tmp[11];
  int i = 10;
  tmp[i] = '\0';
  do {
    tmp[--i] = (char)('0' + v % 10);
    v /= 10;
  } while (v);
  put(o, tmp + i);
}

void put_fixed(Out* o, double v, int decimals) {
  char tmp[32];
  snprintf(tmp, sizeof tmp, "%.*f", decimals, v);
  put(o, tmp);
}

// JSON string with escaping of quotes, backslashes and control characters.
void put_string(Out* o, const char* s) {
  put(o, "\"");
  for (; s && *s; s++) {
    const unsigned char c = (unsigned char)*s;
    char tmp[8];
    if (c == '"' || c == '\\') snprintf(tmp, sizeof tmp, "\\%c", c);
    else if (c < 0x20) snprintf(tmp, sizeof tmp, "\\u%04x", c);
    else snprintf(tmp, sizeof tmp, "%c", c);
    put(o, tmp);
  }
  put(o, "\"");
}

int finish(const Out& o) { return o.overflow ? -1 : (int)o.len; }

}  // namespace

bool sg_email_to_uid(const char* email, char* out, size_t out_len) {
  if (!out || out_len == 0) return false;
  out[0] = '\0';                                       // never leave a partial uid behind
  if (!email) return false;
  while (*email == ' ' || *email == '\t') email++;
  size_t n = strlen(email);
  while (n > 0 && (email[n - 1] == ' ' || email[n - 1] == '\t')) n--;
  size_t len = 0;
  bool has_at = false, ok = n > 0;
  for (size_t i = 0; ok && i < n; i++) {
    char c = email[i];
    if (c >= 'A' && c <= 'Z') c = (char)(c - 'A' + 'a');
    const char* rep = nullptr;
    const char one[2] = {c, '\0'};
    if (c == '.') rep = "_dot_";
    else if (c == '@') { rep = "_at_"; has_at = true; }
    else if ((c >= 'a' && c <= 'z') || (c >= '0' && c <= '9') || c == '_' || c == '+' || c == '-') rep = one;
    const size_t m = rep ? strlen(rep) : 0;
    if (!rep || len + m + 1 > out_len) {
      ok = false;
      break;
    }
    memcpy(out + len, rep, m);
    len += m;
  }
  out[ok && has_at ? len : 0] = '\0';
  return ok && has_at;
}

void sg_local_iso8601(int64_t unix_s, int tz_offset_min, char* out, size_t out_len) {
  const int64_t t = unix_s + (int64_t)tz_offset_min * 60;
  int64_t days = t / 86400;
  int64_t rem = t % 86400;
  if (rem < 0) {
    rem += 86400;
    days -= 1;
  }
  // Civil date from days since 1970-01-01 (H. Hinnant's algorithm).
  const int64_t z = days + 719468;
  const int64_t era = (z >= 0 ? z : z - 146096) / 146097;
  const int64_t doe = z - era * 146097;
  const int64_t yoe = (doe - doe / 1460 + doe / 36524 - doe / 146096) / 365;
  const int64_t doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
  const int64_t mp = (5 * doy + 2) / 153;
  const int d = (int)(doy - (153 * mp + 2) / 5 + 1);
  const int m = (int)(mp < 10 ? mp + 3 : mp - 9);
  const int y = (int)(yoe + era * 400 + (m <= 2 ? 1 : 0));
  snprintf(out, out_len, "%04d-%02d-%02dT%02d:%02d:%02d", y, m, d, (int)(rem / 3600), (int)(rem % 3600 / 60),
           (int)(rem % 60));
}

void sg_record_key(int64_t unix_ms, char* out, size_t out_len) {
  // 13 digits, zero padded, so that keys sort chronologically as strings.
  snprintf(out, out_len, "hd_%013lld", (long long)unix_ms);
}

int sg_vitals_json(char* out, size_t out_len, const SgVitalsRecord* r, const char* key) {
  Out o = {out, out_len, 0, false};
  char iso[24];
  sg_local_iso8601(r->unix_s, r->tz_offset_min, iso, sizeof iso);
  put(&o, "{\"id\":");
  put_string(&o, key);
  if (r->unix_s > 0) {
    put(&o, ",\"timestamp\":");
    put_string(&o, iso);
    put(&o, ",\"ts\":");
    put_fixed(&o, (double)r->unix_s, 0);
  } else {
    put(&o, ",\"timestamp\":null,\"ts\":null");
  }
  put(&o, ",\"pulse\":");
  put_fixed(&o, r->pulse_bpm, 1);
  put(&o, ",\"spo2\":");
  if (r->has_spo2) put_fixed(&o, r->spo2, 1);
  else put(&o, "null");
  put(&o, ",\"sqi\":");
  put_fixed(&o, r->sqi, 2);
  put(&o, ",\"windows\":");
  put_u32(&o, (uint32_t)r->windows);
  put(&o, ",\"reliableWindows\":");
  put_u32(&o, (uint32_t)r->reliable_windows);
  put(&o, ",\"spo2Windows\":");
  put_u32(&o, (uint32_t)r->spo2_windows);
  put(&o, ",\"battery\":");
  if (r->battery_percent >= 0) put_u32(&o, (uint32_t)r->battery_percent);
  else put(&o, "null");
  put(&o, r->charging ? ",\"charging\":true" : ",\"charging\":false");
  put(&o, ",\"sensorTempC\":");
  if (r->has_temperature) put_fixed(&o, r->temperature_c, 1);
  else put(&o, "null");
  put(&o, ",\"spo2Calibrated\":false,\"device\":");
  put_string(&o, r->device_id);
  put(&o, ",\"fw\":");
  put_string(&o, r->firmware);
  put(&o, ",\"model\":");
  put_string(&o, r->model);
  put(&o, "}");
  return finish(o);
}

int sg_raw_window_json(char* out, size_t out_len, const SgWindow* w, int64_t end_unix_ms, uint32_t age_ms,
                       const char* device_id) {
  Out o = {out, out_len, 0, false};
  const double fs = w->fs_hz > 0 ? (double)w->fs_hz : SG_FS;
  put(&o, "{\"ts\":");                                   // unix time of the FIRST sample
  if (end_unix_ms >= 0) put_fixed(&o, (double)end_unix_ms / 1000.0 - SG_WINDOW / fs, 3);
  else put(&o, "null");
  put(&o, ",\"age_ms\":");
  put_u32(&o, age_ms);
  put(&o, ",\"fs\":");
  put_fixed(&o, fs, 3);
  put(&o, ",\"seq\":");
  put_u32(&o, w->seq);
  put(&o, ",\"ledRed\":");
  put_u32(&o, w->led_red);
  put(&o, ",\"ledIr\":");
  put_u32(&o, w->led_ir);
  put(&o, ",\"flags\":");
  put_u32(&o, w->flags);
  put(&o, ",\"temp_c\":");
  if (isnan(w->temperature_c)) put(&o, "null");
  else put_fixed(&o, (double)w->temperature_c, 2);
  put(&o, ",\"device\":");
  put_string(&o, device_id);
  put(&o, ",\"red\":[");
  for (int i = 0; i < SG_WINDOW; i++) {
    if (i) put(&o, ",");
    put_u32(&o, w->red[i]);
  }
  put(&o, "],\"ir\":[");
  for (int i = 0; i < SG_WINDOW; i++) {
    if (i) put(&o, ",");
    put_u32(&o, w->ir[i]);
  }
  put(&o, "]}");
  return finish(o);
}

int sg_event_json(char* out, size_t out_len, int64_t unix_s, int tz_offset_min, const char* type, const char* note) {
  Out o = {out, out_len, 0, false};
  char iso[24];
  sg_local_iso8601(unix_s, tz_offset_min, iso, sizeof iso);
  put(&o, "{\"timestamp\":");
  put_string(&o, iso);
  put(&o, ",\"ts\":");
  put_fixed(&o, (double)unix_s, 0);
  put(&o, ",\"type\":");
  put_string(&o, type);
  put(&o, ",\"note\":");
  put_string(&o, note ? note : "");
  put(&o, "}");
  return finish(o);
}

int sg_console_line(char* out, size_t out_len, const char* type, const char* field, const char* json) {
  Out o = {out, out_len, 0, false};
  put(&o, "{\"t\":\"");
  put(&o, type);
  put(&o, "\",\"");
  put(&o, field);
  put(&o, "\":");
  put(&o, json);
  put(&o, "}\n");
  return finish(o);
}

int sg_db_url(char* out, size_t out_len, const char* db_url, const char* node, const char* uid, const char* leaf,
              const char* key, const char* auth) {
  Out o = {out, out_len, 0, false};
  put(&o, db_url);
  put(&o, "/");
  put(&o, node);
  put(&o, "/");
  put(&o, uid);
  if (leaf) {
    put(&o, "/");
    put(&o, leaf);
  }
  put(&o, "/");
  put(&o, key);
  put(&o, ".json");
  if (auth && auth[0]) {
    put(&o, "?auth=");
    put(&o, auth);
  }
  return finish(o);
}
