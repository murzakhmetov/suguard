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
* optional Wi-Fi upload of one averaged record per minute to Firebase.

It does **not** output glucose. There is no validated glucose model for this sensor (see
[../ml/README.md](../ml/README.md)); the firmware is built so that collecting the data needed for
one is easy (`tools/suguard_monitor.py --record`).

> **Read this first.** This firmware has never run on the real board: I had the KiCad files but no
> hardware, and the ESP32 toolchain cannot be downloaded in the environment where it was written.
> What was verified instead is listed under [Verification](#verification). Expect a first-flash
> debugging session; the [bring-up checklist](#bring-up-checklist) is ordered to make it short.

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
pio run -t upload
pio device monitor
```

No external libraries are needed (the MAX30102 driver is part of the firmware).

## Bring-up checklist

Open a serial terminal at 115200 baud (or `python firmware/tools/suguard_monitor.py --port <port>`)
and type `status`.

| Step | Expected | If not |
|---|---|---|
| 1. `status` | `sensor: settling` or `active`, `part 0x15` | `no_sensor` + rising `i2c errors` → I²C level jumper on the sensor module must be on 3V3 ([HARDWARE.md](docs/HARDWARE.md) note 1) |
| 2. `led red` | the sensor glows visibly red for 5 s | dark → `set swap_red_ir 1`, `save` |
| 3. Bracelet on the wrist, keep still | every ~10 s a line `{"t":"vitals",...,"reliable":true,"hr":...}`; `dc` between 40 000 and 180 000 | `no_contact` → sensor not touching skin; `weak_pulse` → tighten the strap; `adc_saturated` → strong light on the sensor |
| 4. `status` after a minute | `lost samples 0`, `fs` ≈ 50 Hz | lost samples growing → tell me, the task timing needs a look |
| 5. Compare with a finger pulse oximeter at rest | heart rate within a few bpm | — |
| 6. `wifi <ssid> <password>`, `user <e-mail of the app account>`, `save` | `status` shows `wifi: connected`, `cloud <uid>`, `uploads ok` counting up | `tls` errors → check the date/time (`time ok`) |
| 7. Battery: `status` vs a multimeter | within ~3 % | `set bat_cal <multimeter / reported>`, `save` |

SpO2 is computed with Maxim's generic calibration curve and is marked `spo2Calibrated: false`:
treat it as indicative until it has been calibrated against a medical oximeter.

## Console

```
status                 sensor, battery, Wi-Fi and last readings
get [key]              show settings
set <key> <value>      change a setting (then 'save')
wifi <ssid> [password] set the Wi-Fi network
user <email>           account e-mail used in the SuGuard app
stream on|off          print raw PPG windows on USB (for the PC tools)
led red|ir|both|off    light one LED for 5 s
mark [text]            store an event marker (the BOOT button does the same)
save / defaults / reboot
```

Settings (`get` lists them with explanations): `report_interval_s`, `cloud`, `upload_raw`,
`use_nn`, `swap_red_ir`, `led_init`, `led_max`, `adc_range`, `ir_dc_min`, `bat_cal`,
`tz_offset_min`, `device_id`, `db_url`, `db_auth`, `tls_insecure`.

## Output

One line per window on USB:

```json
{"t":"vitals","seq":12,"reliable":true,"hr":71.6,"spo2":97.1,"sqi":0.98,"pi":1.02,"motion":0.00,
 "reasons":"","nn":true,"dc":[88211,126034],"led":[35,38],"temp":31.50,"fs":50.012,"proc_ms":612,"bat":87,"usb":false}
```

`reasons` says why a window was rejected: `no_contact`, `adc_saturated`, `led_current_too_high`,
`weak_pulse`, `implausible_amplitude`, `motion`, `irregular_or_noisy`, `red_ir_inconsistent`,
`no_heart_rate`. `hr` is corrected for the sensor's clock error (`fs` is the measured sample rate).

Every `report_interval_s` (default 60 s), if at least one window was reliable, one record with the
medians goes to USB (`"t":"record"`) and, if Wi-Fi and `user` are set, to Firebase:

```
PUT <db_url>/users/<uid>/vitals/hd_<unix ms>.json
{"id":"hd_1794700060000","timestamp":"2026-11-15T04:47:40","ts":1794700060,"pulse":71.6,"spo2":97.1,
 "sqi":0.98,"windows":6,"reliableWindows":5,"spo2Windows":5,"battery":87,"charging":false,
 "sensorTempC":31.5,"spo2Calibrated":false,"device":"SG-001","fw":"1.0.0","model":"edge-nn"}
```

`<uid>` is derived from the e-mail exactly as the Flutter app does, so the records land under the
user's own node. Up to 6 records are kept in RAM while offline.

**The current app does not show these records yet.** It reads `users/<uid>/healthData` and
requires a `glucose` number in every entry, which this firmware will not invent. Updating the app
to read `vitals` (or to accept entries without glucose) is a small change that I left for you to
decide — see the question in the hand-over notes.

## How it works

```
sampler task (50 ms, high priority)            loop() (low priority)
  MAX30102 FIFO → 512-sample windows   ──►     sg_process_window()
  LED AGC, wear detection, recovery              sensor checks → DC removal + band-pass
                                                 → integer U-Net denoiser (95 k weights)
                                                 → beats, heart rate, SpO2, quality gates
                                               → USB JSON, aggregation, Firebase
```

* `src/drivers/max30102.*` — register-level driver (no third-party library).
* `src/app/sampler.*` — FIFO draining, window assembly, loss detection, automatic LED current,
  standby when not worn, sample-rate measurement.
* `src/core/` — the portable signal core: `sg_dsp`/`sg_vitals` (C++ twin of the Python reference in
  `ml/suguard_ml`), `sg_nn` (integer network engine), `sg_model.h` (generated weights),
  `sg_pipeline` (the whole chain for one window). No Arduino dependencies, no heap.
* `src/app/` — battery, settings, console, record formatting, aggregation.
* `suguard.ino` — board glue: Wire, Wi-Fi, HTTPS, flash storage, tasks.

Because the sampler runs in its own higher-priority task, long work in `loop()` (the network, a
slow HTTPS request) cannot make it miss samples; if it ever does, the chip's overflow counter
reports it and the affected window is discarded rather than analysed with a gap.

## Verification

Everything below runs with `python -m pytest firmware/tests` (needs `g++`; the RV32 test also needs
`gcc-riscv64-unknown-elf`, `picolibc-riscv64-unknown-elf` and `qemu-system-misc`).

| What | How | Result |
|---|---|---|
| Signal core = Python reference | C++ built for the host, compared on simulated windows (clean, every artefact type, edge cases) | RESULT_CORE |
| Integer network = Python reference | bit-exact comparison of the C++ engine with the NumPy integer reference | RESULT_NN |
| Whole pipeline per window | `sg_process_window` vs the Python pipeline, 304 windows × 2 modes | RESULT_PIPE |
| Device layer | driver + sampler against a register-level MAX30102 simulator: bring-up, FIFO overflow, AGC, standby/wake, brown-out reset, bus errors, clock error, LED test — built with ASan/UBSan | 14 scenarios pass |
| The sketch itself | `suguard.ino` compiled against a mock of the Arduino API and run end-to-end on simulated PPG: serial output, uploads, standby, missing sensor, empty battery | RESULT_SIM |
| RISC-V target | core cross-compiled for RV32IMC (the ESP32-C3's instruction set, soft-float) and run under QEMU | RESULT_RV32 |

Not verified: compilation with the real ESP32 Arduino core, anything that depends on the actual
hardware (I²C timing, Wi-Fi/TLS, flash storage, ADC readings, power consumption), and signal
quality on a real wrist.

### Cost on the ESP32-C3 (estimate)

BENCH_TABLE

## Regenerating generated files

```bash
python ml/scripts/export_edge_model.py     # src/core/sg_model.h from the trained edge model
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
