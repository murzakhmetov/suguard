// Integer inference engine for the edge denoiser.
//
// Bit-exact twin of run_int() in ml/suguard_ml/models/edge_int.py (the format
// is documented there). Activations are int16 in one arena, weights int8,
// accumulators int32 (overflow-free by construction, checked at export).
#pragma once

#include <stddef.h>
#include <stdint.h>

enum : uint8_t { SG_NN_CONV = 0, SG_NN_AVGPOOL2 = 1, SG_NN_UPSAMPLE2 = 2 };

struct SgNnOp {
  uint8_t kind;             // SG_NN_*
  uint8_t relu;             // CONV: clamp negative outputs to 0
  uint8_t k;                // CONV: kernel size (odd)
  uint8_t dil;              // CONV: dilation
  uint16_t c_in_a;          // channels of the first input
  uint16_t c_in_b;          // channels of the second input (0 = none); CONV sees [a, b] concatenated
  uint16_t c_out;           // output channels (AVGPOOL2 / UPSAMPLE2: equals c_in_a)
  uint16_t len;             // OUTPUT length in samples
  uint32_t off_a;           // arena offsets, in int16 elements
  uint32_t off_b;
  uint32_t off_out;
  const int8_t* w;          // CONV: [c_out][c_in_a + c_in_b][k]
  const int32_t* b;         // CONV: [c_out], in accumulator units
  const int32_t* m0;        // CONV: [c_out] 31-bit multipliers
  const uint8_t* shift;     // CONV: [c_out] right shifts (1..62)
};

#define SG_NN_MAX_LEN 512   // longest tensor, sizes the accumulator scratch

// Runs `ops` over `arena`. The caller places the input tensor at its offset
// beforehand and reads the output tensor from its offset afterwards.
// `acc` is scratch for SG_NN_MAX_LEN int32 values.
void sg_nn_run(const SgNnOp* ops, int n_ops, int16_t* arena, int32_t* acc);
