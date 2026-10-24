"""Easy updates (Phase 45): python -m unittest tests.test_updates -v.

The check and the API use a stand-in for GitHub. The updater tests run the real installer/Update-Beyond.ps1 on a
small fake BEYOND folder, with fake releases served from this PC; they need Windows PowerShell."""
import hashlib
import http.server
import io
import json
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

import httpx

from app import config, settings, updates

ROOT = Path(__file__).resolve().parent.parent
REAL_CLIENT = httpx.Client


def fake_github(version='1.1.0', notes='New things', status=200, updater=b'# updater', sums=None):
    """A stand-in for GitHub: the VERSION file, the release API and the release files."""
    def handler(request):
        url = str(request.url)
        if url == updates.VERSION_URL:
            return httpx.Response(status, text=version + '\n')
        if url.startswith('https://api.github.com/'):
            return httpx.Response(200, json={'body': notes, 'assets': []})
        if url.endswith('/SHA256SUMS.txt'):
            digest = sums if sums is not None else hashlib.sha256(updater).hexdigest()
            return httpx.Response(200, text=f'{digest}  Update-Beyond.ps1\n')
        if url.endswith('/Update-Beyond.ps1'):
            return httpx.Response(200, content=updater)
        return httpx.Response(404)
    return patch.object(updates.httpx, 'Client',
                        lambda **kwargs: REAL_CLIENT(transport=httpx.MockTransport(handler), **kwargs))


def offline():
    def handler(request):
        raise httpx.ConnectError('offline', request=request)
    return patch.object(updates.httpx, 'Client',
                        lambda **kwargs: REAL_CLIENT(transport=httpx.MockTransport(handler), **kwargs))


class TempData(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.saved = config.DATA_DIR, settings.FILE, config.VERSION
        config.DATA_DIR = Path(self.temp.name)
        settings.FILE = config.DATA_DIR / 'settings.json'
        config.VERSION = '1.0.1'
        self.not_git = patch.object(updates, 'is_git_checkout', return_value=False)
        self.not_git.start()

    def tearDown(self):
        self.not_git.stop()
        config.DATA_DIR, settings.FILE, config.VERSION = self.saved
        self.temp.cleanup()


class CheckTests(TempData):
    def test_version_numbers_compare_as_numbers(self):
        self.assertTrue(updates.is_newer('1.10.0', '1.9.0'))
        self.assertTrue(updates.is_newer('v1.1.0', '1.0.1'))
        self.assertFalse(updates.is_newer('1.0.1', '1.0.1'))
        self.assertFalse(updates.is_newer('1.0.0', '1.0.1'))   # a newer copy (like main) is never "downgraded"
        for bad in ('1.1', 'abc', '1.1.0-beta', '', '1.1.0\nrm'):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                updates.parse_version(bad)

    def test_a_newer_version_is_offered_with_its_notes(self):
        with fake_github('1.1.0', notes='## What is new\n- Updates'):
            result = updates.check()
        self.assertTrue(result['available'])
        self.assertEqual((result['latest'], result['installed'], result['error']), ('1.1.0', '1.0.1', ''))
        self.assertIn('What is new', result['notes'])
        self.assertTrue(result['notes_url'].endswith('/releases/tag/v1.1.0'))
        config.VERSION = '1.1.0'   # after updating, the same saved result no longer offers it
        self.assertFalse(updates.status()['available'])

    def test_same_or_older_is_up_to_date(self):
        for published in ('1.0.1', '1.0.0'):
            with self.subTest(published=published), fake_github(published):
                result = updates.check()
                self.assertFalse(result['available'])
                self.assertEqual(result['error'], '')

    def test_failures_are_recorded_not_raised(self):
        with offline():
            result = updates.check()
        self.assertFalse(result['available'])
        self.assertIn("Couldn't reach GitHub", result['error'])
        with fake_github('<html>oops</html>'):
            self.assertIn("couldn't be read", updates.check()['error'])
        with fake_github(status=500):
            self.assertIn("Couldn't reach GitHub", updates.check()['error'])

    def test_automatic_checks_are_off_by_default_and_daily_when_on(self):
        self.assertFalse(config.DEFAULTS['update_auto_check'])
        self.assertFalse(updates.due())
        settings.save({'update_auto_check': True})
        self.assertTrue(updates.due())
        with fake_github('1.0.1'):
            updates.check()
        self.assertFalse(updates.due())
        with patch.object(updates.time, 'time', return_value=time.time() + updates.CHECK_EVERY_SECONDS + 1):
            self.assertTrue(updates.due())

    def test_each_version_is_announced_once(self):
        with fake_github('1.1.0'):
            updates.check()
        self.assertEqual(updates.needs_announcing(), '1.1.0')
        updates.mark_announced('1.1.0')
        self.assertEqual(updates.needs_announcing(), '')
        with fake_github('1.2.0'):
            updates.check()
        self.assertEqual(updates.needs_announcing(), '1.2.0')

    def test_the_updater_must_match_the_release_checksum(self):
        with fake_github('1.1.0', updater=b'# good'):
            script = updates.fetch_updater('1.1.0')
        self.assertEqual(script.read_bytes(), b'# good')
        with fake_github('1.1.0', updater=b'# tampered', sums='0' * 64), self.assertRaises(updates.UpdateError):
            updates.fetch_updater('1.1.0')
        self.assertFalse(script.exists())   # a file that failed the check is deleted

    def test_starting_an_update_runs_the_updater_then_closes_beyond(self):
        closed = []
        with fake_github('1.1.0'):
            updates.check()
            with patch.object(updates.subprocess, 'Popen') as popen, \
                    patch.object(updates.sys, 'platform', 'win32'), \
                    patch.object(updates, 'request_quit', lambda: closed.append(True)):
                updates.start('1.1.0', 7770)
        command = popen.call_args.args[0]
        self.assertEqual(command[:6], ['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
                                       str(config.DATA_DIR / 'updates' / 'updater-1.1.0' / 'Update-Beyond.ps1')])
        self.assertIn('-WaitPid', command)
        self.assertEqual(closed, [True])
        updates._installing.clear()

    def test_git_copies_and_stale_versions_are_refused(self):
        with fake_github('1.1.0'):
            updates.check()
        with self.assertRaisesRegex(updates.UpdateError, 'no longer available'):
            updates.start('1.2.0', 7770)
        with patch.object(updates, 'is_git_checkout', return_value=True), \
                self.assertRaisesRegex(updates.UpdateError, 'git pull'):
            updates.start('1.1.0', 7770)


class ApiTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        from app.server import app
        cls.app = app

    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.saved = config.DATA_DIR, settings.FILE, config.VERSION
        config.DATA_DIR = Path(self.temp.name)
        settings.FILE = config.DATA_DIR / 'settings.json'
        config.VERSION = '1.0.1'
        settings.save({'require_sign_in': False})
        self.pc, self.phone = self.client('127.0.0.1'), self.client('192.168.1.50')

    async def asyncTearDown(self):
        await self.pc.aclose()
        await self.phone.aclose()
        config.DATA_DIR, settings.FILE, config.VERSION = self.saved
        self.temp.cleanup()

    def client(self, address):
        return httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app, client=(address, 50000)),
                                 base_url='http://beyond.test')

    async def test_only_this_pc_or_an_administrator_sees_and_starts_updates(self):
        with fake_github('1.1.0'):
            checked = (await self.pc.post('/api/updates/check')).json()
            self.assertTrue(checked['allowed'] and checked['available'])
            self.assertEqual((await self.phone.get('/api/updates')).json(), {'allowed': False, 'available': False})
            self.assertEqual((await self.phone.post('/api/updates/check')).status_code, 403)
            self.assertEqual((await self.phone.post('/api/updates/install', json={'version': '1.1.0'})).status_code, 403)
        self.assertEqual(updates.needs_announcing(), '')   # seen in Settings already: no popup later

    async def test_install_needs_beyond_py_and_a_real_version(self):
        reply = await self.pc.post('/api/updates/install', json={'version': '1.1.0'})
        self.assertEqual(reply.status_code, 409)   # tests don't run under beyond.py, so BEYOND can't close itself
        self.assertEqual((await self.pc.post('/api/updates/install', json={'version': 'x'})).status_code, 422)


# ---------- the real updater, on a fake BEYOND folder ----------

def release_zip(version, files):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w') as archive:
        names = sorted(files) + ['app-files.txt']
        for name, text in files.items():
            archive.writestr(f'BEYOND-{version}/{name}', text)
        archive.writestr(f'BEYOND-{version}/app-files.txt', '\n'.join(names) + '\n')
    return buffer.getvalue()


def program(version, extra):
    return {'beyond.py': 'print("BEYOND")\n', 'app/config.py': f"VERSION = '{version}'\n",
            'requirements-text-lock.txt': 'httpx==0.28.1\n', **extra}


class Releases:
    """Serves fake releases at http://127.0.0.1:<port>/v<version>/<file>, like GitHub's download URLs."""

    def __init__(self, root):
        self.root = root
        handler = lambda *args: http.server.SimpleHTTPRequestHandler(*args, directory=str(root))
        handler_class = type('Quiet', (http.server.SimpleHTTPRequestHandler,),
                             {'log_message': lambda *args: None})
        self.server = http.server.ThreadingHTTPServer(
            ('127.0.0.1', 0), lambda *args: handler_class(*args, directory=str(root)))
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.base = f'http://127.0.0.1:{self.server.server_address[1]}'

    def publish(self, version, files, unsafe=False):
        folder = self.root / f'v{version}'
        folder.mkdir(parents=True, exist_ok=True)
        data = release_zip(version, files)
        if unsafe:
            buffer = io.BytesIO(data)
            with zipfile.ZipFile(buffer, 'a') as archive:
                archive.writestr(f'BEYOND-{version}/../evil.txt', 'nope')
            data = buffer.getvalue()
        name = f'BEYOND-{version}-source.zip'
        (folder / name).write_bytes(data)
        (folder / 'SHA256SUMS.txt').write_text(f'{hashlib.sha256(data).hexdigest()}  {name}\n')

    def close(self):
        self.server.shutdown()


@unittest.skipUnless(sys.platform == 'win32' and shutil.which('powershell.exe'), 'needs Windows PowerShell')
class UpdaterTests(unittest.TestCase):
    OLD = program('1.0.0', {'app/old_only.py': 'old\n', 'app/shared.py': 'v1\n'})
    NEW = program('1.1.0', {'app/new_only.py': 'new\n', 'app/shared.py': 'v2\n'})

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        base = Path(self.temp.name)
        self.beyond = base / 'My BEYOND'   # a space in the path, like many real folders
        for name, text in self.OLD.items():
            (self.beyond / name).parent.mkdir(parents=True, exist_ok=True)
            (self.beyond / name).write_bytes(text.encode())   # the same bytes as in the release ZIP
        (self.beyond / '.venv/Scripts').mkdir(parents=True)
        (self.beyond / '.venv/Scripts/python.exe').write_text('')
        for name in ('data/beyond.sqlite3', 'models/chat.gguf', 'files/notes.txt'):
            (self.beyond / name).parent.mkdir(parents=True, exist_ok=True)
            (self.beyond / name).write_text('mine')
        self.releases = Releases(base / 'releases')
        self.releases.publish('1.0.0', self.OLD)
        self.releases.publish('1.1.0', self.NEW)

    def tearDown(self):
        self.releases.close()
        self.temp.cleanup()

    def run_updater(self, fail_at=''):
        env = {**__import__('os').environ, 'BEYOND_UPDATE_FAIL_AT': fail_at}
        return subprocess.run(
            ['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
             str(ROOT / 'installer' / 'Update-Beyond.ps1'), '-InstallDir', str(self.beyond), '-Version', '1.1.0',
             '-DownloadBase', self.releases.base, '-Port', '7799', '-NoStart', '-NoPause', '-Yes'],
            capture_output=True, text=True, timeout=300, env=env)

    def files(self):
        return {str(p.relative_to(self.beyond)).replace('\\', '/'): p.read_text()
                for p in self.beyond.rglob('*') if p.is_file() and 'data' not in p.relative_to(self.beyond).parts[:1]}

    def result(self):
        return json.loads((self.beyond / 'data/updates/last-update.json').read_text(encoding='utf-8-sig'))

    def assert_user_files_kept(self):
        for name in ('data/beyond.sqlite3', 'models/chat.gguf', 'files/notes.txt'):
            self.assertEqual((self.beyond / name).read_text(), 'mine', name)

    def test_updates_the_program_files_and_keeps_everything_else(self):
        run = self.run_updater()
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        files = self.files()
        self.assertEqual(files['app/config.py'], "VERSION = '1.1.0'\n")
        self.assertEqual(files['app/shared.py'], 'v2\n')
        self.assertIn('app/new_only.py', files)
        self.assertNotIn('app/old_only.py', files)   # 1.0.0's list came from its own release ZIP
        self.assert_user_files_kept()
        self.assertTrue(self.result()['ok'])
        installed = (self.beyond / 'data/updates/installed-files.txt').read_text(encoding='utf-8').split()
        self.assertIn('app/new_only.py', installed)
        self.assertFalse((self.beyond / 'data/updates/staging-1.1.0').exists())

    def test_a_failed_step_puts_the_old_version_back(self):
        before = self.files()
        run = self.run_updater(fail_at='swap')
        self.assertEqual(run.returncode, 1, run.stdout + run.stderr)
        self.assertEqual(self.files(), before)
        self.assert_user_files_kept()
        self.assertEqual((self.result()['ok'], self.result()['to']), (False, '1.1.0'))
        self.assertIn('Test failure', self.result()['message'])

    def test_a_failing_library_install_puts_the_old_version_back(self):
        # The new version needs other libraries; the fake .venv's python.exe can't run pip, so that step fails.
        self.releases.publish('1.1.0', {**self.NEW, 'requirements-text-lock.txt': 'httpx==0.28.2\n'})
        before = self.files()
        run = self.run_updater()
        self.assertEqual(run.returncode, 1, run.stdout + run.stderr)
        self.assertIn('[7/8] Updating the libraries', run.stdout)
        self.assertEqual(self.files(), before)
        self.assertFalse(self.result()['ok'])

    def test_already_up_to_date_and_git_copies_change_nothing(self):
        (self.beyond / 'app/config.py').write_text("VERSION = '1.1.0'\n")
        self.assertEqual(self.run_updater().returncode, 0)
        self.assertIn('app/old_only.py', self.files())
        (self.beyond / 'app/config.py').write_text("VERSION = '1.0.0'\n")
        (self.beyond / '.git').mkdir()
        run = self.run_updater()
        self.assertEqual(run.returncode, 2)
        self.assertIn('git pull', run.stdout)
        self.assertEqual(self.files()['app/config.py'], "VERSION = '1.0.0'\n")

    def test_a_damaged_or_unsafe_download_is_refused(self):
        zip_path = self.releases.root / 'v1.1.0' / 'BEYOND-1.1.0-source.zip'
        zip_path.write_bytes(zip_path.read_bytes() + b'damaged')
        run = self.run_updater()
        self.assertEqual(run.returncode, 1)
        self.assertIn("didn't match the release's checksum", run.stdout)
        self.releases.publish('1.1.0', self.NEW, unsafe=True)
        run = self.run_updater()
        self.assertEqual(run.returncode, 1)
        self.assertIn('unsafe file path', run.stdout)
        self.assertEqual(self.files()['app/config.py'], "VERSION = '1.0.0'\n")
        self.assertFalse((self.beyond.parent / 'evil.txt').exists())


class ReleaseToolTests(unittest.TestCase):
    def test_builds_every_release_file_with_matching_checksums(self):
        committed = subprocess.run(['git', 'cat-file', '-e', 'HEAD:installer/Update-Beyond.ps1'], cwd=ROOT,
                                   capture_output=True)
        if committed.returncode:
            self.skipTest('the updater is not committed yet (releases are built from committed files)')
        sys.path.insert(0, str(ROOT / 'tools'))
        import make_release
        version = make_release.committed_version()
        with tempfile.TemporaryDirectory() as out:
            artifact = make_release.build(version, Path(out))
            out = Path(out)
            names = {path.name for path in out.iterdir()}
            self.assertEqual(names, {f'BEYOND-{version}-source.zip', 'Update-Beyond.ps1', 'Update-Beyond.cmd',
                                     'SHA256SUMS.txt', 'artifact.json'})
            for line in (out / 'SHA256SUMS.txt').read_text().splitlines():
                digest, name = line.split()
                self.assertEqual(hashlib.sha256((out / name).read_bytes()).hexdigest(), digest, name)
            with zipfile.ZipFile(out / artifact['artifact']) as archive:
                prefix = f'BEYOND-{version}/'
                self.assertTrue(all(name.startswith(prefix) for name in archive.namelist()))
                self.assertEqual(archive.read(prefix + 'VERSION').decode().strip(), version)
                listed = archive.read(prefix + 'app-files.txt').decode().split()
                self.assertIn('app/updates.py', listed)
                self.assertFalse([name for name in listed if name.split('/')[0] in ('data', 'models', 'files', '.venv')])


if __name__ == '__main__':
    unittest.main()
