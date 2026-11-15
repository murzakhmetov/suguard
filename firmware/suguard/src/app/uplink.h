// When to switch the radio on, when to send and when to give up for a while.
//
// The radio is the largest consumer after the LEDs, and a server that keeps
// refusing must not turn the bracelet into a device that does TLS handshakes
// around the clock. So uploads happen in sessions:
//
//   idle --(something to send and the interval has passed)--> connecting
//        --> waiting for the clock --> sending, one item per step()
//        --> queue empty: radio off, next session after `interval_ms`
//
// A failed session (no access point, no time, transport error, server error)
// switches the radio off and doubles the waiting time (15 s ... 10 min). An
// item the server rejects for good (HTTP 4xx) is dropped so that it cannot
// block the ones behind it; 401/403 means every item would be rejected, so
// the items are kept and the next attempt comes after the longest wait.
//
// Pure logic: the board glue performs the actions and reports the results.
#pragma once

#include <stdint.h>

struct SgUplinkConfig {
  uint32_t interval_ms = 300000;        // at most one session per interval
  bool keep_connected = false;          // stay online between sessions (raw-data collection)
  uint32_t connect_timeout_ms = 20000;
  uint32_t clock_timeout_ms = 20000;
  uint32_t session_max_ms = 120000;
  uint32_t backoff_min_ms = 15000;
  uint32_t backoff_max_ms = 600000;
};

enum class SgUplinkAction : uint8_t {
  kNone,
  kRadioOn,       // WiFi.begin()
  kStartClock,    // connected: start SNTP
  kSend,          // upload the oldest item, then call sent()
  kRadioOff,      // WiFi off
};

enum class SgUplinkState : uint8_t { kIdle, kConnecting, kWaitClock, kOnline };

struct SgUplinkStats {
  uint32_t sessions = 0;
  uint32_t delivered = 0;
  uint32_t rejected = 0;          // dropped after a permanent HTTP error
  uint32_t failures = 0;          // failed sessions
  int last_code = 0;              // last HTTP status (<= 0: transport error)
};

class SgUplink {
 public:
  void configure(const SgUplinkConfig& cfg) { cfg_ = cfg; }

  // Call on every pass of the main loop. `enabled`: Wi-Fi and account are
  // configured; `pending`: items waiting; times in milliseconds since boot.
  SgUplinkAction step(uint64_t now_ms, bool enabled, int pending, bool connected, bool clock_valid);

  // Result of a kSend action. Returns true if the item is done with
  // (delivered or rejected for good) and must be removed from the store.
  bool sent(uint64_t now_ms, int http_code);

  // Result of an upload outside the queue (raw windows): only failures matter.
  void extra_result(uint64_t now_ms, int http_code);

  // Forget the waiting times (settings changed: try right away).
  void retry_now();
  // Connection settings changed: drop the connection and start over with the new ones.
  void restart();

  SgUplinkState state() const { return state_; }
  bool online() const { return state_ == SgUplinkState::kOnline; }
  bool radio_on() const { return radio_on_; }
  const SgUplinkStats& stats() const { return stats_; }
  uint32_t wait_ms(uint64_t now_ms) const;      // time until the next attempt may start (0 = none pending)

 private:
  void fail(uint64_t now_ms, uint32_t min_wait_ms);
  void end_session(uint64_t now_ms);

  SgUplinkConfig cfg_;
  SgUplinkState state_ = SgUplinkState::kIdle;
  SgUplinkStats stats_;
  bool radio_on_ = false;
  bool off_pending_ = false;
  uint64_t state_since_ms_ = 0;
  uint64_t session_start_ms_ = 0;
  uint64_t not_before_ms_ = 0;       // earliest start of the next session
  uint32_t backoff_ms_ = 0;
};
