"""Software AI workflow with a bounded normalized custom activation."""
from activations import curve as load_curve
from pathlib import Path
import argparse
import csv
import hashlib
import json
import urllib.request
import zipfile
import numpy as np
ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'runs' / 'digits'
URL = 'https://archive.ics.uci.edu/static/public/80/optical+recognition+of+handwritten+digits.zip'

def data():
    OUT.mkdir(parents=True, exist_ok=True)
    archive = OUT / 'optdigits.zip'
    if not archive.exists():
        urllib.request.urlretrieve(URL, archive)
    with zipfile.ZipFile(archive) as z:
        arrays = [np.loadtxt(z.open(next((n for n in z.namelist() if n.endswith(s)))), delimiter=',') for s in ['optdigits.tra', 'optdigits.tes']]
    a, b = arrays
    rng = np.random.default_rng(20261019)
    tr, va = ([], [])
    for c in range(10):
        ix = np.flatnonzero(a[:, -1] == c)
        rng.shuffle(ix)
        cut = int(0.8 * len(ix))
        tr.extend(ix[:cut])
        va.extend(ix[cut:])
    tr, va = (np.array(tr), np.array(va))
    x, y = (a[:, :64] / 8 - 1, a[:, -1].astype(int))
    xt, yt = (b[:, :64] / 8 - 1, b[:, -1].astype(int))
    assert np.max(abs(x)) <= 1 and np.max(abs(xt)) <= 1
    return ((x[tr], y[tr]), (x[va], y[va]), (xt, yt), dict(source=URL, archive_sha256=hashlib.sha256(archive.read_bytes()).hexdigest(), curve_sha256=hashlib.sha256((ROOT / 'activation_curve.csv').read_bytes()).hexdigest(), train_indices=tr.tolist(), validation_indices=va.tolist(), split_seed=20261019, official_test_count=len(yt), pixels='8x8 counts normalized as x/8-1'))

def project(w):
    return w / np.maximum(1, abs(w).sum(1, keepdims=True) / 0.98)
from activations import activation

def forward(x, p, kind):
    xa = np.column_stack([x, np.ones(len(x))])
    z = xa @ p['A1'].T
    h, dh = activation(z, kind)
    ha = np.column_stack([h, np.ones(len(h))])
    logits = ha @ p['A2'].T
    exp = np.exp(logits - logits.max(1, keepdims=True))
    return (exp / exp.sum(1, keepdims=True), (xa, z, dh, ha))

def lossgrad(x, y, p, kind):
    prob, (xa, z, dh, ha) = forward(x, p, kind)
    loss = -np.log(np.maximum(prob[np.arange(len(y)), y], 1e-15)).mean()
    g = prob.copy()
    g[np.arange(len(y)), y] -= 1
    g /= len(y)
    return (float(loss), dict(A2=g.T @ ha, A1=(g @ p['A2'][:, :-1] * dh).T @ xa))

def check_gradients():
    rng = np.random.default_rng(1)
    x, y = (rng.uniform(-1, 1, (7, 64)), rng.integers(0, 10, 7))
    p = dict(A1=project(rng.normal(0, 0.1, (32, 65))), A2=rng.normal(0, 0.1, (10, 33)))
    worst = 0.0
    for kind in ['custom', 'matched_linear', 'relu']:
        _, g = lossgrad(x, y, p, kind)
        for key in p:
            for _ in range(10):
                ix = tuple((rng.integers(n) for n in p[key].shape))
                v = p[key][ix]
                p[key][ix] = v + 1e-06
                plus = lossgrad(x, y, p, kind)[0]
                p[key][ix] = v - 1e-06
                minus = lossgrad(x, y, p, kind)[0]
                p[key][ix] = v
                worst = max(worst, abs((plus - minus) / 2e-06 - g[key][ix]))
    assert worst < 1e-06, worst
    return worst

def train(trainset, valset, kind, seed, epochs):
    x, y = trainset
    rng = np.random.default_rng(seed)
    w = rng.normal(0, 0.08, (32, 65))
    w[:, -1] = rng.uniform(-0.3, 0.3, 32)
    p = dict(A1=project(w), A2=rng.normal(0, 0.2, (10, 33)))
    m = {k: np.zeros_like(v) for k, v in p.items()}
    v = {k: a.copy() for k, a in m.items()}
    best, selected, step, bestep = (float('inf'), None, 0, 0)
    history = []
    for ep in range(1, epochs + 1):
        ids = rng.permutation(len(y))
        for start in range(0, len(y), 128):
            ix = ids[start:start + 128]
            _, g = lossgrad(x[ix], y[ix], p, kind)
            step += 1
            for k in p:
                m[k] = 0.9 * m[k] + 0.1 * g[k]
                v[k] = 0.999 * v[k] + 0.001 * g[k] ** 2
                p[k] -= 0.006 * (m[k] / (1 - 0.9 ** step)) / (np.sqrt(v[k] / (1 - 0.999 ** step)) + 1e-08)
            p['A1'] = project(p['A1'])
        if ep == 1 or ep % 5 == 0:
            vl, _ = lossgrad(*valset, p, kind)
            vp, _ = forward(valset[0], p, kind)
            history.append([ep, vl, float(np.mean(vp.argmax(1) == valset[1]))])
            if vl < best:
                best, bestep = (vl, ep)
                selected = {k: a.copy() for k, a in p.items()}
            if ep - bestep >= 80:
                break
    return (selected, dict(activation=kind, seed=seed, best_epoch=bestep, validation_loss=best, epochs_executed=ep), history)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--epochs', type=int, default=400)
    ap.add_argument('--seeds', type=int, nargs='+', default=[11, 22, 33])
    args = ap.parse_args()
    tr, va, te, provenance = data()
    report = dict(architecture=[64, 32, 10], parameter_count=2410, train_count=len(tr[1]), validation_count=len(va[1]), test_count=len(te[1]), gradient_max_error=check_gradients(), results=[])
    for kind in ['custom', 'matched_linear', 'relu']:
        for seed in args.seeds:
            p, metrics, history = train(tr, va, kind, seed, args.epochs)
            prob, (_, z, _, _) = forward(te[0], p, kind)
            pred = prob.argmax(1)
            cm = np.zeros((10, 10), int)
            np.add.at(cm, (te[1], pred), 1)
            metrics.update(test_accuracy=float(np.mean(pred == te[1])), test_cross_entropy=float(-np.log(np.maximum(prob[np.arange(len(pred)), te[1]], 1e-15)).mean()), max_abs_affine_input=float(abs(z).max()), confusion_matrix=cm.tolist())
            d = OUT / f'{kind}_{seed}'
            d.mkdir(parents=True, exist_ok=True)
            np.savez_compressed(d / 'model.npz', **p)
            np.savetxt(d / 'history.csv', history, delimiter=',', header='epoch,validation_loss,validation_accuracy')
            for key, a in p.items():
                np.savetxt(d / f'{key}_weights.csv', a[:, :-1], delimiter=',')
                np.savetxt(d / f'{key}_bias.csv', a[:, -1], delimiter=',')
            np.savetxt(d / 'confusion_matrix.csv', cm, delimiter=',', fmt='%d')
            np.savetxt(d / 'predictions.csv', np.column_stack([te[1], pred, prob]), delimiter=',', header='actual,predicted,' + ','.join((f'p{i}' for i in range(10))))
            (d / 'metrics.json').write_text(json.dumps(metrics, indent=2))
            report['results'].append(metrics)
            print(kind, seed, 'test', round(metrics['test_accuracy'] * 100, 2), 'best epoch', metrics['best_epoch'], flush=True)
    report['summary'] = {k: dict(mean_accuracy=float(np.mean([r['test_accuracy'] for r in report['results'] if r['activation'] == k])), std_accuracy=float(np.std([r['test_accuracy'] for r in report['results'] if r['activation'] == k]))) for k in ['custom', 'matched_linear', 'relu']}
    chosen = min((r for r in report['results'] if r['activation'] == 'custom'), key=lambda r: r['validation_loss'])
    report['selected_custom_model'] = f"custom_{chosen['seed']}"
    (OUT / 'report.json').write_text(json.dumps(report, indent=2))
    (OUT / 'data_provenance.json').write_text(json.dumps(provenance, indent=2))
    print(json.dumps(report['summary'], indent=2), flush=True)
if __name__ == '__main__':
    main()
