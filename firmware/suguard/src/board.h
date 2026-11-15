// SuGuard board (KiCad project "SuGuard", ESP32-C3-WROOM-02 + MH-ET LIVE MAX30102 module).
// Pin assignment taken from the netlist of SuGuard.kicad_pcb; see firmware/docs/HARDWARE.md.
#pragma once

namespace board {

constexpr int kPinI2cScl = 6;       // U1 pad 5  IO6  -> net SCL  -> MAX30102 module pad 2
constexpr int kPinI2cSda = 7;       // U1 pad 6  IO7  -> net SDA  -> MAX30102 module pad 3
constexpr int kPinMaxInt = 10;      // U1 pad 10 IO10 -> net MAX_INT (not used: the FIFO is polled)
constexpr int kPinBatAdc = 2;       // U1 pad 16 IO2  -> BAT_VOLTAGE = VBAT * 47k / (100k + 47k)   [ADC1_CH2]
constexpr int kPinVbusAdc = 4;      // U1 pad 3  IO4  -> VBUS_SENSE  = VBUS / 2                    [ADC1_CH4]
constexpr int kPinButton = 9;       // U1 pad 8  IO9  -> S2 to GND (BOOT strapping pin; free after start-up)
// IO18 / IO19: native USB (serial console + flashing). IO8: 10k pull-up (strapping).
// IO0, IO1, IO3, IO5, IO20, IO21: not connected.

constexpr unsigned long kI2cHz = 400000;

}  // namespace board
