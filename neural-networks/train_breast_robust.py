"""Software AI workflow with a bounded normalized custom activation."""
from activations import curve as load_curve
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS', '4')
from pathlib import Path
import csv, hashlib, json
import numpy as np
from train_mnist import project, forward
from train_breast_histology import metrics
ROOT = Path(__file__).resolve().parent
BASE = ROOT / 'runs' / 'breast_histology'
OUT = BASE / 'robust_custom'
OUT.mkdir(parents=True, exist_ok=True)

def sample_weights(y, groups, case_weighted):
    if not case_weighted:
        return len(y) / (2 * np.bincount(y, minlength=2))[y]
    weights = np.empty(len(y))
    for label in [0, 1]:
        gs = set(groups[y == label])
        for g in gs:
            mask = groups == g
            weights[mask] = len(y) / (2 * len(gs) * mask.sum())
    return weights

def objective(x, y, p, weights, grad=False):
    prob, (xa, z, dh, ha) = forward(x, p, 'custom')
    den = weights.sum()
    loss = float(-(weights * np.log(np.maximum(prob[np.arange(len(y)), y], 1e-15))).sum() / den)
    if not grad:
        return loss
    g = prob.copy()
    g[np.arange(len(y)), y] -= 1
    g *= weights[:, None] / den
    return (loss, dict(A2=g.T @ ha, A1=(g @ p['A2'][:, :-1] * dh).T @ xa))

def train(x, y, ids, weights, hidden, seed, val=None, fixed_epochs=None):
    rng = np.random.default_rng(seed)
    w = rng.normal(0, 0.08, (hidden, x.shape[1] + 1))
    w[:, -1] = rng.uniform(-0.35, 0.35, hidden)
    p = dict(A1=project(w), A2=rng.normal(0, 0.1, (2, hidden + 1)))
    m = {k: np.zeros_like(a) for k, a in p.items()}
    v = {k: a.copy() for k, a in m.items()}
    step = 0
    best = float('inf')
    bestep = 0
    for ep in range(1, (fixed_epochs or 120) + 1):
        order = rng.permutation(len(ids))
        for start in range(0, len(order), 64):
            pos = order[start:start + 64]
            ix = ids[pos]
            _, g = objective(x[ix], y[ix], p, weights[pos], True)
            step += 1
            for k in p:
                m[k] = 0.9 * m[k] + 0.1 * g[k]
                v[k] = 0.999 * v[k] + 0.001 * g[k] ** 2
                p[k] -= 0.003 * (m[k] / (1 - 0.9 ** step)) / (np.sqrt(v[k] / (1 - 0.999 ** step)) + 1e-08)
            p['A1'] = project(p['A1'])
        if val is None:
            continue
        vi, vw = val
        loss = objective(x[vi], y[vi], p, vw)
        if loss < best:
            best = loss
            bestep = ep
            selected = {k: a.copy() for k, a in p.items()}
        if ep - bestep >= 15:
            break
    return (p, fixed_epochs) if val is None else (selected, bestep)

def case_balanced(y, pred, groups):
    cls = []
    for label in [0, 1]:
        cls.append(np.mean([np.mean(pred[groups == g] == y[groups == g]) for g in set(groups[y == label])]))
    return float(np.mean(cls))

def transform(f, ids, dim):
    mean = f[ids].mean(0)
    std = f[ids].std(0)
    std = np.where(std < 1e-06, 1, std)
    a = (f - mean) / std
    _, _, vh = np.linalg.svd(a[ids], full_matrices=False)
    basis = vh[:dim].T
    x = a @ basis
    x /= np.maximum(np.linalg.norm(x, axis=1, keepdims=True), 1e-08)
    return (x, dict(mean=mean, std=std, basis=basis))

def main():
    records = json.loads((BASE / 'manifest.json').read_text())
    y = np.array([r['label'] for r in records])
    groups = np.array([r['group'] for r in records])
    dev = np.array([i for i, r in enumerate(records) if r['split'] != 'test'])
    te = np.array([i for i, r in enumerate(records) if r['split'] == 'test'])
    assert not set(groups[dev]) & set(groups[te])
    rng = np.random.default_rng(20261022)
    foldgroups = [[] for _ in range(5)]
    for label in [0, 1]:
        gs = np.array(sorted(set(groups[dev][y[dev] == label])))
        rng.shuffle(gs)
        for k, part in enumerate(np.array_split(gs, 5)):
            foldgroups[k].extend(part.tolist())
    folds = []
    for part in foldgroups:
        mask = np.isin(groups[dev], part)
        folds.append((dev[~mask], dev[mask]))
    assert set(np.concatenate([va for tr, va in folds])) == set(dev)
    (OUT / 'protocol.json').write_text(json.dumps(dict(fold_groups=foldgroups, development_count=len(dev), test_count=len(te), scope='train+validation cases from the previous split; test groups unchanged', primary_selection_metric='cross-fitted case-balanced accuracy; threshold grid .20:.025:.80; ties prefer .5 then OOF AUC', limitation='fold early stopping and architecture selection share CV validation folds; CV scores are internal selection scores', test_status='development benchmark previously seen, including the preceding single-validation search', manifest_sha256=hashlib.sha256((BASE / 'manifest.json').read_bytes()).hexdigest()), indent=2))
    allresults = []
    for family in ['improved_resnet18', 'efficient_custom']:
        with np.load(BASE / family / 'features.npz') as d:
            f = d['rotation_mean'].copy()
        for dim in [64, 128]:
            prepared = [transform(f, tr, dim)[0] for tr, va in folds]
            for hidden in [128, 256]:
                for caseweighted in [False, True]:
                    name = f'{family}_pca{dim}_h{hidden}_case{int(caseweighted)}'
                    d = OUT / name
                    d.mkdir(parents=True, exist_ok=True)
                    if (d / 'selection.json').exists():
                        result = json.loads((d / 'selection.json').read_text())
                        allresults.append(result)
                        continue
                    oof = np.zeros((len(records), 2))
                    epochs = []
                    for k, (tr, va) in enumerate(folds):
                        tw = sample_weights(y[tr], groups[tr], caseweighted)
                        vw = sample_weights(y[va], groups[va], caseweighted)
                        p, ep = train(prepared[k], y, tr, tw, hidden, 11, val=(va, vw))
                        epochs.append(ep)
                        oof[va] = forward(prepared[k][va], p, 'custom')[0]
                    candidates = []
                    for threshold in np.linspace(0.2, 0.8, 25):
                        pred = oof[dev, 1] >= threshold
                        candidates.append((case_balanced(y[dev], pred, groups[dev]), -abs(threshold - 0.5), float(threshold)))
                    best = max(candidates)
                    threshold = best[2]
                    result = dict(name=name, family=family, pca_dimension=dim, hidden=hidden, case_weighted=caseweighted, threshold=threshold, case_balanced_oof_accuracy=best[0], fold_best_epochs=epochs, oof_metrics=metrics(y[dev], oof[dev, 1] >= threshold, oof[dev, 1]), final_epochs=max(1, int(np.median(epochs))))
                    np.save(d / 'oof_scores.npy', oof)
                    (d / 'selection.json').write_text(json.dumps(result, indent=2))
                    allresults.append(result)
                    print('GROUP CV', name, 'case balanced', round(best[0], 4), 'AUC', round(result['oof_metrics']['roc_auc'], 4), 'threshold', round(threshold, 3), 'epochs', epochs, flush=True)
    best = max(allresults, key=lambda a: (a['case_balanced_oof_accuracy'], a['oof_metrics']['roc_auc']))
    selection = dict(candidates=allresults, selected=best, threshold=best['threshold'], ensemble_seeds=[11, 22, 33], training_count=len(dev), development_group_count=len(set(groups[dev])), test_count=len(te), test_group_count=len(set(groups[te])), test_status='previously seen development benchmark; no independent final validation', custom_head_only=True, software_backbone=True, protocol=json.loads((OUT / 'protocol.json').read_text()))
    (OUT / 'locked_selection.json').write_text(json.dumps(selection, indent=2))
    print('GROUP CV SELECTION LOCKED', best['name'], flush=True)
    with np.load(BASE / best['family'] / 'features.npz') as d:
        f = d['rotation_mean'].copy()
    x, prep = transform(f, dev, best['pca_dimension'])
    np.savez_compressed(OUT / 'preprocessing.npz', **prep)
    tw = sample_weights(y[dev], groups[dev], best['case_weighted'])
    probs = []
    coordinates = []
    for seed in selection['ensemble_seeds']:
        p, _ = train(x, y, dev, tw, best['hidden'], seed, fixed_epochs=best['final_epochs'])
        np.savez_compressed(OUT / f'model_{seed}.npz', **p)
        prob, (_, z, _, _) = forward(x[te], p, 'custom')
        probs.append(prob)
        coordinates.append(dict(seed=seed, coordinate_min=float((z * z).min()), coordinate_max=float((z * z).max())))
    prob = np.mean(probs, axis=0)
    pred = prob[:, 1] >= best['threshold']
    assert all((a['coordinate_min'] >= 0.1 and a['coordinate_max'] <= 2 for a in coordinates))
    selection['test_metrics'] = metrics(y[te], pred, prob[:, 1])
    selection['test_metrics']['case_balanced_accuracy'] = case_balanced(y[te], pred, groups[te])
    selection['test_coordinate_ranges'] = coordinates
    (OUT / 'report.json').write_text(json.dumps(selection, indent=2))
    with (OUT / 'test_predictions.csv').open('w', newline='') as fh:
        w = csv.writer(fh)
        w.writerow(['filename', 'group', 'actual', 'predicted', 'score_malignant'])
        for j, i in enumerate(te):
            w.writerow([records[i]['original_name'], groups[i], int(y[i]), int(pred[j]), float(prob[j, 1])])
    print('GROUP CV SELECTED SYSTEM TEST', json.dumps(selection['test_metrics']), flush=True)
if __name__ == '__main__':
    main()
