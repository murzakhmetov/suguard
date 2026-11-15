# SuGuard

Wrist bracelet (ESP32-C3 + MAX30102) with a companion app for pulse, SpO2 and diabetes-risk
screening, and a research pipeline towards non-invasive glucose estimation.

| Folder | What |
|---|---|
| [`firmware/`](firmware/README.md) | Bracelet firmware: raw PPG acquisition, on-device neural denoiser, heart rate / SpO2 with quality gates, USB console, Firebase upload. Hardware notes in [`firmware/docs/HARDWARE.md`](firmware/docs/HARDWARE.md). |
| [`ml/`](ml/README.md) | Models and their validation: motion-artefact denoiser (server and on-device versions), diabetes-risk model (NHANES), glucose training/evaluation pipeline, inference API. |
| `f_app/` | Flutter app (Firebase, AI consultant, food tracker). |
| `web-application/` | Landing page. |

**Status of glucose.** There is no validated glucose model: PPG-only glucose estimation has not
held up under subject-independent testing in the literature, and no paired PPG/glucose data from
this bracelet exists yet. The firmware and the API therefore report no glucose value. What is
needed to change that is described in [`ml/docs/DATA_COLLECTION.md`](ml/docs/DATA_COLLECTION.md).

Not a medical device.
