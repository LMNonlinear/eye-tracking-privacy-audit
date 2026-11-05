"""Explicit score-table adapter for the paper's frozen equal-fold estimators."""
import csv
import hashlib
import json
from pathlib import Path

import numpy as np



def load_table(path, plan):
    """Qualify complete paired panels; subject IDs are dataset-local."""
    if plan.get('schema_version') != 2 or plan.get('metric') != 'rank1_ir':
        raise ValueError('Blocked mode requires schema2 and percentage Rank1')
    if plan.get('alpha') != .05 or plan.get('correction') != 'holm':
        raise ValueError('Version2 reproduces alpha.05 with separate Holm families')
    if len(plan.get('hypotheses', [])) != 1 or len(plan['hypotheses'][0]) != 2:
        raise ValueError('Version2 supports one declared ordered group pair')
    names = list(plan['conditions'])
    if len(names) != len(set(names)) or plan['baseline'] not in names:
        raise ValueError('Unique conditions including the baseline are required')
    if any(len(p) != 2 or p[0] == p[1] or not set(p) <= set(names)
           for p in plan.get('mechanism_pairs', [])):
        raise ValueError('Mechanism contrasts must name two distinct conditions')
    if plan['n_boot'] != plan['n_perm'] or plan['n_boot'] < 1:
        raise ValueError('Positive matching resampling budgets required')
    panels, metadata = {}, {}
    with Path(path).open(encoding='utf-8', newline='') as stream:
        reader = csv.DictReader(stream)
        required = {'subject_id', 'fold', 'group', 'evaluator', 'condition', 'replicate', 'rank1_ir'}
        if not required <= set(reader.fieldnames or []):
            raise ValueError('Incomplete score-table columns')
        for row in reader:
            dataset = row.get('dataset', 'study').strip()
            sid, group, evaluator, condition, replica = (row[k].strip() for k in
                ('subject_id', 'group', 'evaluator', 'condition', 'replicate'))
            if not all((dataset, sid, group, evaluator, replica)) or condition not in names:
                raise ValueError('Missing identity or undeclared condition')
            fold = int(row['fold'])
            if fold not in range(5):
                raise ValueError('Version2 requires exactly five folds numbered0-4')
            meta = metadata.setdefault(dataset, {})
            if sid in meta and meta[sid] != (fold, group):
                raise ValueError('Participant fold/group differs between paired rows')
            meta[sid] = (fold, group)
            panel = panels.setdefault((dataset, evaluator, condition, replica), {})
            if sid in panel:
                raise ValueError('Duplicate participant within a scoring panel')
            rank = float(row['rank1_ir'])
            utility = float(row['utility']) if row.get('utility', '').strip() else None
            if not np.isfinite(rank) or not 0 <= rank <= 100 or (
                    utility is not None and (not np.isfinite(utility) or not 0 <= utility <= 100)):
                raise ValueError('Outcomes must be finite percentages in[0,100]')
            panel[sid] = (rank, utility)
    if not panels:
        raise ValueError('Empty scoring table')
    result = {}
    pair = plan['hypotheses'][0]
    for dataset, people in sorted(metadata.items()):
        # Numeric subject ordering preserves the frozen resampling stream;
        # lexicographic ordering changes finite-bootstrap draws despite identical means.
        ids = sorted(people, key=lambda s: (int(s), s)) if all(s.lstrip('-').isdigit() for s in people) else sorted(people)
        folds = np.array([people[s][0] for s in ids])
        labels = np.array(['White' if people[s][1] == pair[0] else
                           'Hispanic' if people[s][1] == pair[1] else 'Other' for s in ids])
        if any(sum((labels == group) & (folds == f)) < 2 for group in ['White', 'Hispanic'] for f in range(5)):
            raise ValueError('Both target groups require at least two participants per fold')
        item = {'subjects': ids, 'folds': folds, 'labels': labels, 'biometric': {}, 'utility': {}}
        evaluators = sorted({key[1] for key in panels if key[0] == dataset})
        shared_utility = None
        for evaluator in evaluators:
            replicas = {name: sorted(key[3] for key in panels if key[:3] == (dataset, evaluator, name)) for name in names}
            if not replicas[plan['baseline']] or any(r != replicas[plan['baseline']] for r in replicas.values()):
                raise ValueError('All conditions require identical replicate IDs including baseline')
            arrays, utility = {}, {}
            for name in names:
                records = [panels[dataset, evaluator, name, r] for r in replicas[name]]
                if any(set(rows) != set(ids) for rows in records):
                    raise ValueError('Every panel must retain the complete paired cohort')
                arrays[name] = np.mean([[rows[s][0] for s in ids] for rows in records], axis=0)
                values = [[rows[s][1] for s in ids] for rows in records]
                flat = [v for row in values for v in row]
                if any(v is None for v in flat) and not all(v is None for v in flat):
                    raise ValueError('Partially missing utility is not a valid complete panel')
                utility[name] = None if flat[0] is None else np.mean(values, axis=0)
            if shared_utility is not None:
                if any((shared_utility[n] is None) != (utility[n] is None) or (
                        utility[n] is not None and not np.allclose(shared_utility[n], utility[n], rtol=0, atol=1e-10)) for n in names):
                    raise ValueError('Shared task utility differs across biometric evaluators')
            shared_utility = utility
            item['biometric'][evaluator] = arrays
        item['utility'] = shared_utility
        if any(v is None for v in shared_utility.values()) and not all(v is None for v in shared_utility.values()):
            raise ValueError('Utility must be present for all conditions or omitted throughout')
        result[dataset] = item
    return result
