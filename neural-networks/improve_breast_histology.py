"""Software AI workflow with a bounded normalized custom activation."""
from activations import curve as load_curve
from pathlib import Path
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS', '4')
import csv, hashlib, io, json, zipfile
import numpy as np
from PIL import Image
import train_breast_histology as baseline
from train_mnist import forward
BASE = baseline.OUT
OUT = BASE / 'improved_resnet18'
OUT.mkdir(parents=True, exist_ok=True)

def extract(records):
    import torch
    import torchvision
    from torchvision.models import resnet18, ResNet18_Weights
    torch.set_num_threads(4)
    torch.hub.set_dir(str(OUT / 'weights' / 'hub'))
    cache = OUT / 'features.npz'
    digest = hashlib.sha256((BASE / 'manifest.json').read_bytes()).hexdigest()
    if cache.exists():
        with np.load(cache) as d:
            assert str(d['manifest_sha256']) == digest
            return {k: d[k].copy() for k in ['single', 'rotation_mean']}
    weights = ResNet18_Weights.IMAGENET1K_V1
    net = resnet18(weights=weights).eval()
    net.fc = torch.nn.Identity()
    transform = weights.transforms()
    single = []
    rotated = []
    with zipfile.ZipFile(BASE / 'breakhis_mirror.zip') as z, torch.inference_mode():
        for start in range(0, len(records), 16):
            ims = [Image.open(io.BytesIO(z.read(r['filename']))).convert('RGB') for r in records[start:start + 16]]
            batch = torch.stack([transform(im.rotate(a)) for im in ims for a in [0, 90, 180, 270]])
            f = net(batch).numpy().reshape(len(ims), 4, 512)
            single.extend(f[:, 0])
            rotated.extend(f.mean(1))
            if start % 160 == 0:
                print('features', start, '/', len(records), flush=True)
    features = dict(single=np.array(single), rotation_mean=np.array(rotated))
    np.savez_compressed(cache, **features, manifest_sha256=digest)
    (OUT / 'extractor.json').write_text(json.dumps(dict(model='ResNet18', weights='IMAGENET1K_V1', source='https://docs.pytorch.org/vision/stable/models/generated/torchvision.models.resnet18.html', torch=torch.__version__, torchvision=torchvision.__version__, frozen=True, software=True, manifest_sha256=digest, rotations=[0, 90, 180, 270]), indent=2))
    return features

def preprocess(f, tr):
    mean = f[tr].mean(0)
    std = f[tr].std(0)
    std = np.where(std < 1e-06, 1, std)
    scaled = (f - mean) / std
    _, s, vh = np.linalg.svd(scaled[tr], full_matrices=False)
    basis = vh[:64].T
    x = scaled @ basis
    x /= np.maximum(np.linalg.norm(x, axis=1, keepdims=True), 1e-08)
    return (x, dict(mean=mean, std=std, basis=basis))

def evaluate(x, y, ids, records, p, kind):
    prob, (_, z, _, _) = forward(x[ids], p, kind)
    r = baseline.metrics(y[ids], prob.argmax(1), prob[:, 1])
    r.update(coordinate_min=float((z * z).min()), coordinate_max=float((z * z).max()))
    assert r['coordinate_min'] >= 0 and r['coordinate_max'] <= 1
    gs = sorted(set((records[i]['group'] for i in ids)))
    pg = []
    yg = []
    acc = []
    for group in gs:
        mask = np.array([records[i]['group'] == group for i in ids])
        pg.append(prob[mask, 1].mean())
        yg.append(y[ids][mask][0])
        acc.append((prob[mask].argmax(1) == y[ids][mask]).mean())
    r['mean_case_image_accuracy'] = float(np.mean(acc))
    r['case_mean_score_metrics'] = baseline.metrics(np.array(yg), np.array(pg) >= 0.5, np.array(pg))
    return (r, prob)

def main():
    records = json.loads((BASE / 'manifest.json').read_text())
    y = np.array([r['label'] for r in records])
    tr, va, te = [np.array([i for i, r in enumerate(records) if r['split'] == s]) for s in ['train', 'validation', 'test']]
    groups = [set((records[i]['group'] for i in ids)) for ids in [tr, va, te]]
    assert all((not groups[a] & groups[b] for a, b in [(0, 1), (0, 2), (1, 2)]))
    features = extract(records)
    choices = []
    prepared = {}
    for name, f in features.items():
        x, prep = preprocess(f, tr)
        prepared[name] = (x, prep)
        d = OUT / ('candidate_' + name)
        d.mkdir(parents=True, exist_ok=True)
        baseline.OUT = d
        p, r = baseline.train(x, y, tr, va, 'custom', 11, 300)
        r['representation'] = name
        choices.append(r)
        print('validation candidate', name, r['validation_weighted_cross_entropy'], flush=True)
    selected = min(choices, key=lambda r: r['validation_weighted_cross_entropy'])['representation']
    x, prep = prepared[selected]
    np.savez_compressed(OUT / 'preprocessing.npz', **prep)
    report = dict(architecture=[64, 128, 2], frozen_software_backbone='ResNet18 ImageNet1K V1', representation=selected, selection_metric='validation weighted cross entropy, Custom seed 11', candidates=choices, threshold=0.5, split_counts=[len(a) for a in [tr, va, te]], test_status='previously seen baseline test; development comparison, not independent confirmation', results=[])
    baseline.OUT = OUT
    for kind in ['custom', 'matched_linear', 'relu']:
        for seed in [11, 22, 33]:
            p, r = baseline.train(x, y, tr, va, kind, seed, 300)
            r['validation_metrics'] = evaluate(x, y, va, records, p, kind)[0]
            ev, prob = evaluate(x, y, te, records, p, kind)
            r.update(ev)
            d = OUT / f'{kind}_{seed}'
            (d / 'metrics.json').write_text(json.dumps(r, indent=2))
            with (d / 'predictions.csv').open('w', newline='') as fh:
                w = csv.writer(fh)
                w.writerow(['filename', 'group', 'actual', 'predicted', 'score_malignant'])
                for j, i in enumerate(te):
                    w.writerow([records[i]['original_name'], records[i]['group'], int(y[i]), int(prob[j].argmax()), float(prob[j, 1])])
            report['results'].append(r)
            print(kind, seed, {k: round(r[k], 4) for k in ['accuracy', 'balanced_accuracy', 'roc_auc']}, flush=True)
            (OUT / 'report.json').write_text(json.dumps(report, indent=2))
    report['summary'] = {kind: {metric: dict(mean=float(np.mean([r[metric] for r in report['results'] if r['activation'] == kind])), std=float(np.std([r[metric] for r in report['results'] if r['activation'] == kind]))) for metric in ['accuracy', 'balanced_accuracy', 'sensitivity_malignant', 'specificity_benign', 'roc_auc']} for kind in ['custom', 'matched_linear', 'relu']}
    report['selected_custom'] = min([r for r in report['results'] if r['activation'] == 'custom'], key=lambda r: r['validation_weighted_cross_entropy'])['seed']
    (OUT / 'report.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report['summary'], indent=2), flush=True)
if __name__ == '__main__':
    main()
