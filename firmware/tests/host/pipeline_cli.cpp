// Host harness for the complete on-device pipeline (sg_process_window).
//   pipeline_cli <in.bin> <use_nn 0|1>
// in.bin: records of { uint32 red[512]; uint32 ir[512]; }
// Output: one JSON line per record on stdout.
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

#include "sg_pipeline.h"

int main(int argc, char** argv) {
  if (argc != 3) return 2;
  FILE* in = fopen(argv[1], "rb");
  if (!in) return 3;
  const bool use_nn = atoi(argv[2]) != 0;
  static uint32_t red[SG_WINDOW], ir[SG_WINDOW];
  static SgPipelineOutput out;
  sg_pipeline_init();
  while (fread(red, sizeof red, 1, in) == 1 && fread(ir, sizeof ir, 1, in) == 1) {
    sg_process_window(red, ir, use_nn, SG_FINGER_IR_DC_MIN, &out);
    const SgVitals& v = out.vitals;
    char reasons[160];
    sg_reason_names(v.reasons, reasons, sizeof reasons);
    printf("{\"reliable\":%d,\"has_hr\":%d,\"hr\":%.17g,\"has_spo2\":%d,\"spo2\":%.17g,"
           "\"has_r\":%d,\"r\":%.17g,\"sqi\":%.17g,\"pi_in\":%.17g,\"motion\":%.17g,\"reasons\":\"%s\","
           "\"finger\":%d,\"sat\":%.17g,\"support\":[%.17g,%.17g,%.17g,%.17g]}\n",
           (int)v.reliable, (int)v.has_hr, v.has_hr ? v.hr_bpm : 0.0, (int)v.has_spo2, v.has_spo2 ? v.spo2 : 0.0,
           (int)v.has_r, v.has_r ? v.r_ratio : 0.0, v.quality.sqi, v.pi_in, v.quality.motion_fraction, reasons,
           (int)out.sensor.finger_detected, out.sensor.saturated_fraction, v.support_ir_corr, v.support_ir_gain,
           v.support_red_corr, v.support_red_gain);
  }
  fclose(in);
  return 0;
}
