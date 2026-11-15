// Minimal stand-in for the Arduino-ESP32 API, only for building and running
// suguard.ino on a PC (tests/test_firmware_sim.py). Signatures follow the real
// core so that the sketch is at least type-checked against them.
#pragma once

#include <cstdarg>
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>

#define INPUT_PULLUP 0x05
#define LOW 0
#define HIGH 1
#define pdTRUE 1
#define pdFALSE 0
#define portMAX_DELAY 0xFFFFFFFFu
#define pdMS_TO_TICKS(ms) (ms)

typedef uint32_t TickType_t;
typedef void* SemaphoreHandle_t;
typedef void* TaskHandle_t;
typedef void (*TaskFunction_t)(void*);

// ---- host simulation hooks (implemented in fw_sim.cpp) ----
uint32_t millis();
void delay(uint32_t ms);
void pinMode(int pin, int mode);
int digitalRead(int pin);
uint32_t analogReadMilliVolts(int pin);
bool setCpuFrequencyMhz(uint32_t mhz);
void configTime(long gmt_offset_s, int daylight_offset_s, const char* server1, const char* server2 = nullptr);

SemaphoreHandle_t xSemaphoreCreateMutex();
int xSemaphoreTake(SemaphoreHandle_t s, TickType_t ticks);
int xSemaphoreGive(SemaphoreHandle_t s);
int xTaskCreate(TaskFunction_t fn, const char* name, uint32_t stack, void* arg, int prio, TaskHandle_t* handle);
TickType_t xTaskGetTickCount();
void vTaskDelayUntil(TickType_t* last, TickType_t ticks);

class String {
 public:
  String(const char* s = "") : s_(s ? s : "") {}
  const char* c_str() const { return s_.c_str(); }

 private:
  std::string s_;
};

class HWCDC {
 public:
  size_t setTxBufferSize(size_t n);
  void begin(unsigned long baud);
  operator bool() const;                     // a PC is connected and reading
  int availableForWrite();
  size_t write(const uint8_t* data, size_t n);
  size_t print(const char* s);
  int available();
  int read();
};
extern HWCDC Serial;

class EspClass {
 public:
  uint32_t getFreeHeap();
  uint32_t getMinFreeHeap();
  uint32_t getMaxAllocHeap();
  void restart();
};
extern EspClass ESP;
