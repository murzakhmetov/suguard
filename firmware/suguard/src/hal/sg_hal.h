// Hardware access used by the portable device layer.
//
// The board glue (suguard.ino) implements it with Wire; the host tests
// implement it with a register-level MAX30102 simulator.
#pragma once

#include <stddef.h>
#include <stdint.h>

struct SgI2c {
  void* ctx;
  // Write `n` bytes starting at register `reg`. Returns false on a bus error.
  bool (*write)(void* ctx, uint8_t addr, uint8_t reg, const uint8_t* data, size_t n);
  // Read `n` bytes starting at register `reg`. Returns false on a bus error.
  bool (*read)(void* ctx, uint8_t addr, uint8_t reg, uint8_t* data, size_t n);
};
