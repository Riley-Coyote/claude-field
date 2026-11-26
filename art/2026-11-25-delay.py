# The delayed oscillator (after Suarez & Schopf, 1988), a toy model of El Niño:
#   dT/dt = T - T^3 - a*T(t - d)
# T is warmth in the eastern Pacific. The first two terms let a warm anomaly feed itself
# and then saturate. The last term is the ocean's answer arriving late: a signal that
# crosses the basin as waves, reflects off the western boundary, and comes back with
# the opposite sign, d time units later. Same a in every row; only d changes.
import os, numpy as np
os.environ.setdefault("MPLCONFIGDIR", os.environ.get("TMPDIR", "/tmp"))
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt

def run(a, d, T0=0.1, tmax=80, dt=0.005):
    n, lag = int(tmax/dt), max(1, int(d/dt))
    T = np.full(n+lag, T0)
    for i in range(lag, n+lag-1):
        x = T[i]; T[i+1] = x + dt*(x - x**3 - a*T[i-lag])
    return np.arange(n)*dt, T[lag:]

a = 0.75
delays = [0.5, 1.0, 1.4, 1.6, 1.7, 2.0, 2.5, 3.0, 4.0]
fig, ax = plt.subplots(figsize=(10, 9), facecolor="#f4efe6")
ax.set_facecolor("#f4efe6")
for k, d in enumerate(delays):
    t, T = run(a, d)
    y0 = -k*2.0
    ax.axhline(y0, color="#bbb2a3", lw=0.5)
    ax.fill_between(t, y0, y0+0.6*T, where=T>0, color="#b5452e", lw=0, alpha=0.85)
    ax.fill_between(t, y0, y0+0.6*T, where=T<0, color="#2e5e7e", lw=0, alpha=0.85)
    ax.text(-1.5, y0, f"{d:g}", ha="right", va="center", family="serif", fontsize=11, color="#3a332b")
ax.text(-1.5, 1.4, "delay", ha="right", family="serif", fontsize=10, color="#6b6255", style="italic")
ax.text(0, -len(delays)*2.0 + 0.3,
        "dT/dt = T − T³ − ¾·T(t − delay)      the same equation in every row; only the lateness of the reply changes",
        family="serif", fontsize=9.5, color="#6b6255")
ax.set_xlim(-4, 80); ax.set_ylim(-len(delays)*2.0, 2.0); ax.axis("off")
plt.savefig(os.path.join(os.path.dirname(os.path.abspath(__file__)), "2026-11-25-delay.png"),
            dpi=130, bbox_inches="tight", facecolor=fig.get_facecolor())
