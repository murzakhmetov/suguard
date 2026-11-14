/*
 * SuGuard raw PPG streamer: ESP32 + MAX30102 -> SuGuard ML API / Firebase.
 *
 * Reference implementation (not compiled on hardware in this repo's CI):
 * check the pin-out, LED current and the RED/IR channel order on your board
 * before use.
 *
 * Why raw data: the ML pipeline (motion-artefact denoiser, SpO2 ratio of
 * ratios, PPG morphology for glucose) needs the raw 18-bit red and IR
 * samples. Final numbers computed on the ESP32 cannot be cleaned afterwards.
 *
 * What it does
 *   - samples MAX30102 at 100 Hz (400 sps internal, 4x averaging), both LEDs
 *   - core 1: drains the 32-sample FIFO every 20 ms into 10.24 s windows
 *   - core 0: sends each finished window as JSON
 *       MODE_API      -> POST {API_URL}/v1/analyze, prints HR/SpO2/quality
 *       MODE_COLLECT  -> PUT  {FIREBASE_URL}/rawPpg/{DEVICE_ID}/{ts}.json
 *                        (training data, see ml/docs/DATA_COLLECTION.md)
 *
 * Libraries: "SparkFun MAX3010x Pulse and Proximity Sensor Library" (MAX30105.h),
 *            ESP32 Arduino core >= 2.0 (WiFi, HTTPClient, time.h).
 */

#include <Arduino.h>
#include <HTTPClient.h>
#include <WiFi.h>
#include <Wire.h>
#include <time.h>

#include "MAX30105.h"  // SparkFun library, works with MAX30102

// ------------------------------- settings --------------------------------
#define WIFI_SSID      "your-ssid"
#define WIFI_PASS      "your-password"
#define DEVICE_ID      "SG-001"
#define USER_ID        "user-uid"          // Firebase uid the bracelet belongs to
#define API_URL        "https://your-suguard-ml-host"   // ml/api deployment
#define FIREBASE_URL   "https://suguard-7f535-default-rtdb.asia-southeast1.firebasedatabase.app"

#define MODE_API       1
#define MODE_COLLECT   2
#define MODE           MODE_API

// Some MAX30102 breakout boards report the LEDs swapped in this library.
// With a finger on the sensor at equal LED current, IR DC is normally the
// larger one; if red > IR consistently, set this to 1.
#define SWAP_RED_IR    0

#define FS_HZ          100
#define WINDOW_N       1024                 // 10.24 s at 100 Hz
#define I2C_SDA        21
#define I2C_SCL        22

// --------------------------------------------------------------------------
MAX30105 sensor;

struct Window {
  uint32_t red[WINDOW_N];
  uint32_t ir[WINDOW_N];
  uint32_t ts;          // unix seconds of the first sample
  float temperature_c;
};

static Window buffers[2];
static QueueHandle_t readyQueue;     // indices of full windows
static QueueHandle_t freeQueue;      // indices of empty windows

static void samplerTask(void *) {
  int idx;
  xQueueReceive(freeQueue, &idx, portMAX_DELAY);
  int n = 0;
  for (;;) {
    sensor.check();                        // reads new FIFO samples over I2C
    while (sensor.available()) {
      uint32_t r = sensor.getFIFORed();
      uint32_t i = sensor.getFIFOIR();
      sensor.nextSample();
      if (n == 0) buffers[idx].ts = (uint32_t)time(nullptr);
      buffers[idx].red[n] = SWAP_RED_IR ? i : r;
      buffers[idx].ir[n] = SWAP_RED_IR ? r : i;
      if (++n == WINDOW_N) {
        buffers[idx].temperature_c = sensor.readTemperature();
        xQueueSend(readyQueue, &idx, portMAX_DELAY);
        // Get an empty buffer without blocking the FIFO for long: prefer a
        // free one; if the sender is still busy, reclaim an unsent window
        // (it is dropped) rather than losing samples mid-window.
        for (;;) {
          if (xQueueReceive(freeQueue, &idx, 0) == pdTRUE) break;
          if (xQueueReceive(readyQueue, &idx, 0) == pdTRUE) {
            Serial.println("[warn] sender too slow, dropped a window");
            break;
          }
          vTaskDelay(pdMS_TO_TICKS(2));
        }
        n = 0;
      }
    }
    vTaskDelay(pdMS_TO_TICKS(20));          // FIFO holds 32 samples = 320 ms
  }
}

static String windowJson(const Window &w) {
  String s;
  s.reserve(WINDOW_N * 16 + 256);
  s += "{\"fs\":" + String(FS_HZ) + ",\"timestamp\":" + String(w.ts) +
       ",\"temperature_c\":" + String(w.temperature_c, 2) +
       ",\"device_id\":\"" DEVICE_ID "\",\"user_id\":\"" USER_ID "\",\"red\":[";
  for (int k = 0; k < WINDOW_N; k++) { if (k) s += ','; s += w.red[k]; }
  s += "],\"ir\":[";
  for (int k = 0; k < WINDOW_N; k++) { if (k) s += ','; s += w.ir[k]; }
  s += "]}";
  return s;
}

static void sendWindow(const Window &w) {
  if (WiFi.status() != WL_CONNECTED) return;
  HTTPClient http;
  String body = windowJson(w);
  int code;
  if (MODE == MODE_API) {
    http.begin(String(API_URL) + "/v1/analyze");
    http.addHeader("Content-Type", "application/json");
    code = http.POST(body);
  } else {
    http.begin(String(FIREBASE_URL) + "/rawPpg/" DEVICE_ID "/" + String(w.ts) + ".json");
    http.addHeader("Content-Type", "application/json");
    code = http.PUT(body);
  }
  Serial.printf("[net] %d, %u bytes\n", code, body.length());
  if (code == 200 && MODE == MODE_API) Serial.println(http.getString().substring(0, 400));
  http.end();
}

void setup() {
  Serial.begin(115200);
  Wire.begin(I2C_SDA, I2C_SCL);
  Wire.setClock(400000);
  if (!sensor.begin(Wire, I2C_SPEED_FAST)) {
    Serial.println("MAX30102 not found");
    for (;;) delay(1000);
  }
  // ledBrightness 0x24 (~7 mA), sampleAverage 4, ledMode 2 (red+IR),
  // sampleRate 400 -> 100 Hz output, pulseWidth 411 us (18 bit), adcRange 16384 nA.
  // Lower the LED current if the IR DC sits near 262143 (saturation).
  sensor.setup(0x24, 4, 2, 400, 411, 16384);
  sensor.enableDIETEMPRDY();

  WiFi.begin(WIFI_SSID, WIFI_PASS);
  while (WiFi.status() != WL_CONNECTED) { delay(300); Serial.print('.'); }
  configTime(0, 0, "pool.ntp.org", "time.google.com");   // UTC unix time
  while (time(nullptr) < 1700000000) delay(200);
  Serial.println("\nready");

  readyQueue = xQueueCreate(2, sizeof(int));
  freeQueue = xQueueCreate(2, sizeof(int));
  for (int k = 0; k < 2; k++) xQueueSend(freeQueue, &k, 0);
  xTaskCreatePinnedToCore(samplerTask, "sampler", 4096, nullptr, 3, nullptr, 1);
}

void loop() {
  int idx;
  if (xQueueReceive(readyQueue, &idx, portMAX_DELAY) == pdTRUE) {
    sendWindow(buffers[idx]);
    xQueueSend(freeQueue, &idx, portMAX_DELAY);
  }
}
