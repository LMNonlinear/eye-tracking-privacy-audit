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
    conditions = ['未保护', '低强度保护', '高强度保护']
    means = {'群体A': [80, 58, 25], '群体B': [78, 48, 23]}
    with (destination / 'synthetic_scores.csv').open('w', encoding='utf8', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(['subject_id', 'fold', 'group', 'evaluator', 'condition', 'replicate', 'rank1_ir', 'dataset'])
        for fold in range(5):
            for group in ('群体A', '群体B'):
                for index in range(20):
                    subject = f'S{fold}{"A" if group == "群体A" else "B"}{index:02d}'
                    latent = rng.normal(0, 5)
                    for condition_index, condition in enumerate(conditions):
                        signal = means[group][condition_index] + .6 * latent + rng.normal(0, 3)
                        for replicate in range(3):
                            score = np.clip(signal + rng.normal(0, 1.5), 0, 100)
                            writer.writerow([subject, fold, group, '示例模型', condition, replicate,
                                             f'{score:.6f}', '模拟数据'])
    plan = {
        'schema_version': 2, 'metric': 'rank1_ir', 'baseline': '未保护',
        'conditions': conditions, 'controls': [], 'hypotheses': [['群体A', '群体B']],
        'mechanism_pairs': [], 'alpha': .05, 'correction': 'holm',
        'seed': 42, 'n_boot': 10000, 'n_perm': 10000,
        'scope': 'Synthetic 合成演示：200 名虚拟参与者、五折、两个群体、三个保护条件，每个条件三次配对评分。所有数据均为程序生成，不是真实参与者记录，也不用于方法校准或论文实验结论。',
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
