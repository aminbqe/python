"""Software AI workflow with a bounded normalized custom activation."""
from activations import curve as load_curve
import argparse, json
from pathlib import Path
import numpy as np
from PIL import Image
import torch
from torch import nn
from torchvision.models import resnet18, ResNet18_Weights, efficientnet_b0, EfficientNet_B0_Weights
from train_mnist import forward
BASE = Path(__file__).resolve().parent / 'runs' / 'breast_histology'
OUT = BASE / 'robust_custom'

class TissueClassifier:

    def __init__(self):
        torch.set_num_threads(4)
        torch.hub.set_dir(str(BASE / 'improved_resnet18/weights/hub'))
        self.report = json.loads((OUT / 'report.json').read_text())
        self.threshold = self.report['threshold']
        if self.report['selected']['family'] == 'improved_resnet18':
            weights = ResNet18_Weights.IMAGENET1K_V1
            self.net = resnet18(weights=weights).eval()
            self.net.fc = nn.Identity()
        else:
            weights = EfficientNet_B0_Weights.IMAGENET1K_V1
            self.net = efficientnet_b0(weights=weights).eval()
            self.net.classifier = nn.Identity()
        self.transform = weights.transforms()
        with np.load(OUT / 'preprocessing.npz') as d:
            self.prep = {k: d[k].copy() for k in ['mean', 'std', 'basis']}
        self.models = []
        for seed in self.report['ensemble_seeds']:
            with np.load(OUT / f'model_{seed}.npz') as d:
                self.models.append({k: d[k].copy() for k in ['A1', 'A2']})

    @torch.inference_mode()
    def predict(self, image):
        image = image.convert('RGB')
        batch = torch.stack([self.transform(image.rotate(a)) for a in [0, 90, 180, 270]])
        f = self.net(batch).numpy().mean(0)
        prep = self.prep
        x = (f - prep['mean']) / prep['std'] @ prep['basis']
        x /= max(np.linalg.norm(x), 1e-08)
        scores = []
        coordinates = []
        for model in self.models:
            prob, (_, z, _, _) = forward(x[None], model, 'custom')
            scores.append(prob[0])
            coordinates.append([float((z * z).min()), float((z * z).max())])
        score = np.mean(scores, axis=0)
        label = int(score[1] >= self.threshold)
        return dict(research_label=['benign', 'malignant'][label], model_scores=score.tolist(), decision_threshold=self.threshold, ensemble_members=len(self.models), coordinate_ranges=coordinates, note='40x tissue research only; software backbone + Custom classifier. Scores are not calibrated clinical probabilities.')

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('image')
    args = ap.parse_args()
    print(json.dumps(TissueClassifier().predict(Image.open(args.image))))
if __name__ == '__main__':
    main()
