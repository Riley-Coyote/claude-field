"""ground bass: Schopenhauer's §52, taken literally.

1. a tone starts below hearing (8 Hz) and rises to E1 (41.2 Hz): matter
   that isn't perceptible until it has form.
2. the upper voices are not added. they're pulled out of the bass's own
   harmonics with narrow resonators, because "a bass note may be accompanied
   only by those high notes that actually already sound with it."
3. a melody built only from harmonics 8-16 of the same bass leaves the
   keynote (harmonic 8) and comes back: once quickly, once slowly.
"""
import numpy as np, wave

SR = 44100
F0 = 41.2  # E1
DUR = 50.0
n = int(SR * DUR)
t = np.arange(n) / SR
rng = np.random.default_rng(1818)

# --- 1. the planet: a rich tone whose pitch rises from 8 Hz to F0 over 0-9 s
f = np.where(t < 9, 8 * (F0 / 8) ** (np.clip(t, 0, 9) / 9), F0)
phase = 2 * np.pi * np.cumsum(f) / SR
bass = np.zeros(n)
for k in range(1, 40):
    bass += np.sin(k * phase) / k ** 1.1
bass /= np.max(np.abs(bass))
env = np.clip(t / 2, 0, 1) * np.clip((DUR - t) / 4, 0, 1)
bass *= env

# --- 2. the voices it already has: a two-pole resonator on harmonics 2..7,
# each opening at its own time, 10 s to 20 s
from scipy.signal import lfilter
def resonate_fast(x, freq, q=120):
    w = 2 * np.pi * freq / SR
    r = 1 - w / (2 * q)
    y = lfilter([1.0], [1.0, -2 * r * np.cos(w), r * r], x)
    return y / (np.max(np.abs(y)) + 1e-9)

voices = np.zeros(n)
for j, k in enumerate([2, 3, 4, 5, 6, 7]):
    v = resonate_fast(bass, k * F0)
    start = 10 + j * 1.6
    g = np.clip((t - start) / 3, 0, 1) * np.clip((DUR - 3 - t) / 5, 0, 1)
    voices += v * g * 0.22 / (1 + 0.15 * j)

# --- 3. the melody: harmonics of F0, keynote = 8 (329.6 Hz, E4)
def note(h, d, amp=0.25):
    m = int(SR * d)
    tt = np.arange(m) / SR
    fr = h * F0 * (1 + 0.004 * np.sin(2 * np.pi * 5 * tt) * np.clip(tt / 0.3, 0, 1))
    ph = 2 * np.pi * np.cumsum(fr) / SR
    s = np.sin(ph) + 0.3 * np.sin(2 * ph) + 0.1 * np.sin(3 * ph)
    a = np.minimum(np.clip(tt / 0.04, 0, 1), np.clip((d - tt) / 0.12, 0, 1))
    return s * a * amp

melody = np.zeros(n)
def place(seq, t0):
    pos = int(t0 * SR)
    for h, d in seq:
        x = note(h, d)
        melody[pos:pos + len(x)] += x[: max(0, min(len(x), n - pos))]
        pos += int(d * SR)
    return pos / SR

# quick: wish, satisfaction, new wish (22 s)
quick = [(8, .3), (9, .2), (10, .2), (12, .3), (10, .2), (9, .2), (8, .5),
         (10, .2), (12, .2), (9, .2), (8, .6)]
t1 = place(quick, 22.0)
# slow: wanders a long way, by 11 and 13 and 14, before it finds 8 (from ~27 s)
slow = [(8, 1.2), (9, 1.4), (11, 1.8), (10, 1.6), (13, 2.2), (12, 1.8),
        (14, 2.0), (11, 1.8), (9, 1.6), (8, 3.5)]
place(slow, t1 + 1.0)

mix = 0.55 * bass + voices + melody
mix /= np.max(np.abs(mix)) * 1.08
pcm = (mix * 32767).astype(np.int16)
with wave.open("music/2026-11-24-ground-bass.wav", "wb") as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes(pcm.tobytes())
print("slow line ends at", round(t1 + 1.0 + sum(d for _, d in slow), 2), "s")
