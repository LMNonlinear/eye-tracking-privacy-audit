"""Verify bounded summaries, preservation of results and dual-report entry points."""
import copy
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from scripts.render_audit_summary import (
    _chart_panels, summarize_results, summary_findings, write_report_bundle,
    write_summary_report,
)

ROOT = Path(__file__).resolve().parents[1]


class ReportBundleTests(unittest.TestCase):
    def setUp(self):
        self.sample = json.loads((ROOT / 'examples/ROBUST_AUDIT_SYNTHETIC_REPORT.json').read_text())

    def test_summary_preserves_controls_reversals_and_withheld_decisions(self):
        result = copy.deepcopy(self.sample)
        result['plan']['controls'] = ['control']
        base, protected = result['condition_results'][:2]
        base['signed_gap_pp'] = -2
        protected['signed_gap_pp'] = 1
        control = dict(protected, condition='control', signed_gap_pp=90)
        result['condition_results'].append(control)
        before = copy.deepcopy(result)
        summary = summarize_results(result)
        self.assertEqual(summary['changes'], dict(larger=0, smaller=1, equal=0))
        self.assertEqual(summary['protected'], [1.0])
        self.assertEqual(sum(x['withheld'] for x in summary['decisions']), 1)
        self.assertIn('group B had higher', summary_findings(summary, result)[0])
        self.assertEqual(result, before)

    @unittest.skipUnless(shutil.which('pdfinfo'), 'Poppler is required to verify rendered page counts')
    def test_two_pages_for_large_plan_and_all_ranges_retained(self):
        result = copy.deepcopy(self.sample)
        original = result['condition_results']
        result['condition_results'] = []
        for i in range(40):
            for row in original:
                result['condition_results'].append(dict(row, dataset=f'dataset_{i}',
                    evaluator='model_' + 'x' * 200, signed_gap_pp=float(i)))
        before = copy.deepcopy(result)
        summary = summarize_results(result)
        panels = _chart_panels(summary)
        self.assertEqual(len(panels), 5)
        self.assertEqual(max(panels[-1][1]['protected']), 39)
        self.assertEqual(len(summary['protected']), 40)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'summary.pdf'
            write_summary_report(result, path)
            info = subprocess.check_output(['pdfinfo', str(path)], text=True)
            self.assertRegex(info, r'Pages:\s+2\b')
        self.assertEqual(result, before)

    def test_render_existing_json_creates_two_pdfs_and_preserves_input(self):
        source = ROOT / 'examples/ROBUST_AUDIT_SYNTHETIC_REPORT.json'
        before = source.read_bytes()
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / 'reports'
            command = [sys.executable, '-m', 'scripts.render_audit_report', '--input', str(source),
                       '--output-dir', str(output)]
            done = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(done.returncode, 0, done.stderr)
            self.assertEqual({p.name for p in output.iterdir()}, {'report_summary.pdf', 'report_detailed.pdf'})
            preserved = {p.name: p.read_bytes() for p in output.iterdir()}
            again = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
            self.assertNotEqual(again.returncode, 0)
            self.assertEqual(preserved, {p.name: p.read_bytes() for p in output.iterdir()})
        self.assertEqual(source.read_bytes(), before)

    def test_failed_render_does_not_publish_partial_pdfs(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(ValueError, 'No suitable TrueType font'):
                write_report_bundle(self.sample, folder, report_font=str(Path(folder) / 'missing.ttf'))
            self.assertEqual(list(Path(folder).glob('*.pdf')), [])

    def test_withheld_summary_never_claims_supported_decisions(self):
        result = copy.deepcopy(self.sample)
        result['formal_decisions_enabled'] = False
        for row in result['secondary_tests']:
            row['passes_correction'] = None
        summary = summarize_results(result)
        self.assertEqual(sum(x['passed'] for x in summary['decisions']), 0)
        self.assertEqual(sum(x['withheld'] for x in summary['decisions']), 2)


if __name__ == '__main__':
    unittest.main()
