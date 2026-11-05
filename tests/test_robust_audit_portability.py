"""The calibration identity gate tolerates only Git's line-ending conversion."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import run_robust_privacy_audit as audit


class CalibrationIdentityTests(unittest.TestCase):
    def test_source_identity_and_line_endings(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / 'src/fairness/robust_inference.py'
            source.parent.mkdir(parents=True)
            calibrated = b'value = 1\r\nother = 2\r\n'
            record = root / 'calibration.json'
            record.write_text(json.dumps({
                'status': 'complete', 'calibration_passed': True,
                'source_sha256': {'src/fairness/robust_inference.py': hashlib.sha256(calibrated).hexdigest()},
            }), encoding='utf8')
            with patch.object(audit, 'ROOT', root):
                source.write_bytes(calibrated)
                self.assertTrue(audit.calibration_status(record)[0])
                source.write_bytes(calibrated.replace(b'\r\n', b'\n'))
                self.assertTrue(audit.calibration_status(record)[0])
                source.write_bytes(b'value = 9\nother = 2\n')
                self.assertFalse(audit.calibration_status(record)[0])
                source.write_bytes(b'value = 1\r\nother = 2\n')
                self.assertFalse(audit.calibration_status(record)[0])
                lf = calibrated.replace(b'\r\n', b'\n')
                record.write_text(json.dumps({
                    'status': 'complete', 'calibration_passed': True,
                    'source_sha256': {'src/fairness/robust_inference.py': hashlib.sha256(lf).hexdigest()},
                }), encoding='utf8')
                source.write_bytes(calibrated)
                self.assertTrue(audit.calibration_status(record)[0])
                self.assertFalse(audit.calibration_status(root / 'missing.json')[0])
                source.write_bytes(calibrated)
                record.write_text(json.dumps({'status': 'complete', 'calibration_passed': False}), encoding='utf8')
                self.assertFalse(audit.calibration_status(record)[0])


if __name__ == '__main__':
    unittest.main()
