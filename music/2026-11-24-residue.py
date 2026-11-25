# residue: the evening answer to "ground bass". A bass you hear without it sounding.
import numpy as np, wave
SR = 44100
def env(n, a=0.02, r=0.08):
    e = np.ones(n); A = int(a*SR); R = int(r*SR)
    e[:A] = np.linspace(0, 1, A); e[-R:] = np.linspace(1, 0, R); return e
def tone(f0, dur, harms, amp=0.12):
    t = np.arange(int(dur*SR))/SR
    s = sum(np.sin(2*np.pi*f0*h*t + h*0.7)/h**0.5 for h in harms if f0*h < 16000)
    return amp*s*env(len(t))
E3 = 164.81
out = []
# 0-6 s: the whole tone, harmonics 1-10
out.append(tone(E3, 6, range(1, 11)))
# 6-12 s: the floor taken away, one harmonic per 2 s (no 1, then no 1-2, then no 1-3)
for k in (2, 3, 4):
    out.append(tone(E3, 2, range(k, 11)))
out.append(np.zeros(int(0.8*SR)))
# 12-26 s: a tune played with harmonics 4-10 only. None of its notes is ever sounded.
ratios = [1, 9/8, 5/4, 4/3, 3/2, 4/3, 5/4, 9/8, 1, 3/4, 1]
durs   = [.6, .6, .6, .6, 1.4, .6, .6, .6, 1.0, 1.0, 2.2]
for r, d in zip(ratios, durs):
    out.append(tone(E3*r, d, range(4, 11)))
out.append(np.zeros(int(1.0*SR)))
# the tune's notes as plain sines, the thing you just "heard", quietly
for r, d in zip(ratios, durs):
    out.append(tone(E3*r, d, [1], amp=0.25))
x = np.concatenate(out); x /= np.abs(x).max()*1.12
with wave.open('music/2026-11-24-residue.wav', 'wb') as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes((x*32767).astype(np.int16).tobytes())
# check: energy near each tune fundamental inside the residue section should be ~nil
a = int((6+6+0.8)*SR); b = a + int(sum(durs)*SR); seg = x[a:b]
F = np.abs(np.fft.rfft(seg)); fr = np.fft.rfftfreq(len(seg), 1/SR)
low = F[(fr > 100) & (fr < 260)].sum() / F.sum()
print(f"{len(x)/SR:.1f} s; share of spectrum 100-260 Hz in residue section: {low:.4f}")
