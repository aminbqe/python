"""Software AI workflow with a bounded normalized custom activation."""
from activations import curve as load_curve
import csv, hashlib, json
from pathlib import Path
import numpy as np
import torch
from train_mnist import forward
from train_breast_histology import metrics
from train_breast_strong import TissueNetwork, predict_maps, get_records, loss_scores, grouped_metrics
ROOT = Path(__file__).resolve().parent
BASE = ROOT / 'runs' / 'breast_histology'
OUT = BASE / 'best_custom'
OUT.mkdir(parents=True, exist_ok=True)

def frozen_scores(directory, representation, members, ids):
    with np.load(directory / 'features.npz') as d:
        f = d[representation][ids].copy()
    with np.load(directory / 'preprocessing.npz') as d:
        x = (f - d['mean']) / d['std'] @ d['basis']
    x /= np.maximum(np.linalg.norm(x, axis=1, keepdims=True), 1e-08)
    probs = []
    coordinates = []
    for name in members:
        with np.load(directory / name / 'model.npz') as d:
            p = {k: d[k] for k in ['A1', 'A2']}
        prob, (_, z, _, _) = forward(x, p, 'custom')
        probs.append(prob)
        coordinates.append(dict(model=name, coordinate_min=float((z * z).min()), coordinate_max=float((z * z).max())))
    return (probs, coordinates)

def main():
    records, y, (tr, va, te) = get_records()
    weights = len(tr) / (2 * np.bincount(y[tr], minlength=2))
    fine = json.loads((BASE / 'strong_custom/locked_selection.json').read_text())
    efficient = json.loads((BASE / 'efficient_custom/locked_selection.json').read_text())
    old = json.loads((BASE / 'improved_resnet18/report.json').read_text())
    families = []
    fprob = np.mean([np.load(BASE / 'strong_custom' / n / 'validation_scores.npy') for n in fine['selected_members']], axis=0)
    families.append(dict(name='finetuned_resnet18', directory='strong_custom', members=fine['selected_members'], representation='rotation_mean', pca_dimension=64, hidden=128, prob=fprob))
    families.append(dict(name='frozen_efficientnet_b0', directory='efficient_custom', members=efficient['selected_members'], representation=efficient['representation'], pca_dimension=efficient['pca_dimension'], hidden=efficient['hidden'], prob=np.load(BASE / 'efficient_custom/selected_validation_scores.npy')))
    seeds = [r['seed'] for r in old['results'] if r['activation'] == 'custom']
    oprobs, _ = frozen_scores(BASE / 'improved_resnet18', old['representation'], [f'custom_{s}' for s in seeds], va)
    oldchoice = min(range(len(seeds)), key=lambda i: loss_scores(y[va], oprobs[i], weights))
    avg = np.mean(oprobs, axis=0)
    omembers = [f'custom_{s}' for s in seeds] if loss_scores(y[va], avg, weights) < loss_scores(y[va], oprobs[oldchoice], weights) else [f'custom_{seeds[oldchoice]}']
    oprob = avg if len(omembers) > 1 else oprobs[oldchoice]
    families.append(dict(name='frozen_resnet18', directory='improved_resnet18', members=omembers, representation=old['representation'], pca_dimension=64, hidden=128, prob=oprob))
    family_losses = [loss_scores(y[va], f['prob'], weights) for f in families]
    ranking = np.argsort(family_losses).tolist()
    options = [[i] for i in range(len(families))] + [ranking[:2], ranking]
    candidates = []
    for ids in options:
        prob = np.mean([families[i]['prob'] for i in ids], axis=0)
        candidates.append(dict(families=[families[i]['name'] for i in ids], validation_weighted_cross_entropy=loss_scores(y[va], prob, weights), validation_metrics=metrics(y[va], prob.argmax(1), prob[:, 1])))
    best = min(range(len(candidates)), key=lambda i: candidates[i]['validation_weighted_cross_entropy'])
    chosen = options[best]
    selected = []
    for i in chosen:
        family = families[i]
        for name in family['members']:
            selected.append(dict(family=family['name'], directory=family['directory'], model=name, representation=family['representation'], pca_dimension=family['pca_dimension'], hidden=family['hidden'], weight=1 / (len(chosen) * len(family['members']))))
    report = dict(selection_candidates=candidates, selected_members=selected, validation_weighted_cross_entropy=candidates[best]['validation_weighted_cross_entropy'], validation_metrics=candidates[best]['validation_metrics'], threshold=0.5, selection_metric='class-weighted validation cross entropy; individual families or equal averages of top 2/all 3 families', training_candidates=dict(finetuning=fine['candidates'], efficientnet=efficient['candidates']), split_counts=[len(tr), len(va), len(te)], test_status='previously seen development test; not independent confirmation', manifest_sha256=hashlib.sha256((BASE / 'manifest.json').read_bytes()).hexdigest(), software_backbone=True, custom_head_only=True, hysteresis='fixed branch and known initial state; ideal regeneration', custom_consistency=fine['gradient_check'])
    (OUT / 'locked_selection.json').write_text(json.dumps(report, indent=2))
    print('FINAL SELECTION LOCKED', [(a['family'], a['model'], a['weight']) for a in selected], flush=True)
    total = np.zeros((len(te), 2))
    coordinates = []
    for member in selected:
        directory = BASE / member['directory']
        name = member['model']
        if member['family'] == 'finetuned_resnet18':
            net = TissueNetwork()
            net.load_state_dict(torch.load(directory / name / 'model.pt', map_location='cpu', weights_only=True))
            maps = np.load(directory / 'frozen_stem_maps.npy', mmap_mode='r')
            prob, coordinate = predict_maps(net, maps, te)
            coordinate.update(model=name)
        else:
            probs, ps = frozen_scores(directory, member['representation'], [name], te)
            prob = probs[0]
            coordinate = ps[0]
        assert coordinate['coordinate_min'] >= 0.1 - 1e-07 and coordinate['coordinate_max'] <= 2 + 1e-07
        coordinates.append(coordinate)
        total += member['weight'] * prob
    report['test_metrics'] = metrics(y[te], total.argmax(1), total[:, 1])
    report['test_metrics'].update(grouped_metrics(records, te, y, total))
    report['member_test_coordinate_ranges'] = coordinates
    (OUT / 'report.json').write_text(json.dumps(report, indent=2))
    with (OUT / 'test_predictions.csv').open('w', newline='') as fh:
        w = csv.writer(fh)
        w.writerow(['filename', 'group', 'actual', 'predicted', 'score_malignant'])
        for j, i in enumerate(te):
            w.writerow([records[i]['original_name'], records[i]['group'], int(y[i]), int(total[j].argmax()), float(total[j, 1])])
    print('SELECTED SYSTEM TEST', json.dumps(report['test_metrics']), flush=True)
if __name__ == '__main__':
    main()
