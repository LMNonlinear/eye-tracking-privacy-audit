"""Explicit robust group-risk entry; legacy diagnostics never veto residual gaps."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np

from scripts.privacy_blocked_pipeline import load_table
from src.fairness.robust_inference import METHOD,group_contrast,paired_contrast,adjust_holm

ROOT=Path(__file__).resolve().parents[1]


def calibration_status(path):
    if not Path(path).exists():
        return False,'independent_calibration_missing'
    result=json.loads(Path(path).read_text(encoding='utf-8'))
    source=ROOT/'src/fairness/robust_inference.py'
    expected=result.get('source_sha256',{}).get('src/fairness/robust_inference.py')
    source_bytes=source.read_bytes()
    same=hashlib.sha256(source_bytes).hexdigest()==expected
    # Accept only exact, reversible uniform Git line-ending conversions.
    if not same and b'\r' not in source_bytes:
        same=hashlib.sha256(source_bytes.replace(b'\n',b'\r\n')).hexdigest()==expected
    elif not same and source_bytes.count(b'\r\n')==source_bytes.count(b'\n')==source_bytes.count(b'\r'):
        same=hashlib.sha256(source_bytes.replace(b'\r\n',b'\n')).hexdigest()==expected
    ready=result.get('status')=='complete' and result.get('calibration_passed') is True and same
    return ready,'independent_score_level_gates_passed' if ready else 'calibration_failed_or_method_changed'


def analyze_vectors(data,plan,calibrated):
    primary=[];secondary=[];utility=[];summaries=[];diagnostics=[]
    excluded={plan['baseline'],*plan.get('controls',[])}
    for dataset,item in sorted(data.items()):
        labels=np.array(item['labels']);folds=np.array(item['folds'])
        for evaluator,raw in sorted(item['biometric'].items()):
            vectors={k:np.array(v,dtype=float) for k,v in raw.items()}
            for condition,vector in vectors.items():
                row=group_contrast(vector,labels,folds)
                means={g:float(np.mean([vector[(folds==f)&(labels==g)].mean() for f in range(5)])) for g in ['White','Hispanic']}
                overall=float(np.mean([vector[folds==f].mean() for f in range(5)]))
                summaries.append(dict(dataset=dataset,evaluator=evaluator,condition=condition,overall_rank1_percent=overall,
                                      group_a_percent=means['White'],group_b_percent=means['Hispanic'],signed_gap_pp=row['diff_pp']))
                chance=float(np.mean([100/sum(folds==f) for f in range(5)]))
                diagnostics.append(dict(dataset=dataset,evaluator=evaluator,condition=condition,
                  near_chance_descriptive=overall<=3*chance,full_gallery_chance_percent=chance,
                  fold_differences_pp=row['fold_differences_pp'],leave_one_fold_out_pp=row['leave_one_fold_out_pp'],
                  fold_group_sizes=row['fold_group_sizes'],affects_residual_decision=False,
                  note='Baseline disparity, fold/gallery composition and floor proximity are annotations; no causal attribution or diagnostic veto'))
                if condition in excluded:continue
                secondary.append(dict(row,dataset=dataset,evaluator=evaluator,condition=condition,endpoint='residual_rank1'))
                secondary.append(dict(group_contrast(vector-vectors[plan['baseline']],labels,folds),dataset=dataset,evaluator=evaluator,condition=condition,endpoint='change_from_baseline'))
            for left,right in plan.get('mechanism_pairs',[]):
                primary.append(dict(group_contrast(vectors[left]-vectors[right],labels,folds),dataset=dataset,evaluator=evaluator,left=left,right=right))
        if item['utility'].get(plan['baseline']) is not None:
            for left,right in plan.get('mechanism_pairs',[]):
                utility.append(dict(paired_contrast(np.array(item['utility'][left])-np.array(item['utility'][right]),folds),dataset=dataset,left=left,right=right))
    for rows in [primary,secondary,utility]:adjust_holm(rows,calibrated=calibrated)
    return dict(primary_tests=primary,secondary_tests=secondary,utility_tests=utility,condition_results=summaries,
                diagnostic_annotations=diagnostics,family_sizes=[len(primary),len(secondary),len(utility)])


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--scores',required=True);parser.add_argument('--plan',required=True)
    local=ROOT/'results/robust_audit_precision_confirmation/analysis.json'
    default_calibration=local if local.exists() else ROOT/'dev/robust_audit_calibration_summary.json'
    parser.add_argument('--output',required=True);parser.add_argument('--calibration',default=str(default_calibration))
    args=parser.parse_args();out=Path(args.output)
    if out.exists():raise FileExistsError('Preserve previous results')
    plan=json.loads(Path(args.plan).read_text(encoding='utf-8'))
    data=load_table(args.scores,plan);calibrated,status=calibration_status(args.calibration)
    result=analyze_vectors(data,plan,calibrated)
    result.update(status='complete',analysis_mode=METHOD,calibration_status=status,formal_decisions_enabled=calibrated,
                  plan=plan,uncertainty='Pointwise approximate Welch-Satterthwaite t intervals, conditional fixed-model independent-participant inference',
                  limits=['Score-level calibration does not establish independence in shared-gallery or overlapping-training data.',
                          'Legacy six-check mode is a separate historical reproduction; diagnostic flags never veto residual-risk reporting.',
                          'No equivalence, causal ethnicity, deployment or strongest-attack guarantee.'],
                  scores_sha256=hashlib.sha256(Path(args.scores).read_bytes()).hexdigest())
    out.mkdir(parents=True);(out/'report.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print('ROBUST_AUDIT_COMPLETE',result['family_sizes'],status,flush=True)


if __name__=='__main__':main()
