"""Generate a reproducible, entirely synthetic multi-condition demonstration."""
import argparse
import csv
import json
from pathlib import Path

import numpy as np


def generate(destination):
    destination = Path(destination)
    if destination.exists():
        raise FileExistsError('Preserve previous inputs; choose a fresh directory')
    destination.mkdir(parents=True)
    rng = np.random.default_rng(20261106)
    conditions = ['Unprotected', 'Low protection', 'High protection']
    means = {'Group A': [80, 58, 25], 'Group B': [78, 48, 23]}
    with (destination / 'synthetic_scores.csv').open('w', encoding='utf8', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(['subject_id', 'fold', 'group', 'evaluator', 'condition', 'replicate', 'rank1_ir', 'dataset'])
        for fold in range(5):
            for group in ('Group A', 'Group B'):
                for index in range(20):
                    subject = f'S{fold}{"A" if group == "Group A" else "B"}{index:02d}'
                    latent = rng.normal(0, 5)
                    for condition_index, condition in enumerate(conditions):
                        signal = means[group][condition_index] + .6 * latent + rng.normal(0, 3)
                        for replicate in range(3):
                            score = np.clip(signal + rng.normal(0, 1.5), 0, 100)
                            writer.writerow([subject, fold, group, 'Example model', condition, replicate,
                                             f'{score:.6f}', 'Simulated dataset'])
    plan = {
        'schema_version': 2, 'metric': 'rank1_ir', 'baseline': 'Unprotected',
        'conditions': conditions, 'controls': [], 'hypotheses': [['Group A', 'Group B']],
        'mechanism_pairs': [], 'alpha': .05, 'correction': 'holm',
        'seed': 42, 'n_boot': 10000, 'n_perm': 10000,
        'scope': 'Synthetic demonstration: 200 simulated participants, five folds, two groups, a baseline and two protection settings, with three paired scores per setting. Generated for report illustration only, not for calibration or study conclusions.',
    }
    (destination / 'plan.json').write_text(json.dumps(plan, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    print(f'SYNTHETIC_INPUT_COMPLETE {destination}', flush=True)


def main():
    parser = argparse.ArgumentParser(description='Generate synthetic demonstration inputs')
    parser.add_argument('--output', required=True, help='New output directory; existing directories are not overwritten')
    args = parser.parse_args()
    generate(args.output)


if __name__ == '__main__':
    main()
