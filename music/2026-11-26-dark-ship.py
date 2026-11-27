"""dark ship: what a recorder on a seabird's back might pick up, crossing
a vessel that has switched its transponder off.

after a 404 Media item (Nov 25): scientists put audio recorders on seabirds
and heard more ships than the tracking system admits to. i couldn't read the
article (offline), so this is built from general physics, not their data.

the parts, all synthesized:
- wind over the recorder: low-passed noise, gusting slowly. the bird doesn't
  flap much, so there are almost no wingbeats; the one sound the bird makes
  is the wind it makes by moving.
- the sea underneath: pink-ish noise swelling at swell period (~9 s).
- the ship: a two-stroke diesel at 90 rpm with 6 cylinders -> firing rate
  9 Hz, plus a 4-blade propeller at the same shaft rate -> blade rate 6 Hz.
  both far below the speaker's reach as fundamentals, so what you hear is
  their harmonics (a stack from ~18 to ~400 Hz), and a cavitation hiss
  that pulses at the blade rate.
- the pass: the bird at 14 m/s, flying a straight line that passes 60 m
  from the ship's stack at t = 24 s. loudness ~ 1/distance, air absorption
  as a gentle low-pass that opens as it nears, and Doppler with c = 343 m/s.
  the pitch drop at closest approach is about 8% (a bit over a semitone).
"""
import numpy as np, wave
from scipy.signal import lfilter, butter

SR = 44100
DUR = 48.0
n = int(SR * DUR)
t = np.arange(n) / SR
rng = np.random.default_rng(2026_11_26)

def lp(x, fc, order=2):
    b, a = butter(order, fc / (SR / 2))
    return lfilter(b, a, x)

def norm(x):
    return x / (np.max(np.abs(x)) + 1e-12)

# --- wind: gusts on a 3-7 s scale
gust = lp(rng.standard_normal(n), 0.25, 1)
gust = 0.55 + 0.45 * norm(gust)
wind = norm(lp(rng.standard_normal(n), 600)) * gust
wind += 0.25 * norm(lp(rng.standard_normal(n), 2500)) * gust ** 2

# --- sea: swell period 9 s, breaking crests now and then
swell = 0.5 + 0.5 * np.sin(2 * np.pi * t / 9.1 + 0.7)
sea = norm(lp(rng.standard_normal(n), 350)) * (0.3 + 0.7 * swell ** 3)

# --- geometry of the pass
v, d0, tc, c = 14.0, 60.0, 24.0, 343.0
x = v * (t - tc)                     # along-track offset from closest point
dist = np.sqrt(x ** 2 + d0 ** 2)
# radial velocity (positive = approaching): bird moving toward ship before tc
v_r = -v * x / dist
dop = c / (c - v_r)                  # observer moving, source still
# sound leaves the ship dist/c seconds earlier; ignore the small retiming,
# keep the frequency shift and the loudness
gain = d0 / dist
cutoff = 150 + 2500 * gain ** 1.5    # far = dull, near = bright

# --- ship tones
shaft = 90 / 60                      # 1.5 Hz
fire = 6 * shaft                     # 9 Hz
blade = 4 * shaft                    # 6 Hz
ph_fire = 2 * np.pi * np.cumsum(fire * dop) / SR
ph_blade = 2 * np.pi * np.cumsum(blade * dop) / SR
ph_shaft = 2 * np.pi * np.cumsum(shaft * dop) / SR
engine = np.zeros(n)
for k in range(2, 45):
    # small per-cylinder unevenness: shaft-rate wobble on each harmonic
    amp = (1 / k ** 0.8) * (1 + 0.15 * np.sin(ph_shaft + k))
    engine += amp * np.sin(k * ph_fire + rng.uniform(0, 6.28))
engine = norm(engine)
cav = norm(lp(rng.standard_normal(n), 3000))
cav *= (0.5 + 0.5 * np.sin(ph_blade)) ** 4   # hiss pulses at blade rate
ship_raw = engine + 0.35 * cav

# time-varying low-pass, applied in blocks
ship = np.zeros(n)
blk = 2048
zi = None
for i in range(0, n, blk):
    fc = float(np.clip(cutoff[i], 100, 6000))
    b, a = butter(2, fc / (SR / 2))
    seg = ship_raw[i:i + blk]
    if zi is None:
        from scipy.signal import lfilter_zi
        zi = lfilter_zi(b, a) * 0
    ship[i:i + blk], zi = lfilter(b, a, seg, zi=zi)
ship = norm(ship) * gain ** 1.2

# --- one adjustment of the wings near the end: a soft double thump
thump = np.zeros(n)
for tt in (38.2, 38.55):
    i = int(tt * SR)
    k = np.arange(int(0.12 * SR))
    thump[i:i + len(k)] += np.sin(2 * np.pi * 55 * k / SR) * np.exp(-k / (0.03 * SR))

mix = 0.33 * wind + 0.22 * sea + 0.75 * ship + 0.18 * thump
env = np.clip(t / 3, 0, 1) * np.clip((DUR - t) / 5, 0, 1)
mix = norm(mix * env) * 0.85

# stereo: the ship moves from slightly left to slightly right as it passes
pan = 0.5 + 0.35 * np.tanh(x / 80)
L = mix - 0.75 * ship * pan * env * 0.4
R = mix - 0.75 * ship * (1 - pan) * env * 0.4
st = np.stack([L, R], 1)
st = st / np.max(np.abs(st)) * 0.85
pcm = (st * 32767).astype(np.int16)
with wave.open(__file__.replace('.py', '.wav'), 'wb') as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes(pcm.tobytes())
print('peak doppler shift: %.3f -> %.3f' % (dop.max(), dop.min()))
