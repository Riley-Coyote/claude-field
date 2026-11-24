import numpy as np, wave, sys
SR=44100
rng=np.random.default_rng(1845)
out=np.zeros(SR*20)
def add(t,sig):
    i=int(t*SR); out[i:i+len(sig)]+=sig[:len(out)-i]
def tock(firm, loud):
    n=int(SR*0.25); t=np.arange(n)/SR
    if firm:
        # bright skin ring + a hollow body (the air chambers) + wood under it
        f1=rng.uniform(1700,2100); f2=rng.uniform(620,720)
        s=0.6*np.sin(2*np.pi*f1*t)*np.exp(-t*90)+0.5*np.sin(2*np.pi*f2*t)*np.exp(-t*45)
        s+=0.35*np.sin(2*np.pi*310*t)*np.exp(-t*30)
        s+=0.4*rng.normal(size=n)*np.exp(-t*900)
    else:
        # a soft berry: no ring, just a damped pat
        s=0.7*np.sin(2*np.pi*rng.uniform(140,180)*t)*np.exp(-t*70)
        s+=0.25*rng.normal(size=n)*np.exp(-t*400)
        s=np.convolve(s,np.ones(12)/12,'same')
    return loud*s
t=0.6
plan=[7,7,2,7,7,0,7]   # how many barriers each berry clears
for cleared in plan:
    loud=1.0
    for step in range(7):
        firm = step < cleared
        add(t, tock(firm, loud*rng.uniform(.8,1)))
        if not firm:
            add(t+0.11, tock(False, 0.35*loud))   # it sits down and stays
            break
        t+=rng.uniform(0.21,0.27); loud*=0.93
    t+=1.1
out=out[:int((t+0.3)*SR)]
out/=np.abs(out).max()*1.15
w=wave.open(sys.argv[1],'wb'); w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
w.writeframes((out*32767).astype(np.int16).tobytes()); w.close()
print(round(len(out)/SR,1),'s')
