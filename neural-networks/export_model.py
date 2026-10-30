"""Export a locally trained NumPy model's matrices to CSV."""
import argparse
from pathlib import Path
import numpy as np

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('model',type=Path)
    parser.add_argument('output',type=Path)
    args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    with np.load(args.model,allow_pickle=False) as model:
        for key in ['A1','A2']:
            matrix=model[key]
            np.savetxt(args.output/f'{key}_weights.csv',matrix[:,:-1],delimiter=',')
            np.savetxt(args.output/f'{key}_bias.csv',matrix[:,-1:],delimiter=',')

if __name__=='__main__':main()
