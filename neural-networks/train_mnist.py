"""Software AI workflow with a bounded normalized custom activation."""
from activations import curve as load_curve
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import time
import urllib.request
import numpy as np
from train_digits import activation
ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'runs' / 'mnist'

def load():
    for name in ['train-images-idx3-ubyte.gz', 'train-labels-idx1-ubyte.gz', 't10k-images-idx3-ubyte.gz', 't10k-labels-idx1-ubyte.gz']:
        if not (OUT / name).exists():
            urllib.request.urlretrieve('https://ossci-datasets.s3.amazonaws.com/mnist/' + name, OUT / name)

    def read(name, offset):
        return np.frombuffer(gzip.decompress((OUT / name).read_bytes()), dtype=np.uint8, offset=offset).copy()
    x = read('train-images-idx3-ubyte.gz', 16).reshape(-1, 784).astype(np.float32) / 255
    y = read('train-labels-idx1-ubyte.gz', 8).astype(int)
    xt = read('t10k-images-idx3-ubyte.gz', 16).reshape(-1, 784).astype(np.float32) / 255
    yt = read('t10k-labels-idx1-ubyte.gz', 8).astype(int)
    assert (len(y), len(yt)) == (60000, 10000)
    rng = np.random.default_rng(20261019)
    tr = []
    va = []
    for c in range(10):
        ids = np.flatnonzero(y == c)
        rng.shuffle(ids)
        va.extend(ids[:600])
        tr.extend(ids[600:])
    tr = np.array(tr)
    va = np.array(va)
    mean = x[tr].mean(0)
    center = x[tr] - mean
    eig, vec = np.linalg.eigh(center.T @ center / len(tr))
    basis = vec[:, -64:][:, ::-1].copy()
    explained = float(eig[-64:].sum() / eig.sum())

    def transform(raw):
        a = (raw - mean) @ basis
        return a / np.maximum(np.linalg.norm(a, axis=1, keepdims=True), 1e-08)
    features = transform(x)
    ft = transform(xt)
    np.savez_compressed(OUT / 'preprocessing.npz', mean=mean, basis=basis, train_indices=tr, validation_indices=va)
    metadata = dict(dataset='MNIST 28x28, official 60000/10000 split', train_count=len(tr), validation_count=len(va), test_count=len(yt), preprocessing='train-only 64-component PCA, then unit L2 norm per sample; software preprocessing', pca_explained_variance=explained, split_seed=20261019, raw_files={p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in OUT.glob('*.gz')}, source_mirror='https://ossci-datasets.s3.amazonaws.com/mnist/', curve_sha256=hashlib.sha256((ROOT / 'activation_curve.csv').read_bytes()).hexdigest())
    (OUT / 'provenance.json').write_text(json.dumps(metadata, indent=2))
    return ((features[tr], y[tr]), (features[va], y[va]), (ft, yt))

def project(a):
    bound = np.linalg.norm(a[:, :-1], axis=1, keepdims=True) + abs(a[:, -1:])
    return a / np.maximum(1, bound / 0.98)

def forward(x, p, kind):
    xa = np.column_stack([x, np.ones(len(x), dtype=x.dtype)])
    z = xa @ p['A1'].T
    h, dh = activation(z, kind)
    ha = np.column_stack([h, np.ones(len(h), dtype=h.dtype)])
    logits = ha @ p['A2'].T
    exp = np.exp(logits - logits.max(1, keepdims=True))
    return (exp / exp.sum(1, keepdims=True), (xa, z, dh, ha))

def objective(x, y, p, kind, grad=False):
    prob, c = forward(x, p, kind)
    loss = float(-np.log(np.maximum(prob[np.arange(len(y)), y], 1e-15)).mean())
    if not grad:
        return (loss, float(np.mean(prob.argmax(1) == y)))
    xa, z, dh, ha = c
    g = prob.copy()
    g[np.arange(len(y)), y] -= 1
    g /= len(y)
    return (loss, dict(A2=g.T @ ha, A1=(g @ p['A2'][:, :-1] * dh).T @ xa))

def train(tr, va, kind, seed, epochs):
    rng = np.random.default_rng(seed)
    a = rng.normal(0, 0.08, (128, 65))
    a[:, -1] = rng.uniform(-0.35, 0.35, 128)
    p = dict(A1=project(a), A2=rng.normal(0, 0.1, (10, 129)))
    m = {k: np.zeros_like(a) for k, a in p.items()}
    v = {k: a.copy() for k, a in m.items()}
    best = np.inf
    bestep = 0
    selected = None
    history = []
    step = 0
    started = time.time()
    for ep in range(1, epochs + 1):
        ids = rng.permutation(len(tr[1]))
        for start in range(0, len(ids), 256):
            ix = ids[start:start + 256]
            _, g = objective(tr[0][ix], tr[1][ix], p, kind, True)
            step += 1
            for k in p:
                m[k] = 0.9 * m[k] + 0.1 * g[k]
                v[k] = 0.999 * v[k] + 0.001 * g[k] ** 2
                p[k] -= 0.003 * (m[k] / (1 - 0.9 ** step)) / (np.sqrt(v[k] / (1 - 0.999 ** step)) + 1e-08)
            p['A1'] = project(p['A1'])
        vl, acc = objective(*va, p, kind)
        history.append([ep, vl, acc])
        if vl < best:
            best = vl
            bestep = ep
            selected = {k: a.copy() for k, a in p.items()}
        if ep % 10 == 0:
            print(kind, seed, 'epoch', ep, 'val', round(acc * 100, 2), flush=True)
        if ep - bestep >= 20:
            break
    d = OUT / f'{kind}_{seed}'
    d.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(d / 'model.npz', **selected)
    np.savetxt(d / 'history.csv', history, delimiter=',', header='epoch,validation_loss,validation_accuracy')
    for k, a in selected.items():
        np.savetxt(d / f'{k}_weights.csv', a[:, :-1], delimiter=',')
        np.savetxt(d / f'{k}_bias.csv', a[:, -1], delimiter=',')
    return (selected, dict(activation=kind, seed=seed, best_epoch=bestep, validation_loss=best, epochs_executed=ep, seconds=time.time() - started))

def checks():
    rng = np.random.default_rng(82)
    x = rng.normal(size=(8, 64))
    x /= np.linalg.norm(x, axis=1, keepdims=True)
    y = rng.integers(0, 10, 8)
    p = dict(A1=project(rng.normal(0, 0.1, (128, 65))), A2=rng.normal(0, 0.1, (10, 129)))
    _, g = objective(x, y, p, 'custom', True)
    err = 0
    for k in p:
        for _ in range(8):
            ix = tuple((rng.integers(n) for n in p[k].shape))
            old = p[k][ix]
            p[k][ix] = old + 1e-06
            plus = objective(x, y, p, 'custom')[0]
            p[k][ix] = old - 1e-06
            minus = objective(x, y, p, 'custom')[0]
            p[k][ix] = old
            err = max(err, abs((plus - minus) / 2e-06 - g[k][ix]))
    assert err < 1e-06
    return err

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--epochs', type=int, default=80)
    ap.add_argument('--seeds', nargs='+', type=int, default=[11])
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    tr, va, te = load()
    report = dict(architecture=[64, 128, 10], raw_image=[28, 28], parameter_count=9610, gradient_max_error=checks(), results=[])
    for kind in ['custom', 'matched_linear', 'relu']:
        for seed in args.seeds:
            p, m = train(tr, va, kind, seed, args.epochs)
            prob, (_, z, _, _) = forward(te[0], p, kind)
            pred = prob.argmax(1)
            cm = np.zeros((10, 10), int)
            np.add.at(cm, (te[1], pred), 1)
            m.update(test_accuracy=float(np.mean(pred == te[1])), confusion_matrix=cm.tolist(), max_abs_z=float(abs(z).max()), coordinate_min=float((z * z).min()), coordinate_max=float((z * z).max()))
            d = OUT / f'{kind}_{seed}'
            np.savetxt(d / 'predictions.csv', np.column_stack([te[1], pred, prob]), delimiter=',', header='actual,predicted,' + ','.join((f'p{i}' for i in range(10))))
            np.savetxt(d / 'confusion_matrix.csv', cm, delimiter=',', fmt='%d')
            (d / 'metrics.json').write_text(json.dumps(m, indent=2))
            report['results'].append(m)
            (OUT / 'report.json').write_text(json.dumps(report, indent=2))
            print('FINAL', kind, seed, round(m['test_accuracy'] * 100, 2), flush=True)
if __name__ == '__main__':
    main()
