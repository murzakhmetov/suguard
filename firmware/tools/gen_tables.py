#!/usr/bin/env python3
"""Generate firmware/suguard/src/core/sg_tables.h from the Python reference.

Every number the C++ signal core shares with ml/suguard_ml is produced here,
from the same objects and code paths the reference uses (filters._sos,
scipy.signal.sosfilt_zi, config.py, ...), and written as hexadecimal
floating-point literals, so the C++ constants are bit-identical to the Python
ones. Never edit sg_tables.h by hand.

    python firmware/tools/gen_tables.py            # rewrite sg_tables.h
    python firmware/tools/gen_tables.py -o FILE    # write somewhere else
    python firmware/tools/gen_tables.py --check    # exit 1 if sg_tables.h is stale

Before writing anything the generator runs the reference pipeline on simulated
windows and checks that the filters listed in FILTERS are exactly the ones the
reference designs, with the padding it really uses.
"""
from __future__ import annotations

import argparse
import inspect
import math
import re
import sys
from pathlib import Path

import numpy as np
from scipy import signal

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ml"))

from suguard_ml import config, pipeline  # noqa: E402
from suguard_ml.signal import beats, filters, quality, spo2  # noqa: E402
from suguard_ml.synth.ppg import simulate_window  # noqa: E402

OUT = ROOT / "firmware" / "suguard" / "src" / "core" / "sg_tables.h"

FS = config.FS
NFFT = inspect.signature(beats.spectral_hr).parameters["nfft"].default
TEMPLATE_LEN = inspect.signature(beats.beat_template).parameters["length"].default
MIN_SAMPLES = int(2 * FS)          # pipeline.analyze refuses shorter windows ("need at least 2 s of data")
BAND_MIN_SAMPLES = math.ceil(3 * FS)   # spo2.cardiac_band and quality._r_spread: "x.size >= 3 * fs"

# C name, kind, cut-off (Hz), order, where the reference designs it.
FILTERS = [
    ("DC", "lowpass", inspect.signature(filters.blood_volume).parameters["fc_dc"].default, 2,
     "filters.estimate_dc"),
    ("PPG", "bandpass", config.PPG_BAND_HZ, 3, "filters.preprocess"),
    ("PULSE", "bandpass", (0.5, 8.0), 3, "beats.detect_beats, beats.spectral_hr"),
    ("CARDIAC", "bandpass", spo2.CARDIAC_BAND_HZ, 3, "spo2.cardiac_band"),
    ("RSPREAD", "bandpass", (0.7, 4.0), 3, "quality._r_spread"),
]


def _key(kind, cutoff, order):
    return kind, tuple(np.atleast_1d(cutoff).tolist()), int(order)


def reference_filters() -> dict:
    """Filters the reference really designs and the padlen it passes to
    sosfiltfilt: ``{(kind, cutoff, order): (sos, padlen)}``.

    Runs preprocess + vitals_from_signals on a full and on a minimum-length
    window with spies on filters._sos and scipy.signal.sosfiltfilt.
    """
    designed, padlens = {}, {}
    real_sos, real_filtfilt = filters._sos, signal.sosfiltfilt

    def spy_sos(kind, cutoff, fs, order):
        sos = real_sos(kind, cutoff, fs, order)
        assert fs == FS, f"filter designed for {fs} Hz"
        designed[_key(kind, cutoff, order)] = sos
        return sos

    def spy_filtfilt(sos, x, **kw):
        assert kw.get("padtype") == "odd" and kw.get("axis", -1) == -1
        padlens.setdefault(np.asarray(sos).tobytes(), set()).add(kw["padlen"])
        return real_filtfilt(sos, x, **kw)

    windows = [simulate_window(11, kinds=[]), simulate_window(12, n=MIN_SAMPLES, kinds=[])]
    filters._sos, signal.sosfiltfilt = spy_sos, spy_filtfilt
    try:
        for win in windows:
            sensor = quality.sensor_state(win.red_raw, win.ir_raw)
            ir_bv, _ = filters.preprocess(win.ir_raw)
            red_bv, _ = filters.preprocess(win.red_raw)
            pipeline.vitals_from_signals(ir_bv, red_bv, None, sensor, 1.0)
    finally:
        filters._sos, signal.sosfiltfilt = real_sos, real_filtfilt

    out = {}
    for key, sos in designed.items():
        used = padlens[sos.tobytes()]
        assert len(used) == 1, f"{key}: padlen depends on the window length: {sorted(used)}"
        out[key] = (sos, used.pop())
    return out


def build_filters() -> list[dict]:
    ref = reference_filters()
    mine = {_key(kind, cutoff, order) for _, kind, cutoff, order, _ in FILTERS}
    if mine != set(ref):
        raise SystemExit(f"FILTERS is out of sync with the reference:\n  listed here: {sorted(mine)}\n"
                         f"  designed by suguard_ml: {sorted(ref)}")
    out = []
    for name, kind, cutoff, order, where in FILTERS:
        sos, padlen = ref[_key(kind, cutoff, order)]
        assert np.array_equal(sos, filters._sos(kind, cutoff, FS, order))
        assert np.all(sos[:, 3] == 1.0), "sections must be normalised (a0 = 1)"
        assert padlen == 3 * (2 * sos.shape[0] + 1) * 4 <= MIN_SAMPLES - 1   # filters._filtfilt, never clipped
        out.append(dict(name=name, kind=kind, cutoff=np.atleast_1d(cutoff).tolist(), order=order, where=where,
                        sos=sos, zi=signal.sosfilt_zi(sos), padlen=padlen))
    return out


def spectral_bins() -> dict:
    """Integer-bin form of the frequency masks in beats.spectral_hr.

    The FFT frequencies k * fs / nfft are exact binary fractions, so every
    mask is an index range. The equivalence is verified here for every bin
    the peak can fall on.
    """
    f = np.fft.rfftfreq(NFFT, 1.0 / FS)
    df = FS / NFFT
    assert np.array_equal(f, np.arange(NFFT // 2 + 1) * df)
    idx = np.arange(f.size)

    def bounds(mask):
        k = np.flatnonzero(mask)
        assert k.size and np.array_equal(k, np.arange(k[0], k[-1] + 1))
        return int(k[0]), int(k[-1])

    lo_hz, hi_hz = config.HR_BAND_HZ
    band = (f >= lo_hz) & (f <= hi_hz)
    k_lo, k_hi = bounds(band)
    t_lo, t_hi = bounds((f >= 0.5) & (f <= 8.0))
    assert t_lo <= k_lo and k_hi <= t_hi          # in-band power > 0 implies total power > 0
    near = int(math.floor(0.1 / df))              # |f - f0| <= 0.1
    half2 = int(math.floor(2 * 0.08 / df))        # |f - f0 / 2| <= 0.08  <=>  |2 j - k| <= half2
    half_min = int(np.flatnonzero(f / 2 >= lo_hz)[0])
    fb = f[band]
    for k in range(k_lo, k_hi + 1):
        f0 = f[k]
        mask = (np.abs(f - f0) <= 0.1) | (np.abs(f - 2 * f0) <= 0.1)
        assert np.array_equal(mask, (np.abs(idx - k) <= near) | (np.abs(idx - 2 * k) <= near))
        assert k - near >= 0 and k + near < 2 * k - near and 2 * k + near <= NFFT // 2
        assert np.array_equal(np.abs(fb - f0 / 2) <= 0.08, np.abs(2 * idx[band] - k) <= half2)
        assert (f0 / 2 >= lo_hz) == (k >= half_min)
        assert float(f0 * 60.0) == k * df * 60.0
    return dict(df=df, k_lo=k_lo, k_hi=k_hi, t_lo=t_lo, t_hi=t_hi, near=near, half2=half2, half_min=half_min)


# --------------------------------------------------------------------------
# C++ output
# --------------------------------------------------------------------------

def hexfloat(v, suffix="") -> str:
    """C++17 hexadecimal literal that denotes exactly ``v``."""
    v = float(v)
    assert math.isfinite(v)
    lit = re.sub(r"\.?0*p", "p", v.hex())      # 0x1.9000000000000p+5 -> 0x1.9p+5
    assert float.fromhex(lit) == v
    return lit + suffix


def render() -> str:
    filts = build_filters()
    bins = spectral_bins()
    log2n = NFFT.bit_length() - 1
    assert 1 << log2n == NFFT and NFFT % 4 == 0

    ma_peak = max(int(round(0.111 * FS)), 1)       # beats.detect_beats: w1
    ma_beat = max(int(round(0.667 * FS)), 1)       # beats.detect_beats: w2
    lookback = int(0.6 * FS)                       # beats._find_onsets: look
    min_dist = FS * 60.0 / config.HR_MAX_BPM       # beats.detect_beats: refractory period in samples
    max_beats = int((config.WINDOW - 1) // min_dist) + 1

    out = []
    add = out.append

    def check(macro, value, origin):
        lit = str(value) if isinstance(value, int) else hexfloat(value)
        add(f"static_assert({macro} == {lit},")
        add(f'              "{macro} in sg_core.h differs from {origin} = {value!r}");')

    def const(ctype, name, value, comment):
        if ctype == "int":
            add(f"constexpr int {name} = {value};  // {comment}")
        else:
            add(f"constexpr double {name} = {hexfloat(value)};  // {float(value)!r} ({comment})")

    add("// GENERATED by firmware/tools/gen_tables.py from ml/suguard_ml - DO NOT EDIT.")
    add("//")
    add("// Constants the C++ core shares with the Python reference. Floating-point values are")
    add("// hexadecimal literals, i.e. exactly the bits Python computes with; the comments show")
    add("// them in decimal.")
    add("#pragma once")
    add("")
    add('#include "sg_core.h"')
    add('#include "sg_dsp.h"')
    add("")
    add("// ---- the hand-written contract must agree with suguard_ml ----------------------------")
    check("SG_FS", FS, "config.FS")
    check("SG_WINDOW", config.WINDOW, "config.WINDOW")
    check("SG_ADC_MAX", config.ADC_MAX, "config.ADC_MAX")
    check("SG_FINGER_IR_DC_MIN", config.FINGER_IR_DC_MIN, "config.FINGER_IR_DC_MIN")
    check("SG_FFT_N", NFFT, "the default nfft of beats.spectral_hr")
    check("SG_MAX_ARTIFACT_FRACTION", pipeline.MAX_ARTIFACT_FRACTION, "pipeline.MAX_ARTIFACT_FRACTION")
    check("SG_MIN_INPUT_PI", pipeline.MIN_INPUT_PI, "pipeline.MIN_INPUT_PI")
    check("SG_MIN_SPECTRAL_PURITY", pipeline.MIN_SPECTRAL_PURITY, "pipeline.MIN_SPECTRAL_PURITY")
    add("")
    add("// ---- scalar constants ------------------------------------------------------------------")
    const("double", "SG_PI", math.pi, "math.pi")
    const("double", "SG_SATURATION_LEVEL", config.SATURATION_LEVEL, "config.SATURATION_LEVEL")
    const("double", "SG_HR_MIN_BPM", config.HR_MIN_BPM, "config.HR_MIN_BPM")
    const("double", "SG_HR_MAX_BPM", config.HR_MAX_BPM, "config.HR_MAX_BPM")
    for name, value in zip("ABC", config.SPO2_COEFFS):   # SpO2 = A R^2 + B R + C
        const("double", f"SG_SPO2_{name}", value, f"config.SPO2_COEFFS, {name} of A R^2 + B R + C")
    const("double", "SG_R_MIN_PLAUSIBLE", spo2.R_MIN_PLAUSIBLE, "spo2.R_MIN_PLAUSIBLE")
    const("double", "SG_R_MAX_CALIBRATED", spo2.R_MAX_CALIBRATED, "spo2.R_MAX_CALIBRATED")
    const("double", "SG_MIN_RED_IR_CORR", spo2.MIN_RED_IR_CORR, "spo2.MIN_RED_IR_CORR")
    const("double", "SG_COMPONENT_MIN", quality.COMPONENT_MIN, "quality.COMPONENT_MIN")
    const("double", "SG_USABLE_SQI", quality.USABLE_SQI, "quality.USABLE_SQI")
    const("int", "SG_MIN_SAMPLES", MIN_SAMPLES, "shortest window, 2 s (pipeline.analyze)")
    const("int", "SG_BAND_MIN_SAMPLES", BAND_MIN_SAMPLES, "3 s: below it, no cardiac band-pass and no R spread")
    const("int", "SG_MA_PEAK_LEN", ma_peak, "beats.detect_beats: max(int(round(0.111 * fs)), 1)")
    const("int", "SG_MA_BEAT_LEN", ma_beat, "beats.detect_beats: max(int(round(0.667 * fs)), 1)")
    const("int", "SG_ONSET_LOOKBACK", lookback, "beats._find_onsets: int(0.6 * fs)")
    const("int", "SG_MAX_BEATS", max_beats, f"peaks of a window are >= fs * 60 / HR_MAX_BPM = {min_dist:.3f} samples apart")
    const("int", "SG_TEMPLATE_LEN", TEMPLATE_LEN, "the default length of beats.beat_template")
    add("")
    add("// ---- zero-phase Butterworth filters ----------------------------------------------------")
    add("// From filters._sos and scipy.signal.sosfilt_zi. One row per second-order section:")
    add("// {b0, b1, b2, a1, a2, zi0, zi1} with a0 = 1. The padding is the padlen of")
    add("// filters._filtfilt, 3 * (2 * sections + 1) * 4; it is never clipped to n - 1 because")
    add("// windows have at least SG_MIN_SAMPLES samples.")
    for f in filts:
        name, sections = f["name"], f["sos"].shape[0]
        cutoff = " - ".join(f"{v:g}" for v in f["cutoff"])
        add("")
        add(f"// {f['kind']} {cutoff} Hz, order {f['order']} ({f['where']})")
        add(f"static const SgBiquad SG_{name}_SECTIONS[{sections}] = {{")
        for row, zi in zip(f["sos"], f["zi"]):
            b, a = row[:3], row[4:]
            add("    // b = " + ", ".join(repr(float(v)) for v in b))
            add("    // a = 1, " + ", ".join(repr(float(v)) for v in a) + "; zi = " + ", ".join(repr(float(v)) for v in zi))
            add("    {" + ", ".join(hexfloat(v) for v in b) + ",")
            add("     " + ", ".join(hexfloat(v) for v in (*a, *zi)) + "},")
        add("};")
        add(f"static const SgFilter SG_FILTER_{name} = {{SG_{name}_SECTIONS, {sections}, {f['padlen']}}};")
    add("")
    const("int", "SG_MAX_SECTIONS", max(f["sos"].shape[0] for f in filts), "sections of the largest filter")
    const("int", "SG_MAX_PADLEN", max(f["padlen"] for f in filts), "longest padding")
    add('static_assert(SG_MAX_PADLEN < SG_MIN_SAMPLES, "the padding would be clipped to n - 1");')
    add("")
    add("// ---- spectral heart rate (beats.spectral_hr) ---------------------------------------------")
    add("// Bin k of the SG_FFT_N-point spectrum is the frequency k * SG_FFT_DF, so the frequency")
    add("// masks of the reference are index ranges (the generator verifies it for every bin).")
    const("int", "SG_FFT_LOG2N", log2n, "SG_FFT_N = 1 << SG_FFT_LOG2N")
    add('static_assert((1 << SG_FFT_LOG2N) == SG_FFT_N, "SG_FFT_N must be a power of two");')
    const("double", "SG_FFT_DF", bins["df"], "fs / nfft, Hz per bin")
    const("int", "SG_K_HR_LO", bins["k_lo"], "first bin of the cardiac band, f >= HR_BAND_HZ[0]")
    const("int", "SG_K_HR_HI", bins["k_hi"], "last bin of the cardiac band, f <= HR_BAND_HZ[1]")
    const("int", "SG_K_TOTAL_LO", bins["t_lo"], "first bin with f >= 0.5 Hz")
    const("int", "SG_K_TOTAL_HI", bins["t_hi"], "last bin with f <= 8 Hz")
    const("int", "SG_K_NEAR", bins["near"], "|f[j] - f[k]| <= 0.1 Hz  <=>  |j - k| <= SG_K_NEAR")
    const("int", "SG_K_HALF2", bins["half2"], "|f[j] - f[k] / 2| <= 0.08 Hz  <=>  |2 j - k| <= SG_K_HALF2")
    const("int", "SG_K_HALF_MIN", bins["half_min"], "f[k] / 2 >= HR_BAND_HZ[0]  <=>  k >= SG_K_HALF_MIN")
    add("")
    add("// sin(2 pi k / SG_FFT_N) for k = 0 .. SG_FFT_N / 4, rounded to float.")
    quarter = NFFT // 4
    table = [hexfloat(np.float32(math.sin(2.0 * math.pi * k / NFFT)), "f") for k in range(quarter + 1)]
    assert table[0] == "0x0p+0f" and table[-1] == "0x1p+0f"
    add(f"static const float SG_FFT_SIN[{quarter + 1}] = {{")
    for i in range(0, len(table), 6):
        add("    " + ", ".join(table[i:i + 6]) + ",")
    add("};")
    add("")
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("-o", "--output", type=Path, default=OUT, help=f"file to write (default: {OUT})")
    ap.add_argument("--check", action="store_true", help="do not write; fail if the output file is out of date")
    args = ap.parse_args()
    text = render()
    if args.check:
        if not args.output.exists() or args.output.read_text() != text:
            print(f"{args.output} is out of date: run {Path(__file__).name}", file=sys.stderr)
            return 1
        return 0
    args.output.write_text(text)
    print(f"wrote {args.output} ({len(text.splitlines())} lines)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
