// Formatting of what the bracelet sends to the Firebase Realtime Database.
// Pure string code (no network), so it is unit-tested on the host.
//
// Nodes (all under the database root):
//   users/<uid>/vitals/<key>      one averaged record per report interval
//   rawPpg/<uid>/<key>            raw windows, only in data-collection mode
//   users/<uid>/events/<key>      button presses / markers
// <uid> is derived from the account e-mail exactly as the Flutter app does
// (FirebaseService._emailToUid), <key> = "hd_<unix milliseconds>" so keys
// sort chronologically.
//
// There is deliberately NO glucose field: the bracelet has no validated
// glucose model (see ml/README.md). A record is written only from windows
// that passed every signal-quality gate.
#pragma once

#include <stddef.h>
#include <stdint.h>

#include "sampler.h"

struct SgVitalsRecord {
  int64_t unix_s;           // end of the interval (UTC); <= 0 if the clock is not set (time fields are then null)
  int tz_offset_min;
  double pulse_bpm;
  bool has_spo2;
  double spo2;
  double sqi;               // mean signal quality of the windows used (0..1)
  int windows;              // windows recorded in the interval
  int reliable_windows;     // windows that passed all gates (>= 1)
  int spo2_windows;
  int battery_percent;      // -1 = unknown
  bool charging;
  bool has_temperature;
  double temperature_c;     // sensor die temperature (close to skin temperature when worn)
  const char* device_id;
  const char* firmware;
  const char* model;        // "edge-nn" or "classical"
};

// "User@Mail.com" -> "user_at_mail_dot_com". Returns false if the address is
// empty, too long or contains characters other than a-z 0-9 . _ + - @.
bool sg_email_to_uid(const char* email, char* out, size_t out_len);

// "2026-11-15T14:03:10" in local time (no offset suffix: the app parses it as local).
void sg_local_iso8601(int64_t unix_s, int tz_offset_min, char* out, size_t out_len);

// "hd_1763200000123"
void sg_record_key(int64_t unix_ms, char* out, size_t out_len);

// JSON bodies. Return the length, or -1 if the buffer is too small.
int sg_vitals_json(char* out, size_t out_len, const SgVitalsRecord* r, const char* key);
// `end_unix_ms`: unix time of the window's last sample, < 0 if the clock is not set ("ts" is then
// null); `age_ms`: how long ago the window ended. A PC that receives the line can always compute the
// time of the first sample as  now - age_ms / 1000 - 512 / fs.
int sg_raw_window_json(char* out, size_t out_len, const SgWindow* w, int64_t end_unix_ms, uint32_t age_ms,
                       const char* device_id);
int sg_event_json(char* out, size_t out_len, int64_t unix_s, int tz_offset_min, const char* type, const char* note);

// One line for the USB console: {"t":"<type>","<field>":<json>}\n . Returns the length, or -1.
int sg_console_line(char* out, size_t out_len, const char* type, const char* field, const char* json);

// "<db_url>/<node>/<uid>/<leaf>/<key>.json[?auth=...]"; pass leaf = NULL for "<node>/<uid>/<key>".
int sg_db_url(char* out, size_t out_len, const char* db_url, const char* node, const char* uid, const char* leaf,
              const char* key, const char* auth);

#define SG_RAW_JSON_MAX 9216   // enough for 2 x 512 values of up to 6 digits plus the header
