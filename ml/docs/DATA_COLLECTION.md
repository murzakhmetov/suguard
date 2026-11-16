# Collecting paired data with the SuGuard bracelet

A glucose model that works **on your bracelet** can only be trained and validated on data from
that bracelet (MAX30102, red 660 nm + IR 880 nm, your enclosure, your wrist placement) paired with
reference glucose measurements. Public datasets (BIG IDEAs, PPG-DaLiA) were recorded with other
sensors (Empatica E4, green light): they are useful to test the idea, not to replace your own data.

## 1. Study design

| | Pilot (go / no-go) | Validation |
|---|---|---|
| Participants | 30–50 | 100+, new people, model frozen beforehand |
| Who | normal, prediabetes and type 2 diabetes (include insulin users for a wide range) | same, balanced by sex, age, BMI and skin tone |
| Duration | 10–14 days each | 10–14 days each |
| Reference | CGM (FreeStyle Libre 2/3 or Dexcom) + an ISO 15197:2013 meter, ≥ 4 fingersticks a day | same, part of the points from venous blood in a laboratory |
| Pairs "PPG ↔ glucose" | ≥ 100 per person over ≥ 7 days | ≥ 300 per person |

* **Ethics first.** This is medical research on people with personal health data: you need
  approval from a local ethics committee and written informed consent before recording anything.
* **A CGM as reference** gives thousands of pairs per person, including the rises after meals.
  Without those the model only ever sees "morning" glucose and learns nothing useful.
* **People matter more than points.** Generalisation to new users is limited by the number of
  participants, not by the number of readings per participant.
* **Fix the success criteria in advance** (pre-registration). The training script already encodes
  them: on people and days the model has never seen, after calibration, MARD ≤ 15 %, at least 10 %
  better than fingerstick-only baselines (with the confidence interval above zero), better than the
  "context only" and "shuffled PPG" controls, Clarke A+B ≥ 99 %. If that is not reached, the honest
  conclusion is that PPG glucose is not confirmed.

## 2. What to record

1. **Raw PPG windows** from the bracelet (512 samples of red and IR at 50 Hz, LED currents, sensor
   temperature). Two ways:
   * **USB (recommended, loss-free):** bracelet plugged into a PC,
     `python firmware/tools/suguard_monitor.py --port <port> --record <folder> --user <id>`.
     Everything is written in the formats below; type `g 5.6` to store a fingerstick.
   * **Wi-Fi:** `set upload_raw 1` on the console; windows go to `rawPpg/<uid>/` in Firebase
     (about 8 kB every 10 s, best effort — windows are dropped when the network is slow).
     Export them with `ml/scripts/export_firebase_raw.py`.
2. **Reference glucose** — the CGM export (CSV) and the fingersticks with exact times.
3. **Meals** — carbohydrates and start time (the app's food tracker).
4. **Profile** — age, sex, height, weight, diagnosis, medication (beta blockers and insulin matter).
5. **Notes** — exercise, sleep, illness, how the bracelet was worn.

## 3. File formats

`windows.jsonl` — one line per window:

```json
{"user_id": "u17", "device_id": "SG-001", "ts": 1763100000.0, "fs": 50.02, "temp_c": 31.4,
 "red": [101234, 101201, ...], "ir": [143002, 142987, ...]}
```

`ts` is the unix time (UTC) of the first sample, `fs` the measured sample rate. The PC recorder
also stores which clock dated the window (`clock`: the bracelet's, or the PC's when the bracelet
has no Wi-Fi), the LED currents, a sequence number and the window flags; windows without any time
cannot be paired and are skipped.

`fingersticks.csv` (a CGM export converted to the same columns works too):

```
user_id,ts,glucose_mgdl,source
u17,2026-11-14T08:05:00+05:00,104,meter
```

`meals.csv` — `user_id,ts,carbs_g,calories`; `profiles.csv` — `user_id,age,sex,height_cm,weight_kg`.

Times with an explicit offset (`+05:00`, `Z`) are taken as given; times without one are local
wall-clock time at `tz_offset_h`.

## 4. From recordings to a model

```python
from suguard_ml.data.paired import build_from_device_logs
df = build_from_device_logs("windows.jsonl", "fingersticks.csv", "meals.csv", "profiles.csv",
                            tz_offset_h=5)            # Kazakhstan, UTC+5
df.to_parquet("data/suguard_paired.parquet")
```

```bash
python scripts/train_glucose.py --table data/suguard_paired.parquet --out models --name suguard
```

The script reports three protocols (random split — only to show how much it inflates the result;
new people; personal calibration scored on later days), the baselines without PPG, the two controls
and whether the model is `validated`. The API presents glucose as a measurement only for a
validated model.

## 5. SpO2

The SpO2(R) curve in use is Maxim's reference curve. For your enclosure it has to be calibrated
against a medical pulse oximeter (`suguard_ml.signal.spo2.fit_spo2_calibration`, with the ratio R of
each window from the per-window file of section 6, `classical_r`, and the reference SpO2). The range
94–100 % can be checked on resting volunteers; accuracy below 90 % can only be established in a
controlled desaturation study in a laboratory (ISO 80601-2-61).

## 6. Checking heart rate and SpO2 against a reference

Before any glucose study, check the whole chain on your wrist: record windows with the PC tool
while a reference device records next to it — a chest strap (the best heart-rate reference) or a
fingertip pulse oximeter that exports its readings (for SpO2) — at rest, then walking, then with
hand movements. Then:

```bash
python ml/scripts/validate_vitals.py --windows rec/windows.jsonl --reference oximeter.csv \
    --tz-offset-h 5 --ref-lag-s auto --out rec/validation.json --per-window rec/per_window.csv
```

The reference file needs a time (one column, or a date and a time-of-day column; unix seconds or
milliseconds, or date and time — text without an offset is local time at `--tz-offset-h`, default
this computer's time zone; dotted dates such as 05.11.2025 are read day first, slashed ones with
`--dayfirst yes|no` where it is ambiguous) and a heart-rate and/or SpO2 column. The usual names, with
or without units (`Time`, `Date`, `HR`, `Pulse Rate`, `PR (bpm)`, `SpO2 (%)`, ...), are recognised,
others are given with `--time-col`, `--date-col`, `--hr-col`, `--spo2-col`; the report's first lines
say which columns were used. Each window is compared with the median of the readings inside its
10.24 s. `--ref-lag-s auto` looks for the delay of the reference (oximeters average over several
seconds) within ±15 s and keeps one only if it clearly fits better than none, which needs
heart-rate changes in the recording (rest, then walking); the report says whether a delay was found.
Set the reference device's clock and the PC's (or the bracelet's, with Wi-Fi) to the same time: if
nothing overlaps, the script prints both time ranges, hints at a wrong `--tz-offset-h` and exits with
code 2. The report gives, for the classical path, the bracelet network and the server network: how
many windows get a value, the mean error (bias, bracelet minus reference), the mean absolute error,
the 95 % limits of agreement, the share of heart rates within 5 bpm and the number beyond 10 bpm,
the SpO2 ARMS and why the other windows got nothing. What to look for: at rest almost every window with a heart rate within a few bpm and no
SpO2 bias beyond 1–2 points (else calibrate SpO2, section 5); `denoiser_mismatch` or `motion` on
most resting windows means the networks do not fit your signal.
