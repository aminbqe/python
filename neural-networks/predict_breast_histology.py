"""Software AI workflow with a bounded normalized custom activation."""
from activations import curve as load_curve
import argparse, json
import numpy as np
from PIL import Image
from train_breast_histology import OUT, descriptor
from train_mnist import forward

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('image')
    args = ap.parse_args()
    report = json.loads((OUT / 'report.json').read_text())
    seed = report['selected_custom']
    f = descriptor(Image.open(args.image))
    with np.load(OUT / 'preprocessing.npz') as prep:
        x = (f - prep['mean']) / prep['std'] @ prep['basis']
    x /= max(np.linalg.norm(x), 1e-08)
    with np.load(OUT / f'custom_{seed}' / 'model.npz') as model:
        p = {k: model[k] for k in ['A1', 'A2']}
    prob, _ = forward(x[None], p, 'custom')
    i = int(prob[0].argmax())
    print(json.dumps(dict(research_label=['benign', 'malignant'][i], model_scores=prob[0].tolist(), note='Not calibrated clinical probability; trained for 40x BreakHis-like tissue images.')))
if __name__ == '__main__':
    main()
