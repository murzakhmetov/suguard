#pragma once
#include <cstdint>

int esp_sleep_enable_timer_wakeup(uint64_t time_in_us);
void esp_deep_sleep_start();
