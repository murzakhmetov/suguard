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
   `set swap_red_ir 1`, `save`. With exchanged LEDs no window is accepted (the red/IR ratio is
   not that of blood); after a minute of this the firmware prints a hint that names the setting.

4. **IO2 is a strapping pin and carries the battery divider.** Espressif's boot-mode table asks
   for IO2 = high at reset; the divider holds it at 1.0–1.35 V, which is neither a valid high nor
   a valid low. Many ESP32-C3 boards start fine with IO2 undefined, so this may never show, but it
   is outside the datasheet.
   *Check:* power-cycle on battery 20–30 times and confirm it always starts.
   *Fix for the next PCB revision:* route `BAT_VOLTAGE` to IO3 (free, ADC1_CH3, the neighbouring
   module pad) and give IO2 a 10 kΩ pull-up. Firmware change: one constant, `kPinBatAdc`.

5. **Charge current vs. cell size.** R1 = 5.1 kΩ sets ≈235 mA. That is right for cells of
   ~250 mAh and more; for a smaller cell raise R1 (10 kΩ → ≈120 mA).

6. **No under-voltage cut-off on the board.** Use a cell with a built-in protection circuit. At
   ≈3.45 V (held for a minute, without USB) the firmware shuts the sensor down and goes to deep
   sleep; it looks again every 10 minutes and resumes only above 3.60 V or on USB power. The regulator (≈55 µA), the dividers (≈30 µA) and the sleeping sensor and MCU
   still draw about 0.1 mA, so a bracelet left empty for weeks will over-discharge an unprotected
   cell.

7. **3.3 V rail under Wi-Fi bursts.** There is 4.7 µF + 4.7 µF + 100 nF on 3V3. If you see
   resets when Wi-Fi transmits, add 10–22 µF close to U1.

8. **Battery reading is noisy.** The divider has ≈32 kΩ source impedance and no capacitor at
   the ADC pin. The firmware averages; 100 nF from IO2 to GND would help. Calibrate once against
   a multimeter with `set bat_cal <multimeter V / reported V>`.

9. **The slide switch does not switch USB power.** With S3 off and USB plugged in, the board
   still runs from the charger output (without a battery behind it).

10. **No accelerometer and no MCU-controlled LED.** Motion is detected from the PPG itself (the
    denoiser uses the two wavelengths). Rhythmic motion whose red/IR proportion lies in the range
    arterial blood produces cannot be told from a pulse by a PPG sensor alone: steady arm swing
    without any pulse underneath is still reported as a pulse in a large share of such windows, and
    next to a real pulse the swing can win. Motion locked to the pulse rate shifts SpO2 even with a
    venous red/IR proportion (bracelet network: 13 of the 15 values shown off by more than 4 points;
    all measured in `ml/README.md`, "Known hard cases"). A 3-axis accelerometer on the same I²C bus (e.g. LIS2DH12, BMA400) is the standard
    remedy and the most valuable addition for the next revision. A status LED would help pairing and debugging: today the only feedback
    for a button press is the USB console.

11. **No power path: the charger never finishes while the bracelet runs.** The 3.3 V regulator
    hangs directly on the battery node, so on USB the running system draws its 20–100 mA through
    the TP4056 together with the cell. The charger ends a charge when its current falls below
    ≈1/10 of the programmed value (≈24 mA); with the system in parallel that never happens, and
    the cell is held at 4.2 V for as long as USB is plugged in. This is harmless for an overnight
    charge and bad for a cell that lives on the charger. The firmware cannot see the charger state
    (`CHRG`/`STDBY` only drive the LEDs): it reports "USB power" and a percentage that only rises.
    *Next revision:* route `CHRG` to a free pin (IO5) and add a power-path (e.g. a P-MOSFET +
    Schottky load switch) so that the system runs from USB while charging.

12. **USB power cannot wake the bracelet from the empty-battery sleep.** `VBUS_SENSE` is VBUS / 2
    = 2.5 V, right at the ESP32-C3's logic-high threshold (0.75 × 3.3 V = 2.48 V), and the Arduino
    core adds its internal pull-down (≈45 kΩ) to a wake-up pin, which pulls the divider down to
    ≈1.2 V. The firmware therefore wakes by timer only: after plugging in the charger an empty
    bracelet starts within 10 minutes, or at once when S1 (reset) is pressed. *Next revision:* a
    stiffer divider on a wake-capable pin (IO0–IO5), e.g. 10 kΩ / 22 kΩ (3.4 V; still 2.9 V with
    the pull-down), allows a wake-up on USB.

13. **RAM head-room for HTTPS.** The firmware keeps about 142 kB of the ESP32-C3's RAM for
    itself (signal pipeline 117 kB, windows and record store 17 kB, task and USB buffers 8 kB).
    Wi-Fi needs roughly 50–60 kB of heap and a TLS handshake another 45–50 kB, which should fit
    but was not measured. *Check:* after the first successful upload type `status` and read
    `heap: ... lowest ... largest block`: the lowest value should stay above ≈15 kB. If uploads
    fail with a low heap, tell me: the pipeline's buffers can be made smaller.

14. **Battery life is hours to a day, not a week** (estimate from datasheet figures, nothing was
    measured). The MCU runs continuously (≈20 mA at 160 MHz, ≈15 mA at 80 MHz), the sensor's LEDs
    add 4–8 mA (two LEDs at 12.6–25.4 mA with 16 % duty at 400 conversions/s) and the 5-minute
    Wi-Fi sessions about 1–2 mA on average: 25–30 mA in total, i.e. roughly 9 h from a 250 mAh
    cell and 18 h from 500 mAh. Two settings trade signal quality or speed for runtime:
    `set sensor_sps 100` (LED duty and power ÷ 4, twice the noise) and `set cpu_mhz 80`
    (processing a window then takes about twice as long). Reaching several days needs light
    sleep between sensor polls, which has to be developed on the real board.

## Sensor configuration used by the firmware

| Setting | Value | Why |
|---|---|---|
| Mode | SpO2 (red + IR) | both wavelengths are needed for SpO2 and for motion rejection |
| Sample rate / averaging | 400 sps ÷ 8 = **50 Hz** output (`sensor_sps`: 200 ÷ 4, 100 ÷ 2, 50 ÷ 1) | the pipeline's native rate; 8× averaging gives the best SNR and acts as the anti-alias filter, fewer conversions save LED power |
| Pulse width | 411 µs (18-bit) | best resolution |
| ADC range | 4096 nA (`adc_range` setting) | |
| LED current | starts at 12.6 mA; automatic 1.6–25.4 mA | keeps the DC level at 15–70 % of full scale; changes only between windows; a dim signal is tried at full current before it counts as "not worn" |
| FIFO | roll-over off, polled every 50 ms | lost samples are counted by the chip and the affected window is discarded |
| Interrupts | only the ambient-light-overflow flag is enabled (read by polling) | a window recorded while sunlight overwhelmed the sensor is rejected |

The sensor's sample clock is not crystal-accurate, so the firmware measures the real output rate
against the ESP32 clock and corrects the heart rate with it (`fs` in the output).
