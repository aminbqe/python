"""Software AI workflow with a bounded normalized custom activation."""
from activations import curve as load_curve
from pathlib import Path
import argparse
import json
import numpy as np
from train_digits import OUT, forward

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('csv', type=Path)
    args = ap.parse_args()
    report = json.loads((OUT / 'report.json').read_text())
    x = np.loadtxt(args.csv, delimiter=',', ndmin=2)
    if x.shape[1] != 64 or not np.isfinite(x).all() or x.min() < 0 or (x.max() > 16):
        raise ValueError('Expected 64 finite pixel counts per row, each in 0..16')
    with np.load(OUT / report['selected_custom_model'] / 'model.npz') as model:
        p = {k: model[k] for k in ['A1', 'A2']}
    prob, _ = forward(x / 8 - 1, p, 'custom')
    for row in prob:
        print(json.dumps(dict(digit=int(row.argmax()), scores=row.tolist())))
if __name__ == '__main__':
    main()
