#include "uplink.h"

namespace {

// HTTP answers that will not change when the same item is sent again.
bool permanent_rejection(int code) { return code >= 400 && code < 500 && code != 401 && code != 403 && code != 408 && code != 429; }

}  // namespace

void SgUplink::retry_now() {
  not_before_ms_ = 0;
  backoff_ms_ = 0;
}

void SgUplink::restart() {
  state_ = SgUplinkState::kIdle;
  off_pending_ = radio_on_;
  retry_now();
}

uint32_t SgUplink::wait_ms(uint64_t now_ms) const {
  return state_ == SgUplinkState::kIdle && not_before_ms_ > now_ms ? (uint32_t)(not_before_ms_ - now_ms) : 0;
}

void SgUplink::fail(uint64_t now_ms, uint32_t min_wait_ms) {
  backoff_ms_ = backoff_ms_ ? backoff_ms_ * 2 : cfg_.backoff_min_ms;
  if (backoff_ms_ < min_wait_ms) backoff_ms_ = min_wait_ms;
  if (backoff_ms_ > cfg_.backoff_max_ms) backoff_ms_ = cfg_.backoff_max_ms;
  not_before_ms_ = now_ms + backoff_ms_;
  stats_.failures++;
  state_ = SgUplinkState::kIdle;
  off_pending_ = radio_on_;
}

void SgUplink::end_session(uint64_t now_ms) {
  (void)now_ms;
  not_before_ms_ = session_start_ms_ + cfg_.interval_ms;
  state_ = SgUplinkState::kIdle;
  off_pending_ = radio_on_;
}

SgUplinkAction SgUplink::step(uint64_t now_ms, bool enabled, int pending, bool connected, bool clock_valid) {
  if (off_pending_) {
    off_pending_ = false;
    radio_on_ = false;
    return SgUplinkAction::kRadioOff;
  }
  if (!enabled) {
    state_ = SgUplinkState::kIdle;
    if (radio_on_) {
      radio_on_ = false;
      return SgUplinkAction::kRadioOff;
    }
    return SgUplinkAction::kNone;
  }

  switch (state_) {
    case SgUplinkState::kIdle:
      if (!(cfg_.keep_connected || pending > 0) || now_ms < not_before_ms_) return SgUplinkAction::kNone;
      state_ = SgUplinkState::kConnecting;
      state_since_ms_ = session_start_ms_ = now_ms;
      radio_on_ = true;
      stats_.sessions++;
      return SgUplinkAction::kRadioOn;

    case SgUplinkState::kConnecting:
      if (connected) {
        state_ = SgUplinkState::kWaitClock;
        state_since_ms_ = now_ms;
        return SgUplinkAction::kStartClock;
      }
      if (now_ms - state_since_ms_ > cfg_.connect_timeout_ms) fail(now_ms, 0);
      return SgUplinkAction::kNone;

    case SgUplinkState::kWaitClock:
      if (!connected) {
        fail(now_ms, 0);
      } else if (clock_valid) {
        state_ = SgUplinkState::kOnline;
        state_since_ms_ = now_ms;
      } else if (now_ms - state_since_ms_ > cfg_.clock_timeout_ms) {
        fail(now_ms, 0);
      }
      return SgUplinkAction::kNone;

    case SgUplinkState::kOnline:
      if (!connected) {
        fail(now_ms, 0);
        return SgUplinkAction::kNone;
      }
      if (pending > 0) {
        if (cfg_.keep_connected || now_ms - session_start_ms_ <= cfg_.session_max_ms) return SgUplinkAction::kSend;
        end_session(now_ms);                       // took too long: continue in the next session
        return SgUplinkAction::kNone;
      }
      backoff_ms_ = 0;                             // everything delivered
      if (!cfg_.keep_connected) end_session(now_ms);
      return SgUplinkAction::kNone;
  }
  return SgUplinkAction::kNone;
}

bool SgUplink::sent(uint64_t now_ms, int http_code) {
  stats_.last_code = http_code;
  if (http_code >= 200 && http_code < 300) {
    stats_.delivered++;
    return true;
  }
  if (permanent_rejection(http_code)) {            // this item will never be accepted: do not block the rest
    stats_.rejected++;
    return true;
  }
  // Not authorised: nothing will be accepted until the settings or the database rules change.
  fail(now_ms, http_code == 401 || http_code == 403 ? cfg_.backoff_max_ms : 0);
  return false;
}

void SgUplink::extra_result(uint64_t now_ms, int http_code) {
  stats_.last_code = http_code;
  if (http_code >= 200 && http_code < 300) return;
  if (permanent_rejection(http_code)) return;
  if (state_ == SgUplinkState::kOnline) fail(now_ms, http_code == 401 || http_code == 403 ? cfg_.backoff_max_ms : 0);
}
