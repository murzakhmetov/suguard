// What the bracelet still has to upload: averaged records and markers, kept
// in RAM in compact form while there is no connection (about four hours of
// records). The JSON is only built at upload time.
//
// Items created before the clock was set carry the time since boot instead
// of a unix time; set_boot_time() converts them once the clock is known, so
// nothing recorded in the first seconds after power-up is lost.
#pragma once

#include <stddef.h>
#include <stdint.h>

#define SG_STORE_RECORDS 240   // one per report interval: 4 h at the default 60 s
#define SG_STORE_MARKERS 16
#define SG_MARKER_NOTE_MAX 48  // including the terminating zero

enum SgStoredFlag : uint8_t {
  SG_SF_UNIX_TIME = 1u << 0,   // t_ms is unix time (else: milliseconds since boot)
  SG_SF_CHARGING = 1u << 1,
  SG_SF_NEURAL = 1u << 2,      // computed with the neural denoiser
  SG_SF_HAS_SPO2 = 1u << 3,
  SG_SF_HAS_TEMPERATURE = 1u << 4,
};

struct SgStoredRecord {
  int64_t t_ms;                // end of the report interval
  float pulse_bpm;
  float spo2;
  float sqi;
  float temperature_c;
  uint16_t windows;
  uint16_t reliable_windows;
  uint16_t spo2_windows;
  int8_t battery_percent;      // -1 = unknown
  uint8_t flags;               // SgStoredFlag
};

struct SgStoredMarker {
  int64_t t_ms;
  uint8_t flags;               // SG_SF_UNIX_TIME
  char note[SG_MARKER_NOTE_MAX];
};

enum class SgStoredKind : uint8_t { kNone, kMarker, kRecord };

class SgStore {
 public:
  // Both return false if the oldest entry had to be dropped to make room.
  bool add_record(const SgStoredRecord& r);
  bool add_marker(int64_t t_ms, bool unix_time, const char* note);

  int records() const { return n_records_; }
  int markers() const { return n_markers_; }
  int pending() const { return n_records_ + n_markers_; }
  uint32_t dropped() const { return dropped_; }

  // The clock became known: unix time (ms) of the moment the device booted.
  void set_boot_time(int64_t boot_unix_ms);

  // Oldest item first, markers before records (they are few and small).
  SgStoredKind next() const;
  const SgStoredRecord& record() const { return records_[rec_head_]; }
  const SgStoredMarker& marker() const { return markers_[mark_head_]; }
  void pop();

 private:
  SgStoredRecord records_[SG_STORE_RECORDS];
  SgStoredMarker markers_[SG_STORE_MARKERS];
  int rec_head_ = 0, n_records_ = 0;
  int mark_head_ = 0, n_markers_ = 0;
  uint32_t dropped_ = 0;
};
