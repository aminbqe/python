"""Software AI workflow with a bounded normalized custom activation."""
from activations import curve as load_curve
import argparse, json
from pathlib import Path
import numpy as np
from PIL import Image
import torch
from torch import nn
from torchvision.models import efficientnet_b0, EfficientNet_B0_Weights, ResNet18_Weights
from train_mnist import forward
from train_breast_strong import TissueNetwork, stem, backbone
BASE = Path(__file__).resolve().parent / 'runs' / 'breast_histology'
OUT = BASE / 'best_custom'

class BestTissueClassifier:

    def __init__(self, report=None):
        self.report = report if report is not None else json.loads((OUT / 'report.json').read_text())
        self.models = []
        self.extractors = {}
        for member in self.report['selected_members']:
            family = member['family']
            directory = BASE / member['directory']
            name = member['model']
            if family == 'finetuned_resnet18':
                model = TissueNetwork()
                model.load_state_dict(torch.load(directory / name / 'model.pt', map_location='cpu', weights_only=True))
                model.eval()
                if family not in self.extractors:
                    self.extractors[family] = (stem(backbone()), ResNet18_Weights.IMAGENET1K_V1.transforms())
                self.models.append((member, model, None))
            else:
                if family not in self.extractors:
                    if family == 'frozen_resnet18':
                        net = backbone()
                        net.fc = nn.Identity()
                        transform = ResNet18_Weights.IMAGENET1K_V1.transforms()
                    else:
                        net = efficientnet_b0(weights=EfficientNet_B0_Weights.IMAGENET1K_V1).eval()
                        net.classifier = nn.Identity()
                        transform = EfficientNet_B0_Weights.IMAGENET1K_V1.transforms()
                    self.extractors[family] = (net, transform)
                with np.load(directory / name / 'model.npz') as d:
                    model = {k: d[k].copy() for k in ['A1', 'A2']}
                with np.load(directory / 'preprocessing.npz') as d:
                    prep = {k: d[k].copy() for k in ['mean', 'std', 'basis']}
                self.models.append((member, model, prep))

    @torch.inference_mode()
    def predict(self, image):
        image = image.convert('RGB')
        features = {}
        total = np.zeros(2)
        coordinates = []
        for family, (extractor, transform) in self.extractors.items():
            features[family] = extractor(torch.stack([transform(image.rotate(a)) for a in [0, 90, 180, 270]]))
        for member, model, prep in self.models:
            family = member['family']
            f = features[family]
            if family == 'finetuned_resnet18':
                pooled = model.features(f).mean(0, keepdim=True)
                logits, z = model.head(pooled, True)
                prob = logits.softmax(1).numpy()[0]
                coordinate = z.square().numpy()
            else:
                pooled = f[0].numpy() if member['representation'] == 'single' else f.numpy().mean(0)
                x = (pooled - prep['mean']) / prep['std'] @ prep['basis']
                x /= max(np.linalg.norm(x), 1e-08)
                prob, (_, z, _, _) = forward(x[None], model, 'custom')
                prob = prob[0]
                coordinate = z * z
            total += member['weight'] * prob
            coordinates.append([float(coordinate.min()), float(coordinate.max())])
        return dict(research_label=['benign', 'malignant'][int(total.argmax())], model_scores=total.tolist(), ensemble_members=len(self.models), coordinate_ranges=coordinates, note='40x tissue research only; software backbone and bounded Custom head; uncalibrated scores.')

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('image')
    args = ap.parse_args()
    print(json.dumps(BestTissueClassifier().predict(Image.open(args.image))))
if __name__ == '__main__':
    main()
