// Runs the complete on-device pipeline on embedded test windows and prints the
// results plus the number of executed instructions per window.
//
// Built twice by tests/test_rv32.py: for the host (reference values) and for
// RV32IMC - the instruction set of the ESP32-C3 - where it runs bare-metal
// under QEMU (-icount shift=0 makes the instruction counter exact).
#include <stdint.h>
#include <stdio.h>

#include "bench_windows.h"   // generated: BENCH_N, bench_red[][512], bench_ir[][512]
#include "sg_pipeline.h"

static inline uint64_t instructions() {
#if defined(__riscv)
  uint32_t lo, hi, hi2;
  do {
    __asm__ volatile("csrr %0, minstreth" : "=r"(hi));
    __asm__ volatile("csrr %0, minstret" : "=r"(lo));
    __asm__ volatile("csrr %0, minstreth" : "=r"(hi2));
  } while (hi != hi2);
  return ((uint64_t)hi << 32) | lo;
#else
  return 0;
#endif
}

int main() {
  static SgPipelineOutput out;
  sg_pipeline_init();
  printf("{\"static_bytes\":%lu}\n", (unsigned long)sg_pipeline_static_bytes());
  for (int nn = 0; nn < 2; nn++) {
    for (int i = 0; i < BENCH_N; i++) {
      const uint64_t t0 = instructions();
      sg_process_window(bench_red[i], bench_ir[i], nn != 0, SG_FINGER_IR_DC_MIN, &out);
      const uint64_t t1 = instructions();
      const SgVitals& v = out.vitals;
      printf("{\"i\":%d,\"nn\":%d,\"instr\":%lu,\"reliable\":%d,\"has_hr\":%d,\"hr\":%.9f,\"has_spo2\":%d,"
             "\"spo2\":%.9f,\"sqi\":%.9f,\"pi_in\":%.9f,\"motion\":%.6f,\"reasons\":%u,\"n_beats\":%d}\n",
             i, nn, (unsigned long)(t1 - t0), (int)v.reliable, (int)v.has_hr, v.has_hr ? v.hr_bpm : 0.0,
             (int)v.has_spo2, v.has_spo2 ? v.spo2 : 0.0, v.quality.sqi, v.pi_in, v.quality.motion_fraction,
             (unsigned)v.reasons, v.n_beats);
    }
  }
  return 0;
}
