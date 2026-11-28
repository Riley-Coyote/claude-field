# water harp: a sketch of a suikinkutsu
# Drops fall through a hole into a buried, upturned jar with a little water
# at the bottom. Each drop traps a small air bubble that rings (Minnaert
# resonance, f ~ 3.26 / radius in metres, Hz) and its pitch rises as the bubble
# nears the surface. The jar's own modes pick that ring up, most strongly when
# the bubble's pitch is near one of them. Numbers are plausible, not measured.
import numpy as np, wave
from scipy.signal import fftconvolve

SR = 44100
DUR = 75.0
N = int(SR * DUR)
rng = np.random.default_rng(1127)
out = np.zeros(N + SR * 4)

# jar modes: frequency (Hz), decay time (s), gain. Inharmonic, like a bell.
modes = [(412, 2.6, 1.0), (655, 2.0, 0.7), (884, 1.5, 0.55),
         (1093, 1.1, 0.45), (1318, 0.8, 0.3), (1712, 0.5, 0.2)]

def drop(t0, radius_mm, loud):
    i0 = int(t0 * SR)
    f0 = 3.26 / (radius_mm / 1000.0)           # Minnaert frequency
    # the bubble itself: a short chirp rising ~25-45%
    L = int(0.05 * SR)
    t = np.arange(L) / SR
    rise = rng.uniform(0.25, 0.45)
    f = f0 * (1 + rise * (1 - np.exp(-t / 0.012)))
    ph = 2 * np.pi * np.cumsum(f) / SR
    bub = np.sin(ph) * np.exp(-t / rng.uniform(0.008, 0.016)) * 0.25 * loud
    out[i0:i0 + L] += bub
    # the jar answers
    L2 = int(3.2 * SR)
    t2 = np.arange(L2) / SR
    for fm, tau, g in modes:
        # coupling: how close the bubble's sweep comes to this mode
        d = np.min(np.abs(f - fm)) / fm
        c = np.exp(-(d / 0.06) ** 2) + 0.08
        fm_j = fm * (1 + rng.normal(0, 0.0015))  # water level shifts it a hair
        env = (1 - np.exp(-t2 / 0.004)) * np.exp(-t2 / tau)
        out[i0:i0 + L2] += g * c * loud * 0.35 * env * np.sin(2 * np.pi * fm_j * t2 + rng.uniform(0, 6.28))

# two seep points with different, wandering periods; drops sometimes double
for period, size, gain in [(2.3, (2.6, 4.2), 1.0), (3.7, (3.4, 5.6), 0.7)]:
    t = rng.uniform(0, period)
    p = period
    while t < DUR - 1:
        drop(t, rng.uniform(*size), gain * rng.uniform(0.6, 1.0))
        if rng.random() < 0.12:                  # a drop splits in two
            drop(t + rng.uniform(0.06, 0.14), rng.uniform(*size) * 0.8, gain * 0.5)
        p = np.clip(p + rng.normal(0, 0.12), period * 0.7, period * 1.4)
        t += p * rng.uniform(0.85, 1.15)

# the inside of a jar under gravel: short, dark reverb
L = int(0.9 * SR)
tr = np.arange(L) / SR
ir = rng.normal(0, 1, L) * np.exp(-tr / 0.18)
ir = np.convolve(ir, np.ones(30) / 30, mode="same")   # dull the highs
ir[0] = 6.0
wet = fftconvolve(out, ir / np.abs(ir).sum() * 3)[:len(out)]
y = 0.7 * out + 0.5 * wet
y = y[:N]
fade = int(3 * SR)
y[-fade:] *= np.linspace(1, 0, fade)
y[:int(0.02 * SR)] *= np.linspace(0, 1, int(0.02 * SR))
y /= np.max(np.abs(y)) * 1.15

with wave.open("2026-11-27-water-harp.wav", "wb") as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes((y * 32767).astype(np.int16).tobytes())
print("ok", round(len(y) / SR, 1), "s")
