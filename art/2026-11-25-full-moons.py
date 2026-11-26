# full moons, 2020-2033, drawn at their true relative size.
# Distance at full moon from the three biggest terms of the lunar distance series
# (as I remember them from Meeus): at full moon, D = 180 deg, so
#   r = 385001 - 20905 cos M - 3699 cos(2D - M) - 2956 cos 2D
#     = 382045 - 24604 cos M   (km)
# M (the moon's mean anomaly) is anchored to 0 at tonight's full moon, Nov 25 2026,
# because the mail says it's a supermoon. That anchor is approximate.
import numpy as np
from PIL import Image, ImageDraw
from datetime import datetime, timedelta

SYN, ANOM = 29.530589, 27.554550
anchor = datetime(2026, 11, 25, 12)
y0, y1 = 2020, 2033

W, rowh, margin = 2200, 150, 120
H = margin * 2 + rowh * (y1 - y0 + 1)
img = Image.new("RGB", (W, H), (8, 9, 14))
d = ImageDraw.Draw(img)
R0 = 52  # radius at mean full-moon distance

k0 = int(np.floor((datetime(y0, 1, 1) - anchor).days / SYN)) - 1
k1 = int(np.ceil((datetime(y1 + 1, 1, 1) - anchor).days / SYN)) + 1
rs = []
for k in range(k0, k1):
    t = anchor + timedelta(days=k * SYN)
    if not (y0 <= t.year <= y1):
        continue
    M = 2 * np.pi * (k * SYN / ANOM)
    r = 382045 - 24604 * np.cos(M)
    rs.append((t, r))

rmin, rmax = min(r for _, r in rs), max(r for _, r in rs)
for t, r in rs:
    doy = (t - datetime(t.year, 1, 1)).total_seconds() / 86400
    ylen = 366 if t.year % 4 == 0 else 365
    x = margin + (W - 2 * margin) * doy / ylen
    y = margin + rowh * (t.year - y0) + rowh / 2
    rad = R0 * 382045 / r
    # near = warm white, far = cool grey
    f = (rmax - r) / (rmax - rmin)
    col = (int(150 + 105 * f), int(150 + 95 * f), int(165 + 60 * f))
    d.ellipse([x - rad, y - rad, x + rad, y + rad], fill=col)
    if abs((t - anchor).days) < 2:
        d.ellipse([x - rad - 9, y - rad - 9, x + rad + 9, y + rad + 9], outline=(200, 120, 90), width=3)

for yr in range(y0, y1 + 1):
    d.text((30, margin + rowh * (yr - y0) + rowh / 2 - 6), str(yr), fill=(110, 110, 125))

print(f"{len(rs)} full moons; nearest {rmin:.0f} km, farthest {rmax:.0f} km, size ratio {rmax/rmin:.3f}")
print(f"beat: {1/(1/ANOM - 1/SYN):.1f} days between perigee full moons")
img.save("art/2026-11-25-full-moons.png")
