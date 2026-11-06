"""Check report content, preserved decisions, and safe CLI output behavior."""
import copy
import csv
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from reportlab.platypus import KeepTogether, LongTable, Paragraph
from scripts.render_audit_report import EffectChart, RateChart, _interpret_results, _main_findings, write_pdf_report

ROOT = Path(__file__).resolve().parents[1]


class ReadableReportTests(unittest.TestCase):
    def setUp(self):
        self.sample = json.loads((ROOT / 'examples/ROBUST_AUDIT_SYNTHETIC_REPORT.json').read_text(encoding='utf8'))

    def test_results_and_withheld_decision_are_preserved(self):
        original = copy.deepcopy(self.sample)
        captured = []
        with tempfile.TemporaryDirectory() as folder, patch('scripts.render_audit_report.SimpleDocTemplate.build') as build:
            write_pdf_report(self.sample, Path(folder) / 'out.pdf')
            story = build.call_args.args[0]
            for item in story:
                if isinstance(item, Paragraph):
                    captured.append(item.getPlainText())
                elif isinstance(item, LongTable):
                    captured.extend(cell.getPlainText() for row in item._cellvalues for cell in row if isinstance(cell, Paragraph))
                elif isinstance(item, KeepTogether):
                    captured.extend(child.getPlainText() for child in item._content if isinstance(child, Paragraph))
        text = '\n'.join(captured)
        self.assertIn('[-0.5330, 0.5330]', text)
        self.assertIn('Withheld', text)
        self.assertIn('Not passed', text)
        self.assertIn('0 passed, 1 did not pass, 1 withheld; 2 total', text)
        self.assertNotIn('Synthetic example', text)
        self.assertNotIn('Mechanism comparisons', text)
        self.assertNotIn('Utility comparisons', text)
        self.assertEqual(self.sample, original)

    def test_uncalibrated_decisions_not_converted_to_negative(self):
        report = copy.deepcopy(self.sample)
        report['formal_decisions_enabled'] = False
        report['calibration_status'] = 'independent_calibration_missing'
        for row in report['secondary_tests']:
            row['passes_correction'] = None
        with tempfile.TemporaryDirectory() as folder, patch('scripts.render_audit_report.SimpleDocTemplate.build') as build:
            write_pdf_report(report, Path(folder) / 'out.pdf')
            text = '\n'.join(item.getPlainText() for item in build.call_args.args[0] if isinstance(item, Paragraph))
        self.assertIn('Formal decisions enabled: No', text)
        self.assertIn('0 passed, 0 did not pass, 2 withheld; 2 total', text)

    def test_overview_chart_uses_saved_rates_without_changing_results(self):
        original = copy.deepcopy(self.sample)
        with tempfile.TemporaryDirectory() as folder, patch('scripts.render_audit_report.SimpleDocTemplate.build') as build:
            write_pdf_report(self.sample, Path(folder) / 'out.pdf')
            charts = [item for item in build.call_args.args[0] if isinstance(item, RateChart)]
            self.assertTrue(charts)
            self.assertEqual([row for chart in charts for row in chart.rows], self.sample['condition_results'])
        self.assertEqual(self.sample, original)

    def test_interpretation_separates_baseline_and_unavailable_decisions(self):
        text = '\n'.join(_interpret_results(self.sample, 'en'))
        self.assertIn('does not separately test the baseline gap', text)
        self.assertIn('Change in gap from baseline', text)
        self.assertIn('formal decision withheld', text)
        self.assertIn('alpha 0.0500', text)

    def test_main_findings_are_two_sentences_and_respect_withholding(self):
        original = copy.deepcopy(self.sample)
        self.assertEqual(len(_main_findings(self.sample, 'zh')), 2)
        report = copy.deepcopy(self.sample)
        report['formal_decisions_enabled'] = False
        self.assertIn('withheld', _main_findings(report, 'en')[1])
        self.assertEqual(self.sample, original)

    def test_effect_plots_preserve_intervals_and_highlight_conclusions(self):
        with tempfile.TemporaryDirectory() as folder, patch('scripts.render_audit_report.SimpleDocTemplate.build') as build:
            write_pdf_report(self.sample, Path(folder) / 'out.pdf')
            story = build.call_args.args[0]
            plots = [child for item in story if isinstance(item, KeepTogether)
                     for child in item._content if isinstance(child, EffectChart)]
            self.assertEqual([p.interval for p in plots], [t.get('ci95') for t in self.sample['secondary_tests']])
            conclusions = [p for p in story if isinstance(p, Paragraph) and p.style.name == 'conclusion']
            self.assertTrue(conclusions)
            self.assertTrue(any('formal decision withheld' in p.getPlainText() for p in conclusions))

    def test_cli_creates_pdf_json_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / 'audit'
            command = [sys.executable, '-m', 'scripts.run_robust_privacy_audit', '--scores',
                       'examples/privacy_pipeline_scores.csv', '--plan', 'configs/privacy_pipeline_blocked_example.json',
                       '--output', str(output)]
            completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            report = json.loads((output / 'report.json').read_text(encoding='utf8'))
            self.assertEqual(report['family_sizes'], [0, 2, 0])
            self.assertTrue((output / 'report.pdf').read_bytes().startswith(b'%PDF-'))
            again = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
            self.assertNotEqual(again.returncode, 0)
            self.assertIn('Preserve previous results', again.stderr)

    def test_font_failure_keeps_json_and_reports_error(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / 'audit'
            command = [sys.executable, '-m', 'scripts.run_robust_privacy_audit', '--scores',
                       'examples/privacy_pipeline_scores.csv', '--plan', 'configs/privacy_pipeline_blocked_example.json',
                       '--output', str(output), '--report-font', str(Path(folder) / 'missing.ttf')]
            completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn('No suitable TrueType font', completed.stderr)
            self.assertTrue((output / 'report.json').is_file())
            self.assertFalse((output / 'report.pdf').exists())

    def test_existing_json_can_be_rendered_without_overwriting(self):
        source = ROOT / 'examples/ROBUST_AUDIT_SYNTHETIC_REPORT.json'
        before = source.read_bytes()
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / 'report.pdf'
            command = [sys.executable, '-m', 'scripts.render_audit_report', '--input', str(source), '--output', str(output)]
            completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            original_pdf = output.read_bytes()
            self.assertTrue(original_pdf.startswith(b'%PDF-'))
            again = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
            self.assertNotEqual(again.returncode, 0)
            self.assertIn('Preserve existing reports', again.stderr)
            self.assertEqual(output.read_bytes(), original_pdf)
        self.assertEqual(source.read_bytes(), before)

    def test_illustrative_generator_is_reproducible_and_safe(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / 'inputs'
            command = [sys.executable, 'examples/generate_illustrative_scores.py', '--output', str(output)]
            completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            source = output / 'synthetic_scores.csv'
            with source.open(encoding='utf8', newline='') as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(len(rows), 200 * 3 * 3)
            self.assertEqual(len({row['subject_id'] for row in rows}), 200)
            self.assertEqual({row['fold'] for row in rows}, {'0', '1', '2', '3', '4'})
            self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(),
                             '34d1769100c8015052ba2843526a0d2b2c3a23d42af1a5d24685638c36c0305f')
            self.assertIn('Synthetic', json.loads((output / 'plan.json').read_text(encoding='utf8'))['scope'])
            again = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
            self.assertNotEqual(again.returncode, 0)
            self.assertIn('Preserve previous inputs', again.stderr)


if __name__ == '__main__':
    unittest.main()
