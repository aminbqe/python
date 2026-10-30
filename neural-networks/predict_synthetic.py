"""Predict two-dimensional samples using a generated synthetic model."""
import argparse
import json
from pathlib import Path
import numpy as np
from train_synthetic import forward

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('model_directory',type=Path)
    parser.add_argument('--x',type=float,nargs=2,required=True)
    args=parser.parse_args()
    metrics=json.loads((args.model_directory/'metrics.json').read_text())
    norm=metrics['normalization']
    x=np.array([args.x],dtype=float)
    if not np.isfinite(x).all():raise ValueError('Inputs must be finite')
    x=np.clip((x-norm['center'])/norm['scale'],-1,1)
    with np.load(args.model_directory/'model.npz') as data:p={k:data[k] for k in ['A1','A2']}
    prob,_=forward(x,p,metrics['activation'])
    print(json.dumps({'label':int(prob[0].argmax()),'scores':prob[0].tolist()}))

if __name__=='__main__':main()
