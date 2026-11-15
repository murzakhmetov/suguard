# Model card — SuGuard ML v0.1.0

Research prototype. Not a medical device; not for diagnosis or for choosing a treatment.

Contents: [1 denoiser](#1-motion-artefact-denoiser) · [2 reliability decision](#2-the-decision-to-report-a-value) ·
[3 heart rate, HRV, SpO2, features](#3-heart-rate-hrv-spo2-pulse-shape-features) · [4 diabetes risk](#4-diabetes-risk--modelsrisk_modeljson-v110) ·
[5 glucose](#5-glucose--no-model) · [6 personal calibration](#6-personal-calibration-filter)

## 1. Motion-artefact denoiser

Two networks with the same job, the same inputs and outputs and the same training data (version
v4 of the training simulator; the networks shipped before, "v2", are evaluated with the same code
and data in `models/metrics/previous/`).

| | Server model | Bracelet model |
|---|---|---|
| File | `models/denoiser.onnx` (float, ONNX Runtime) | `models/denoiser_edge_int.npz`; compiled into the firmware as `firmware/suguard/src/core/sg_model.h` |
| Purpose | Remove motion artefacts from raw MAX30102 windows (red + IR) before heart rate, SpO2 and pulse-shape features are computed, and mark the samples where the pulse cannot be recovered | same, on an ESP32-C3 without a floating-point unit |
| Architecture | 1-D U-Net, 457,267 parameters, channel widths 16/32/48/64, kernel 7, dilated bottleneck, GELU | 1-D U-Net, channel widths 8/16/24/32, ReLU, average pooling and sample repetition instead of strided/transposed convolutions; 94,667 parameters after batch-norm folding |
| Arithmetic | float32 | integers only: int8 weights with one scale per output channel, int16 activations, int32 accumulators (overflow-free by construction, checked at export) |
| Input | (2, 512): IR and red blood-volume signals, 10.24 s at 50 Hz, both divided by the IR standard deviation (one common scale, so the red/IR ratio is preserved) | same |
| Output | clean IR, clean red, artefact logit per sample | same |
| Training | 16,000 steps of 128 windows, best at the last step; validation mask AUC 0.9965 (`denoiser_train.json`) | 16,000 steps, best at step 15,000; validation mask AUC 0.9947 (`denoiser_edge_train.json`) |
| Cost | — | 9.19 million multiply-accumulates per window, 45,056 bytes of working memory, 94,216 bytes of weights; whole pipeline 132 million RV32IMC instructions per window (QEMU), not yet timed on the chip |
| Integer vs. float version of the same network | — | waveform SNR 38.9 dB, artefact decisions agree on 99.86 % of samples, no output saturation (`models/metrics/denoiser_edge_export.json`) |

**Training data.** 200,000 windows from a simulator of the MAX30102 (`suguard_ml/synth/ppg.py`):
a pulse train with heart-rate variability, respiratory modulation and ectopic beats; red/IR optics
for SpO2 82–99.5 %; perfusion 0.08–5 %; motion as periodic swing (also at the pulse rate), bursts,
pressure steps, spikes, drift and partial loss of contact; sensor noise, 18-bit quantisation, ADC
saturation. The shape of the pulse is drawn from four families (`SHAPE_SHARES`): the wave model (a
skewed systolic wave, a reflected wave and a windkessel decay; 30 %), the same behind a low-pass
down to little more than the fundamental (30 %), a smooth harmonic series (15 %) and a harmonic
series rich in overtones, with a 2nd harmonic of up to 1.6 times the fundamental (25 %). No recorded
data is used for training, and nothing glucose-related is simulated.

**Why four shape families.** The v2 networks were trained on the wave model alone (2nd harmonic
below about 0.6 of the fundamental). They took smooth pulses for motion — a clean sine-shaped
pulse got a heart rate in 0–1 % of windows, against 99 % on the classical path — and also real
pulses with a strong 2nd harmonic: of the clean real recordings at rest they reported 62–75 %.
Those recordings have a 2nd harmonic of 0.9–1.6 times the fundamental (a dicrotic notch below the
diastolic foot, a diastolic wave of about 40 %). With the four families both networks report
99–100 % of every smooth shape and every clean real window, and still none of the periodic motion
without a pulse (README, "Results").

**Loss.** L1 on the waveform + L1 on its derivative + cross-entropy on the artefact mask + error of
the red/IR ratio. The mask marks a sample as artefact when either channel is disturbed.

**Evaluation data.** 4,000 held-out simulated windows; 600 further windows through the complete
gated pipeline; 3,300 windows that must not produce a value; 1,200 clean windows of eight pulse
shapes built outside the training simulator; real PPG recordings (heartpy, 835 s) with a simulated
second wavelength and simulated motion, scored without checks and through the complete pipeline.
Files: `models/metrics/denoiser_eval.json` (server), `denoiser_edge_eval.json` (bracelet model,
integer arithmetic exactly as on the device).

**Results without gates** (every window scored; shows the network alone). Share of the test
windows that are clean / lightly / moderately / heavily disturbed: 20 % / 19 % / 23 % / 39 %.

| 4,000 simulated windows | No network | Bracelet | Server |
|---|---|---|---|
| Artefact mask, AUC | – | 0.995 | 0.996 |
| Heart-rate error, mean (all windows) | 11.2 bpm | 3.04 | 2.51 |
| … clean / light / moderate / heavy motion | 1.00 / 1.59 / 10.99 / 21.45 | 0.99 / 1.00 / 1.65 / 5.89 | 1.00 / 1.07 / 1.20 / 4.76 |
| SpO2 error, mean, on the 2,423 windows where the server network and no network both give a value | 3.49 points | 0.39 ¹ | 0.32 |
| … clean / light / moderate / heavy motion, each path on the windows where it gives a value | 0.13 / 2.69 / 6.21 / 8.21 | 0.14 / 0.20 / 0.33 / 1.14 | 0.12 / 0.18 / 0.25 / 0.94 |

¹ On the 2,438 windows where the bracelet network and no network both give a value.

| Real PPG + simulated motion, no checks: heart-rate error (SpO2 error on the windows where all paths give one) | No network | Bracelet | Server |
|---|---|---|---|
| At rest (52) | 0.04 bpm (0.25) | 0.04 (0.36) | 0.03 (0.25) |
| Walking: periodic motion, a quarter of it near the pulse rate (312) | 21.67 bpm (6.48) | 5.17 (0.78) | 3.62 (0.66) |
| Gestures, pressure changes (312) | 4.52 bpm (6.75) | 1.29 (0.77) | 0.98 (0.70) |
| Mixed (312) | 11.42 bpm (4.57) | 3.03 (0.91) | 1.81 (0.69) |

The heart-rate column is over all windows; the SpO2 values in brackets are over the windows where
the network and no network both give a value (from each network's own file; the "no network"
value from the server's file). At rest the bracelet network makes SpO2 slightly worse (0.25 →
0.36 points): a clean signal has nothing to gain.

**Results with gates** are in [README.md](../README.md#results): about 54 % of mixed windows get a
heart rate with 0.35 bpm mean error and no error above 10 bpm; windows that are mostly motion get
no value.

**Limits.**

* Trained on simulation only. Real artefacts of the SuGuard enclosure and strap can differ; the
  input-support check (section 2) is the safeguard, and its reason code `denoiser_mismatch`
  appearing on most windows of a real recording would mean the network does not fit the signal.
* No accelerometer: motion is recognised only by the shape of the signal and the red/IR
  proportion. Motion that is periodic near the pulse rate and equal in both channels cannot be
  told from a pulse in principle.
* During continuous motion most windows are rejected (20–48 % pass in the real-PPG scenarios).
* Shapes with two humps per beat are hard for the beat detector: at slow rates a large diastolic
  wave is sometimes counted as a beat, and the onset of a beat is ambiguous when the notch dips
  below the foot. The checks then reject the window (deep-notch test shape: 83–84 % reported on
  all paths, mean error of the reported values 0.2 bpm, none above 10 bpm). Next step: peak-aligned beat templates and an
  amplitude-aware peak selection that still keeps premature beats.

## 2. The decision to report a value

`suguard_ml.pipeline.vitals_from_signals` (Python) and `sg_vitals_from_signals` (firmware) are the
same algorithm; the firmware tests compare them window by window. A window is **reliable** (gets a
heart rate) only if all of this holds:

| Check | Rule | Reason code when it fails |
|---|---|---|
| Sensor | IR level ≥ 20,000 counts and red level ≥ 4,000; at most 5 % of the samples at the ADC rails | `no_contact`, `adc_saturated` |
| Measured pulse strength | peak-to-peak IR perfusion of the *measured* signal ≥ 0.03 % | `weak_pulse` |
| Quality components: each must reach 0.25 and their geometric mean 0.5 | perfusion (rising over 0.03–0.12 %, falling over 10–20 %); beat-template correlation; spectral purity; beat-amplitude spread; share of plausible beat intervals; agreement of the beat-based and the spectral heart rate; share of samples not flagged as motion. A component that cannot be computed fails | `weak_pulse`, `implausible_amplitude`, `motion`, `irregular_or_noisy` |
| Motion share | ≤ 70 % of the samples flagged by the network | `motion` |
| Input support | on the samples the network calls clean (≥ 10 of them), its IR output must correlate with the measured IR signal (≥ 0.7) and have a comparable size (0.7–1.4) | `denoiser_mismatch` |
| Arterial ratio | the red/IR ratio R must be one that arterial blood can produce (0.30–1.1) | `red_ir_inconsistent` |

**SpO2** additionally needs two more quality components — the stability of the red/IR ratio over
the window and the red/IR correlation (`red_ir_inconsistent`) — a red/IR correlation of at least
0.9 in the cardiac band (`spo2_low_red_ir_agreement`) and the same input-support check on the red
channel (`red_denoiser_mismatch`). So a still but weakly perfused wrist can give a heart rate and
no SpO2. **Pulse-shape features** (for a future glucose model) are produced only for SpO2-grade
windows.

An IR level above 90 % of full scale adds the note `led_current_too_high`; it does not reject a
window by itself (the firmware's LED control then lowers the current).

## 3. Heart rate, HRV, SpO2, pulse-shape features

Numbers in this section without another source come from `scripts/check_model_card.py`
(`models/metrics/model_card_checks.json`), which states the simulation behind each one.

* **Heart rate** — beat detection after Elgendi (two moving averages) with refinement of the
  peak positions. The rate is the mean of the beat intervals that lie within 30 % of their median:
  the band keeps missed and extra beats out, and the mean cancels the jitter of the peak times
  (a peak found late lengthens one interval and shortens the next), which the median used before
  did not (simulated clean windows: mean error 0.55 → 0.32 bpm). There is no fall-back to a
  spectral estimate or to a previous value.
* **HRV** (Python and API only, from ≥ 60 s of signal; the firmware works on 10.24-s windows and
  has none) — premature beats and their compensatory pauses are removed with the decision rule of
  Lipponen & Tarvainen before SDNN/RMSSD are computed; the output states how many intervals were
  excluded. One simulated minute with four premature beats: with the rule the median RMSSD is
  within 5 % of the value without them for every rhythm tested when they come at up to 80 % of the
  normal interval; late ones (88 %) in a variable rhythm (RMSSD 60 ms, or strong respiratory
  variation) are not recognised and RMSSD comes out 1.3–1.4 times too high. Single minutes
  scatter: 5th–95th percentile 0.85–1.1 in most settings, up to 1.5 for premature beats at 80–88 %
  in a variable rhythm. Without any editing RMSSD is 1.4–15 times too high, the more the steadier
  the rhythm.
* **SpO2** — ratio of ratios R from a total-least-squares fit of red on IR in the cardiac band
  (0.7–5 Hz), weighted by the network's artefact mask; Maxim's reference curve
  `SpO2 = −45.060·R² + 30.354·R + 94.845`. **Not calibrated for the SuGuard enclosure**: calibrate
  against a medical pulse oximeter (`suguard_ml.signal.spo2.fit_spo2_calibration`). The estimator's
  own bias in simulation (the simulator uses the same curve, so the sensor's error is not in it):
  2,000 simulated windows per condition with true SpO2 82–95 % (`spo2_bias`): below 90 % the mean
  signed error is between 0.0 and +0.3 points for every path, with and without motion (the
  networks up to +0.5 at 82–84 %); at 90–95 % every path is within ±0.15 points except the
  classical path with motion (−0.5). Real accuracy below 90 % can only be established in a controlled desaturation
  study (ISO 80601-2-61).
* **Features** — morphology of the average beat, second-derivative (SDPPG) ratios, harmonics,
  red/IR ratios. The dicrotic notch is reported only when it stands out from the noise of the
  averaged beat by three standard errors. Clean simulated windows whose noise-free beat has no
  notch, at a perfusion of 1 / 0.3 / 0.1 %: beats without a reflected wave get a notch reported in
  0 / 2 / 11 % of the windows with this rule and in 45 / 76 / 95 % without it; the simulator's
  whole shape family in 3 / 3 / 17 % and 66 / 77 / 91 %. The price: a notch the noise-free beat
  does have is missed in 6 / 14 / 13 % of those windows (30–35 each).

## 4. Diabetes risk — `models/risk_model.json` (v1.1.0)

| | |
|---|---|
| Purpose | Screening estimate of the probability that HbA1c is elevated **now** in an adult **without a diabetes diagnosis**. Not a diagnosis and not a forecast |
| Output | P(HbA1c ≥ 5.7 %), P(HbA1c ≥ 6.5 %), P(5.7–6.4 %), `risk_score` = 100 · P(HbA1c ≥ 5.7 %), category low / moderate / elevated / high, the contribution of each factor the user gave, the inputs that were not used and the inputs that were averaged because they were missing |
| Model | Logistic regression (L2, C = 1): age (and its square), sex, log BMI, resting pulse, physical activity, ancestry (Asian, with an interaction with BMI; European). Missing sex/activity/ancestry are averaged over their NHANES shares, missing pulse is imputed from age/sex/BMI. Age is limited to the range of the data (18–80) |
| Data | NHANES 2017–2018: 4,318 adults without diagnosed or treated diabetes, with HbA1c and BMI; HbA1c ≥ 5.7 % in 34.0 %, ≥ 6.5 % in 3.6 % |
| Validation | Repeated stratified 5-fold cross-validation (5 repeats), imputation inside each fold, out-of-fold metrics, bootstrap 95 % confidence intervals, calibration by subgroup (`models/metrics/risk_cv.json`) |
| HbA1c ≥ 5.7 % | AUC 0.770 [0.756–0.783], average precision 0.594, Brier 0.180 (0.224 without a model), calibration slope 1.00 |
| HbA1c ≥ 6.5 % | AUC 0.789 [0.749–0.815], average precision 0.113 (prevalence 0.036), Brier 0.033 (0.034), slope 0.97 |
| For comparison | age + BMI only: 0.748 / 0.749; without ancestry: 0.749 / 0.756 |
| Calibration by subgroup (predicted / observed, HbA1c ≥ 5.7 %) | Asian 0.382 / 0.383; White 0.277 / 0.277; age 18–39 0.141 / 0.144; age 60–80 0.538 / 0.533. **A systematic error of 4–6 points remains** for Black (0.400 / 0.458), Mexican-American (0.337 / 0.292), other Hispanic (0.370 / 0.321) and multiracial participants (0.338 / 0.297). Without the ancestry terms: Asian 0.276 / 0.383, White 0.367 / 0.277 (`subgroup_calibration_without_ancestry`) |
| Categories (out-of-fold) | low: 32 % of people, HbA1c ≥ 5.7 % in 9 %; moderate: 27 % / 30 %; elevated: 27 % / 50 %; high: 14 % / 66 % (HbA1c ≥ 6.5 % in 11 %, three times the average) |
| Left out on purpose | Waist (correlation 0.91 with BMI, unstable sign) and smoking (gets a spurious "protective" sign in cross-sectional data): with them the AUC is 0.771 / 0.792 instead of 0.770 / 0.789, well inside the confidence intervals, and they should not explain a risk. If sent, the API returns them under `inputs_not_used` |
| Tested and not added | Measured blood pressure, self-rated general health, sedentary time and sleep duration, each added to the shipped model on the same folds: the cross-validated AUC changes by −0.002 to +0.002, inside the noise, so they would only lengthen the questionnaire (`scripts/risk_extra_inputs.py`, `models/metrics/risk_extra_inputs.json`). The bundled NHANES item "family history" is the reason given by people who already think they are at risk (DIQ175A), not a family history, and would leak perceived risk into the screening; it was not used. A real family-history question remains worth asking |
| Glucose from the bracelet | Off. It would be used only with a glucose model validated on this bracelet (the server then knows its error): HbA1c from the ADAG relation (mean glucose + 46.7) / 28.7 and a Bayesian update with the NHANES HbA1c distributions. GMI is not used: in normoglycaemia it reads high (about 5.7 % at a mean of 100 mg/dL) |
| Limits | US population, unweighted sample (survey-weighted variant: `--weights DEMO_J.xpt`, in the Colab notebook). The ancestry groups are those of a US survey; how they carry over to Kazakhstan is an assumption to be checked on local data with HbA1c. Family history, gestational diabetes and blood pressure — strong factors of the ADA and FINDRISC questionnaires — are missing and worth adding to the profile. Discrimination is weaker within the oldest group (AUC 0.63 for age 60–80) |

## 5. Glucose — no model

| | |
|---|---|
| Intended purpose | Estimate glucose from PPG features and context, personalised with fingersticks |
| Model class | LightGBM: median and 10 %/90 % quantiles; input = median of the features of ≥ 3 reliable 10.24-s windows (the same aggregation in training and in the API) + context (time of day, meals) |
| State | **Not trained**: none of the available sources has paired PPG and glucose from this sensor. The API answers `unavailable`, or `calibration_only` after ≥ 3 fingersticks (their filtered average, `mg_dl` = null). A model that is installed but not `validated` answers `not_validated` without a number, unless the server runs with `SUGUARD_EXPERIMENTAL_GLUCOSE=1` (research only; status `experimental`). The firmware has no glucose output |
| Criteria for `validated` (`scripts/train_glucose.py`) | data from the SuGuard bracelet; ≥ 20 people, of whom ≥ 80 % can be scored in the personalised protocol; on new people better than predicting the mean; after calibration ≥ 10 % better (MARD) than the best baseline without PPG — fingerstick level, last fingerstick, personal time-of-day profile — with the lower bootstrap bound above zero; PPG beats the controls "context only" and "PPG shuffled within a person"; MARD ≤ 15 % and Clarke A+B ≥ 99 %; on a locked hold-out group (20 % of the people): the same MARD and Clarke bar, ≥ 80 % of them scored and a gain over the best baseline without PPG (the 10 % margin, the bootstrap bound and the controls are not repeated on this small group). A check that cannot be run (no PPG features, a control missing, too few people scored) fails |
| The bar (real CGM, no bracelet) | 19 people without diagnosed diabetes: a constant gives MARD 16.8–16.9 %, fingerstick calibration alone 15.3–16.4 %; 5 people with type 2 diabetes: 35 % and 21.7–22.7 % (`models/metrics/calibration_baselines_cgm.json`) |
| Check of the logic | synthetic positive and negative controls (`tests/synthetic_paired.py`): a real signal passes every evidential criterion, time-of-day effects and noise do not; the synthetic tables are labelled as not coming from the bracelet and so are not `validated`. The label (`meta_source`) is trusted, not verified: a table must only be labelled as bracelet data if it is (one test labels the positive control that way to show that a strong signal then passes) |
| Time base | every paired table carries its own UTC offset per row (`meta_tz_offset_h`), so "days" and "time of day" are local for every participant |

## 6. Personal calibration filter

`suguard_ml.models.glucose.PersonalCalibration` — a Kalman filter on `y = a + b·f` (f: the
population model's output, or a constant while there is no model), with slow drift of a and b.

* The state is kept by the client and checked on every request: finite numbers in fixed ranges,
  symmetric positive covariance, timestamps in a plausible range. With `SUGUARD_STATE_KEY` set
  the server signs the states (HMAC-SHA-256) and refuses any it did not issue.
* Reference values are accepted from 20 to 600 mg/dL; entries that arrive late (older than the
  newest one) are used with extra noise instead of moving the clock backwards; the drift is
  limited to a year.
* The level prior is broad (SD 100 mg/dL around 105): someone with diabetes may run at twice that.
  With the narrow prior used before (30 mg/dL) the filter took the first, large deviations for
  noise and then converged slowly (40 readings of 600 mg/dL ended at 581).
* The spread around the level that the state does not explain starts at 30 mg/dL, counts as three
  fingersticks at first and then becomes a slow running average of the excess of the prediction
  errors over the filter's own uncertainty and the meter's error.
* Simulation without a population model (`models/metrics/model_card_checks.json` →
  `calibration_filter`: 300 people per setting, two fingersticks a day, 5 % meter error): when a
  person's glucose scatters by 20–40 mg/dL around the level, the 80 % interval holds 78–79 % of the
  next true values after 30 fingersticks (71–85 % after 6, while the start value still counts),
  and the learnt spread is 18.5–19.9 and 38.5–39.7 mg/dL. For a very steady person (5 mg/dL) the
  learnt spread comes out low (3.4 for a level that does not drift, 5.2 for one that drifts as the
  filter assumes) and the interval holds 76–80 % of the true values but only 64–72 % of new meter
  readings, because the meter's own error is then larger than the glucose spread.
* Fingerstick calibration alone on real CGM data: see section 5.
* Without a population model its output is only the smoothed level of the user's own
  fingersticks, and the API says so.
