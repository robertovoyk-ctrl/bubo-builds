import json, numpy as np, soundfile as sf
from scipy.signal import butter, sosfilt, fftconvolve
SR=48000; tl=json.load(open('timeline.json')); DUR=tl['total']; N=int(DUR*SR)
mix=np.zeros((N,2)); rng=np.random.RandomState(2)
mf=lambda m:440*2**((m-69)/12)
def env(n,a,d): t=np.arange(n)/SR; return np.minimum(1,t/max(a,1e-4))*np.exp(-t*d)
def put(s,t,pan=0,gain=1):
    i=int(t*SR); j=min(N,i+len(s))
    if i>=N or j<=i: return
    s=s[:j-i]*gain; mix[i:j,0]+=s*(1-pan)*.7; mix[i:j,1]+=s*(1+pan)*.7
def tone(m,dur,dec,harm=(1,.4,.15)):
    n=int(dur*SR); t=np.arange(n)/SR; f=mf(m); return sum(a*np.sin(2*np.pi*f*(k+1)*t) for k,a in enumerate(harm))*env(n,.002,dec)
def tick():
    n=int(.02*SR); s=rng.normal(0,1,n)*np.exp(-np.arange(n)/SR*300); return sosfilt(butter(2,[3000,8000],'band',fs=SR,output='sos'),s)
def kick():
    n=int(.3*SR); t=np.arange(n)/SR; f=48+80*np.exp(-t*30); return np.sin(2*np.pi*np.cumsum(f)/SR)*env(n,.001,10)
def whoosh(dur=.5,up=True):
    n=int(dur*SR); t=np.arange(n)/SR; s=rng.normal(0,1,n); e=np.sin(np.pi*t/dur)**2
    lo=np.linspace(400,4000,n) if up else np.linspace(4000,400,n); out=np.zeros(n)
    for i in range(0,n,2048):
        f=lo[i]; out[i:i+2048]=sosfilt(butter(2,[f*.7,min(f*1.4,20000)],'band',fs=SR,output='sos'),s[i:i+2048])
    return out*e
PAN=[-.6,0,.6]; BASE=[64,67,71]; eats=[0,0,0]
freezes=[e['t'] for e in tl['events'] if e['k'] in('freeze',)]+[0.0]
def in_freeze(t): return any(f<=t<f+1.5 for f in freezes)
lastTick=[-1]
for e in tl['events']:
    k=e['k']
    if k=='tick' and not in_freeze(e['t']) and e['t']-lastTick[0]>0.06: put(tick(),e['t'],gain=.05); lastTick[0]=e['t']
    if k=='eat': m=e['m']; eats[m]+=1; put(tone(BASE[m]+12+[0,2,4,7,9][eats[m]%5],.35,10),e['t'],PAN[m],.2)
    if k=='death':
        m=e['m']; n=int(.7*SR); t=np.arange(n)/SR
        s=np.sign(np.sin(2*np.pi*np.cumsum(220*np.exp(-t*3))/SR))*env(n,.002,5); s=sosfilt(butter(2,2500,'low',fs=SR,output='sos'),s)
        put(s,e['t'],PAN[m],.28); put(kick(),e['t'],PAN[m],.55)
    if k=='freeze': put(whoosh(.45,False),e['t'],0,.25); put(tone(38,1.6,2,(1,.5,.2)),e['t']+.05,0,.3)
    if k=='win':
        for i,m in enumerate([67,71,74,79]): put(tone(m,.6,5),e['t']+.15+i*.07,-.3+.2*i,.18)
        put(kick(),e['t']+.15,0,.5)
    if k=='coldhit':
        n=int(.7*SR); t=np.arange(n)/SR
        s2=np.sign(np.sin(2*np.pi*np.cumsum(220*np.exp(-t*3))/SR))*env(n,.002,5); s2=sosfilt(butter(2,2500,'low',fs=SR,output='sos'),s2)
        put(s2,e['t'],0,.3); put(kick(),e['t'],0,.7); put(tone(38,2.4,1.5,(1,.5,.2)),e['t']+.05,0,.3)
    if k=='rewind': put(whoosh(.7,True),e['t'],0,.35)
    if k=='final':
        for i,m in enumerate([60,64,67,72,76,79]): put(tone(m,3,1.2,(1,.5,.25,.1)),e['t']+i*.09,-.5+.2*i,.17)
        put(kick(),e['t'],0,.6)
# bass bed outside freezes
B=60/128; t=[e['t'] for e in tl['events'] if e['k']=='rewind'][0]+0.7 if any(e['k']=='rewind' for e in tl['events']) else 1.5; k=0; last=[e['t'] for e in tl['events'] if e['k']=='final'][0]
while t<last:
    if not in_freeze(t):
        put(kick(),t,0,.2)
        if k%2: put(tone(40+[0,0,3,5][(k//2)%4],.4,6,(1,.3)),t,0,.17)
    t+=B; k+=1
L=int(.9*SR); ir=rng.normal(0,1,(L,2))*np.exp(-np.arange(L)/SR*6)[:,None]; ir/=np.abs(ir).sum(0)/4
wet=np.stack([fftconvolve(mix[:,c],ir[:,c])[:N] for c in range(2)],1); out=mix*.85+wet*.15
f=int(.6*SR); out[-f:]*=np.linspace(1,0,f)[:,None]; out/=np.abs(out).max()*1.12
sf.write('arena.wav',out.astype(np.float32),SR); print('ok',round(DUR,2))
