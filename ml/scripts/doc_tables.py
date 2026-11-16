"""Print the result tables of README.md and docs/MODEL_CARD.md from the metric files.

    python scripts/doc_tables.py                      # models/metrics, previous networks "v4"
    python scripts/doc_tables.py --previous v2

Every number in those tables comes from models/metrics/denoiser_eval.json
(server network and classical path), denoiser_edge_eval.json (bracelet
network) and, for the columns of the networks shipped before,
previous/denoiser_<version>_eval.json and previous/denoiser_edge_<version>_eval.json
(scored with the same code and data). Run it after eval_denoiser.py and paste
the tables; sections a metrics file does not have yet are skipped.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ML = Path(__file__).resolve().parents[1]


def pct(x):
    return "–" if x is None else f"{100 * x:.0f} %"


def num(x, d=2):
    return "–" if x is None else f"{x:.{d}f}"


SEVERITY_LABEL = "clean / light / moderate / heavy motion"
MOTION_LABEL = {"0-0.05": "0–5 %", "0.05-0.3": "5–30 %", "0.3-0.7": "30–70 %", "0.7-1.01": "more than 70 %"}
SHAPE_LABEL = {"sharp_with_reflected_wave": "Sharp systolic peak and reflected wave",
               "deep_notch_large_diastolic_wave": "Deep notch, large diastolic wave (like the real recording data3)",
               "rounded_with_reflected_wave": "Rounded peak and reflected wave",
               "skewed_triangle_rise_20pct": "Steep rise, slow fall",
               "skewed_triangle_rise_35pct_smooth": "Slower rise, smoothed",
               "three_harmonics": "Three harmonics",
               "two_harmonics": "Two harmonics",
               "sine": "Sine"}
MNR_LABEL = {"noise_only": "Noise, no pulse", "ir_without_pulse": "No pulse in the infrared channel",
             "red_without_pulse": "Pulse in infrared only, none in red ¹",
             "red_pulse_a_fifth_in_noise": "Red pulse at a fifth of its size, in noise ¹",
             "led_channels_swapped": "The two LED channels swapped ²",
             "no_pulse_with_motion": "A pulse of 0.01 % (below the 0.03 % threshold), the usual motion mix ³",
             "periodic_motion_no_pulse": "The same pulse, periodic motion as large as a pulse ⁴"}
SCENARIO_LABEL = {"clean": "At rest", "walking": "Walking: periodic motion, a quarter of it near the pulse rate",
                  "gestures": "Gestures, pressure changes", "mixed": "Mixed"}
REST_LABEL = {"0.08-0.15%": "0.08–0.15 %", "0.15-0.3%": "0.15–0.3 %", "0.3-1%": "0.3–1 %", "1-5%": "1–5 %"}
HARD_LABEL = {"steady_periodic_motion_no_pulse": "Steady periodic motion, no pulse",
              "pulse_with_steady_motion_at_another_rate": "Pulse + steady motion 1.5–4× as large at another rate",
              "pulse_with_motion_at_half_the_rate": "Pulse + motion at half its rate (arm swing)",
              "motion_locked_to_the_pulse_rate_venous_ratio": "Motion locked to the pulse rate, venous red/IR ratio",
              "fast_breathing": "Fast breathing (27–45 /min) swinging the baseline, red/IR gain 0.8–1.3",
              "bigeminy_weak_premature_beats": "Bigeminy with weak premature beats",
              "slow_35_45bpm_double_humped": "35–45 bpm, double-humped pulse, no motion",
              "fast_150_210bpm_spo2_82_90": "150–210 bpm at SpO2 82–90 %, no motion",
              "venous_pulsation_locked_to_the_beat": "Venous pulsation locked to the beat (0.3–0.6×), no motion",
              "cadence_locked_to_the_pulse": "Cadence locked to the pulse (0.3–1×), the simulator's motion gains"}


class Tables:
    def __init__(self, metrics: Path, previous: str | None):
        def load(name):
            f = metrics / name
            return json.loads(f.read_text()) if f.exists() else None
        self.srv, self.edge = load("denoiser_eval.json"), load("denoiser_edge_eval.json")
        if self.srv is None or self.edge is None:
            raise SystemExit(f"{metrics} needs denoiser_eval.json and denoiser_edge_eval.json")
        self.prev = previous
        self.psrv = load(f"previous/denoiser_{previous}_eval.json") if previous else None
        self.pedge = load(f"previous/denoiser_edge_{previous}_eval.json") if previous else None
        self.paths = [("Classical", self.srv, "classical"), ("Bracelet", self.edge, "denoiser"),
                      ("Server", self.srv, "denoiser")]

    def _with_previous(self):
        cols = [("Classical", self.srv, "classical")]
        if self.pedge:
            cols.append((f"Bracelet {self.prev}", self.pedge, "denoiser"))
        cols.append(("Bracelet", self.edge, "denoiser"))
        if self.psrv:
            cols.append((f"Server {self.prev}", self.psrv, "denoiser"))
        cols.append(("Server", self.srv, "denoiser"))
        return cols

    @staticmethod
    def _head(first, cols):
        return ["| " + first + " | " + " | ".join(c[0] for c in cols) + " |", "|---|" + "---|" * len(cols)]

    def pipeline(self):
        rows = [("Windows that get a heart rate", lambda p: pct(p["hr_coverage"])),
                ("… of the windows with less than 5 % motion", lambda p: pct(p["clean_window_hr_coverage"])),
                ("Heart rate: mean / 95th-percentile error", lambda p: f"{num(p['hr_mae'])} / {num(p['hr_p95'], 1)} bpm"),
                ("Heart-rate errors above 10 bpm", lambda p: str(p["hr_errors_over_10bpm"])),
                ("Windows that get an SpO2 value", lambda p: pct(p["spo2_coverage"])),
                ("SpO2: mean / 95th-percentile error", lambda p: f"{num(p['spo2_mae'])} / {num(p['spo2_p95'], 1)} points"),
                ("SpO2 errors above 4 points", lambda p: str(p["spo2_errors_over_4pts"]))]
        out = self._head("", self.paths)
        for label, fn in rows:
            out.append(f"| {label} | " + " | ".join(fn(src["pipeline_with_gates"][k]) for _, src, k in self.paths) + " |")
        return "\n".join(out)

    def motion(self):
        bins = self.srv["pipeline_with_gates"]["classical"]["by_motion_share"]
        out = self._head("Motion in the window (windows)", self.paths)
        for b, v in bins.items():
            out.append(f"| {MOTION_LABEL.get(b, b)} ({v['windows']}) | " + " | ".join(
                pct(src["pipeline_with_gates"][k]["by_motion_share"][b]["hr_coverage"]) for _, src, k in self.paths) + " |")
        return "\n".join(out)

    def shapes(self):
        cols = self._with_previous()
        out = self._head("Pulse shape (150 clean windows each)", cols)
        for s in self.srv["shape_robustness"]:
            out.append(f"| {SHAPE_LABEL.get(s, s)} | " + " | ".join(
                pct(src["shape_robustness"][s][k]["hr_coverage"]) for _, src, k in cols) + " |")
        cells = [src["shape_robustness"][s][k] for _, src, k in cols for s in self.srv["shape_robustness"]]
        worst = max(c["hr_errors_over_10bpm"] for c in cells)
        maes = [c["hr_mae"] for c in cells if c["hr_mae"] is not None]
        out.append(f"\n(largest number of heart-rate errors above 10 bpm in a cell: {worst}; "
                   f"mean errors {min(maes):.2f}–{max(maes):.2f} bpm)")
        return "\n".join(out)

    def rest(self):
        if "rest_by_perfusion" not in self.srv or "rest_by_perfusion" not in self.edge:
            return None
        off = "denoiser_without_low_perfusion_fallback"
        cols = [("Classical", self.srv, "classical"), ("Bracelet, rule off", self.edge, off),
                ("Bracelet", self.edge, "denoiser"), ("Server, rule off", self.srv, off), ("Server", self.srv, "denoiser")]
        bins = self.srv["rest_by_perfusion"]["classical"]
        out = self._head("Pulse size (windows): heart rate / SpO2 given", cols)
        for b, v in bins.items():
            out.append(f"| {REST_LABEL.get(b, b)} ({v['windows']}) | " + " | ".join(
                f"{pct(src['rest_by_perfusion'][k][b]['hr_coverage'])} / {pct(src['rest_by_perfusion'][k][b]['spo2_coverage'])}"
                for _, src, k in cols) + " |")
        total = lambda src, k, key: sum(x[key] for x in src["rest_by_perfusion"][k].values())  # noqa: E731
        out.append("\n(errors: heart rate above 10 bpm " + ", ".join(
            f"{name} {total(src, k, 'hr_errors_over_10bpm')}" for name, src, k in cols)
            + "; SpO2 above 4 points " + ", ".join(f"{name} {total(src, k, 'spo2_errors_over_4pts')}" for name, src, k in cols)
            + f"; windows decided by the classical checks: bracelet {total(self.edge, 'denoiser', 'classical_fallback')}, "
              f"server {total(self.srv, 'denoiser', 'classical_fallback')})")
        return "\n".join(out)

    def must_not_report(self):
        out = self._head("Input (windows)", self.paths)
        for s, v in self.srv["must_not_report"]["classical"].items():
            out.append(f"| {MNR_LABEL.get(s, s)} ({v['windows']}) | " + " | ".join(
                f"{src['must_not_report'][k][s]['heart_rate_reported']} / {src['must_not_report'][k][s]['spo2_reported']}"
                for _, src, k in self.paths) + " |")
        return "\n".join(out)

    def real_pipeline(self):
        out = self._head("Scenario (windows)", self.paths)
        for s, v in self.srv["real_ppg_simulated_motion"]["scenarios"].items():
            cells = []
            for _, src, k in self.paths:
                p = src["real_ppg_simulated_motion"]["scenarios"][s]["pipeline"][k]
                cells.append(f"{pct(p['hr_coverage'])}, {num(p['hr_mae'], 1)} bpm"
                             + (f", {p['hr_errors_over_10bpm']} > 10" if p["hr_errors_over_10bpm"] else ""))
            out.append(f"| {SCENARIO_LABEL.get(s, s)} ({v['windows']}) | " + " | ".join(cells) + " |")
        return "\n".join(out)

    def real_no_checks(self):
        out = ["| Real PPG + simulated motion, no checks: heart-rate error against the beat detector's rate on the "
               "uncorrupted recording (SpO2 error on the windows where that network and no network both give one) "
               "| No network | Bracelet | Server |", "|---|---|---|---|"]
        for s, v in self.srv["real_ppg_simulated_motion"]["scenarios"].items():
            e = self.edge["real_ppg_simulated_motion"]["scenarios"][s]
            out.append(f"| {SCENARIO_LABEL.get(s, s)} ({v['windows']}) | {v['raw']['hr']['mae']:.2f} bpm "
                       f"({num(v['raw_on_common']['spo2']['mae'])}) | {e['denoised']['hr']['mae']:.2f} "
                       f"({num(e['denoised_on_common']['spo2']['mae'])}) | {v['denoised']['hr']['mae']:.2f} "
                       f"({num(v['denoised_on_common']['spo2']['mae'])}) |")
        return "\n".join(out)

    def hard_cases(self):
        if "hard_cases" not in self.srv or "hard_cases" not in self.edge:
            return None
        cols = [c for c in self._with_previous() if "hard_cases" in c[1]]
        out = self._head("Input (windows): heart rate reported / wrong, SpO2 reported / wrong", cols)
        for k, v in self.srv["hard_cases"]["classical"].items():
            cells = []
            for _, src, path in cols:
                x = src["hard_cases"][path][k]
                cells.append(f"{x['heart_rate_reported']} / {x['heart_rate_wrong']}, {x['spo2_reported']} / {x['spo2_wrong']}")
            out.append(f"| {HARD_LABEL.get(k, k)} ({v['windows']}) | " + " | ".join(cells) + " |")
        return "\n".join(out)

    def synthetic(self):
        s, e = self.srv["synthetic_test"], self.edge["synthetic_test"]
        sev = list(s["by_severity"])
        n_common = s["all"]["raw_on_common"]["spo2"]["n_scored"]
        raw = s["all"]["raw"]["hr"]
        out = [f"| {s['all']['raw']['hr']['n']:,} simulated windows | No network | Bracelet | Server |", "|---|---|---|---|",
               f"| Artefact mask, AUC | – | {e['mask_auc']:.3f} | {s['mask_auc']:.3f} |",
               f"| Heart-rate error, mean (all windows) | {raw['mae']:.1f} bpm ² | {e['all']['denoised']['hr']['mae']:.2f} | "
               f"{s['all']['denoised']['hr']['mae']:.2f} |",
               f"| … {SEVERITY_LABEL} | " + " / ".join(f"{s['by_severity'][k]['raw']['hr']['mae']:.2f}" for k in sev)
               + " | " + " / ".join(f"{e['by_severity'][k]['denoised']['hr']['mae']:.2f}" for k in sev)
               + " | " + " / ".join(f"{s['by_severity'][k]['denoised']['hr']['mae']:.2f}" for k in sev) + " |",
               f"| SpO2 error, mean, on the {n_common:,} windows where the server network and no network both give a "
               f"value | {s['all']['raw_on_common']['spo2']['mae']:.2f} points | "
               f"{e['all']['denoised_on_common']['spo2']['mae']:.2f} ¹ | {s['all']['denoised_on_common']['spo2']['mae']:.2f} |",
               f"| … {SEVERITY_LABEL}, each path on the windows where it gives a value | "
               + " / ".join(num(s["by_severity"][k]["raw"]["spo2"]["mae"]) for k in sev)
               + " | " + " / ".join(num(e["by_severity"][k]["denoised"]["spo2"]["mae"]) for k in sev)
               + " | " + " / ".join(num(s["by_severity"][k]["denoised"]["spo2"]["mae"]) for k in sev) + " |",
               "",
               f"¹ On the {e['all']['raw_on_common']['spo2']['n_scored']:,} windows where the bracelet network and no "
               "network both give a value.",
               f"² Over the {raw['n_scored']:,} of {raw['n']:,} windows where it gives a heart rate; the networks give one "
               f"in {s['all']['denoised']['hr']['n_scored']:,} (server) and {e['all']['denoised']['hr']['n_scored']:,} "
               "(bracelet).",
               "",
               "Shares of clean / lightly / moderately / heavily disturbed windows: "
               + " / ".join(f"{100 * s['by_severity'][k]['share']:.0f} %" for k in sev) + "."]
        return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--metrics", default=str(ML / "models" / "metrics"))
    ap.add_argument("--previous", default="v4", help="version label of the networks shipped before ('' for none)")
    a = ap.parse_args()
    t = Tables(Path(a.metrics), a.previous or None)
    sections = [("README: whole pipeline with every reliability check", t.pipeline),
                ("README: share of windows that get a heart rate, by motion", t.motion),
                ("README: windows without motion, by pulse size", t.rest),
                ("README: pulse shapes generated outside the training simulator", t.shapes),
                ("README: inputs that must not produce a value", t.must_not_report),
                ("README: real PPG recordings through the complete pipeline", t.real_pipeline),
                ("README: known hard cases", t.hard_cases),
                ("MODEL_CARD section 1: results without gates", t.synthetic),
                ("MODEL_CARD section 1: real PPG, no checks", t.real_no_checks)]
    for title, fn in sections:
        table = fn()
        if table is not None:
            print(f"<!-- {title} -->\n{table}\n")


if __name__ == "__main__":
    main()
