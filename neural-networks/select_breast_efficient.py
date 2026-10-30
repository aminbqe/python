"""Software AI workflow with a bounded normalized custom activation."""
from activations import curve as load_curve
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS', '4')
import io, json, zipfile, hashlib, time
from pathlib import Path
import numpy as np
from PIL import Image
import torch
from torch import nn
from torchvision.models import efficientnet_b0, EfficientNet_B0_Weights
import train_breast_histology as baseline
from train_mnist import project, forward
ROOT = Path(__file__).resolve().parent
BASE = ROOT / 'runs' / 'breast_histology'
OUT = BASE / 'efficient_custom'
OUT.mkdir(parents=True, exist_ok=True)
torch.set_num_threads(4)
torch.hub.set_dir(str(BASE / 'improved_resnet18/weights/hub'))

def extract(records):
    digest = hashlib.sha256((BASE / 'manifest.json').read_bytes()).hexdigest()
    path = OUT / 'features.npz'
    if path.exists():
        with np.load(path) as d:
            assert str(d['manifest_sha256']) == digest
            return {k: d[k].copy() for k in ['single', 'rotation_mean']}
    net = efficientnet_b0(weights=EfficientNet_B0_Weights.IMAGENET1K_V1).eval()
    net.classifier = nn.Identity()
    transform = EfficientNet_B0_Weights.IMAGENET1K_V1.transforms()
    features = []
    means = []
    started = time.monotonic()
    with zipfile.ZipFile(BASE / 'breakhis_mirror.zip') as z, torch.inference_mode():
        for start in range(0, len(records), 12):
            ims = [Image.open(io.BytesIO(z.read(r['filename']))).convert('RGB') for r in records[start:start + 12]]
            batch = torch.stack([transform(im.rotate(a)) for im in ims for a in [0, 90, 180, 270]])
            f = net(batch).numpy().reshape(len(ims), 4, 1280)
            features.extend(f[:, 0])
            means.extend(f.mean(1))
            if start % 120 == 0:
                print('EfficientNet features', start, '/', len(records), 'seconds', round(time.monotonic() - started), flush=True)
    result = dict(single=np.array(features), rotation_mean=np.array(means))
    np.savez_compressed(path, **result, manifest_sha256=digest)
    return result

def train(x, y, tr, va, hidden, seed, directory):
    directory.mkdir(parents=True, exist_ok=True)
    if (directory / 'selection.json').exists():
        return (json.loads((directory / 'selection.json').read_text()), np.load(directory / 'validation_scores.npy'))
    rng = np.random.default_rng(seed)
    w = rng.normal(0, 0.08, (hidden, x.shape[1] + 1))
    w[:, -1] = rng.uniform(-0.35, 0.35, hidden)
    p = dict(A1=project(w), A2=rng.normal(0, 0.1, (2, hidden + 1)))
    m = {k: np.zeros_like(a) for k, a in p.items()}
    v = {k: a.copy() for k, a in m.items()}
    weights = len(tr) / (2 * np.bincount(y[tr], minlength=2))
    step = 0
    best = np.inf
    bestep = 0
    history = []
    for ep in range(1, 301):
        ids = rng.permutation(tr)
        for start in range(0, len(ids), 64):
            ix = ids[start:start + 64]
            _, g = baseline.objective(x[ix], y[ix], p, 'custom', weights, True)
            step += 1
            for k in p:
                m[k] = 0.9 * m[k] + 0.1 * g[k]
                v[k] = 0.999 * v[k] + 0.001 * g[k] ** 2
                p[k] -= 0.003 * (m[k] / (1 - 0.9 ** step)) / (np.sqrt(v[k] / (1 - 0.999 ** step)) + 1e-08)
            p['A1'] = project(p['A1'])
        loss = baseline.objective(x[va], y[va], p, 'custom', weights)
        history.append([ep, loss])
        if loss < best:
            best = loss
            bestep = ep
            selected = {k: a.copy() for k, a in p.items()}
        if ep - bestep >= 40:
            break
    np.savez_compressed(directory / 'model.npz', **selected)
    prob = forward(x[va], selected, 'custom')[0]
    np.save(directory / 'validation_scores.npy', prob)
    result = dict(name=directory.name, seed=seed, pca_dimension=x.shape[1], hidden=hidden, best_epoch=bestep, epochs_executed=ep, validation_weighted_cross_entropy=best, validation_metrics=baseline.metrics(y[va], prob.argmax(1), prob[:, 1]))
    (directory / 'selection.json').write_text(json.dumps(result, indent=2))
    np.savetxt(directory / 'history.csv', history, delimiter=',', header='epoch,validation_weighted_cross_entropy')
    print('Efficient Custom candidate', directory.name, 'val CE', round(best, 4), flush=True)
    return (result, prob)

def main():
    records = json.loads((BASE / 'manifest.json').read_text())
    y = np.array([r['label'] for r in records])
    tr, va = [np.array([i for i, r in enumerate(records) if r['split'] == s]) for s in ['train', 'validation']]
    allfeatures = extract(records)
    candidates = []
    scores = {}
    prepared = {}
    for representation, f in allfeatures.items():
        mean = f[tr].mean(0)
        std = f[tr].std(0)
        std = np.where(std < 1e-06, 1, std)
        scaled = (f - mean) / std
        _, s, vh = np.linalg.svd(scaled[tr], full_matrices=False)
        for dim in [64, 128]:
            basis = vh[:dim].T
            x = scaled @ basis
            x /= np.maximum(np.linalg.norm(x, axis=1, keepdims=True), 1e-08)
            prepared[representation, dim] = (x, dict(mean=mean, std=std, basis=basis))
            for hidden in [128, 256]:
                name = f'{representation}_pca{dim}_hidden{hidden}_seed11'
                result, prob = train(x, y, tr, va, hidden, 11, OUT / name)
                result['representation'] = representation
                candidates.append(result)
                scores[name] = prob
    winner = min(candidates, key=lambda a: a['validation_weighted_cross_entropy'])
    rep, dim, hidden = (winner['representation'], winner['pca_dimension'], winner['hidden'])
    x, prep = prepared[rep, dim]
    np.savez_compressed(OUT / 'preprocessing.npz', **prep)
    for seed in [22, 33]:
        name = f'{rep}_pca{dim}_hidden{hidden}_seed{seed}'
        result, prob = train(x, y, tr, va, hidden, seed, OUT / name)
        result['representation'] = rep
        candidates.append(result)
        scores[name] = prob
    members = [a['name'] for a in candidates if a['representation'] == rep and a['pca_dimension'] == dim and (a['hidden'] == hidden)]
    avg = np.mean([scores[n] for n in members], axis=0)
    weights = len(tr) / (2 * np.bincount(y[tr], minlength=2))
    w = weights[y[va]]
    ensemble_loss = float(-(w * np.log(np.maximum(avg[np.arange(len(va)), y[va]], 1e-15))).sum() / w.sum())
    best = min(candidates, key=lambda a: a['validation_weighted_cross_entropy'])
    selected = members if ensemble_loss < best['validation_weighted_cross_entropy'] else [best['name']]
    selected_record = next((a for a in candidates if a['name'] == selected[0]))
    _, prep = prepared[selected_record['representation'], selected_record['pca_dimension']]
    np.savez_compressed(OUT / 'preprocessing.npz', **prep)
    avg = np.mean([scores[n] for n in selected], axis=0)
    loss = float(-(w * np.log(np.maximum(avg[np.arange(len(va)), y[va]], 1e-15))).sum() / w.sum())
    result = dict(backbone='EfficientNet-B0 ImageNet1K V1, frozen and software', candidates=candidates, selected_members=selected, representation=selected_record['representation'], pca_dimension=selected_record['pca_dimension'], hidden=selected_record['hidden'], validation_weighted_cross_entropy=loss, validation_metrics=baseline.metrics(y[va], avg.argmax(1), avg[:, 1]), manifest_sha256=hashlib.sha256((BASE / 'manifest.json').read_bytes()).hexdigest(), threshold=0.5, selection_metric='validation class-weighted cross entropy, test never evaluated in this script')
    (OUT / 'locked_selection.json').write_text(json.dumps(result, indent=2))
    np.save(OUT / 'selected_validation_scores.npy', avg)
    print('Efficient SELECTION LOCKED', selected, 'val CE', loss, flush=True)
if __name__ == '__main__':
    main()
