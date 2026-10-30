"""Software AI workflow with a bounded normalized custom activation."""
from activations import curve as load_curve
from pathlib import Path
import argparse, copy, csv, hashlib, io, json, time, zipfile
import numpy as np
from PIL import Image
import torch
from torch import nn
import torch.nn.functional as F
from torchvision.models import resnet18, ResNet18_Weights
from train_breast_histology import metrics, EXPECTED_SHA
from train_digits import activation as numpy_activation
ROOT = Path(__file__).resolve().parent
BASE = ROOT / 'runs' / 'breast_histology'
PREVIOUS = BASE / 'improved_resnet18'
OUT = BASE / 'strong_custom'
OUT.mkdir(parents=True, exist_ok=True)
torch.set_num_threads(4)
torch.hub.set_dir(str(PREVIOUS / 'weights/hub'))

def get_records():
    records = json.loads((BASE / 'manifest.json').read_text())
    splits = [np.array([i for i, r in enumerate(records) if r['split'] == s]) for s in ['train', 'validation', 'test']]
    gs = [set((records[i]['group'] for i in ids)) for ids in splits]
    assert not (gs[0] & gs[1] or gs[0] & gs[2] or gs[1] & gs[2])
    return (records, np.array([r['label'] for r in records]), splits)

def backbone():
    return resnet18(weights=ResNet18_Weights.IMAGENET1K_V1).eval()

def stem(net):
    return nn.Sequential(net.conv1, net.bn1, net.relu, net.maxpool, net.layer1, net.layer2, net.layer3).eval()

def feature_maps(records):
    path = OUT / 'frozen_stem_maps.npy'
    meta = OUT / 'cache.json'
    sha = hashlib.sha256((BASE / 'manifest.json').read_bytes()).hexdigest()
    if path.exists() and meta.exists():
        m = json.loads(meta.read_text())
        assert m['manifest_sha256'] == sha
        return np.load(path, mmap_mode='r')
    assert hashlib.sha256((BASE / 'breakhis_mirror.zip').read_bytes()).hexdigest() == EXPECTED_SHA
    net = stem(backbone())
    transform = ResNet18_Weights.IMAGENET1K_V1.transforms()
    maps = np.lib.format.open_memmap(path, mode='w+', dtype=np.float32, shape=(len(records), 4, 256, 14, 14))
    started = time.monotonic()
    with zipfile.ZipFile(BASE / 'breakhis_mirror.zip') as z, torch.inference_mode():
        for start in range(0, len(records), 16):
            ims = [Image.open(io.BytesIO(z.read(r['filename']))).convert('RGB') for r in records[start:start + 16]]
            batch = torch.stack([transform(im.rotate(a)) for im in ims for a in [0, 90, 180, 270]])
            maps[start:start + len(ims)] = net(batch).numpy().reshape(len(ims), 4, 256, 14, 14)
            if start % 160 == 0:
                print('stem cache', start, '/', len(records), 'seconds', round(time.monotonic() - started), flush=True)
    maps.flush()
    meta.write_text(json.dumps(dict(manifest_sha256=sha, archive_sha256=EXPECTED_SHA, dtype='float32', shape=list(maps.shape), rotations=[0, 90, 180, 270], frozen_through='layer3'), indent=2))
    return np.load(path, mmap_mode='r')

class CustomHead(nn.Module):

    def __init__(self, seed=11):
        super().__init__()
        with np.load(PREVIOUS / 'preprocessing.npz') as d:
            for key in ['mean', 'std', 'basis']:
                self.register_buffer(key, torch.tensor(d[key], dtype=torch.float32))
        curve = load_curve()
        self.register_buffer('knots', torch.tensor(curve[:, 0], dtype=torch.float32))
        self.register_buffer('values', torch.tensor(curve[:, 1], dtype=torch.float32))
        self.a1 = nn.Linear(64, 128)
        self.a2 = nn.Linear(128, 2)
        with np.load(PREVIOUS / f'custom_{seed}/model.npz') as d, torch.no_grad():
            for name, layer in [('A1', self.a1), ('A2', self.a2)]:
                layer.weight.copy_(torch.tensor(d[name][:, :-1], dtype=torch.float32))
                layer.bias.copy_(torch.tensor(d[name][:, -1], dtype=torch.float32))

    def activate(self, z):
        q = z.square()
        ix = (torch.bucketize(q.detach().contiguous(), self.knots, right=True) - 1).clamp(0, len(self.knots) - 2)
        slope = (self.values[ix + 1] - self.values[ix]) / (self.knots[ix + 1] - self.knots[ix])
        return torch.sqrt(self.values[ix] + slope * (q - self.knots[ix]))

    def forward(self, f, return_z=False):
        x = F.normalize((f - self.mean) / self.std @ self.basis, dim=1, eps=1e-08)
        z = self.a1(x)
        logits = self.a2(self.activate(z))
        return (logits, z) if return_z else logits

    @torch.no_grad()
    def project(self):
        scale = (torch.linalg.vector_norm(self.a1.weight, dim=1) + self.a1.bias.abs()).div(0.98).clamp_min(1)
        self.a1.weight.div_(scale[:, None])
        self.a1.bias.div_(scale)

class TissueNetwork(nn.Module):

    def __init__(self, seed=11):
        super().__init__()
        net = backbone()
        self.layer4 = net.layer4
        self.head = CustomHead(seed)

    def features(self, maps):
        return F.adaptive_avg_pool2d(self.layer4(maps), (1, 1)).flatten(1)

    def train(self, mode=True):
        super().train(mode)
        for m in self.modules():
            if isinstance(m, nn.BatchNorm2d):
                m.eval()
        return self

    def forward(self, maps):
        return self.head(self.features(maps))

def loss_scores(y, prob, weights):
    w = weights[y]
    return float(-(w * np.log(np.maximum(prob[np.arange(len(y)), y], 1e-15))).sum() / w.sum())

@torch.inference_mode()
def predict_maps(net, maps, ids):
    net.eval()
    scores = []
    minp = 1.0
    maxp = 0.0
    for start in range(0, len(ids), 16):
        ix = ids[start:start + 16]
        batch = torch.from_numpy(np.array(maps[ix], copy=True)).flatten(0, 1)
        f = net.features(batch).reshape(len(ix), 4, 512).mean(1)
        logits, z = net.head(f, True)
        scores.append(logits.softmax(1).numpy())
        coordinate = z.square()
        minp = min(minp, float(coordinate.min()))
        maxp = max(maxp, float(coordinate.max()))
    assert minp >= -1e-07 and maxp <= 1 + 1e-07
    return (np.concatenate(scores), dict(coordinate_min=minp, coordinate_max=maxp))

def train_candidate(maps, y, tr, va, lr, seed, epochs):
    name = f'finetune_lr{lr:g}_seed{seed}'
    d = OUT / name
    d.mkdir(parents=True, exist_ok=True)
    if (d / 'selection.json').exists():
        result = json.loads((d / 'selection.json').read_text())
        return (result, np.load(d / 'validation_scores.npy'))
    torch.manual_seed(seed)
    rng = np.random.default_rng(seed)
    net = TissueNetwork(seed)
    optimizer = torch.optim.AdamW([dict(params=net.layer4.parameters(), lr=lr), dict(params=net.head.parameters(), lr=0.0003)], weight_decay=0.0001)
    weights = len(tr) / (2 * np.bincount(y[tr], minlength=2))
    tw = torch.tensor(weights, dtype=torch.float32)
    best = float('inf')
    bestep = 0
    history = []
    started = time.monotonic()
    for epoch in range(epochs + 1):
        trainloss = []
        if epoch:
            net.train()
            ids = rng.permutation(tr)
            for start in range(0, len(ids), 32):
                ix = ids[start:start + 32]
                angles = rng.integers(0, 4, len(ix))
                batch = torch.from_numpy(np.array(maps[ix, angles], copy=True))
                target = torch.tensor(y[ix], dtype=torch.long)
                optimizer.zero_grad(set_to_none=True)
                loss = F.cross_entropy(net(batch), target, weight=tw)
                loss.backward()
                torch.nn.utils.clip_grad_norm_(net.parameters(), 5.0)
                optimizer.step()
                net.head.project()
                trainloss.append(float(loss.detach()))
        prob, _ = predict_maps(net, maps, va)
        vl = loss_scores(y[va], prob, weights)
        met = metrics(y[va], prob.argmax(1), prob[:, 1])
        history.append(dict(epoch=epoch, train_weighted_cross_entropy=float(np.mean(trainloss)) if trainloss else None, validation_weighted_cross_entropy=vl, validation_balanced_accuracy=met['balanced_accuracy']))
        if vl < best:
            best = vl
            bestep = epoch
            selected = copy.deepcopy(net.state_dict())
            selected_prob = prob.copy()
        print(name, 'epoch', epoch, 'val CE', round(vl, 4), 'val balanced', round(met['balanced_accuracy'], 4), 'best', bestep, 'elapsed', round(time.monotonic() - started), flush=True)
        if epoch - bestep >= 7:
            break
    torch.save(selected, d / 'model.pt')
    np.save(d / 'validation_scores.npy', selected_prob)
    result = dict(name=name, seed=seed, backbone_lr=lr, head_lr=0.0003, best_epoch=bestep, epochs_executed=epoch, validation_weighted_cross_entropy=best, validation_metrics=metrics(y[va], selected_prob.argmax(1), selected_prob[:, 1]))
    (d / 'history.json').write_text(json.dumps(history, indent=2))
    (d / 'selection.json').write_text(json.dumps(result, indent=2))
    return (result, selected_prob)

def check_activation():
    head = CustomHead().double()
    z = torch.linspace(-0.98, 0.98, 321, dtype=torch.float64, requires_grad=True)
    h = head.activate(z)
    h.sum().backward()
    reference, derivative = numpy_activation(z.detach().numpy(), 'custom')
    err = float(np.max(abs(h.detach().numpy() - reference)))
    derr = float(np.max(abs(z.grad.numpy() - derivative)))
    assert err < 1e-07 and derr < 2e-06, (err, derr)
    return dict(output_max_error=err, gradient_max_error=derr)

def grouped_metrics(records, ids, y, prob):
    gs = sorted(set((records[i]['group'] for i in ids)))
    gp = []
    gy = []
    ga = []
    for g in gs:
        mask = np.array([records[i]['group'] == g for i in ids])
        gp.append(prob[mask, 1].mean())
        gy.append(y[ids][mask][0])
        ga.append((y[ids][mask] == prob[mask].argmax(1)).mean())
    return dict(mean_case_image_accuracy=float(np.mean(ga)), case_mean_score_metrics=metrics(np.array(gy), np.array(gp) >= 0.5, np.array(gp)))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--epochs', type=int, default=35)
    ap.add_argument('--selection-only', action='store_true')
    args = ap.parse_args()
    records, y, (tr, va, te) = get_records()
    check = check_activation()
    print('Custom consistency', check, flush=True)
    maps = feature_maps(records)
    candidates = []
    scores = {}
    for lr in [1e-06, 3e-05, 0.0001]:
        result, prob = train_candidate(maps, y, tr, va, lr, 11, args.epochs)
        candidates.append(result)
        scores[result['name']] = prob
    winner = min(candidates, key=lambda a: a['validation_weighted_cross_entropy'])
    lr = winner['backbone_lr']
    for seed in [22, 33]:
        result, prob = train_candidate(maps, y, tr, va, lr, seed, args.epochs)
        candidates.append(result)
        scores[result['name']] = prob
    weights = len(tr) / (2 * np.bincount(y[tr], minlength=2))
    best = min(candidates, key=lambda a: a['validation_weighted_cross_entropy'])
    ensemble_members = [a['name'] for a in candidates if a['backbone_lr'] == lr]
    ensemble = np.mean([scores[n] for n in ensemble_members], axis=0)
    ensemble_loss = loss_scores(y[va], ensemble, weights)
    chosen = ensemble_members if ensemble_loss < best['validation_weighted_cross_entropy'] else [best['name']]
    valprob = np.mean([scores[n] for n in chosen], axis=0)
    selection = dict(candidates=candidates, selected_members=chosen, ensemble_validation_loss=ensemble_loss, selection_metric='validation class-weighted cross entropy; fixed decision threshold 0.5', validation_metrics=metrics(y[va], valprob.argmax(1), valprob[:, 1]), architecture='software ResNet18, frozen stem through layer3, fine-tuned layer4; train-only fixed PCA64; bounded Custom128; 2 scores', training_rotations=[0, 90, 180, 270], inference='mean of 4 rotation feature vectors before PCA and Custom head; mean model scores if ensemble', frozen_batch_norm_statistics=True, gradient_check=check, threshold=0.5, test_status='same previously seen development test, not independent external validation', manifest_sha256=hashlib.sha256((BASE / 'manifest.json').read_bytes()).hexdigest(), trainable_stem=False, split_counts=[len(tr), len(va), len(te)])
    (OUT / 'locked_selection.json').write_text(json.dumps(selection, indent=2))
    print('SELECTION LOCKED', chosen, flush=True)
    if args.selection_only:
        print('Selection only: test evaluation deferred.', flush=True)
        return
    test_probs = []
    coordinates = []
    for name in chosen:
        net = TissueNetwork()
        net.load_state_dict(torch.load(OUT / name / 'model.pt', map_location='cpu', weights_only=True))
        prob, coordinate = predict_maps(net, maps, te)
        test_probs.append(prob)
        coordinates.append(coordinate)
    prob = np.mean(test_probs, axis=0)
    selection['test_metrics'] = metrics(y[te], prob.argmax(1), prob[:, 1])
    selection['test_metrics'].update(grouped_metrics(records, te, y, prob))
    selection['member_test_coordinate_ranges'] = coordinates
    (OUT / 'report.json').write_text(json.dumps(selection, indent=2))
    with (OUT / 'test_predictions.csv').open('w', newline='') as fh:
        w = csv.writer(fh)
        w.writerow(['filename', 'group', 'actual', 'predicted', 'score_malignant'])
        for j, i in enumerate(te):
            w.writerow([records[i]['original_name'], records[i]['group'], int(y[i]), int(prob[j].argmax()), float(prob[j, 1])])
    print('FINAL TEST', json.dumps(selection['test_metrics']), flush=True)
if __name__ == '__main__':
    main()
