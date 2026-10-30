"""Summarize locally generated report metrics."""
import argparse
import json
from pathlib import Path

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('report',type=Path)
    parser.add_argument('--output',type=Path)
    parser.add_argument('--plot',type=Path)
    args=parser.parse_args()
    report=json.loads(args.report.read_text())
    rows=report.get('results',[report])
    fields=['activation','seed','best_epoch','validation_loss','validation_weighted_cross_entropy','test_accuracy','accuracy','balanced_accuracy','roc_auc']
    fields=[k for k in fields if any(k in row for row in rows)]
    if not fields:raise ValueError('No supported metrics found')
    lines=['| '+' | '.join(fields)+' |','| '+' | '.join(['---']*len(fields))+' |']
    lines+=['| '+' | '.join(str(row.get(k,'')) for k in fields)+' |' for row in rows]
    text='\n'.join(lines)+'\n'
    if args.output:args.output.write_text(text,encoding='utf-8')
    else:print(text)
    if args.plot:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        metric=next((k for k in ['test_accuracy','accuracy','balanced_accuracy'] if k in fields),None)
        if metric is None:raise ValueError('No accuracy metric available')
        selected=[r for r in rows if metric in r]
        fig,ax=plt.subplots(figsize=(8,4))
        ax.bar(range(len(selected)),[r[metric] for r in selected])
        ax.set_xticks(range(len(selected)),[str(r.get('activation','model'))+' '+str(r.get('seed','')) for r in selected],rotation=30)
        ax.set_ylabel(metric);fig.tight_layout();fig.savefig(args.plot,dpi=160);plt.close(fig)

if __name__=='__main__':main()
