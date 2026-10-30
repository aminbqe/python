from pathlib import Path
import argparse,json
import numpy as np
from activations import activation as activate
ROOT=Path(__file__).resolve().parent
def dataset(name, seed=20261017):
    rng = np.random.default_rng(seed)
    n = 1200
    if name == 'moons':
        t = rng.uniform(0, np.pi, n // 2)
        a = np.column_stack([np.cos(t), np.sin(t)])
        t = rng.uniform(0, np.pi, n // 2)
        b = np.column_stack([1 - np.cos(t), 0.5 - np.sin(t)])
        x = np.vstack([a, b]) + rng.normal(0, 0.1, (n, 2))
        y = np.repeat([0, 1], n // 2)
    else:
        y = np.tile([0, 1, 1, 0], n // 4)
        centers = np.array([[-0.65, -0.65], [-0.65, 0.65], [0.65, -0.65], [0.65, 0.65]])
        x = np.tile(centers, (n // 4, 1)) + rng.normal(0, 0.17, (n, 2))
    splits = [[], [], []]
    for c in [0, 1]:
        ix = np.flatnonzero(y == c)
        rng.shuffle(ix)
        for dest, part in zip(splits, [ix[:360], ix[360:480], ix[480:]]):
            dest.extend(part)
    splits = [np.array(i) for i in splits]
    center = x[splits[0]].mean(0)
    scale = np.max(abs(x[splits[0]] - center), axis=0) * 1.05
    norm = (x - center) / scale
    clipped = int(np.sum(np.any(abs(norm) > 1, axis=1)))
    norm = np.clip(norm, -1, 1)
    return (norm, y, splits, dict(center=center.tolist(), scale=scale.tolist(), clipped_samples=clipped))

def project(a):
    return a / np.maximum(1, np.sum(abs(a), axis=1, keepdims=True) / 0.98)

def forward(x, p, kind):
    xa = np.column_stack([x, np.ones(len(x))])
    z = xa @ p['A1'].T
    h, dh = activate(z, kind)
    ha = np.column_stack([h, np.ones(len(h))])
    logits = ha @ p['A2'].T
    e = np.exp(logits - logits.max(1, keepdims=True))
    prob = e / e.sum(1, keepdims=True)
    return (prob, (xa, z, h, dh, ha, logits))

def lossgrad(x, y, p, kind):
    prob, c = forward(x, p, kind)
    xa, z, h, dh, ha, _ = c
    loss = -np.log(np.maximum(prob[np.arange(len(y)), y], 1e-15)).mean()
    g = prob.copy()
    g[np.arange(len(y)), y] -= 1
    g /= len(y)
    grads = {'A2': g.T @ ha, 'A1': (g @ p['A2'][:, :4] * dh).T @ xa}
    return (float(loss), grads)

def train(name, kind, seed, epochs):
    x, y, splits, norm = dataset(name)
    tr, va, te = splits
    rng = np.random.default_rng(seed)
    p = {'A1': project(rng.normal(0, 0.28, (4, 3))), 'A2': rng.normal(0, 0.35, (2, 5))}
    m = {k: np.zeros_like(v) for k, v in p.items()}
    v = {k: np.zeros_like(a) for k, a in p.items()}
    best = np.inf
    chosen = None
    history = []
    for ep in range(1, epochs + 1):
        loss, g = lossgrad(x[tr], y[tr], p, kind)
        for k in p:
            m[k] = 0.9 * m[k] + 0.1 * g[k]
            v[k] = 0.999 * v[k] + 0.001 * g[k] ** 2
            p[k] -= 0.015 * (m[k] / (1 - 0.9 ** ep)) / (np.sqrt(v[k] / (1 - 0.999 ** ep)) + 1e-08)
        p['A1'] = project(p['A1'])
        if ep % 20 == 0 or ep == 1:
            val, _ = lossgrad(x[va], y[va], p, kind)
            history.append([ep, loss, val])
            if val < best:
                best = val
                chosen = {k: a.copy() for k, a in p.items()}
                bestep = ep
    p = chosen
    pr, c = forward(x[te], p, kind)
    pred = pr.argmax(1)
    cm = np.zeros((2, 2), int)
    np.add.at(cm, (y[te], pred), 1)
    metrics = dict(dataset=name, activation=kind, seed=seed, best_epoch=bestep, validation_loss=best, test_accuracy=float(np.mean(pred == y[te])), test_n=len(te), confusion_matrix=cm.tolist(), normalization=norm)
    return (p, metrics, np.array(history), (x, y, splits))

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--epochs',type=int,default=2500)
    ap.add_argument('--seeds',type=int,nargs='+',default=[11,22,33])
    ap.add_argument('--activation',choices=['custom','relu','matched_linear','identity'],default='custom')
    args=ap.parse_args()
    if args.epochs < 1: ap.error('--epochs must be positive')
    out=ROOT/'runs'/'synthetic';out.mkdir(parents=True,exist_ok=True)
    for name in ['moons','xor']:
        for seed in args.seeds:
            p,metrics,history,_=train(name,args.activation,seed,args.epochs)
            d=out/f'{name}_{args.activation}_{seed}';d.mkdir(exist_ok=True)
            np.savez_compressed(d/'model.npz',**p)
            (d/'metrics.json').write_text(json.dumps(metrics,indent=2))
            np.savetxt(d/'history.csv',history,delimiter=',',header='epoch,train_loss,validation_loss')
            print(name,seed,metrics['test_accuracy'])
if __name__=='__main__':main()
