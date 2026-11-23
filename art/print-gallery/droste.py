import numpy as np
from PIL import Image
import sys
S = float(sys.argv[1]); N = int(sys.argv[2]); out = sys.argv[3]; twist = sys.argv[4]=='1'
L = np.log(S)
ys, xs = np.mgrid[-1:1:N*1j, -1:1:N*1j]
w = xs + 1j*ys
w[w==0] = 1e-9
if twist:
    beta = (2j*np.pi + L)/(2j*np.pi)
    z = np.exp(np.log(w)*beta)
else:
    z = w.copy()
# reduce into square annulus 1/S <= sup norm < 1
r = np.maximum(abs(z.real), abs(z.imag))
k = np.floor(np.log(r)/L) + 1
z = z / S**k
x, y = z.real, z.imag
r = np.maximum(abs(x), abs(y))
img = np.zeros(z.shape+(3,))
# wall: warm paper, brick courses scaled to the local size
wall = np.array([0.93,0.89,0.80])
img[:] = wall
# brick courses (horizontal lines), in tile units
course = 0.06
row = np.floor(y/course)
line = (np.abs(y/course - np.round(y/course)) < 0.06)
off = (row % 2)*0.5
vline = (np.abs((x/(course*2)+off) - np.round(x/(course*2)+off)) < 0.03)
img[line|vline] = [0.78,0.70,0.58]
# a window frame around the inner square
inner = 1.0/S
frame = (r >= inner) & (r < inner*1.35)
img[frame] = [0.22,0.16,0.12]
gilt = (r >= inner*1.35) & (r < inner*1.5)
img[gilt] = [0.75,0.58,0.25]
# four small hung pictures, one on each side
for cx, cy, col in [(0.62,0,[0.25,0.38,0.55]),(-0.62,0,[0.55,0.25,0.25]),(0,0.62,[0.30,0.50,0.32]),(0,-0.62,[0.55,0.48,0.22])]:
    m = (abs(x-cx)<0.14)&(abs(y-cy)<0.14)
    img[m] = [0.22,0.16,0.12]
    m2 = (abs(x-cx)<0.11)&(abs(y-cy)<0.11)
    img[m2] = col
    # a little horizon in each
    m3 = m2 & (y-cy < -0.02)
    img[m3] = np.array(col)*0.6
# outer border shadow
edge = r > 0.97
img[edge] = [0.35,0.30,0.26]
Image.fromarray((img*255).astype(np.uint8)).save(out)
