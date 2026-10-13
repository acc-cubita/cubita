"""No database or installed services: exercise the frozen entry-point bootstrap."""
import importlib.util
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch


def entry():
    path = Path(__file__).resolve().parents[1] / 'packaging/server_entry.py'
    spec = importlib.util.spec_from_file_location('libpq_entry_probe', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class LegacyLibpqRuntimeTests(unittest.TestCase):
    def test_legacy_prepends_absolute_directory_and_keeps_cookie(self):
        module = entry()
        with TemporaryDirectory(prefix='Cubita DLL path ') as root:
            pg = Path(root) / 'pgsql/bin'
            pg.mkdir(parents=True)
            (pg / 'libpq.dll').write_bytes(b'fixture only')
            cookie = object()
            with patch.object(module, '_bundle_dir', return_value=Path(root)), \
                 patch.object(module.sys, 'frozen', True, create=True), \
                 patch.object(module.sys, 'platform', 'win32'), \
                 patch.object(module.sys, 'version_info', (3, 8, 10)), \
                 patch.dict(os.environ, {'PATH': 'system-only'}), \
                 patch.object(module.os, 'add_dll_directory', return_value=cookie, create=True) as add:
                module._prepare_legacy_libpq()
                module._prepare_legacy_libpq()
                self.assertEqual(os.environ['PATH'].split(os.pathsep), [str(pg), 'system-only'])
                self.assertEqual(module._dll_directories, [cookie])
                add.assert_called_once_with(str(pg))

    def test_missing_bundled_dll_fails_before_database_work(self):
        module = entry()
        with TemporaryDirectory() as root, \
             patch.object(module, '_bundle_dir', return_value=Path(root)), \
             patch.object(module.sys, 'frozen', True, create=True), \
             patch.object(module.sys, 'platform', 'win32'), \
             patch.object(module.sys, 'version_info', (3, 8, 10)), \
             patch.dict(os.environ, {'PATH': 'system-only'}):
            with self.assertRaises(SystemExit):
                module._prepare_legacy_libpq()
            self.assertEqual(os.environ['PATH'], 'system-only')

    def test_modern_and_source_runs_are_unchanged(self):
        for frozen, version in ((False, (3, 8)), (True, (3, 12))):
            module = entry()
            with patch.object(module.sys, 'frozen', frozen, create=True), \
                 patch.object(module.sys, 'platform', 'win32'), \
                 patch.object(module.sys, 'version_info', version), \
                 patch.dict(os.environ, {'PATH': 'unchanged'}):
                module._prepare_legacy_libpq()
                self.assertEqual(os.environ['PATH'], 'unchanged')


if __name__ == '__main__':
    unittest.main()
