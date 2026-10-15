"""Failed source/boot checks must never replace a public legacy image."""
import importlib.util
import os
from pathlib import Path
import sys
import unittest
import tempfile
import zipfile
import warnings
import subprocess
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

    def test_fedora_ssh_repair_is_idempotent_and_failed_validation_never_publishes(self):
        for endpoint in ('fedora34', 'rockylinux8'):
            producer = self.source()
            producer.assets.return_value = {endpoint+'.qcow2': {'state': 'uploaded'}}
            with mock.patch.dict(os.environ, GH_TOKEN='fixture'), mock.patch.object(refresh, 'Publisher', return_value=producer) as publisher, mock.patch.object(refresh, 'download'), mock.patch.object(refresh, 'validate_image', side_effect=RuntimeError('boot failed')), mock.patch.object(refresh.subprocess, 'run') as execute:
                with self.assertRaisesRegex(RuntimeError, 'boot failed'):
                    refresh.refresh(endpoint)
            self.assertEqual(publisher.call_count, 1)
            self.assertEqual(execute.call_count, 2)
            self.assertNotIn('release_assets.py', ' '.join(execute.call_args.args[0]))
        command = execute.call_args.args[0][execute.call_args.args[0].index('--run-command') + 1]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            ssh = root / 'etc/ssh'
            snippets = ssh / 'sshd_config.d'
            snippets.mkdir(parents=True)
            (ssh / 'sshd_config').write_text('PubkeyAuthentication no\nPasswordAuthentication no\nPermitRootLogin no\nInclude /etc/ssh/sshd_config.d/*.conf\nPort 22\n')
            (snippets / 'vendor.conf').write_text('PasswordAuthentication no\n')
            binary = root / 'bin'
            binary.mkdir()
            (binary / 'systemctl').write_text('#!/bin/sh\n[ "$1 $2" = "enable sshd" ]\n')
            (binary / 'systemctl').chmod(0o755)
            environment = dict(os.environ, PATH=str(binary) + ':' + os.environ['PATH'])
            for _ in range(2):
                subprocess.run(['sh', '-c', command.replace('/etc/ssh', str(ssh))], env=environment, check=True, timeout=5)
            config = (ssh / 'sshd_config').read_text()
            self.assertTrue(config.startswith('PubkeyAuthentication yes\nPasswordAuthentication yes\nPermitRootLogin yes\n'))
            self.assertEqual(config.count('PubkeyAuthentication yes'), 1)
            self.assertIn('Port 22', config)
            self.assertNotIn('PasswordAuthentication no', (snippets / 'vendor.conf').read_text())

    def test_opensuse_missing_dhcp_repair_preserves_existing_config_and_failed_boot(self):
        producer = self.source()
        producer.assets.return_value = {'opensuse-leap-15.qcow2': {'state': 'uploaded'}}
        with mock.patch.dict(os.environ, GH_TOKEN='fixture'), mock.patch.object(refresh, 'Publisher', return_value=producer) as publisher, mock.patch.object(refresh, 'download'), mock.patch.object(refresh, 'validate_image', side_effect=RuntimeError('boot failed')), mock.patch.object(refresh.subprocess, 'run') as execute:
            with self.assertRaisesRegex(RuntimeError, 'boot failed'):
                refresh.refresh('opensuse15')
        self.assertEqual(publisher.call_count, 1)
        self.assertEqual(execute.call_count, 2)
        command = execute.call_args.args[0][execute.call_args.args[0].index('--run-command') + 1]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            network = root / 'network'
            network.mkdir()
            (network / 'ifcfg-ens18').write_text('BOOTPROTO=static\nIPADDR=192.0.2.1/24\n')
            binary = root / 'bin'
            binary.mkdir()
            wicked = binary / 'wicked'
            wicked.write_text('#!/bin/sh\nexit 0\n')
            wicked.chmod(0o755)
            (binary / 'systemctl').write_text('#!/bin/sh\nexit 0\n')
            (binary / 'systemctl').chmod(0o755)
            command = command.replace('/etc/sysconfig/network', str(network)).replace('/usr/sbin/wicked', str(wicked))
            environment = dict(os.environ, PATH=str(binary) + ':' + os.environ['PATH'])
            for _ in range(2):
                subprocess.run(['sh', '-c', command], env=environment, check=True, timeout=5)
            self.assertEqual((network / 'ifcfg-ens18').read_text(), 'BOOTPROTO=static\nIPADDR=192.0.2.1/24\n')
            for interface in ['eth0', 'ens3', 'enp1s0', 'enp5s0']:
                self.assertEqual((network / ('ifcfg-' + interface)).read_text(), 'BOOTPROTO=dhcp\nSTARTMODE=auto\nDHCLIENT_SET_DEFAULT_ROUTE=yes\n')

    def test_archived_recovery_disks_are_not_active_published_endpoints(self):
        import published_image_suite as suite
        publisher = mock.Mock(base='/fixture')
        publisher.request.return_value = [
            {'id': 1, 'draft': False, 'prerelease': False, 'tag_name': 'v2.0'},
            {'id': 2, 'draft': False, 'prerelease': False, 'tag_name': 'legacy-archived'},
        ]
        publisher.assets.return_value = {'debian12.qcow2': {'name': 'debian12.qcow2', 'state': 'uploaded', 'size': 1, 'updated_at': '2026-10-15'}}
        self.assertEqual(len(suite.published(publisher)), 1)
        publisher.assets.assert_called_once_with(1)

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
