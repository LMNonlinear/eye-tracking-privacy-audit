"""Check report content, preserved decisions, and safe CLI output behavior."""
import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from reportlab.platypus import LongTable, Paragraph
from scripts.render_audit_report import write_pdf_report

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
        text = '\n'.join(captured)
        self.assertIn('[-0.5330, 0.5330]', text)
        self.assertIn('Withheld', text)
        self.assertIn('Not passed', text)
        self.assertIn('0 passed, 1 did not pass, 1 withheld; 2 total', text)
        self.assertIn('Synthetic example', text)
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


if __name__ == '__main__':
    unittest.main()
