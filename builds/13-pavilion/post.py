# Bloom + warm grade + vignette + grain for rendered frames.
#   python3 post.py <in_dir> <out_dir>
import sys, os, glob
import numpy as np
from PIL import Image, ImageFilter

def bloom(img):
    a = np.asarray(img).astype(np.float32) / 255.0
    lum = a @ np.array([0.2126, 0.7152, 0.0722], np.float32)
    hi = np.clip((lum - 0.72) / 0.28, 0, 1)[..., None] * a
    hi_img = Image.fromarray((hi * 255).astype(np.uint8)); w = img.size[0]; acc = np.zeros_like(a)
    for r, g in ((0.004, 0.5), (0.015, 0.35), (0.05, 0.25)):
        acc += np.asarray(hi_img.filter(ImageFilter.GaussianBlur(max(1, r * w)))).astype(np.float32) / 255.0 * g
    return 1 - (1 - a) * (1 - np.clip(acc, 0, 1))

def grade(a, seed):
    h, w, _ = a.shape
    lum = (a @ np.array([0.2126, 0.7152, 0.0722], np.float32))[..., None]
    # warm the mids and shadows (interior), keep the snow clean
    warm = np.array([1.08, 1.0, 0.88], np.float32); cool_hi = np.array([0.99, 1.0, 1.03], np.float32)
    t = np.clip(lum * 1.4, 0, 1)
    a = a * (warm * (1 - t) + cool_hi * t)
    a = np.clip(a, 0, 1)
    a = a + 0.10 * (a - a * a) * (a - 0.35)          # gentle s-curve
    yy, xx = np.mgrid[0:h, 0:w]; v = ((xx / w - 0.5) ** 2 * 1.0 + (yy / h - 0.5) ** 2 * 1.6) ** 0.5
    a = a * (1 - 0.32 * np.clip(v - 0.22, 0, 1)[..., None])
    a = a + np.random.RandomState(seed).normal(0, 0.010, a.shape).astype(np.float32)
    return np.clip(a, 0, 1)

if __name__ == '__main__':
    ind, outd = sys.argv[1], sys.argv[2]; os.makedirs(outd, exist_ok=True)
    for p in sorted(glob.glob(os.path.join(ind, 'f*.png'))):
        q = os.path.join(outd, os.path.basename(p))
        if os.path.exists(q): continue
        fr = int(os.path.basename(p)[1:5])
        o = grade(bloom(Image.open(p).convert('RGB')), fr)
        Image.fromarray((o * 255).astype(np.uint8)).save(q)
