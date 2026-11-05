"""Approximate heteroscedastic inference for fixed-model equal-fold means.

Participants are independent sampling units conditional on the fitted models
and galleries. Shared-gallery or training-induced dependence is not estimated.
Historical permutation/diagnostic modules remain separate reproduction paths.
"""
import numpy as np
from scipy.stats import t

METHOD = 'welch_equal_fold_v1'


def _qualify(values, folds):
    x = np.asarray(values, dtype=float)
    if x.ndim == 1:
        x = x[None, :]
    f = np.asarray(folds)
    if x.ndim != 2 or not x.shape[0] or not x.shape[1] or f.ndim != 1 or x.shape[1] != len(f):
        raise ValueError('Complete outcome-by-participant matrix and aligned folds required')
    if not np.isfinite(x).all() or not np.isin(f, np.arange(5)).all() or set(f.tolist()) != set(range(5)):
        raise ValueError('Finite outcomes and all five integer folds0-4 required')
    return x, f


def _summarize(estimates, components, degrees):
    variance = np.sum(components, axis=1)
    denominator = np.sum(components**2/np.asarray(degrees)[None, :], axis=1)
    valid = (variance > 0) & (denominator > 0) & np.isfinite(variance) & np.isfinite(denominator)
    se = np.sqrt(variance)
    df = np.divide(variance**2, denominator, out=np.full_like(variance, np.nan), where=valid)
    statistic = np.divide(estimates, se, out=np.full_like(se, np.nan), where=valid)
    p = 2*t.sf(np.abs(statistic), df)
    width = t.ppf(.975, df)*se
    rows=[]
    for i in range(len(estimates)):
        rows.append(dict(method=METHOD, status='estimable' if valid[i] else 'withheld_zero_sampling_variance',
                         diff_pp=float(estimates[i]), standard_error_pp=float(se[i]),
                         degrees_of_freedom=float(df[i]) if valid[i] else None,
                         p=float(p[i]) if valid[i] else None,
                         ci95=[float(estimates[i]-width[i]),float(estimates[i]+width[i])] if valid[i] else None,
                         inference_scope='Approximate t inference, independent participants conditional on fixed models/galleries'))
    return rows


def group_batch(values, labels, folds):
    x,f = _qualify(values, folds)
    g = np.asarray(labels)
    if g.ndim != 1 or len(g) != x.shape[1]:
        raise ValueError('Aligned group labels required')
    contrasts=[]; components=[]; degrees=[]; sizes=[]
    for fold in range(5):
        a=x[:,(f==fold)&(g=='White')]; b=x[:,(f==fold)&(g=='Hispanic')]
        if min(a.shape[1],b.shape[1])<2:
            raise ValueError('At least two participants per target group and fold required')
        contrasts.append(a.mean(1)-b.mean(1)); sizes.append((a.shape[1],b.shape[1]))
        for cell in [a,b]:
            components.append(cell.var(1,ddof=1)/cell.shape[1]/25)
            degrees.append(cell.shape[1]-1)
    delta=np.asarray(contrasts).T
    rows=_summarize(delta.mean(1),np.asarray(components).T,degrees)
    for i,row in enumerate(rows):
        row['fold_differences_pp']=delta[i].tolist()
        row['fold_group_sizes']=[list(s) for s in sizes]
        row['leave_one_fold_out_pp']=((delta[i].sum()-delta[i])/4).tolist()
    return rows


def group_contrast(values, labels, folds):
    if np.asarray(values).ndim!=1:
        raise ValueError('One value per participant required')
    return group_batch(values,labels,folds)[0]


def paired_batch(differences, folds):
    x,f=_qualify(differences,folds)
    means=[];components=[];degrees=[]
    for fold in range(5):
        cell=x[:,f==fold]
        if cell.shape[1]<2:
            raise ValueError('At least two participant differences per fold required')
        means.append(cell.mean(1));components.append(cell.var(1,ddof=1)/cell.shape[1]/25);degrees.append(cell.shape[1]-1)
    means=np.asarray(means).T
    rows=_summarize(means.mean(1),np.asarray(components).T,degrees)
    for row,m in zip(rows,means):
        row['fold_effects_pp']=m.tolist()
    return rows


def paired_contrast(differences, folds):
    if np.asarray(differences).ndim!=1:
        raise ValueError('One paired difference per participant required')
    return paired_batch(differences,folds)[0]


def adjust_holm(rows, calibrated=True):
    """Retain every hypothesis; nonestimable rows use p1 only for multiplicity."""
    order=sorted(range(len(rows)),key=lambda i:1. if rows[i]['p'] is None else rows[i]['p'])
    maximum=0.
    for rank,index in enumerate(order):
        row=rows[index]; effective=1. if row['p'] is None else row['p']
        maximum=max(maximum,min(1.,(len(rows)-rank)*effective))
        row['holm_p']=maximum
        row['passes_correction']=bool(maximum<.05) if calibrated and row['p'] is not None else None
        row['decision_status']='conditional_calibrated' if calibrated and row['p'] is not None else 'withheld'
    return rows
