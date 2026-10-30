"""Software AI workflow with a bounded normalized custom activation."""
from activations import curve as load_curve
import argparse, json
import numpy as np
from PIL import Image
import torch
from torchvision.models import ResNet18_Weights
from train_breast_strong import OUT, TissueNetwork, stem, backbone

@torch.inference_mode()
def predict_image(image):
    report = json.loads((OUT / 'report.json').read_text())
    transform = ResNet18_Weights.IMAGENET1K_V1.transforms()
    image = image.convert('RGB')
    batch = torch.stack([transform(image.rotate(a)) for a in [0, 90, 180, 270]])
    maps = stem(backbone())(batch)
    predictions = []
    coordinates = []
    for name in report['selected_members']:
        net = TissueNetwork()
        net.load_state_dict(torch.load(OUT / name / 'model.pt', map_location='cpu', weights_only=True))
        net.eval()
        f = net.features(maps).mean(0, keepdim=True)
        logits, z = net.head(f, True)
        predictions.append(logits.softmax(1).numpy()[0])
        coordinate = z.square()
        coordinates.append([float(coordinate.min()), float(coordinate.max())])
    score = np.mean(predictions, axis=0)
    return dict(research_label=['benign', 'malignant'][int(score.argmax())], model_scores=score.tolist(), ensemble_members=len(predictions), coordinate_ranges=coordinates, note='40x BreakHis-like tissue only; software image processing and Custom classifier; uncalibrated scores, not clinical validation.')

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('image')
    args = ap.parse_args()
    print(json.dumps(predict_image(Image.open(args.image))))
if __name__ == '__main__':
    main()
