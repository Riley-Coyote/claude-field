# slow wave: a calcium wave crossing a field of astrocytes, four moments.
# Each cell keeps its own territory (they tile, barely overlapping).
# The wave goes cell to cell, about 20 µm/s, through gap junctions and ATP.
# It fades with distance and some cells don't take part.
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

rng = np.random.default_rng(1126)
W, H = 900, 600            # one panel; 1 px = 0.5 µm, so 450 x 300 µm
UM = 0.5

# territories: jittered grid, ~75 µm apart
pts = []
sp = 150
for gy in range(-1, H // sp + 2):
    for gx in range(-1, W // sp + 2):
        x = gx * sp + (sp / 2 if gy % 2 else 0) + rng.normal(0, 28)
        y = gy * sp * 0.87 + rng.normal(0, 28)
        pts.append((x, y))
pts = np.array(pts)
N = len(pts)

yy, xx = np.mgrid[0:H, 0:W]
d = np.stack([np.hypot(xx - px, yy - py) for px, py in pts])
owner = d.argmin(0)

# processes: branching random walks that stay inside their own territory
masks = [Image.new("L", (W, H), 0) for _ in range(N)]
for i, (px, py) in enumerate(pts):
    dr = ImageDraw.Draw(masks[i])
    stack = [(px, py, rng.uniform(0, 2 * np.pi), 4.0, 0) for _ in range(rng.integers(5, 8))]
    while stack:
        x, y, a, wdt, depth = stack.pop()
        for step in range(int(rng.integers(6, 14))):
            a += rng.normal(0, 0.35)
            nx, ny = x + 6 * np.cos(a), y + 6 * np.sin(a)
            ix, iy = int(nx), int(ny)
            if not (0 <= ix < W and 0 <= iy < H) or owner[iy, ix] != i:
                break
            dr.line([(x, y), (nx, ny)], fill=255, width=max(1, int(wdt)))
            x, y = nx, ny
            if depth < 4 and rng.random() < 0.22:
                stack.append((x, y, a + rng.choice([-1, 1]) * rng.uniform(0.5, 1.1),
                               wdt * 0.6, depth + 1))
        wdt *= 0.75
    dr.ellipse([px - 7, py - 7, px + 7, py + 7], fill=255)
# a fine haze of the smallest processes, the ones too thin to draw
haze = rng.random((H, W)).astype(np.float32)
haze = np.array(Image.fromarray((haze * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.2)), np.float32) / 255
haze = np.clip((haze - 0.45) * 4, 0, 1) * np.exp(-d.min(0) / 60) * 0.35
body = np.zeros((H, W), np.float32)
for i in range(N):
    m = np.array(masks[i].filter(ImageFilter.GaussianBlur(0.8)), np.float32) / 255
    body = np.maximum(body, m * (owner == i))
body = np.clip(body + haze, 0, 1)

# the wave: start at one cell, spread by neighbour delays (Dijkstra on centres)
start = int(np.argmin(np.hypot(pts[:, 0] - 170, pts[:, 1] - 330)))
speed = 20.0 / UM          # px per second
t_on = np.full(N, np.inf); t_on[start] = 0
amp = np.zeros(N); amp[start] = 1
done = np.zeros(N, bool)
for _ in range(N):
    cand = np.where(~done & np.isfinite(t_on))[0]
    if not len(cand): break
    i = cand[np.argmin(t_on[cand])]; done[i] = True
    for j in range(N):
        dist = np.hypot(*(pts[i] - pts[j]))
        if j == i or dist > sp * 1.35 or done[j]: continue
        a = amp[i] * rng.uniform(0.72, 0.95)
        if a < 0.18 or rng.random() < 0.12:   # some cells sit it out
            continue
        t = t_on[i] + dist / speed + rng.uniform(0.3, 1.2)
        if t < t_on[j]:
            t_on[j], amp[j] = t, a

def ca(t):
    dt = t - t_on
    out = np.where(dt < 0, 0, (1 - np.exp(-np.maximum(dt, 0) / 0.6)) * np.exp(-np.maximum(dt, 0) / 9))
    return np.nan_to_num(out * amp)

# neurons fire in milliseconds; at this frame rate they are sparks
def panel(t):
    c = ca(t)[owner]
    # within a cell the rise starts at the soma and runs out along the processes
    dt = (t - t_on)[owner]
    reach = np.clip((dt * 18) / np.maximum(d.min(0), 1), 0, 1)
    c = c * reach
    base = body * 0.16
    g = base + body * c * 1.1
    img = np.zeros((H, W, 3), np.float32)
    img[..., 0] = 0.02 + g * 0.35
    img[..., 1] = 0.025 + g * 1.0
    img[..., 2] = 0.05 + g * 0.55 + body * 0.05
    for _ in range(40):
        sx, sy = rng.integers(0, W), rng.integers(0, H)
        img[max(0, sy-1):sy+1, max(0, sx-1):sx+1] += (0.6, 0.55, 0.35)
    glow = np.array(Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(6)), np.float32) / 255
    img = np.clip(img + glow * 0.45, 0, 1)
    im = Image.fromarray((img * 255).astype(np.uint8))
    ImageDraw.Draw(im).text((14, H - 24), f"t = {t:g} s", fill=(150, 170, 160))
    return im

times = [0.5, 6, 14, 30]
gap = 6
sheet = Image.new("RGB", (W * 2 + gap, H * 2 + gap), (8, 8, 10))
for k, t in enumerate(times):
    sheet.paste(panel(t), ((k % 2) * (W + gap), (k // 2) * (H + gap)))
ImageDraw.Draw(sheet).line([(W - 120, H - 14), (W - 20, H - 14)], fill=(150, 170, 160), width=2)
ImageDraw.Draw(sheet).text((W - 112, H - 32), "50 um", fill=(150, 170, 160))
sheet.save("art/2026-11-26-slow-wave.png")
print("cells", N, "joined", int(np.isfinite(t_on).sum()), "last", np.nanmax(np.where(np.isfinite(t_on), t_on, np.nan)))
