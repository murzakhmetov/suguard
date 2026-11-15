// Persistent settings of the bracelet (stored in NVS by the board glue).
#pragma once

#include <stddef.h>
#include <stdint.h>

#define SG_CONFIG_VERSION 1

struct SgConfig {
  uint16_t version;
  char wifi_ssid[33];
  char wifi_pass[65];
  char user_email[96];        // SuGuard account; the Firebase user node is derived from it
  char device_id[24];         // e.g. SG-001 (shown in the app settings)
  char db_url[128];           // Firebase Realtime Database root, no trailing slash
  char db_auth[160];          // optional database secret / ID token (sent as ?auth=)
  int16_t tz_offset_min;      // local time = UTC + this (Kazakhstan: 300)
  uint16_t report_interval_s; // one averaged record per interval
  uint8_t cloud;              // upload vitals records
  uint8_t upload_raw;         // also upload every raw window (data collection; ~8 kB per 10 s)
  uint8_t stream_raw;         // print raw windows on USB serial
  uint8_t use_nn;             // on-device denoiser (0 = classical signal processing only)
  uint8_t swap_red_ir;        // clone MAX30102 modules with exchanged LEDs
  uint8_t tls_insecure;       // debugging only: skip TLS certificate verification
  uint8_t led_init;           // LED current register at start, 0.2 mA per step
  uint8_t led_max;
  uint8_t adc_range;          // MAX30102 ADC range code 0..3 (2048..16384 nA)
  float ir_dc_min;            // "not worn" threshold on the IR level (counts)
  float bat_cal;              // battery voltage calibration factor
};

void sg_config_defaults(SgConfig* c);

// Text access for the serial console. Keys: see sg_config_key().
// set: returns false and writes a message to `err` if the key is unknown or the value invalid.
bool sg_config_set(SgConfig* c, const char* key, const char* value, char* err, size_t err_len);
// get: secrets are masked unless `reveal` is true.
bool sg_config_get(const SgConfig* c, const char* key, char* out, size_t out_len, bool reveal);
// Iterate over the keys: returns NULL past the end.
const char* sg_config_key(int index);
const char* sg_config_help(int index);
