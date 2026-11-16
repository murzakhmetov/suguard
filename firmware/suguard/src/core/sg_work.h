// SuGuard signal core - scratch memory (struct SgWork, declared in sg_core.h).
//
// One static instance (about 42 kB) serves every core function; nothing is
// allocated at run time. The buffers are reused from call to call, so no
// state is kept between windows and the functions are not re-entrant.
#pragma once

#include "sg_core.h"
#include "sg_tables.h"

// Twin of suguard_ml.signal.beats.Beats for one window.
struct SgBeats {
  int n;                         // systolic peaks found
  int n_valid;                   // inter-beat intervals accepted as valid
  bool has_hr;                   // Beats.hr_bpm is not None
  double hr_bpm;                 // 60 / median valid interval (valid if has_hr)
  double peak[SG_MAX_BEATS];     // sample index of each peak (sub-sample)
  double onset[SG_MAX_BEATS];    // sample index of each beat foot, NaN if none was found
  double ibi[SG_MAX_BEATS];      // ibi[k]: seconds from peak k to peak k + 1 (n - 1 values)
  bool valid[SG_MAX_BEATS];      // ibi[k] is plausible and consistent with the others
};

struct SgWork {
  float* fft;                                  // 2 * SG_FFT_N floats owned by the caller (sg_work_init)
  double ext[SG_WINDOW + 2 * SG_MAX_PADLEN];   // sg_filtfilt: the padded signal
  double pulse[SG_WINDOW];                     // 0.5-8 Hz band of the IR signal: beats and spectrum (then, in
                                               // a clean window, of the measured IR for its spectrum)
  // sg_vitals_from_signals, in a window the network calls clean: the measured IR and red with the
  // flagged samples taken from the network's output (pipeline.vitals_from_signals `reference`).
  double ref_ir[SG_WINDOW];
  double ref_red[SG_WINDOW];
  // General-purpose arrays; each function names the role it gives them.
  double a[SG_WINDOW];
  double b[SG_WINDOW];
  double c[SG_WINDOW];
  double seg[SG_MAX_BEATS - 1][SG_TEMPLATE_LEN];   // beat_template: onset-to-onset beats, resampled
  double tmpl[SG_TEMPLATE_LEN];                    // beat_template: their median
  double per_beat[SG_MAX_BEATS];                   // one value per beat: intervals, amplitudes, a template column
  SgBeats beats;
};
