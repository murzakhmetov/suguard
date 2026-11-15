// One raw window in, vital signs out: the complete on-device pipeline.
//
//   raw counts -> sensor checks -> DC removal + band-pass -> edge denoiser
//   (integer NN) -> beats / heart rate / SpO2 / quality gates
//
// Python twin: SuGuardPipeline(denoiser=EdgeDenoiserInt(model)).analyze(red, ir, fs=50)
// in ml/suguard_ml (firmware/tests/test_pipeline_parity.py compares them).
//
// The working memory (about 130 kB) is one static block inside sg_pipeline.cpp,
// so the functions are not re-entrant: call them from one task.
#pragma once

#include <stddef.h>
#include <stdint.h>

#include "sg_core.h"

struct SgPipelineOutput {
  SgVitals vitals;
  SgSensorState sensor;
  double pi_in;               // IR perfusion index of the input signal, %
  bool used_nn;
};

void sg_pipeline_init(void);

// `red`, `ir`: SG_WINDOW raw 18-bit counts sampled at 50 Hz.
// `prior_hr`: heart rate of the previous reliable window in bpm (<= 0: none).
// `use_nn`: run the neural denoiser (false = classical signal processing only).
void sg_process_window(const uint32_t* red, const uint32_t* ir, double prior_hr, bool use_nn,
                       SgPipelineOutput* out);

// Bytes of static working memory (for the start-up report).
size_t sg_pipeline_static_bytes(void);

// Human-readable names of the SgReason bits set in `reasons`, comma separated.
void sg_reason_names(uint16_t reasons, char* out, size_t out_len);
