"""Failed source/boot checks must never replace a public legacy image."""
import importlib.util
import os
from pathlib import Path
import sys
import unittest
import tempfile
import zipfile
import warnings
from unittest import mock

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location('refresh_legacy', SCRIPTS / 'refresh_legacy_arch.py')
refresh = importlib.util.module_from_spec(spec); spec.loader.exec_module(refresh)


class LegacyRefreshTests(unittest.TestCase):
    def source(self):
        producer = mock.Mock(base='/public-producer')
        producer.request.return_value = {'id': 1}
        producer.assets.return_value = {'alpine3.22.qcow2': {'state': 'uploaded'}}
        return producer

    def test_unavailable_producer_does_not_touch_previous_release(self):
        producer = self.source(); producer.assets.return_value = {}
        with mock.patch.dict(os.environ, GH_TOKEN='fixture'), mock.patch.object(refresh, 'Publisher', return_value=producer) as publisher, mock.patch.object(refresh.subprocess, 'run') as execute:
            with self.assertRaises(RuntimeError):
                refresh.refresh('alpine')
        self.assertEqual(publisher.call_count, 1)
        execute.assert_not_called()

    def test_failed_boot_validation_does_not_publish_or_read_previous_asset(self):
        producer = self.source()
        with mock.patch.dict(os.environ, GH_TOKEN='fixture'), mock.patch.object(refresh, 'Publisher', return_value=producer) as publisher, mock.patch.object(refresh, 'download'), mock.patch.object(refresh, 'validate_image', side_effect=RuntimeError('boot failed')), mock.patch.object(refresh.subprocess, 'run') as execute:
            with self.assertRaisesRegex(RuntimeError, 'boot failed'):
                refresh.refresh('alpine')
        self.assertEqual(publisher.call_count, 1)
        self.assertEqual(execute.call_count, 1)
        self.assertIn('root:password', execute.call_args.args[0][-2])
        self.assertNotIn('release_assets.py', ' '.join(execute.call_args.args[0]))

    def test_producer_zip_extraction_rejects_traversal_and_duplicate_disks(self):
        for names in [('disk.qcow2', '../outside'), ('disk.qcow2', 'disk.qcow2')]:
            with tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                path = root / 'source.zip'
                with warnings.catch_warnings(), zipfile.ZipFile(path, 'w') as archive:
                    warnings.simplefilter('ignore', UserWarning)
                    archive.writestr('incus.tar.xz', b'metadata')
                    for name in names:
                        archive.writestr(name, b'QFI\xfb')
                with self.assertRaisesRegex(ValueError, 'ambiguous'):
                    refresh.extract_disk(path, root / 'disk.qcow2', 'disk.qcow2')
                self.assertFalse((root / 'disk.qcow2').exists())

    def test_producer_zip_extracts_exact_qcow2_and_rejects_wrong_format(self):
        for header in [b'QFI\xfb', b'junk']:
            with tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                path = root / 'source.zip'
                data = header + b'\0' * (10 * 1024 * 1024)
                with zipfile.ZipFile(path, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
                    archive.writestr('incus.tar.xz', b'metadata')
                    archive.writestr('disk.qcow2', data)
                if header == b'junk':
                    with self.assertRaisesRegex(ValueError, 'not QCOW2'):
                        refresh.extract_disk(path, root / 'disk.qcow2', 'disk.qcow2')
                else:
                    refresh.extract_disk(path, root / 'disk.qcow2', 'disk.qcow2')
                    self.assertEqual((root / 'disk.qcow2').read_bytes(), data)


if __name__ == '__main__':
    unittest.main()
