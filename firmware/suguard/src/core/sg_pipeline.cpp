// Complete on-device pipeline - see sg_pipeline.h.
#include "sg_pipeline.h"

#include <math.h>
#include <string.h>

#include "sg_dsp.h"
#include "sg_model.h"
#include "sg_nn.h"
#include "sg_work.h"

namespace {

constexpr double kInputClip = 12.0;                       // INPUT_CLIP in ml/suguard_ml/models/denoiser.py
constexpr int kFftScratchElems = 4 * SG_FFT_N;            // 2 * SG_FFT_N floats, counted in int16 elements
constexpr int kArenaElems = SG_MODEL_ARENA > kFftScratchElems ? SG_MODEL_ARENA : kFftScratchElems;

static_assert(SG_MODEL_FORMAT == 1, "unknown edge model format");
static_assert(SG_MODEL_OUT_CHANNELS == 3, "edge model must output IR, red and the artefact logit");

struct Mem {
  SgWork work;
  // The network arena and the FFT scratch are never needed at the same time.
  union {
    int16_t nn[kArenaElems];
    float fft[2 * SG_FFT_N];
  } scratch;
  int32_t acc[SG_NN_MAX_LEN];
  double ir[SG_WINDOW];        // raw IR counts, later the denoised IR signal
  double red[SG_WINDOW];       // raw red counts, later the denoised red signal
  double bv_ir[SG_WINDOW];     // measured (band-passed) blood-volume signals: the network input,
  double bv_red[SG_WINDOW];    // kept to check that the network's output is supported by them
  double p_art[SG_WINDOW];     // artefact probability from the network
};

Mem g_mem;

// Twin of edge_int.quantize_input + run_int + the de-quantisation in EdgeDenoiserInt._window.
void denoise(Mem* m) {
  double scale = sg_std(m->bv_ir, SG_WINDOW, m->ir);      // m->ir is free scratch at this point
  if (!isfinite(scale) || scale < 1e-9) scale = 1e-9;
  int16_t* in = m->scratch.nn + SG_MODEL_IN_OFFSET;
  const double* src[2] = {m->bv_ir, m->bv_red};
  for (int ch = 0; ch < 2; ch++) {
    for (int i = 0; i < SG_WINDOW; i++) {
      double v = src[ch][i] / scale;
      if (v > kInputClip) v = kInputClip;
      if (v < -kInputClip) v = -kInputClip;
      in[ch * SG_WINDOW + i] = (int16_t)floor(v * (double)(1 << SG_MODEL_IN_FB) + 0.5);
    }
  }
  sg_nn_run(SG_MODEL_OPS, SG_MODEL_N_OPS, m->scratch.nn, m->acc);
  const int16_t* out = m->scratch.nn + SG_MODEL_OUT_OFFSET;
  const double lsb = (double)(1 << SG_MODEL_OUT_FB);
  for (int i = 0; i < SG_WINDOW; i++) {
    m->ir[i] = (double)out[i] / lsb * scale;
    m->red[i] = (double)out[SG_WINDOW + i] / lsb * scale;
    m->p_art[i] = 1.0 / (1.0 + exp(-((double)out[2 * SG_WINDOW + i] / lsb)));
  }
}

}  // namespace

void sg_pipeline_init(void) { sg_work_init(&g_mem.work, g_mem.scratch.fft); }

size_t sg_pipeline_static_bytes(void) { return sizeof(Mem); }

char* sg_pipeline_scratch(size_t* bytes) {
  *bytes = sizeof(g_mem.scratch);
  return (char*)&g_mem.scratch;
}

void sg_process_window(const uint32_t* red, const uint32_t* ir, bool use_nn, double ir_dc_min,
                       SgPipelineOutput* out) {
  Mem* m = &g_mem;
  for (int i = 0; i < SG_WINDOW; i++) {
    m->ir[i] = (double)ir[i];
    m->red[i] = (double)red[i];
  }
  sg_sensor_state(m->red, m->ir, SG_WINDOW, ir_dc_min, &out->sensor, &m->work);
  sg_preprocess(m->ir, SG_WINDOW, m->bv_ir, &m->work);
  sg_preprocess(m->red, SG_WINDOW, m->bv_red, &m->work);
  out->pi_red = sg_perfusion_index(m->bv_red, SG_WINDOW, &m->work);
  out->used_nn = use_nn;
  if (use_nn) {
    denoise(m);
    sg_vitals_from_signals(m->bv_ir, m->bv_red, m->ir, m->red, m->p_art, SG_WINDOW, &out->sensor, &out->vitals,
                           &m->work);
  } else {
    sg_vitals_from_signals(m->bv_ir, m->bv_red, nullptr, nullptr, nullptr, SG_WINDOW, &out->sensor, &out->vitals,
                           &m->work);
  }
}

void sg_reason_names(uint16_t reasons, char* out, size_t out_len) {
  static const char* const kNames[] = {"no_contact", "adc_saturated", "led_current_too_high",
                                       "weak_pulse", "implausible_amplitude", "motion",
                                       "irregular_or_noisy", "red_ir_inconsistent", "denoiser_mismatch"};
  size_t len = 0;
  if (out_len == 0) return;
  out[0] = '\0';
  for (int bit = 0; bit < (int)(sizeof(kNames) / sizeof(kNames[0])); bit++) {
    if (!(reasons & (1u << bit))) continue;
    const size_t n = strlen(kNames[bit]);
    if (len + n + 2 > out_len) break;
    if (len) out[len++] = ',';
    memcpy(out + len, kNames[bit], n + 1);
    len += n;
  }
}
