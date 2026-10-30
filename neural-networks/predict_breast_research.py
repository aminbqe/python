"""Software AI workflow with a bounded normalized custom activation."""
from activations import curve as load_curve
import argparse, json
from pathlib import Path
from PIL import Image
from predict_breast_best import BestTissueClassifier
from predict_breast_final import TissueClassifier
BASE = Path(__file__).resolve().parent / 'runs' / 'breast_histology'

def load_classifier(variant='balanced'):
    if variant == 'group_cv':
        return TissueClassifier()
    if variant == 'efficient':
        return BestTissueClassifier()
    report = json.loads((BASE / 'improved_resnet18/report.json').read_text())
    return BestTissueClassifier(dict(selected_members=[dict(family='frozen_resnet18', directory='improved_resnet18', model=f"custom_{report['selected_custom']}", representation=report['representation'], weight=1.0, pca_dimension=64, hidden=128)]))

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('image')
    ap.add_argument('--variant', choices=['balanced', 'efficient', 'group_cv'], default='balanced')
    args = ap.parse_args()
    result = load_classifier(args.variant).predict(Image.open(args.image))
    result['variant'] = args.variant
    print(json.dumps(result))
if __name__ == '__main__':
    main()
