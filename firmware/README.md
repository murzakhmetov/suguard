# SuGuard bracelet firmware

Firmware for the SuGuard board (ESP32-C3-WROOM-02 + MH-ET LIVE MAX30102 module, TP4056 charger).
Pin map and hardware notes: [docs/HARDWARE.md](docs/HARDWARE.md).

What it does:

* samples raw red/IR PPG at 50 Hz in gap-free 10.24-s windows (automatic LED current, wear
  detection, recovery from sensor resets and lost samples);
* runs the whole signal pipeline **on the bracelet**: a small neural network (integer arithmetic,
  no FPU needed) removes motion artefacts, then heart rate, SpO2 and nine signal-quality checks are
  computed; a value is reported only if the window passes every check;
* USB console (115200 baud): live results as JSON lines, settings, raw-data streaming for the PC tools;
* optional upload to Firebase: one averaged record per minute, sent in a short Wi-Fi session every
  five minutes; about four hours of records are kept while there is no connection.

It does **not** output glucose. There is no validated glucose model for this sensor (see
[../ml/README.md](../ml/README.md)); the firmware is built so that collecting the data needed for
one is easy (`tools/suguard_monitor.py --record`).

> **Read this first.** This firmware has never run on the real board and has never been built
> with the ESP32 toolchain: I had the KiCad files but no hardware, and the toolchain could not be
> run where the firmware was written. Every source file was type-checked against the real
> Arduino-ESP32 headers (cores 2.0.17 and 3.3.12), but that is not a build. What was verified is
> listed under [Verification](#verification). Expect a first-build and first-flash debugging
> session; the [bring-up checklist](#bring-up-checklist) is ordered to make it short. If the
> compiler or the linker reports an error, send me its output.

## Build and flash

**Arduino IDE 2.x**

1. Boards Manager → install **esp32 by Espressif Systems**, version 3.x.
2. Open `firmware/suguard/suguard.ino`.
3. Tools → Board **ESP32C3 Dev Module**; **USB CDC On Boot: Enabled**; CPU Frequency 160 MHz;
   Flash Size 4MB; Partition Scheme **Minimal SPIFFS (1.9MB APP with OTA)**.
4. Connect USB-C, select the port, Upload. If no port appears: hold **S2** (BOOT), tap **S1**
   (RESET), release S2, then upload.

**PlatformIO**

```bash
cd firmware/suguard
pio run -t upload            # Arduino core 2.0.17; or: pio run -e suguard-core3 -t upload  (core 3.x)
pio device monitor
```

No external libraries are needed (the MAX30102 driver is part of the firmware). The sketch only
uses functions that exist in both Arduino core 2.0.17 and 3.x. With core 2.0.x the Arduino IDE
compiles as C++11, which is too old for this code: use core 3.x in the IDE, or PlatformIO.

## Bring-up checklist

Open a serial terminal at 115200 baud (or `python firmware/tools/suguard_monitor.py --port <port>`)
and type `status`.

| Step | Expected | If not |
|---|---|---|
| 1. `status` | `sensor: settling` or `active`, `part 0x15` | `no_sensor` + rising `i2c errors` → I²C level jumper on the sensor module must be on 3V3 ([HARDWARE.md](docs/HARDWARE.md) note 1) |
| 2. `led red` | the sensor glows visibly red for 5 s | dark → `set swap_red_ir 1`, `save` (the firmware also prints a hint after a minute of wearing) |
| 3. Bracelet on the wrist, keep still | every ~10 s a line `{"t":"vitals",...,"reliable":true,"hr":...}`; `dc` between 40 000 and 180 000 | `no_contact` → sensor not touching skin; `weak_pulse` → tighten the strap; `adc_saturated` → strong light on the sensor; `denoiser_mismatch` on most windows → tell me (the network does not fit your signal) |
| 4. `status` after a minute | `lost samples 0`, `no-data timeouts 0`, `fs` ≈ 50 Hz; note `proc_ms` in the vitals lines | lost samples growing, or `proc_ms` above 5000 → tell me |
| 5. Compare with a finger pulse oximeter at rest | heart rate within a few bpm | — |
| 6. `wifi <ssid> <password>`, `user <e-mail of the app account>`, `save` | within a minute or two `status` shows `time ok`, `delivered` counting up, `last http 200` | `last http 401`/`403` → database rules or `db_auth`; `last http -1` → no connection or TLS; then check `heap: ... lowest` (HARDWARE.md note 13) |
| 7. Battery: `status` vs a multimeter (USB unplugged) | within ~3 % | `set bat_cal <multimeter / reported>`, `save` |
| 8. Unplug USB, wear it until it stops | note the runtime (HARDWARE.md note 14) | — |

SpO2 is computed with Maxim's generic calibration curve and is marked `spo2Calibrated: false`:
treat it as indicative until it has been calibrated against a medical oximeter.

## Console

```
status                 sensor, battery, Wi-Fi, uploads, memory
get [key]              show settings
set <key> <value>      change a setting (then 'save')
wifi <ssid> [password] set the Wi-Fi network
user <email>           account e-mail used in the SuGuard app
stream on|off          print raw PPG windows on USB (for the PC tools)
led red|ir|both|off    light one LED for 5 s
mark [text]            store an event marker (the BOOT button does the same)
save / defaults / reboot
```

Settings (`get` lists them with explanations):

| Setting | Default | Meaning |
|---|---|---|
| `report_interval_s` | 60 | one averaged record per interval (20–600) |
| `upload_interval_s` | 300 | the radio is switched on at most this often (0 = stay connected) |
| `cloud`, `upload_raw` | 1, 0 | upload records / also every raw window (data collection; keeps Wi-Fi on) |
| `use_nn` | 1 | 0 = classical signal processing only: for diagnostics, it cannot tell rhythmic motion from a pulse |
| `sensor_sps`, `cpu_mhz` | 400, 160 | power options, see [HARDWARE.md](docs/HARDWARE.md) note 14 |
| `swap_red_ir`, `led_init`, `led_max`, `adc_range`, `ir_dc_min` | 0, 63, 127, 1, 20000 | sensor |
| `bat_cal`, `tz_offset_min`, `device_id`, `db_url`, `db_auth`, `tls_insecure` | | calibration, time zone (300 = UTC+5), cloud |

## Output

One line per window on USB:

```json
{"t":"vitals","seq":12,"reliable":true,"hr":71.6,"spo2":97.1,"sqi":0.98,"pi":1.020,"motion":0.00,
 "reasons":"","spo2_why":"","nn":true,"dc":[88211,126034],"led":[35,38],"temp":31.50,"fs":50.012,
 "proc_ms":1400,"bat":87,"usb":false}
```

`reasons` is filled only for a rejected window and says why: `no_contact`, `adc_saturated`,
`weak_pulse`, `implausible_amplitude`, `motion`, `irregular_or_noisy`, `red_ir_inconsistent`,
`denoiser_mismatch` (the cleaned-up pulse is not supported by the measured signal), and
`led_current_too_high` as an extra note (the level is near the top of the ADC range; the LED
control lowers the current). `spo2_why` is filled only for an accepted window without an SpO2
value: `no_common_pulse`, `spo2_low_red_ir_agreement`, `red_ir_inconsistent` (the two
wavelengths do not agree well enough) or `red_denoiser_mismatch` (the cleaned-up red pulse is not
supported by the measurement). `hr` is corrected for the sensor's clock error (`fs` is the measured
sample rate). The rules behind each reason are listed in
[../ml/docs/MODEL_CARD.md](../ml/docs/MODEL_CARD.md#2-the-decision-to-report-a-value).

Every `report_interval_s`, if at least one window was reliable, one record with the medians goes to
USB (`"t":"record"`) and, if Wi-Fi and `user` are set, to Firebase:

```
PUT <db_url>/users/<uid>/vitals/hd_<unix ms>.json
{"id":"hd_1794700060050","timestamp":"2026-11-15T04:47:40","ts":1794700060,"pulse":71.6,"spo2":97.1,
 "sqi":0.98,"windows":6,"reliableWindows":5,"spo2Windows":5,"battery":87,"charging":false,
 "sensorTempC":31.5,"spo2Calibrated":false,"device":"SG-001","fw":"1.2.0","model":"edge-nn"}
```

`<uid>` is derived from the e-mail exactly as the Flutter app does, so the records land under the
user's own node. Markers go to `users/<uid>/events`, raw windows (only with `upload_raw`) to
`rawPpg/<uid>`.

Uploads happen in sessions: Wi-Fi on, clock from NTP, send what is waiting, Wi-Fi off. Records
and markers made while offline are kept in RAM (240 records = 4 h at one per minute, 16 markers;
the oldest are dropped first, and a reboot or an empty battery loses them) and carry the time they
were made, also those from before the clock was first set. If the server or the network fails, the
next attempt comes after 15 s, 30 s, ... up to 10 minutes (immediately 10 minutes after HTTP
401/403); a record the server rejects for good (a 4xx other than 401, 403, 408 and 429) is
dropped so that it cannot block the queue. `status` shows all of this.

**The current app does not show these records yet.** It reads `users/<uid>/healthData` and
requires a `glucose` number in every entry, which this firmware will not invent. Updating the app
to read `vitals` (or to accept entries without glucose) is a small change that I left for you to
decide.

## How it works

```
sampler task (50 ms, high priority)            loop() (low priority)
  MAX30102 FIFO → 512-sample windows   ──►     sg_process_window()
  LED AGC, wear detection, recovery              sensor checks → DC removal + band-pass
  BOOT button                                    → integer U-Net denoiser (95 k weights)
                                                 → beats, heart rate, SpO2, quality gates
                                               → USB JSON, aggregation, record store → upload sessions
```

* `src/drivers/max30102.*` — register-level driver (no third-party library).
* `src/app/sampler.*` — FIFO draining, window assembly, loss detection, automatic LED current,
  standby when not worn, rest when there is no pulse, sample-rate measurement.
* `src/core/` — the portable signal core: `sg_dsp`/`sg_vitals` (C++ twin of the Python reference in
  `ml/suguard_ml`), `sg_nn` (integer network engine), `sg_model.h` (generated weights),
  `sg_pipeline` (the whole chain for one window). No Arduino dependencies, no heap.
* `src/app/uplink.*`, `store.*`, `power.*` — when to use the radio, what is waiting to be sent,
  when the battery is empty: pure logic, tested on the PC.
* `src/app/` (rest) — battery, settings, console, record formatting, aggregation.
* `suguard.ino` — board glue: Wire, Wi-Fi, HTTPS, flash storage, tasks.

Because the sampler runs in its own higher-priority task, long work in `loop()` (the network, a
slow HTTPS request) cannot make it miss samples; if it ever does, the chip's overflow counter
reports it and the affected window is discarded rather than analysed with a gap.

Behaviour worth knowing:

* **Not worn** (too little light comes back even at full LED current): the sensor is shut down and
  probed for 0.3 s every 3 s.
* **No pulse for a minute** although light comes back (lying on a table, in a bag): the sensor
  rests and looks again when the reflected level changes, or after 5 minutes.
* **Battery empty** (≤ 3.45 V for a minute, no USB): sensor off, deep sleep. It looks again every
  10 minutes and resumes above 3.60 V or when USB power is there (press S1 to start at once after
  plugging in the charger).
* **The denoiser is not trusted blindly.** A neural network can draw a pulse that is not there.
  On the samples it calls clean, its output must match the measured signal (correlation ≥ 0.7,
  size within 0.7–1.4) or the window (IR) / the SpO2 value (red) is withheld. Where it flags at
  most 20 % of the window as motion, the measured signals are the reference: SpO2 comes from the
  measured red/IR, the rate of the detected beats must agree with the spectrum of the measured IR,
  and the red/IR ratio must be stable in the measured signals (a network can attenuate red at fast
  rates, or suppress the fundamental of a slow, double-humped pulse; windows it flags more heavily
  keep its own output as the reference). Wherever the network is used, SpO2 is shown only if the
  measured red/IR (weighted by its mask) and its output give values within 2 points of each other.
  See `ml/README.md`, "Known hard cases", for what this catches and what it costs.

## Verification

Everything below except the first row runs with `python -m pytest firmware/tests` (45 tests; needs
`g++`; the RV32 tests also need `gcc-riscv64-unknown-elf`, `picolibc-riscv64-unknown-elf` and
`qemu-system-misc`). The first row is a 46th test that runs when `SG_ARDUINO_CACHE` names a folder
that `tools/typecheck_arduino.sh <folder>` has filled once (that first run downloads the Arduino
packages from GitHub, about 370 MB); it needs `arm-none-eabi-g++`.

| What | How | Result |
|---|---|---|
| Sources against the real Arduino API | `tools/typecheck_arduino.sh`: the sketch and every source file through a GCC front end with the headers, include paths and defines of Arduino core 2.0.17 (ESP-IDF 4.4, as C++17) and 3.3.12 (ESP-IDF 5.5, as C++20) | no error, no warning; **not a build** (generic 32-bit compiler, nothing generated or linked) |
| Signal core = Python reference | C++ built for the host, compared on simulated windows: 300 classical, 200 denoised, 50 degenerate or constructed inputs (some with the measured signals given directly) | every decision identical; the tests allow 10⁻⁹ (relative) for double-precision values and 10⁻⁴ (absolute) for FFT-dependent ones; the largest differences measured are 1.7·10⁻¹⁴ and 5.4·10⁻⁷ |
| Integer network = Python reference | the C++ engine against the NumPy integer reference, random models and the shipped one | bit-exact |
| Whole pipeline per window | `sg_process_window` against the Python pipeline, 316 windows × 2 modes, incl. inputs where the network must be overruled | same decisions and reasons; heart rate and SpO2 within 10⁻⁶ |
| Device layer | driver, sampler, record store, upload scheduler and battery guard against a register-level MAX30102 simulator, with ASan/UBSan | 24 scenarios pass |
| The sketch itself | `suguard.ino` compiled against a mock of the Arduino API and run on simulated PPG for up to an hour of simulated time: vital signs against the Python pipeline, upload sessions, failing and refusing servers, an hour offline, slow processing and slow requests, button presses, sensor resets, empty battery, clock wrap-around, the USB recording path through the PC tool | 31 tests pass |
| RISC-V target | core cross-compiled for RV32IMC (the ESP32-C3's instruction set, soft-float) and run under QEMU | same results as on the PC (differences ≤ 2·10⁻¹⁶) |

Two independent reviews of the firmware (one against the toolchain and the hardware, one of its
behaviour over time) found the defects that the second half of this list now tests for; the
reviewers reproduced each in the simulator before it was fixed.

Not verified: a real build and link with the ESP32 toolchain, anything that depends on the actual
hardware (I²C timing, Wi-Fi/TLS, flash storage, ADC readings, memory head-room, power
consumption), real pre-emption between the two tasks (the simulation runs them in turn), and
signal quality on a real wrist.

### Cost on the ESP32-C3 (estimate)

| | Value | Source |
|---|---|---|
| Instructions per window, with the network | 146 million (median), 176 million (max: a window the network calls clean also gets the spectrum of the measured signal); the second SpO2 estimate of the agreement check costs about 13 million | counted exactly under QEMU for RV32IMC (`docs/rv32_benchmark.json`) |
| ... classical processing only | 77 million | same |
| Time per 10.24-s window | about 1.4–2.8 s at 160 MHz (2.7–5.5 s at 80 MHz) | estimate: 1.5–2.5 cycles per instruction; **not measured on the chip** — read `proc_ms` |
| Static RAM of the signal pipeline | 117 kB | size of the pipeline's memory block |
| Code and constants of the signal core | 126 kB (94 kB of it network weights, in flash), plus the C library's maths and soft-float routines it calls | `size` of the core's RV32 object files; the whole benchmark program (with its harness, picolibc and 24.6 kB of test windows) is 184 kB |

## Regenerating generated files

```bash
python ml/scripts/export_edge_model.py     # src/core/sg_model.h from ml/data/edge_s/denoiser_edge.pt
python firmware/tools/gen_tables.py        # src/core/sg_tables.h (filter coefficients, FFT table)
python firmware/tools/gen_certs.py         # src/certs.h (TLS root certificates)
```

## Recording data with a PC

```bash
pip install pyserial
python firmware/tools/suguard_monitor.py --port /dev/ttyACM0 --record session1 --user u01 --check
```

Stores raw windows, the firmware's results, typed-in fingersticks (`g 5.6`) and markers in the
formats the training code reads ([../ml/docs/DATA_COLLECTION.md](../ml/docs/DATA_COLLECTION.md)).
`--check` recomputes every window on the PC and reports any disagreement with the bracelet.
A bracelet without Wi-Fi has no clock; its windows are then dated with the PC's clock, the same
clock that dates the fingersticks, so keep the PC clock right.
