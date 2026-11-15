# SuGuard

Wrist bracelet (ESP32-C3 + MAX30102) with a companion app for pulse, SpO2 and diabetes-risk
screening, and a research pipeline towards non-invasive glucose estimation.

| Folder | What |
|---|---|
| [`firmware/`](firmware/README.md) | Bracelet firmware: raw PPG acquisition, on-device neural denoiser, heart rate / SpO2 with quality gates, USB console, Firebase upload. Hardware notes in [`firmware/docs/HARDWARE.md`](firmware/docs/HARDWARE.md). |
| [`ml/`](ml/README.md) | Models and their validation: motion-artefact denoiser (server and on-device versions), diabetes-risk model (NHANES), glucose training/evaluation pipeline, inference API. |
| `f_app/` | Flutter app (Firebase, AI consultant, food tracker). |
| `web-application/` | Landing page. |

## State of the work

| Part | State |
|---|---|
| Signal processing and motion-artefact removal | Trained and evaluated on simulated sensor data and on real PPG recordings with simulated motion ([results](ml/README.md#results)). Not yet tried on a wrist. |
| Firmware | Written for the board in the KiCad files; tested on a PC against a simulated sensor and type-checked against the Arduino-ESP32 headers. **Never built with the ESP32 toolchain and never run on the board** — start with the [bring-up checklist](firmware/README.md#bring-up-checklist). |
| Diabetes-risk screening | Trained and cross-validated on NHANES 2017–2018 (AUC 0.77 for HbA1c ≥ 5.7 %). A screening estimate, not a diagnosis; to be confirmed on local data. |
| Glucose | **No model.** PPG-only glucose estimation has not held up under subject-independent testing in the literature, and no paired PPG/glucose data from this bracelet exists yet. The firmware and the API therefore report no glucose value. What is needed to change that: [`ml/docs/DATA_COLLECTION.md`](ml/docs/DATA_COLLECTION.md). |
| App and website | Not changed. The app does not read the bracelet's new records yet; its "risk %" is a hand-made formula over a glucose value the bracelet cannot measure, and the repository holds no study behind the website's accuracy figure ([recommendations](ml/README.md#recommendations-for-the-app-and-the-website)). |

Not a medical device.
