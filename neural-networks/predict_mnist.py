"""Software AI workflow with a bounded normalized custom activation."""
from activations import curve as load_curve
import argparse
import json
from pathlib import Path
import numpy as np
from train_mnist import OUT, forward

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('image', type=Path)
    args = ap.parse_args()
    x = np.load(args.image) if args.image.suffix.lower() == '.npy' else np.loadtxt(args.image, delimiter=',', ndmin=2)
    if x.ndim == 2 and x.shape == (28, 28):
        x = x[None]
    if x.ndim == 3 and x.shape[1:] == (28, 28):
        x = x.reshape(-1, 784)
    if x.ndim != 2 or x.shape[1] != 784 or (not np.isfinite(x).all()) or (x.min() < 0) or (x.max() > 255):
        raise ValueError('Expected 28x28 image(s), or rows of 784 pixels, with values 0..255')
    r = json.loads((OUT / 'report.json').read_text())
    chosen = min((a for a in r['results'] if a['activation'] == 'custom'), key=lambda a: a['validation_loss'])
    with np.load(OUT / 'preprocessing.npz') as prep:
        x = (x.astype(np.float32) / 255 - prep['mean']) @ prep['basis']
    x /= np.maximum(np.linalg.norm(x, axis=1, keepdims=True), 1e-08)
    with np.load(OUT / f"custom_{chosen['seed']}" / 'model.npz') as model:
        p = {k: model[k] for k in ['A1', 'A2']}
    prob, _ = forward(x, p, 'custom')
    for a in prob:
        print(json.dumps(dict(digit=int(a.argmax()), scores=a.tolist())))
if __name__ == '__main__':
    main()
