// Integer inference engine - see sg_nn.h.
//
// This file dominates the CPU time of a window (about 9 M multiply-adds), so
// it is always compiled with optimisation, whatever the build default is.
#pragma GCC optimize("O3")

#include "sg_nn.h"

// y = saturate16((acc * m0 + 2^(shift-1)) >> shift), optional ReLU.
// The 64-bit product cannot overflow: |acc| < 2^31, m0 < 2^31, shift <= 62.
static inline int16_t requantize(int32_t acc, int32_t m0, unsigned shift, bool relu) {
  int64_t y = ((int64_t)acc * m0 + ((int64_t)1 << (shift - 1))) >> shift;  // arithmetic shift (floor)
  if (y > 32767) y = 32767;
  if (y < -32768) y = -32768;
  if (relu && y < 0) y = 0;
  return (int16_t)y;
}

// acc[t] += w * x[t + off] for every t where the input index is inside [0, len).
static inline void add_tap(int32_t* acc, const int16_t* x, int32_t w, int off, int t_begin, int t_end, int len) {
  int t0 = off < 0 ? -off : 0;
  int t1 = off > 0 ? len - off : len;
  if (t0 < t_begin) t0 = t_begin;
  if (t1 > t_end) t1 = t_end;
  const int16_t* xs = x + off;
  for (int t = t0; t < t1; t++) acc[t] += w * xs[t];
}

// One input channel of a 7-tap kernel. Away from the borders all seven taps
// are in range, so they are applied together with the weights in registers:
// about 4 instructions per multiply-add on RV32IMC instead of 8.
static void add_channel_k7(int32_t* acc, const int16_t* x, const int8_t* w, int d, int len) {
  const int32_t w0 = w[0], w1 = w[1], w2 = w[2], w3 = w[3], w4 = w[4], w5 = w[5], w6 = w[6];
  if ((w0 | w1 | w2 | w3 | w4 | w5 | w6) == 0) return;
  int lo = 3 * d;
  int hi = len - 3 * d;
  if (hi < lo) lo = hi = 0;                         // window shorter than the kernel span: borders only
  for (int t = lo; t < hi; t++) {
    const int16_t* c = x + t;
    acc[t] += w0 * c[-3 * d] + w1 * c[-2 * d] + w2 * c[-d] + w3 * c[0] + w4 * c[d] + w5 * c[2 * d] + w6 * c[3 * d];
  }
  for (int j = 0; j < 7; j++) {                     // borders: [0, lo) and [hi, len)
    const int32_t wv = w[j];
    if (wv == 0) continue;
    const int off = (j - 3) * d;
    add_tap(acc, x, wv, off, 0, lo, len);
    add_tap(acc, x, wv, off, hi, len, len);
  }
}

// "Same" zero-padded dilated convolution over one or two input tensors.
static void conv(const SgNnOp& op, int16_t* arena, int32_t* acc) {
  const int len = op.len;
  const int k = op.k;
  const int half = (k - 1) / 2 * op.dil;
  const int c_in = op.c_in_a + op.c_in_b;
  const int8_t* w = op.w;
  int16_t* out = arena + op.off_out;
  for (int oc = 0; oc < op.c_out; oc++) {
    const int32_t bias = op.b[oc];
    for (int t = 0; t < len; t++) acc[t] = bias;
    for (int ic = 0; ic < c_in; ic++) {
      const int16_t* x = ic < op.c_in_a ? arena + op.off_a + (size_t)ic * len
                                        : arena + op.off_b + (size_t)(ic - op.c_in_a) * len;
      if (k == 7) {
        add_channel_k7(acc, x, w, op.dil, len);
      } else {
        for (int j = 0; j < k; j++) {
          if (w[j] != 0) add_tap(acc, x, w[j], j * op.dil - half, 0, len, len);
        }
      }
      w += k;
    }
    const int32_t m0 = op.m0[oc];
    const unsigned shift = op.shift[oc];
    const bool relu = op.relu != 0;
    for (int t = 0; t < len; t++) out[t] = requantize(acc[t], m0, shift, relu);
    out += len;
  }
}

static void avgpool2(const SgNnOp& op, int16_t* arena) {
  const int16_t* x = arena + op.off_a;
  int16_t* out = arena + op.off_out;
  const int n = (int)op.c_out * op.len;               // channels are contiguous, lengths are even
  for (int i = 0; i < n; i++) out[i] = (int16_t)(((int32_t)x[2 * i] + x[2 * i + 1] + 1) >> 1);
}

static void upsample2(const SgNnOp& op, int16_t* arena) {
  const int16_t* x = arena + op.off_a;
  int16_t* out = arena + op.off_out;
  const int n = (int)op.c_out * (op.len / 2);
  for (int i = 0; i < n; i++) {
    out[2 * i] = x[i];
    out[2 * i + 1] = x[i];
  }
}

void sg_nn_run(const SgNnOp* ops, int n_ops, int16_t* arena, int32_t* acc) {
  for (int i = 0; i < n_ops; i++) {
    const SgNnOp& op = ops[i];
    if (op.kind == SG_NN_CONV) conv(op, arena, acc);
    else if (op.kind == SG_NN_AVGPOOL2) avgpool2(op, arena);
    else upsample2(op, arena);
  }
}
