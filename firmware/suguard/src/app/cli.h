// Line-oriented console on the USB serial port (115200 baud, any terminal).
// Type "help". Pure parsing/formatting; device actions go through SgCliHooks.
#pragma once

#include <stddef.h>
#include <stdint.h>

#include "config.h"

struct SgCliHooks {
  void* ctx;
  void (*print)(void* ctx, const char* text);                // output, no newline added
  void (*status)(void* ctx);                                 // print the live device status
  void (*save)(void* ctx);                                   // persist the configuration
  void (*apply)(void* ctx);                                  // configuration changed in RAM
  void (*reboot)(void* ctx);
  bool (*led_test)(void* ctx, uint8_t mode);                 // bit0 red, bit1 IR
  void (*mark)(void* ctx, const char* note);                 // event marker
};

// Handles one command line (modified in place: it is tokenised).
void sg_cli_handle(char* line, SgConfig* cfg, const SgCliHooks* hooks);
