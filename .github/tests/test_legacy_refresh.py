"""Failed source/boot checks must never replace a public legacy image."""
import importlib.util
import os
from pathlib import Path
import sys
import unittest
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


if __name__ == '__main__':
    unittest.main()
