"""Software AI workflow with a bounded normalized custom activation."""
from activations import curve as load_curve
from pathlib import Path
import argparse, csv, hashlib, io, json, re, zipfile
from collections import Counter, defaultdict
import numpy as np
from PIL import Image
from train_mnist import project, forward
ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'runs' / 'breast_histology'
MIRROR = 'https://huggingface.co/datasets/hirundo-io/BreaKHis-original'
EXPECTED_SHA = 'e8f2bdaa4f16d0c8febed6acf6a434ef996025993e2fa748a972b789e6b06dbf'

def descriptor(image):
    rgb = np.asarray(image.convert('RGB').resize((64, 64), Image.Resampling.BILINEAR), dtype=np.float64) / 255
    thumb = np.asarray(image.convert('RGB').resize((16, 16), Image.Resampling.BILINEAR), dtype=np.float64).ravel() / 255
    gray = rgb @ np.array([0.299, 0.587, 0.114])
    gy, gx = np.gradient(gray)
    mag = np.hypot(gx, gy)
    ang = np.mod(np.arctan2(gy, gx), np.pi)
    bins = np.minimum((ang * 9 / np.pi).astype(int), 8)
    hog = []
    for i in range(4):
        for j in range(4):
            sl = (slice(i * 16, (i + 1) * 16), slice(j * 16, (j + 1) * 16))
            h = np.bincount(bins[sl].ravel(), weights=mag[sl].ravel(), minlength=9)
            hog.extend(h / (np.linalg.norm(h) + 1e-08))
    hist = np.concatenate([np.histogram(rgb[:, :, c], bins=16, range=(0, 1))[0] / 4096 for c in range(3)])
    od = -np.log(np.maximum(rgb, 1 / 255))
    stats = np.quantile(od.reshape(-1, 3), [0.05, 0.25, 0.5, 0.75, 0.95], axis=0).ravel()
    stats = np.r_[stats, od.mean((0, 1)), od.std((0, 1))]
    c = gray[1:-1, 1:-1]
    lbp = np.zeros(c.shape, np.uint8)
    for k, (dy, dx) in enumerate([(-1, -1), (-1, 0), (-1, 1), (0, 1), (1, 1), (1, 0), (1, -1), (0, -1)]):
        lbp |= (gray[1 + dy:63 + dy, 1 + dx:63 + dx] >= c).astype(np.uint8) << k
    texture = np.histogram(lbp, bins=32, range=(0, 256))[0] / lbp.size
    return np.r_[thumb, hog, hist, stats, texture]

def load(magnification):
    archive = OUT / 'breakhis_mirror.zip'
    sha = hashlib.sha256(archive.read_bytes()).hexdigest()
    if sha != EXPECTED_SHA:
        raise ValueError('Mirror archive SHA mismatch')
    records = []
    features = []
    seen = {}
    duplicates = []
    pattern = re.compile('SOB_([BM])_([A-Z]+)-(\\d{2})-([^-]+)-(40|100|200|400)-(\\d+)\\.(?:png|jpg|jpeg)$', re.I)
    with zipfile.ZipFile(archive) as z:
        candidates = [n for n in z.namelist() if pattern.search(Path(n).name)]
        for name in sorted(candidates):
            m = pattern.search(Path(name).name)
            if magnification != 'all' and m[5] != magnification:
                continue
            label = int(m[1].upper() == 'M')
            numeric = re.match('\\d+', m[4])
            if not numeric:
                raise ValueError('Unknown case identifier ' + name)
            group = m[3] + '-' + numeric[0]
            raw = z.read(name)
            im = Image.open(io.BytesIO(raw)).convert('RGB')
            digest = hashlib.sha256(np.asarray(im).tobytes()).hexdigest()
            if digest in seen:
                old = records[seen[digest]]
                if old['label'] != label or old['group'] != group:
                    raise ValueError('Duplicate crosses labels/cases')
                duplicates.append(name)
                continue
            seen[digest] = len(records)
            records.append(dict(filename=name, original_name=Path(name).name, label=label, group=group, slide_identifier=m[3] + '-' + m[4], subtype=m[2].upper(), magnification=int(m[5]), pixel_sha256=digest))
            features.append(descriptor(im))
    if len(records) < 100:
        raise ValueError(f'Insufficient named images: {len(records)}; candidates={len(candidates)}')
    groups = defaultdict(list)
    for i, r in enumerate(records):
        groups[r['group']].append(i)
    rng = np.random.default_rng(20261022)
    split = [[], [], []]
    group_splits = [[], [], []]
    for label in [0, 1]:
        gs = sorted((g for g, ids in groups.items() if records[ids[0]]['label'] == label))
        assert all((len({records[i]['label'] for i in ids}) == 1 for ids in groups.values()))
        rng.shuffle(gs)
        nt = max(1, round(0.2 * len(gs)))
        nv = max(1, round(0.2 * len(gs)))
        if len(gs) - nt - nv < 2:
            raise ValueError('Too few independent cases in a class')
        parts = [gs[nt + nv:], gs[nt:nt + nv], gs[:nt]]
        for k, part in enumerate(parts):
            group_splits[k].extend(part)
            for g in part:
                split[k].extend(groups[g])
    split = [np.array(ids) for ids in split]
    assert not (set(group_splits[0]) & set(group_splits[1]) or set(group_splits[0]) & set(group_splits[2]) or set(group_splits[1]) & set(group_splits[2]))
    features = np.array(features)
    y = np.array([r['label'] for r in records])
    tr, va, te = split
    mean = features[tr].mean(0)
    std = features[tr].std(0)
    std = np.where(std < 1e-06, 1, std)
    f = (features - mean) / std
    _, s, vh = np.linalg.svd(f[tr], full_matrices=False)
    basis = vh[:64].T
    x = f @ basis
    x /= np.maximum(np.linalg.norm(x, axis=1, keepdims=True), 1e-08)
    np.savez_compressed(OUT / 'preprocessing.npz', mean=mean, std=std, basis=basis)
    for k, ids in enumerate(split):
        for i in ids:
            records[i]['split'] = ['train', 'validation', 'test'][k]
    (OUT / 'manifest.json').write_text(json.dumps(records, indent=2))
    provenance = dict(source='BreakHis histopathology, mirrored archive; not the original 4.27 GB archive', mirror=MIRROR, archive_sha256=sha, magnification=magnification, image_count=len(records), groups=len(groups), unique_original_slide_ids=len(set((r['slide_identifier'] for r in records))), grouping='year + numeric case identifier; all alphabetic suffix variants remain in the same group', split_seed=20261022, group_splits=group_splits, split_counts=[len(ids) for ids in split], split_class_counts=[np.bincount(y[ids], minlength=2).tolist() for ids in split], skipped_duplicates=len(duplicates), raw_archive_named_images=len(candidates), descriptor='16x16 RGB thumbnail, HOG, RGB histograms, color-density quantiles/moments, local-binary texture; all software', descriptor_dimension=features.shape[1], pca_dimension=64, pca_explained_variance=float((s[:64] ** 2).sum() / (s * s).sum()), curve_sha256=hashlib.sha256((ROOT / 'activation_curve.csv').read_bytes()).hexdigest())
    (OUT / 'provenance.json').write_text(json.dumps(provenance, indent=2))
    print(json.dumps({k: provenance[k] for k in ['image_count', 'groups', 'split_counts', 'split_class_counts', 'pca_explained_variance']}), flush=True)
    return (x, y, split, records, provenance)

def auc(y, p):
    if len(np.unique(y)) < 2:
        return None
    order = np.argsort(p, kind='stable')
    ranks = np.empty(len(p))
    a = 0
    while a < len(p):
        b = a + 1
        while b < len(p) and p[order[b]] == p[order[a]]:
            b += 1
        ranks[order[a:b]] = (a + 1 + b) / 2
        a = b
    n = int(y.sum())
    return float((ranks[y == 1].sum() - n * (n + 1) / 2) / (n * (len(y) - n)))

def metrics(y, pred, p):
    y = np.asarray(y, dtype=int)
    pred = np.asarray(pred, dtype=int)
    cm = np.zeros((2, 2), int)
    np.add.at(cm, (y, pred), 1)
    tn, fp, fn, tp = cm.ravel()
    sensitivity = tp / max(1, tp + fn)
    specificity = tn / max(1, tn + fp)
    return dict(accuracy=float(np.mean(y == pred)), balanced_accuracy=float((sensitivity + specificity) / 2), sensitivity_malignant=float(sensitivity), specificity_benign=float(specificity), precision_malignant=float(tp / max(1, tp + fp)), f1_malignant=float(2 * tp / max(1, 2 * tp + fp + fn)), roc_auc=auc(y, p), confusion_matrix=cm.tolist())

def objective(x, y, p, kind, weights, grad=False):
    prob, c = forward(x, p, kind)
    w = weights[y]
    den = w.sum()
    loss = float(-(w * np.log(np.maximum(prob[np.arange(len(y)), y], 1e-15))).sum() / den)
    if not grad:
        return loss
    xa, z, dh, ha = c
    g = prob.copy()
    g[np.arange(len(y)), y] -= 1
    g *= w[:, None] / den
    return (loss, dict(A2=g.T @ ha, A1=(g @ p['A2'][:, :-1] * dh).T @ xa))

def train(x, y, tr, va, kind, seed, epochs):
    rng = np.random.default_rng(seed)
    w = rng.normal(0, 0.08, (128, 65))
    w[:, -1] = rng.uniform(-0.35, 0.35, 128)
    p = dict(A1=project(w), A2=rng.normal(0, 0.1, (2, 129)))
    m = {k: np.zeros_like(a) for k, a in p.items()}
    v = {k: a.copy() for k, a in m.items()}
    step = 0
    best = np.inf
    bestep = 0
    history = []
    weights = len(tr) / (2 * np.bincount(y[tr], minlength=2))
    for ep in range(1, epochs + 1):
        ids = rng.permutation(tr)
        for start in range(0, len(ids), 64):
            ix = ids[start:start + 64]
            _, g = objective(x[ix], y[ix], p, kind, weights, True)
            step += 1
            for k in p:
                m[k] = 0.9 * m[k] + 0.1 * g[k]
                v[k] = 0.999 * v[k] + 0.001 * g[k] ** 2
                p[k] -= 0.003 * (m[k] / (1 - 0.9 ** step)) / (np.sqrt(v[k] / (1 - 0.999 ** step)) + 1e-08)
            p['A1'] = project(p['A1'])
        vl = objective(x[va], y[va], p, kind, weights)
        history.append([ep, vl])
        if vl < best:
            best = vl
            bestep = ep
            selected = {k: a.copy() for k, a in p.items()}
        if ep - bestep >= 50:
            break
    d = OUT / f'{kind}_{seed}'
    d.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(d / 'model.npz', **selected)
    np.savetxt(d / 'history.csv', history, delimiter=',', header='epoch,validation_weighted_cross_entropy')
    return (selected, dict(activation=kind, seed=seed, best_epoch=bestep, epochs_executed=ep, validation_weighted_cross_entropy=best))

def gradient_check(x, y, tr):
    rng = np.random.default_rng(7)
    ids = np.r_[tr[y[tr] == 0][:4], tr[y[tr] == 1][:4]]
    p = dict(A1=project(rng.normal(0, 0.1, (128, 65))), A2=rng.normal(0, 0.1, (2, 129)))
    w = np.array([1.0, 1.5])
    err = 0.0
    for kind in ['custom', 'matched_linear', 'relu']:
        _, g = objective(x[ids], y[ids], p, kind, w, True)
        for k in p:
            for _ in range(6):
                ix = tuple((rng.integers(n) for n in p[k].shape))
                a = p[k][ix]
                p[k][ix] = a + 1e-06
                plus = objective(x[ids], y[ids], p, kind, w)
                p[k][ix] = a - 1e-06
                minus = objective(x[ids], y[ids], p, kind, w)
                p[k][ix] = a
                err = max(err, abs((plus - minus) / 2e-06 - g[k][ix]))
    assert err < 1e-06, err
    return err

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--epochs', type=int, default=300)
    ap.add_argument('--seeds', type=int, nargs='+', default=[11, 22, 33])
    ap.add_argument('--magnification', choices=['40', '100', '200', '400', 'all'], default='40')
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    x, y, (tr, va, te), records, prov = load(args.magnification)
    report = dict(task='benign vs malignant breast tissue images, not single cells', architecture=[64, 128, 2], software_image_preprocessing=True, threshold=0.5, gradient_max_error=gradient_check(x, y, tr), majority_test_accuracy=float(np.bincount(y[te]).max() / len(te)), results=[])
    for kind in ['custom', 'matched_linear', 'relu']:
        for seed in args.seeds:
            p, r = train(x, y, tr, va, kind, seed, args.epochs)
            prob, (_, z, _, _) = forward(x[te], p, kind)
            pred = prob.argmax(1)
            r.update(metrics(y[te], pred, prob[:, 1]))
            r.update(coordinate_min=float((z * z).min()), coordinate_max=float((z * z).max()))
            groups = sorted(set((records[i]['group'] for i in te)))
            pg = []
            yg = []
            case_correct = []
            for group in groups:
                mask = np.array([records[i]['group'] == group for i in te])
                pg.append(float(prob[mask, 1].mean()))
                yg.append(int(y[te][mask][0]))
                case_correct.append(float(np.mean(y[te][mask] == pred[mask])))
            r['mean_case_image_accuracy'] = float(np.mean(case_correct))
            r['case_mean_probability_metrics'] = metrics(np.array(yg), np.array(pg) >= 0.5, np.array(pg))
            d = OUT / f'{kind}_{seed}'
            (d / 'metrics.json').write_text(json.dumps(r, indent=2))
            with (d / 'predictions.csv').open('w', newline='') as f:
                w = csv.writer(f)
                w.writerow(['filename', 'group', 'actual', 'predicted', 'p_malignant'])
                for j, i in enumerate(te):
                    w.writerow([records[i]['original_name'], records[i]['group'], int(y[i]), int(pred[j]), float(prob[j, 1])])
            report['results'].append(r)
            (OUT / 'report.json').write_text(json.dumps(report, indent=2))
            print(kind, seed, {k: round(r[k], 4) for k in ['accuracy', 'balanced_accuracy', 'roc_auc']}, flush=True)
    report['summary'] = {k: {m: dict(mean=float(np.mean([r[m] for r in report['results'] if r['activation'] == k])), std=float(np.std([r[m] for r in report['results'] if r['activation'] == k]))) for m in ['accuracy', 'balanced_accuracy', 'sensitivity_malignant', 'specificity_benign', 'roc_auc']} for k in ['custom', 'matched_linear', 'relu']}
    report['selected_custom'] = min([r for r in report['results'] if r['activation'] == 'custom'], key=lambda r: r['validation_weighted_cross_entropy'])['seed']
    (OUT / 'report.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report['summary'], indent=2), flush=True)
if __name__ == '__main__':
    main()
