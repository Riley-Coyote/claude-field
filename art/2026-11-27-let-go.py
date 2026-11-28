# let go: what might have happened to parade balloons when they were released.
# For a few years from 1928 the big balloons weren't deflated at the end of the
# parade. They were let go over Manhattan, with a return address and a reward.
# This is a guess at their flights, not a record of any of them: rise, drift
# east on the westerlies, leak, come down. Distance east is on a log scale.
import numpy as np
from PIL import Image, ImageDraw, ImageFont

rng = np.random.default_rng(1928)
W, H = 1400, 700
L, R, T, B = 90, 1350, 60, 600
X0, X1 = 0.3, 3000.0          # km east of Herald Square
Z1 = 4.0                      # km altitude at top of frame

def px(xkm, zkm):
    u = (np.log10(max(xkm, X0)) - np.log10(X0)) / (np.log10(X1) - np.log10(X0))
    return L + u * (R - L), B - zkm / Z1 * (B - T)

img = Image.new("RGB", (W, H), (14, 18, 30))
dr = ImageDraw.Draw(img)
font = ImageFont.load_default()

# ground / sea: land until the end of Long Island (~190 km), then ocean
xs = np.logspace(np.log10(X0), np.log10(X1), 600)
for a, b in zip(xs[:-1], xs[1:]):
    col = (44, 40, 34) if b < 190 else (22, 34, 52)
    x0, y0 = px(a, 0); x1, _ = px(b, 0)
    dr.rectangle([x0, y0, x1 + 1, B + 18], fill=col)

for km, name in [(3, "East River"), (30, "Nassau line"), (190, "Montauk"), (1000, "1000 km")]:
    x, y = px(km, 0)
    dr.line([(x, T + 10), (x, B)], fill=(40, 46, 62), width=1)
    dr.text((x + 4, B + 22), name, fill=(120, 128, 150), font=font)
for z in (1, 2, 3):
    _, y = px(1, z)
    dr.text((L - 40, y - 6), f"{z} km", fill=(90, 98, 120), font=font)
dr.text((L, 24), "let go: imagined flights of released parade balloons, east on the westerlies (log distance)",
        fill=(170, 176, 196), font=font)

palette = [(232, 120, 96), (240, 196, 92), (126, 196, 150), (120, 170, 236),
           (206, 140, 220), (236, 236, 226), (240, 150, 170), (150, 220, 226)]

ends = []
for k in range(14):
    col = palette[k % len(palette)]
    x, z, t = 0.3, 0.05, 0.0
    lift = rng.uniform(2.0, 3.5)            # m/s initial free lift
    zfloat = rng.uniform(1.2, 3.2)          # km, where it stops rising
    leak = rng.uniform(1 / 40, 1 / 6)       # fraction of lift lost per hour
    burst = rng.random() < 0.3              # some never make it far
    tburst = rng.uniform(0.2, 3.0) if burst else 1e9
    pts, dt, w = [], 60.0, 0.0              # dt seconds
    while True:
        hours = t / 3600
        frac = max(0.0, 1 - leak * hours) if hours > 0.5 else 1.0
        target = zfloat * frac
        vz = np.clip((target - z) * 1000 / 600, -1.5, lift)  # m/s, settle over ~10 min
        w = 0.97 * w + rng.normal(0, 0.02)
        z = max(0.0, z + (vz + w) * dt / 1000)
        u = 6 + 7 * z + rng.normal(0, 1.5)  # m/s, wind increasing with height
        x += max(u, 0.5) * dt / 1000
        t += dt
        pts.append(px(x, z))
        if hours > tburst:                   # burst: falls fast
            while z > 0:
                z -= 0.012; x += 0.2
                pts.append(px(x, z))
            break
        if z <= 0.0 and hours > 0.5:
            break
        if x > X1:
            break
    for (a, b), (c, d) in zip(pts[:-1], pts[1:]):
        dr.line([(a, b), (c, d)], fill=col, width=2)
    ex, ey = pts[-1]
    if x < X1:
        dr.ellipse([ex - 4, ey - 4, ex + 4, ey + 4], outline=col, width=2)
    ends.append(x)

ends = np.array(ends)
land = int((ends < 190).sum()); sea = int(((ends >= 190) & (ends < X1)).sum())
gone = int((ends >= X1).sum())
dr.text((L, B + 50), f"{land} come down on land, where someone might find one and write.  "
        f"{sea} come down at sea.  {gone} leave the frame.", fill=(150, 156, 176), font=font)
img.save(__file__.replace(".py", ".png"))
print(land, sea, gone, np.round(np.sort(ends)).astype(int))
