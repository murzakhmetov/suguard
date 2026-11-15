#pragma once
#include <cstdint>

typedef enum { ESP_SLEEP_WAKEUP_UNDEFINED = 0, ESP_SLEEP_WAKEUP_TIMER = 4, ESP_SLEEP_WAKEUP_GPIO = 7 } esp_sleep_wakeup_cause_t;
typedef enum { ESP_GPIO_WAKEUP_GPIO_LOW = 0, ESP_GPIO_WAKEUP_GPIO_HIGH = 1 } esp_deepsleep_gpio_wake_up_mode_t;

int esp_sleep_enable_timer_wakeup(uint64_t time_in_us);
int esp_deep_sleep_enable_gpio_wakeup(uint64_t gpio_pin_mask, esp_deepsleep_gpio_wake_up_mode_t mode);
esp_sleep_wakeup_cause_t esp_sleep_get_wakeup_cause();
void esp_deep_sleep_start();
