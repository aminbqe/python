"""Software AI workflow with a bounded normalized custom activation."""
from activations import curve as load_curve
import argparse, json
import numpy as np
from PIL import Image
from improve_breast_histology import OUT
from train_mnist import forward

def main():
    import torch
    from torchvision.models import resnet18, ResNet18_Weights
    ap = argparse.ArgumentParser()
    ap.add_argument('image')
    args = ap.parse_args()
    torch.set_num_threads(4)
    torch.hub.set_dir(str(OUT / 'weights' / 'hub'))
    report = json.loads((OUT / 'report.json').read_text())
    weights = ResNet18_Weights.IMAGENET1K_V1
    net = resnet18(weights=weights).eval()
    net.fc = torch.nn.Identity()
    im = Image.open(args.image).convert('RGB')
    angles = [0] if report['representation'] == 'single' else [0, 90, 180, 270]
    with torch.inference_mode():
        f = net(torch.stack([weights.transforms()(im.rotate(a)) for a in angles])).numpy().mean(0)
    with np.load(OUT / 'preprocessing.npz') as prep:
        x = (f - prep['mean']) / prep['std'] @ prep['basis']
    x /= max(np.linalg.norm(x), 1e-08)
    with np.load(OUT / f"custom_{report['selected_custom']}" / 'model.npz') as d:
        p = {k: d[k] for k in ['A1', 'A2']}
    prob, (_, z, _, _) = forward(x[None], p, 'custom')
    print(json.dumps(dict(research_label=['benign', 'malignant'][int(prob[0].argmax())], model_scores=prob[0].tolist(), coordinate_range=[float((z * z).min()), float((z * z).max())], note='40x tissue research only; software ResNet18 features; uncalibrated scores.')))
if __name__ == '__main__':
    main()
