// One raw window in, vital signs out: the complete on-device pipeline.
//
//   raw counts -> sensor checks -> DC removal + band-pass -> edge denoiser
//   (integer NN) -> beats / heart rate / SpO2 / quality gates
//
// Python twin: SuGuardPipeline(denoiser=EdgeDenoiserInt(model)).analyze(red, ir, fs=50)
// in ml/suguard_ml (firmware/tests/test_pipeline_parity.py compares them).
//
// The working memory (about 110 kB) is one static block inside sg_pipeline.cpp,
// so the functions are not re-entrant: call them from one task.
#pragma once

#include <stddef.h>
#include <stdint.h>

#include "sg_core.h"

struct SgPipelineOutput {
  SgVitals vitals;            // vitals.pi_in: IR perfusion index of the measured signal, %
  SgSensorState sensor;
  double pi_red;              // perfusion index of the measured red signal, % (below the IR one for blood)
  bool used_nn;
};

void sg_pipeline_init(void);

// `red`, `ir`: SG_WINDOW raw 18-bit counts sampled at 50 Hz.
// `use_nn`: run the neural denoiser. false = classical signal processing only, which cannot
// tell rhythmic motion from a pulse: meant for diagnostics, not for unattended use.
// `ir_dc_min`: IR level (counts) below which nothing is in front of the sensor
// (SG_FINGER_IR_DC_MIN unless the board is configured otherwise).
void sg_process_window(const uint32_t* red, const uint32_t* ir, bool use_nn, double ir_dc_min,
                       SgPipelineOutput* out);

// The pipeline's largest scratch block, free for the caller between two
// sg_process_window() calls (e.g. to format a raw window as text).
char* sg_pipeline_scratch(size_t* bytes);

// Bytes of static working memory (for the start-up report).
size_t sg_pipeline_static_bytes(void);

// Human-readable names of the SgReason bits set in `reasons`, comma separated.
void sg_reason_names(uint16_t reasons, char* out, size_t out_len);
