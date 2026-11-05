"""Scientific contracts for the heteroscedastic equal-fold inference path."""
import numpy as np
import unittest
from scipy.stats import ttest_ind

from src.fairness.robust_inference import group_contrast, paired_contrast, adjust_holm


def test_matches_welch_when_five_folds_have_same_samples():
    a = np.array([2., 3., 7., 9.])
    b = np.array([1., 4., 5., 11., 15., 19.])
    values = np.tile(np.r_[a, b], 5)
    labels = np.tile(['White']*len(a)+['Hispanic']*len(b), 5)
    folds = np.repeat(np.arange(5), len(a)+len(b))
    row = group_contrast(values, labels, folds)
    expected = ttest_ind(a, b, equal_var=False)
    np.testing.assert_allclose(row['diff_pp'], a.mean()-b.mean())
    np.testing.assert_allclose(row['standard_error_pp'], np.sqrt((a.var(ddof=1)/len(a)+b.var(ddof=1)/len(b))/5))
    np.testing.assert_allclose(row['degrees_of_freedom'], expected.df*5)


def test_weak_null_with_opposite_fold_differences():
    folds = np.repeat(np.arange(5), 8)
    labels = np.tile(['White']*4+['Hispanic']*4, 5)
    values = np.tile([-.3, -.1, .1, .3]*2, 5)
    for f, effect in enumerate([-8., -4., 0., 4., 8.]):
        values[(folds == f)&(labels == 'White')] += effect/2
        values[(folds == f)&(labels == 'Hispanic')] -= effect/2
    row = group_contrast(values, labels, folds)
    np.testing.assert_allclose(row['diff_pp'], 0., atol=1e-12)
    np.testing.assert_allclose(row['p'], 1.)
    assert row['ci95'][0] < 0 < row['ci95'][1]


def test_paired_participant_differences_and_shift_invariance():
    folds = np.repeat(np.arange(5), 9)
    values = np.tile(np.arange(9.), 5)
    a = paired_contrast(values, folds)
    b = paired_contrast(values+3, folds)
    np.testing.assert_allclose(b['diff_pp']-a['diff_pp'], 3)
    np.testing.assert_allclose(b['standard_error_pp'], a['standard_error_pp'])
    np.testing.assert_allclose(b['degrees_of_freedom'], 40)


def test_zero_variance_withheld_and_family_size_preserved():
    row = paired_contrast(np.ones(15), np.repeat(np.arange(5), 3))
    assert row['p'] is None and row['ci95'] is None
    rows = [dict(p=.02), row]
    adjust_holm(rows)
    np.testing.assert_allclose(rows[0]['holm_p'], .04)
    assert row['passes_correction'] is None


def test_invalid_inputs_fail():
    for values,folds in [([1., float('nan')], [0, 1]), ([1., 2.], [0, 5]), ([1., 2.], [0])]:
        try:
            paired_contrast(values, folds)
        except ValueError:
            continue
        raise AssertionError('Invalid input accepted')


def load_tests(loader, tests, pattern):
    return unittest.TestSuite(unittest.FunctionTestCase(v) for k,v in globals().items() if k.startswith('test_'))


if __name__ == '__main__':
    unittest.main()
