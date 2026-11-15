# SuGuard board — what the firmware assumes

Source: the KiCad project you sent (`SuGuard.kicad_pcb`, 36 footprints, 37 nets). The pin map
below was extracted from the PCB netlist, not from the screenshots, and is what
`firmware/suguard/src/board.h` uses.

## Parts

| Ref | Part | Role |
|---|---|---|
| U1 | ESP32-C3-WROOM-02 | MCU: single-core RISC-V (RV32IMC, **no FPU**), 4 MB flash, Wi-Fi + BLE 5, native USB |
| U4 | MH-ET LIVE MAX30102 module (bottom side, facing the skin) | PPG sensor: red 660 nm + IR 880 nm, 18-bit ADC, I²C `0x57`; the module has its own 1.8 V regulator and pull-ups |
| U3 | TP4056 (R1 = 5.1 kΩ) | Li-ion charger from USB, ≈235 mA; `CHRG`/`STDBY` drive the red/green LEDs only |
| U9 | AP2112K-3.3 | 3.3 V regulator, fed from VBAT |
| U2 | USBLC6-2SC6 | USB ESD protection |
| J1 | USB-C (CC1/CC2 5.1 kΩ to GND) | charging, flashing, serial console |
| J10 + S3 | JST-EH 2-pin + slide switch | battery; the switch opens the battery's negative lead |
| S1 / S2 | push buttons | S1 = reset (EN), S2 = BOOT (IO9), usable as a user button after start-up |

## Pin map

| ESP32-C3 pin | Net | Used for |
|---|---|---|
| IO6 | `SCL` | I²C clock to the MAX30102 module |
| IO7 | `SDA` | I²C data |
| IO10 | `MAX_INT` | sensor interrupt — **not used**: the firmware polls the FIFO (see note 2) |
| IO2 (ADC1_CH2) | `BAT_VOLTAGE` | battery voltage × 47 k / (100 k + 47 k) = 0.320 × VBAT |
| IO4 (ADC1_CH4) | `VBUS_SENSE` | USB voltage / 2 → "USB present" |
| IO9 | S2 → GND | BOOT strap; after start-up a press stores an event marker |
| IO8 | 10 kΩ pull-up | strap only |
| IO18 / IO19 | `USB_DN` / `USB_DP` | native USB: console at 115200 baud and flashing |
| EN | 10 kΩ pull-up, 100 nF, S1 | reset |
| IO0, IO1, IO3, IO5, IO20, IO21 | — | not connected |

There is no UART header: all logs go over USB, so the firmware must be built with **USB CDC On
Boot enabled**.

## Things to check on the bench (ordered by how likely they are to bite)

These are observations from the schematic. None of them was measured — I do not have the board.

1. **I²C logic level of the MAX30102 module.** The main board has no I²C pull-ups; they are on
   the MH-ET LIVE module, which has a solder jumper that ties them to either 1.8 V or 3.3 V.
   The ESP32-C3 only guarantees a "high" above 0.75 × 3.3 V = 2.48 V, so with the jumper on
   1.8 V the bus can be flaky or dead.
   *Check:* measure SDA and SCL at rest — they must read ≈3.3 V. *Symptom:* `status` shows
   `sensor: no_sensor` and a growing `i2c errors` count. *Fix:* move the jumper to 3V3.

2. **`MAX_INT` may idle at 1.8 V for the same reason.** The firmware therefore does not use the
   interrupt line at all; it reads the FIFO every 50 ms (the FIFO holds 640 ms of data).

3. **Red and IR can be exchanged on clone modules.** Type `led red` on the console: a visible
   red glow must appear for 5 s. If the sensor stays dark (IR is invisible), run
   `set swap_red_ir 1`, `save`. A wrong assignment gives nonsense SpO2.

4. **IO2 is a strapping pin and carries the battery divider.** Espressif's boot-mode table asks
   for IO2 = high at reset; the divider holds it at 1.0–1.35 V, which is neither a valid high nor
   a valid low. Many ESP32-C3 boards start fine with IO2 undefined, so this may never show, but it
   is outside the datasheet.
   *Check:* power-cycle on battery 20–30 times and confirm it always starts.
   *Fix for the next PCB revision:* route `BAT_VOLTAGE` to IO3 (free, ADC1_CH3, the neighbouring
   module pad) and give IO2 a 10 kΩ pull-up. Firmware change: one constant, `kPinBatAdc`.

5. **Charge current vs. cell size.** R1 = 5.1 kΩ sets ≈235 mA. That is right for cells of
   ~250 mAh and more; for a smaller cell raise R1 (10 kΩ → ≈120 mA).

6. **No under-voltage cut-off on the board.** Use a cell with a built-in protection circuit. The
   firmware goes to deep sleep at ≈3.45 V (below that the regulator drops out anyway), but the
   regulator, the dividers and the sensor module still draw a little.

7. **3.3 V rail under Wi-Fi bursts.** There is 4.7 µF + 4.7 µF + 100 nF on 3V3. If you see
   resets when Wi-Fi transmits, add 10–22 µF close to U1.

8. **Battery reading is noisy.** The divider has ≈32 kΩ source impedance and no capacitor at
   the ADC pin. The firmware averages; 100 nF from IO2 to GND would help. Calibrate once against
   a multimeter with `set bat_cal <multimeter V / reported V>`.

9. **The slide switch does not switch USB power.** With S3 off and USB plugged in, the board
   still runs from the charger output (without a battery behind it).

10. **No accelerometer and no MCU-controlled LED.** Motion is detected from the PPG itself (the
    denoiser uses the two wavelengths). A 3-axis accelerometer on the same I²C bus would make
    motion handling more robust in a later revision; a status LED would help pairing and debugging.

## Sensor configuration used by the firmware

| Setting | Value | Why |
|---|---|---|
| Mode | SpO2 (red + IR) | both wavelengths are needed for SpO2 and for motion rejection |
| Sample rate / averaging | 400 sps ÷ 8 = **50 Hz** output | the pipeline's native rate; 8× averaging improves SNR and acts as the anti-alias filter |
| Pulse width | 411 µs (18-bit) | best resolution |
| ADC range | 4096 nA (`adc_range` setting) | |
| LED current | starts at 12.6 mA; automatic 1.6–25.4 mA | keeps the DC level at 15–70 % of full scale; changes only between windows |
| FIFO | roll-over off, polled every 50 ms | lost samples are counted by the chip and the affected window is discarded |

The sensor's sample clock is not crystal-accurate, so the firmware measures the real output rate
against the ESP32 clock and corrects the heart rate with it (`fs` in the output).
