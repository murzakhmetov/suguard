#include "store.h"

#include <string.h>

bool SgStore::add_record(const SgStoredRecord& r) {
  bool kept_all = true;
  if (n_records_ == SG_STORE_RECORDS) {                // full: the oldest record makes room
    rec_head_ = (rec_head_ + 1) % SG_STORE_RECORDS;
    n_records_--;
    dropped_++;
    kept_all = false;
  }
  records_[(rec_head_ + n_records_) % SG_STORE_RECORDS] = r;
  n_records_++;
  return kept_all;
}

bool SgStore::add_marker(int64_t t_ms, bool unix_time, const char* note) {
  bool kept_all = true;
  if (n_markers_ == SG_STORE_MARKERS) {
    mark_head_ = (mark_head_ + 1) % SG_STORE_MARKERS;
    n_markers_--;
    dropped_++;
    kept_all = false;
  }
  SgStoredMarker& m = markers_[(mark_head_ + n_markers_) % SG_STORE_MARKERS];
  m.t_ms = t_ms;
  m.flags = unix_time ? SG_SF_UNIX_TIME : 0;
  size_t n = note ? strlen(note) : 0;
  if (n >= sizeof m.note) n = sizeof m.note - 1;
  memcpy(m.note, note ? note : "", n);
  m.note[n] = '\0';
  n_markers_++;
  return kept_all;
}

void SgStore::set_boot_time(int64_t boot_unix_ms) {
  for (int i = 0; i < n_records_; i++) {
    SgStoredRecord& r = records_[(rec_head_ + i) % SG_STORE_RECORDS];
    if (r.flags & SG_SF_UNIX_TIME) continue;
    r.t_ms += boot_unix_ms;
    r.flags |= SG_SF_UNIX_TIME;
  }
  for (int i = 0; i < n_markers_; i++) {
    SgStoredMarker& m = markers_[(mark_head_ + i) % SG_STORE_MARKERS];
    if (m.flags & SG_SF_UNIX_TIME) continue;
    m.t_ms += boot_unix_ms;
    m.flags |= SG_SF_UNIX_TIME;
  }
}

SgStoredKind SgStore::next() const {
  if (n_markers_) return SgStoredKind::kMarker;
  if (n_records_) return SgStoredKind::kRecord;
  return SgStoredKind::kNone;
}

void SgStore::pop() {
  if (n_markers_) {
    mark_head_ = (mark_head_ + 1) % SG_STORE_MARKERS;
    n_markers_--;
  } else if (n_records_) {
    rec_head_ = (rec_head_ + 1) % SG_STORE_RECORDS;
    n_records_--;
  }
}
