"""Physiologically informed simulator of raw MAX30102 red/IR windows.

Used to train and test the motion-artefact denoiser, where the clean signal
under the artefacts must be known exactly. It is *not* used for anything
glucose-related: the simulator encodes no glucose physiology, and a glucose
model fitted to simulated data would only learn the simulator's assumptions.

Model of one channel (counts):

    raw(t) = DC(t) * (1 - bv(t) * contact(t)) * (1 + m(t)) + noise

* ``bv``: pulsatile blood-volume signal (AC/DC units): a train of beats with
  respiratory sinus arrhythmia, Mayer waves, jitter and occasional ectopic
  beats, with respiratory amplitude and baseline modulation. The shape of a
  beat comes from a deliberately wide family (``sample_morphology``): a
  skewed systolic wave plus a reflected/diastolic wave and a windkessel decay
  (a fingertip-like pulse), the same pulse low-passed down to little more
  than its fundamental (as the tissue does at the wrist), a smooth harmonic
  series, or a harmonic series rich in overtones (a 2nd harmonic up to 1.6
  times the fundamental: a deep notch and a large diastolic wave), each with
  one dominant peak per beat in the noise-free shape. The rich family's
  diastolic wave can still pass for a beat after band-pass filtering at slow
  rates: in a review, the beat detector found double the rate in 14 of 200
  clean windows of that family, all below 66 bpm.
  The red channel's pulsatile part is the IR one scaled by the ratio of
  ratios R that corresponds to the simulated SpO2.
* ``m``: motion modulation of the detected light (periodic arm swing / gait,
  band-limited bursts, pressure steps with recovery, spikes, slow wander),
  present in both channels with a channel gain that differs from R, which is
  what lets a dual-wavelength model separate motion from pulse.
* ``contact``: partial loss of skin contact (pulse amplitude drops).
* sensor noise, 18-bit quantisation and ADC saturation.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy import ndimage, signal

from ..config import ADC_MAX, FS, HR_MAX_BPM, HR_MIN_BPM, SPO2_COEFFS, WINDOW
from ..signal.filters import bandpass, lowpass, preprocess


# ---------------------------------------------------------------------------
# SpO2 <-> R
# ---------------------------------------------------------------------------

def spo2_from_r(r: np.ndarray | float, coeffs=SPO2_COEFFS) -> np.ndarray | float:
    a, b, c = coeffs
    return a * np.square(r) + b * np.asarray(r) + c


def r_from_spo2(spo2: float, coeffs=SPO2_COEFFS) -> float:
    """Invert the calibration curve on the physiological branch of R.

    Values above the curve's maximum (~99.96 % for the default curve) map to
    the R at the vertex.
    """
    a, b, c = coeffs
    r_vertex = -b / (2 * a)
    if spo2 >= spo2_from_r(r_vertex, coeffs) - 1e-9:
        return float(r_vertex)
    roots = np.roots([a, b, c - spo2])
    roots = roots[np.isreal(roots)].real
    roots = roots[(roots > 0.15) & (roots < 2.0)]
    if roots.size == 0:
        raise ValueError(f"SpO2 {spo2} outside calibration range")
    # The quadratic peaks near R=0.34; the descending branch is physiological.
    return float(roots.max())


# ---------------------------------------------------------------------------
# Containers
# ---------------------------------------------------------------------------

@dataclass
class Morphology:
    c1: float          # systolic peak latency offset (s)
    s1l: float         # systolic rise width (s)
    s1r: float         # systolic fall width (s)
    dtr: float         # delay of reflected / diastolic wave after systole (s)
    a2: float          # relative amplitude of the reflected wave
    s2: float          # width of the reflected wave (s)
    a3: float          # windkessel decay amplitude
    tau: float         # windkessel time constant (s)
    lp_hz: float | None = None       # cut-off of a low-pass on the pulse train (None: the wave model as it is)
    harmonics: tuple | None = None   # (sign, amplitudes, phases) of harmonics 2..4: a harmonic-series pulse instead


@dataclass
class SimWindow:
    fs: float
    red_raw: np.ndarray
    ir_raw: np.ndarray
    red_clean_raw: np.ndarray
    ir_clean_raw: np.ndarray
    mask: np.ndarray                 # 1 where an artefact dominates the pulse
    beat_onsets: np.ndarray          # seconds, beats whose onset is in-window
    hr_bpm: float
    spo2: float
    r_ratio: float
    pi_ir: float                     # IR perfusion index, fraction (0.01 = 1 %)
    artifact_types: list[str] = field(default_factory=list)
    artifact_level: float = 0.0
    meta: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Building blocks
# ---------------------------------------------------------------------------

def _loguniform(rng, lo, hi):
    return float(np.exp(rng.uniform(np.log(lo), np.log(hi))))


# Shares of the pulse-shape families: the wave model as it is, the wave model
# behind a low-pass, a smooth harmonic series, a harmonic series rich in
# overtones. Real recordings span both ends: wrist pulses can be nearly
# sinusoidal, while three public recordings (heartpy) have a 2nd harmonic of
# 0.9-1.6 times the fundamental, more than the wave model ever makes (< 0.6).
SHAPE_SHARES = (0.30, 0.30, 0.15, 0.25)
# Harmonics 2..5 of the two harmonic families: upper bounds of the uniform amplitude draws.
SMOOTH_HARMONICS = (0.45, 0.2, 0.08, 0.0)
RICH_HARMONICS = (1.6, 0.7, 0.35, 0.15)
PULSE_PAD_S = 1.0          # margin simulated around the window for the low-pass (beat_train covers 2 s)


def _sample_harmonics(rng: np.random.Generator, bounds=SMOOTH_HARMONICS) -> tuple:
    """A pulse as fundamental + harmonics 2..5 with random amplitudes (up to
    ``bounds``) and phases: ``sign * (sin(th) + sum a_k sin(k th + p_k))``.
    Drawn until the unfiltered shape has one dominant peak per beat (the
    second highest local maximum below 0.6 of it, by height above the
    minimum); oriented so that the steeper flank rises (systole)."""
    th = np.linspace(0.0, 2 * np.pi, 240, endpoint=False)
    for _ in range(30):
        amps = np.array([rng.uniform(0, b) for b in bounds])
        phases = rng.uniform(0, 2 * np.pi, len(bounds))
        x = np.sin(th) + sum(a * np.sin((k + 2) * th + p) for k, (a, p) in enumerate(zip(amps, phases)))
        d = np.diff(np.concatenate([x, x[:1]]))
        sign = 1.0 if d.max() >= -d.min() else -1.0
        x = sign * x
        # local maxima of the periodic shape, by height above the minimum
        peaks = np.flatnonzero((x > np.roll(x, 1)) & (x >= np.roll(x, -1)))
        heights = np.sort(x[peaks] - x.min())[::-1]
        if heights.size == 1 or heights[1] < 0.6 * heights[0]:
            return sign, amps, phases
    # Not reached in practice (no fallback in 4,000 draws): sin(th) - 0.2 sin(2 th), oriented by the same rule.
    amps, phases = np.array([0.2] + [0.0] * (len(bounds) - 1)), np.array([np.pi] + [0.0] * (len(bounds) - 1))
    x = np.sin(th) + amps[0] * np.sin(2 * th + phases[0])
    d = np.diff(np.concatenate([x, x[:1]]))
    return (1.0 if d.max() >= -d.min() else -1.0), amps, phases


SHAPE_FAMILIES = ("wave", "low_pass", "smooth_harmonics", "rich_harmonics")


def sample_morphology(rng: np.random.Generator, hr_bpm: float = 75.0, shape: str | None = None) -> Morphology:
    """Shape of the pulse in one window.

    The shape matters to a model that has to tell a pulse from motion. A
    fingertip pulse has a sharp systolic peak and a visible reflected wave; a
    wrist reflectance pulse at red/IR is often little more than a fundamental
    with a weak second harmonic, which is also what periodic motion looks
    like. Networks trained on the sharp kind alone took the smooth kind for
    motion: they accepted 100 % of clean windows of the wave model, 28-68 %
    with the content above 3.5 Hz removed and 1-12 % above 2.5 Hz, where the
    classical path kept 100 %. So the family is wide on purpose, and what is
    left to tell motion from a pulse is what does not depend on the shape:
    the red/IR proportion and the regularity over the window.
    """
    # "stiffness" in [0, 1]: young/compliant (0) -> old/stiff (1). Stiff
    # arteries bring the reflected wave forward and make it larger, which
    # blurs the dicrotic notch, as in real ageing.
    stiff = rng.beta(2.0, 2.0)
    s1l = rng.uniform(0.03, 0.06)
    m = Morphology(
        c1=max(rng.uniform(0.08, 0.14), 3.0 * s1l),
        s1l=s1l,
        s1r=rng.uniform(0.07, 0.14),
        dtr=float(np.clip(0.33 - 0.18 * stiff + rng.normal(0, 0.025), 0.10, 0.40)),
        a2=float(np.clip(0.25 + 0.4 * stiff + rng.normal(0, 0.08), 0.05, 0.85)),
        s2=rng.uniform(0.06, 0.14),
        a3=rng.uniform(0.0, 0.3),
        tau=rng.uniform(0.2, 0.6),
    )
    u = rng.random()
    edges = np.cumsum(SHAPE_SHARES)
    if shape is not None:                    # a given family (tests, evaluations); same random stream
        if shape not in SHAPE_FAMILIES:
            raise ValueError(f"shape must be one of {SHAPE_FAMILIES}")
        u = (0.0, edges[0], edges[1], edges[2])[SHAPE_FAMILIES.index(shape)]
    if u >= edges[2]:
        m.harmonics = _sample_harmonics(rng, RICH_HARMONICS)
    elif u >= edges[1]:
        m.harmonics = _sample_harmonics(rng, SMOOTH_HARMONICS)
    elif u >= edges[0]:
        # From "the second harmonic is still there" (1.25 x the pulse rate) to "nearly the wave model" (8 Hz).
        m.lp_hz = _loguniform(rng, max(1.25 * hr_bpm / 60.0, 1.2), 8.0)
    return m


def beat_train(t0: float, t1: float, hr_bpm: float, rng: np.random.Generator, *,
               resp_hz: float, rsa: float, lf: float, jitter: float,
               trend: float = 0.0, ectopic_prob: float = 0.0) -> tuple[np.ndarray, np.ndarray]:
    """Beat onset times (s) and RR intervals covering [t0 - 2 s, t1 + 2 s]."""
    ph_r, ph_lf = rng.uniform(0, 2 * np.pi, 2)
    lf_hz = rng.uniform(0.07, 0.13)
    rr_min, rr_max = 60.0 / HR_MAX_BPM, 60.0 / HR_MIN_BPM
    t = t0 - 2.0 + rng.uniform(0, 60.0 / hr_bpm)
    onsets, rrs = [], []
    span = max(t1 - t0, 1e-6)
    while t < t1 + 2.0:
        frac = float(np.clip((t - t0) / span, 0.0, 1.0))
        rr0 = 60.0 / (hr_bpm * (1.0 + trend * frac))
        rr = rr0 * (1.0 + rsa * np.sin(2 * np.pi * resp_hz * t + ph_r)
                    + lf * np.sin(2 * np.pi * lf_hz * t + ph_lf)
                    + jitter * rng.standard_normal())
        if ectopic_prob > 0 and rng.random() < ectopic_prob:
            prem = rng.uniform(0.55, 0.8)
            for r in (rr * prem, rr * (2.0 - prem)):  # premature + compensatory
                r = float(np.clip(r, rr_min, rr_max))
                onsets.append(t)
                rrs.append(r)
                t += r
            continue
        rr = float(np.clip(rr, rr_min, rr_max))
        onsets.append(t)
        rrs.append(rr)
        t += rr
    return np.asarray(onsets), np.asarray(rrs)


def pulse_signal(t: np.ndarray, onsets: np.ndarray, rrs: np.ndarray, morph: Morphology,
                 rng: np.random.Generator, *, resp_hz: float, am_resp: float) -> np.ndarray:
    """The pulse waveform at times ``t``, normalised to unit median beat amplitude."""
    fs = 1.0 / (t[1] - t[0])
    pad = int(round(PULSE_PAD_S * fs)) if (morph.lp_hz or morph.harmonics) else 0
    tt = t[0] + (np.arange(t.size + 2 * pad) - pad) / fs
    ph = rng.uniform(0, 2 * np.pi)
    if morph.harmonics is not None:
        sign, amps, phases = morph.harmonics
        amp = 1.0 + am_resp * np.sin(2 * np.pi * resp_hz * onsets + ph) + 0.03 * rng.standard_normal(onsets.size)
        th = 2 * np.pi * np.interp(tt, onsets, np.arange(onsets.size))          # one turn per beat
        p = np.sin(th)
        for k, (a, q) in enumerate(zip(amps, phases)):
            p = p + a * np.sin((k + 2) * th + q)
        p = sign * p * np.interp(tt, onsets, amp)
    else:
        p = np.zeros_like(tt)
        for t_on, rr in zip(onsets, rrs):
            amp = 1.0 + am_resp * np.sin(2 * np.pi * resp_hz * t_on + ph) + 0.03 * rng.standard_normal()
            j = 1.0 + 0.03 * rng.standard_normal(4)  # per-beat shape jitter
            mu1 = morph.c1 * j[0] + 0.05 * rr
            mu2 = mu1 + morph.dtr * j[1] * (0.75 + 0.25 * min(rr / 0.8, 1.5))
            i0 = max(int((t_on - tt[0] - 0.05) * fs), 0)
            i1 = min(int((t_on - tt[0] + 3.0) * fs) + 1, tt.size)
            if i1 <= i0:
                continue
            tau = tt[i0:i1] - t_on
            s1 = np.where(tau < mu1, morph.s1l, morph.s1r * j[2])
            g1 = np.exp(-0.5 * ((tau - mu1) / s1) ** 2)
            g2 = morph.a2 * j[3] * np.exp(-0.5 * ((tau - mu2) / morph.s2) ** 2)
            gate = 1.0 / (1.0 + np.exp(-(tau - mu1) / 0.02))
            g3 = morph.a3 * gate * np.exp(-np.clip(tau - mu1, 0, None) / morph.tau)
            p[i0:i1] += amp * (g1 + g2 + g3)
        if morph.lp_hz:
            p = lowpass(p, fs, morph.lp_hz, order=2)
    p = p[pad:pad + t.size]
    bp = bandpass(p, fs, 0.4, 12.0)
    scale = np.percentile(bp, 97) - np.percentile(bp, 3)
    return p / max(scale, 1e-9)


def _smooth_noise(rng, n, fs, lo, hi, order=2):
    x = rng.standard_normal(n + int(4 * fs))
    nyq = fs / 2
    if lo <= 0:
        sos = signal.butter(order, min(hi, 0.95 * nyq) / nyq, btype="lowpass", output="sos")
    else:
        sos = signal.butter(order, [lo / nyq, min(hi, 0.95 * nyq) / nyq], btype="bandpass", output="sos")
    y = signal.sosfiltfilt(sos, x)[int(2 * fs): int(2 * fs) + n]
    return y / max(np.std(y), 1e-12)


def _envelope(rng, n, fs, min_s, max_s, full_prob=0.0):
    """Smooth on/off envelope covering a random sub-interval (or everything)."""
    if rng.random() < full_prob:
        return np.ones(n)
    dur = int(rng.uniform(min_s, max_s) * fs)
    dur = int(np.clip(dur, 2, n))
    start = rng.integers(-dur // 3, n - 2 * dur // 3 + 1)
    env = np.zeros(n)
    ramp = max(int(0.15 * fs), 1)
    win = signal.windows.tukey(dur, alpha=min(1.0, 2 * ramp / dur))
    a, b = max(start, 0), min(start + dur, n)
    env[a:b] = win[a - start: b - start]
    return env


def motion_artifact(n: int, fs: float, rng: np.random.Generator, amp: float, hr_hz: float,
                    kinds: list[str]) -> tuple[np.ndarray, np.ndarray]:
    """Motion modulation m(t) for IR and red, in relative-intensity units."""
    t = np.arange(n) / fs
    m = np.zeros(n)
    contact = np.ones(n)
    for kind in kinds:
        a = amp * _loguniform(rng, 0.4, 2.0)
        if kind == "periodic":
            # Arm swing / steps. A quarter of the time the motion frequency
            # sits within +-15 % of the heart rate, the hardest case for any
            # spectral method.
            if rng.random() < 0.25:
                f = hr_hz * rng.uniform(0.85, 1.15)
            else:
                f = rng.uniform(0.7, 3.2)
            fm = 1.0 + 0.04 * np.sin(2 * np.pi * rng.uniform(0.05, 0.3) * t + rng.uniform(0, 6.3))
            phase = 2 * np.pi * np.cumsum(f * fm) / fs
            wave = np.zeros(n)
            for h, ha in enumerate([1.0, rng.uniform(0, 0.6), rng.uniform(0, 0.3)], start=1):
                wave += ha * np.sin(h * phase + rng.uniform(0, 2 * np.pi))
            # From the steady amplitude of an even gait to a 30 % wander: networks trained on
            # modulated swing alone took steady swing with an arterial-like red/IR gain for a pulse.
            am = 1.0 + rng.uniform(0.0, 0.3) * _smooth_noise(rng, n, fs, 0, 0.3)
            m += a * wave * am * _envelope(rng, n, fs, 2.0, n / fs, full_prob=0.35)
        elif kind == "burst":
            hi = rng.uniform(2.0, 8.0)
            m += a * 1.5 * _smooth_noise(rng, n, fs, 0.2, hi) * _envelope(rng, n, fs, 0.3, 3.0)
        elif kind == "step":
            t0 = rng.uniform(0, n / fs)
            h = a * rng.uniform(1.0, 4.0) * rng.choice([-1, 1])
            if rng.random() < 0.3:  # permanent DC shift (sensor moved)
                m += np.where(t >= t0, h, 0.0)
            else:                   # pressure change that recovers
                tau = rng.uniform(0.2, 3.0)
                m += np.where(t >= t0, h * np.exp(-np.clip(t - t0, 0, None) / tau), 0.0)
        elif kind == "spike":
            for _ in range(rng.integers(1, 4)):
                i = rng.integers(0, n)
                w = rng.integers(1, 4)
                m[i:i + w] += a * rng.uniform(2.0, 8.0) * rng.choice([-1, 1])
        elif kind == "wander":
            m += a * _smooth_noise(rng, n, fs, 0, rng.uniform(0.3, 1.0))
        elif kind == "contact":
            env = _envelope(rng, n, fs, 0.5, 3.0)
            contact *= 1.0 - env * rng.uniform(0.7, 1.0)
            # Lifting the sensor changes the detected light by a lot (ambient
            # leak or loss of tissue path), either way.
            m += env * rng.uniform(0.05, 0.5) * rng.choice([-1, 1])
    # Red sees the same motion with a different gain plus a small independent part.
    g = rng.uniform(0.5, 1.8)
    m_red = g * m + 0.15 * amp * _smooth_noise(rng, n, fs, 0.2, 5.0) * (np.abs(m) > 0).astype(float) * rng.random()
    return np.stack([m, m_red]), contact


ARTIFACT_KINDS = ("periodic", "burst", "step", "spike", "wander", "contact")
ARTIFACT_WEIGHTS = np.array([0.3, 0.25, 0.15, 0.1, 0.15, 0.05])


def _measure(t: np.ndarray, fs: float, rng: np.random.Generator, pulse: np.ndarray, r: float, pi_ir: float,
             resp_hz: float, hr_bpm: float, clean_prob: float, artifact_level: float | None,
             kinds: list[str] | None):
    """Optics, motion, sensor noise and the ground-truth artefact mask for a
    unit-amplitude pulse waveform (shared by simulated and real pulses)."""
    n = t.size
    riiv = rng.uniform(0, 0.6) * pi_ir * np.sin(2 * np.pi * resp_hz * t + rng.uniform(0, 6.3))
    vaso = rng.uniform(0, 0.5) * pi_ir * _smooth_noise(rng, n, fs, 0, 0.15)
    delay = rng.uniform(0, 0.008)
    pulse_red = np.interp(t - delay, t, pulse)
    rv = rng.uniform(0.8, 1.3)  # ratio for non-arterial (venous/tissue) modulation
    bv_ir = pi_ir * pulse + riiv + vaso
    bv_red = r * pi_ir * pulse_red + rv * (riiv + vaso)

    # --- optics / DC ------------------------------------------------------
    dc_ir0 = rng.uniform(30_000, 200_000)
    dc_red0 = dc_ir0 * rng.uniform(0.5, 1.1)
    drift = 1.0 + rng.uniform(0, 0.02) * _smooth_noise(rng, n, fs, 0, 0.05)
    dc_ir, dc_red = dc_ir0 * drift, dc_red0 * drift

    ir_clean = dc_ir * (1.0 - bv_ir)
    red_clean = dc_red * (1.0 - bv_red)

    # --- motion ------------------------------------------------------------
    types: list[str] = []
    level = 0.0
    m = np.zeros((2, n))
    contact = np.ones(n)
    if kinds is not None or rng.random() >= clean_prob:
        if kinds is None:
            k = rng.choice([1, 2, 3], p=[0.55, 0.33, 0.12])
            kinds = list(rng.choice(ARTIFACT_KINDS, size=k, replace=False, p=ARTIFACT_WEIGHTS))
        types = list(kinds)
        level = artifact_level if artifact_level is not None else _loguniform(rng, 0.1, 15.0)
        if types:
            m, contact = motion_artifact(n, fs, rng, level * pi_ir, hr_bpm / 60.0, types)

    noise_rel = _loguniform(rng, 1e-5, 3e-4)
    ir = dc_ir * (1.0 - bv_ir * contact) * (1.0 + m[0]) + rng.normal(0, noise_rel * dc_ir0, n)
    red = dc_red * (1.0 - bv_red * contact) * (1.0 + m[1]) + rng.normal(0, noise_rel * dc_red0, n)
    ir = np.clip(np.round(ir), 0, ADC_MAX)
    red = np.clip(np.round(red), 0, ADC_MAX)

    # --- ground-truth artefact mask ----------------------------------------
    # A sample is "artefact" if either channel deviates from its clean pulse
    # by more than a quarter of that channel's pulse amplitude: the mask also
    # weights the SpO2 ratio, which needs *both* channels clean.
    k = max(int(0.3 * fs), 1)
    mask = np.zeros(t.size, dtype=bool)
    for noisy_raw, clean_raw in ((ir, ir_clean), (red, red_clean)):
        bv_noisy, _ = preprocess(noisy_raw, fs)
        bv_clean, _ = preprocess(clean_raw, fs)
        ac_pp = np.percentile(bv_clean, 97) - np.percentile(bv_clean, 3)
        mask |= ndimage.maximum_filter1d(np.abs(bv_noisy - bv_clean), size=k) > 0.25 * ac_pp
    mask = mask.astype(np.float32)
    sat = (ir >= 0.98 * ADC_MAX) | (red >= 0.98 * ADC_MAX) | (ir <= 0) | (red <= 0)
    mask[ndimage.binary_dilation(sat, iterations=int(0.2 * fs))] = 1.0

    extra = {"noise_rel": noise_rel, "dc_ir": dc_ir0, "dc_red": dc_red0}
    return ir, red, ir_clean, red_clean, mask, types, float(level), extra


def corrupt_pulse(pulse: np.ndarray, rng: np.random.Generator | int | None = None, *, fs: float = FS,
                  spo2: float = 97.0, pi_ir: float = 0.01, hr_bpm: float = 75.0, clean_prob: float = 0.0,
                  artifact_level: float | None = None, kinds: list[str] | None = None) -> SimWindow:
    """Put a *given* blood-volume pulse (e.g. a real PPG recording, systolic
    peaks up) through the simulated MAX30102 optics, motion and noise.

    Used to test the denoiser on real pulse morphology and real heart-rate
    variability, which the synthetic beat model only approximates.
    """
    rng = np.random.default_rng(rng)
    x = np.asarray(pulse, dtype=np.float64)
    bp = bandpass(x - x.mean(), fs, 0.4, 12.0)
    x = (x - x.mean()) / max(np.percentile(bp, 97) - np.percentile(bp, 3), 1e-12)
    t = np.arange(x.size) / fs
    resp_hz = rng.uniform(0.12, 0.45)
    r = r_from_spo2(spo2)
    ir, red, ir_clean, red_clean, mask, types, level, extra = _measure(
        t, fs, rng, x, r, pi_ir, resp_hz, hr_bpm, clean_prob, artifact_level, kinds)
    return SimWindow(fs=fs, red_raw=red, ir_raw=ir, red_clean_raw=red_clean, ir_clean_raw=ir_clean, mask=mask,
                     beat_onsets=np.array([]), hr_bpm=float(hr_bpm), spo2=float(spo2), r_ratio=r, pi_ir=float(pi_ir),
                     artifact_types=types, artifact_level=level, meta={"resp_hz": resp_hz, **extra})


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def simulate_window(rng: np.random.Generator | int | None = None, *, n: int = WINDOW, fs: float = FS,
                    clean_prob: float = 0.2, artifact_level: float | None = None,
                    hr_bpm: float | None = None, spo2: float | None = None,
                    pi_ir: float | None = None, kinds: list[str] | None = None,
                    shape: str | None = None) -> SimWindow:
    """Simulate one raw MAX30102 window (both channels, counts). ``shape``: one of
    SHAPE_FAMILIES to fix the pulse-shape family (default: drawn with SHAPE_SHARES)."""
    rng = np.random.default_rng(rng)
    t = np.arange(n) / fs

    # --- physiology -------------------------------------------------------
    if hr_bpm is None:
        hr_bpm = float(np.clip(rng.normal(75, 15) if rng.random() < 0.8 else rng.uniform(45, 170), 40, 185))
    resp_hz = rng.uniform(0.12, 0.45)
    morph = sample_morphology(rng, hr_bpm, shape)
    onsets, rrs = beat_train(
        t[0], t[-1], hr_bpm, rng, resp_hz=resp_hz,
        rsa=rng.uniform(0.0, 0.06) * (75.0 / hr_bpm), lf=rng.uniform(0.0, 0.04),
        jitter=_loguniform(rng, 0.003, 0.03), trend=rng.normal(0, 0.05) if rng.random() < 0.3 else 0.0,
        ectopic_prob=0.03 if rng.random() < 0.1 else 0.0,
    )
    pulse = pulse_signal(t, onsets, rrs, morph, rng, resp_hz=resp_hz, am_resp=rng.uniform(0, 0.2))

    if spo2 is None:
        spo2 = float(np.clip(rng.normal(97, 1.5), 85, 99.5) if rng.random() < 0.85 else rng.uniform(82, 99.5))
    r = r_from_spo2(spo2)
    if pi_ir is None:
        pi_ir = _loguniform(rng, 0.0008, 0.05)  # 0.08 % (wrist, cold) .. 5 % (finger)

    ir, red, ir_clean, red_clean, mask, types, level, extra = _measure(
        t, fs, rng, pulse, r, pi_ir, resp_hz, hr_bpm, clean_prob, artifact_level, kinds)

    in_win = (onsets >= t[0]) & (onsets <= t[-1])
    rr_in = rrs[in_win]
    hr_true = 60.0 / float(np.mean(rr_in)) if rr_in.size else float(hr_bpm)
    return SimWindow(
        fs=fs, red_raw=red, ir_raw=ir, red_clean_raw=red_clean, ir_clean_raw=ir_clean,
        mask=mask, beat_onsets=onsets[in_win], hr_bpm=hr_true, spo2=float(spo2), r_ratio=r,
        pi_ir=float(pi_ir), artifact_types=types, artifact_level=float(level),
        meta={"resp_hz": resp_hz, "morph": morph.__dict__, **extra},
    )
