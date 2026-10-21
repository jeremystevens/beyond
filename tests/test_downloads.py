"""Phase 35 (model downloads) checks: python -m unittest discover -s tests -v. A stand-in Hugging Face serves small
files from memory, so nothing is downloaded and no model is loaded."""
import hashlib
import json
import os
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx

from app import config, downloads, models, settings

DATA = os.urandom(3 * 1024 * 1024 + 12345)
SHA = hashlib.sha256(DATA).hexdigest()
PART_A, PART_B = DATA[:2_000_000], DATA[2_000_000:]


def wait(seconds=0.05):
    threading.Event().wait(seconds)


class SlowStream(httpx.SyncByteStream):
    """Hands out the body in small pieces, optionally failing part-way like a dropped connection."""

    def __init__(self, body, delay=0.0, fail_after=None):
        self.body, self.delay, self.fail_after = body, delay, fail_after

    def __iter__(self):
        sent = 0
        for start in range(0, len(self.body), 64 * 1024):
            if self.fail_after is not None and sent >= self.fail_after:
                raise httpx.ReadError('connection dropped')
            if self.delay:
                wait(self.delay)
            piece = self.body[start:start + 64 * 1024]
            sent += len(piece)
            yield piece


class FakeHub:
    def __init__(self):
        self.files = {'model-Q4_K_M.gguf': DATA, 'big-00001-of-00002.gguf': PART_A, 'big-00002-of-00002.gguf': PART_B}
        self.ranges, self.honour_range, self.delay, self.fail_once_after, self.gated = [], True, 0.0, None, False
        self.licence = 'apache-2.0'

    def __call__(self, request):
        path = request.url.path
        if path == '/api/models/someone/Model-GGUF':
            return httpx.Response(200, json={'gated': self.gated, 'cardData': {'license': self.licence}})
        if path == '/api/models/someone/Model-GGUF/tree/main':
            tree = [{'type': 'file', 'path': name, 'size': len(body),
                     'lfs': {'oid': hashlib.sha256(body).hexdigest(), 'size': len(body)}}
                    for name, body in self.files.items()]
            tree += [{'type': 'file', 'path': 'mmproj-f16.gguf', 'size': 10, 'lfs': {'oid': 'a' * 64, 'size': 10}},
                     {'type': 'file', 'path': 'README.md', 'size': 10}]
            return httpx.Response(200, json=tree)
        if path.startswith('/api/models/'):
            return httpx.Response(404, json={'error': 'not found'})
        name = path.rsplit('/', 1)[-1]
        body = self.files.get(name)
        if body is None:
            return httpx.Response(404)
        header = request.headers.get('Range')
        self.ranges.append(header)
        fail, self.fail_once_after = self.fail_once_after, None
        if header and self.honour_range:
            start = int(header.split('=')[1].rstrip('-'))
            return httpx.Response(206, stream=SlowStream(body[start:], self.delay, fail))
        return httpx.Response(200, stream=SlowStream(body, self.delay, fail))


class DownloadTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        folder = Path(self.temp.name)
        self.saved = config.DATA_DIR, config.MODELS_DIR, settings.FILE
        config.DATA_DIR, config.MODELS_DIR, settings.FILE = folder / 'data', folder / 'models', folder / 'settings.json'
        config.MODELS_DIR.mkdir()
        self.hub = FakeHub()
        self.client = patch.object(downloads, '_client',
                                   lambda **kw: httpx.Client(transport=httpx.MockTransport(self.hub), follow_redirects=True))
        self.client.start()
        downloads._jobs.clear()
        downloads._stop_requests.clear()

    def tearDown(self):
        downloads.shutdown()
        self.client.stop()
        downloads._jobs.clear()
        config.DATA_DIR, config.MODELS_DIR, settings.FILE = self.saved
        self.temp.cleanup()

    def until(self, job_id, *states, seconds=20):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            job = next((j for j in downloads._jobs if j['id'] == job_id), None)
            if job is None and 'gone' in states:
                return None
            if job and job['state'] in states:
                return job
            wait()
        self.fail(f'download never reached {states}')

    def target(self, name='model-Q4_K_M.gguf'):
        return downloads.folder_for('someone/Model-GGUF') / name

    def test_links_and_names(self):
        for text in ('someone/Model-GGUF', 'https://huggingface.co/someone/Model-GGUF',
                     'https://huggingface.co/someone/Model-GGUF/blob/main/model-Q4_K_M.gguf', 'hf.co/someone/Model-GGUF'):
            self.assertEqual(downloads.parse_repo(text), 'someone/Model-GGUF')
        for bad in ('', 'just-a-name', 'https://example.com/someone/model', '../etc/passwd', 'a/b/c d'):
            with self.subTest(bad=bad), self.assertRaises(downloads.DownloadError):
                downloads.parse_repo(bad)

    def test_browse_lists_models_and_groups_split_files(self):
        found = downloads.browse('someone/Model-GGUF')
        self.assertEqual([f['name'] for f in found['files']], ['model-Q4_K_M.gguf', 'big-00001-of-00002.gguf'])
        self.assertEqual(found['files'][1]['parts'], 2)
        self.assertFalse(found['accept'])                       # Apache 2.0 needs no extra acceptance
        self.hub.licence = 'llama3.2'
        self.assertTrue(downloads.browse('someone/Model-GGUF')['accept'])
        self.hub.gated = True
        self.assertTrue(downloads.browse('someone/Model-GGUF')['gated'])
        with self.assertRaises(downloads.DownloadError):
            downloads.browse('someone/Missing')

    def test_download_is_verified_and_appears_in_your_models(self):
        job = downloads.start_custom('someone/Model-GGUF', 'model-Q4_K_M.gguf')
        done = self.until(job['id'], 'done', 'failed')
        self.assertEqual(done['state'], 'done', done['error'])
        self.assertEqual(self.target().read_bytes(), DATA)
        self.assertFalse(self.target().with_name('model-Q4_K_M.gguf.part').exists())
        listed = {m['name']: m for m in models.catalogue()}
        self.assertIn('model-Q4_K_M.gguf', listed)
        self.assertEqual(downloads.view()['jobs'][0]['model_id'], listed['model-Q4_K_M.gguf']['id'])
        with self.assertRaises(downloads.DownloadError):        # already there
            downloads.start_custom('someone/Model-GGUF', 'model-Q4_K_M.gguf')

    def test_split_model_downloads_every_part(self):
        job = downloads.start_custom('someone/Model-GGUF', 'big-00001-of-00002.gguf')
        self.assertEqual(self.until(job['id'], 'done', 'failed')['state'], 'done')
        self.assertEqual(self.target('big-00001-of-00002.gguf').read_bytes() +
                         self.target('big-00002-of-00002.gguf').read_bytes(), DATA)
        self.assertEqual([m['parts'] for m in models.catalogue()], [2])

    def test_resumes_from_the_part_already_downloaded(self):
        self.target().parent.mkdir(parents=True)
        self.target().with_name('model-Q4_K_M.gguf.part').write_bytes(DATA[:1_000_000])
        job = downloads.start_custom('someone/Model-GGUF', 'model-Q4_K_M.gguf')
        self.assertEqual(job['received'], 1_000_000)
        self.assertEqual(self.until(job['id'], 'done', 'failed')['state'], 'done')
        self.assertEqual(self.hub.ranges, ['bytes=1000000-'])
        self.assertEqual(self.target().read_bytes(), DATA)

    def test_a_server_that_ignores_resume_still_gives_a_good_file(self):
        self.hub.honour_range = False
        self.target().parent.mkdir(parents=True)
        self.target().with_name('model-Q4_K_M.gguf.part').write_bytes(DATA[:500_000])
        job = downloads.start_custom('someone/Model-GGUF', 'model-Q4_K_M.gguf')
        self.assertEqual(self.until(job['id'], 'done', 'failed')['state'], 'done')
        self.assertEqual(self.target().read_bytes(), DATA)

    def test_a_dropped_connection_is_retried_from_where_it_stopped(self):
        self.hub.fail_once_after = 1_000_000
        with patch.object(downloads.time, 'sleep', lambda s: None):
            job = downloads.start_custom('someone/Model-GGUF', 'model-Q4_K_M.gguf')
            self.assertEqual(self.until(job['id'], 'done', 'failed')['state'], 'done')
        self.assertIsNone(self.hub.ranges[0])
        self.assertTrue(self.hub.ranges[1].startswith('bytes=10'))   # resumed, not restarted
        self.assertEqual(self.target().read_bytes(), DATA)

    def test_a_wrong_fingerprint_is_never_kept(self):
        self.hub.files['model-Q4_K_M.gguf'] = DATA[:-1] + b'X'   # damaged on the way
        found = downloads.browse('someone/Model-GGUF')
        found['files'][0]['files'][0]['sha256'] = SHA         # the fingerprint Hugging Face published
        with patch.object(downloads, 'browse', return_value=found):
            job = downloads.start_custom('someone/Model-GGUF', 'model-Q4_K_M.gguf')
        failed = self.until(job['id'], 'done', 'failed')
        self.assertEqual(failed['state'], 'failed')
        self.assertIn('fingerprint', failed['error'])
        self.assertEqual(list(self.target().parent.iterdir()), [])
        self.assertEqual(models.catalogue(), [])

    def test_free_space_is_checked_first(self):
        with patch.object(downloads, '_free_space', return_value=100 * 1024 * 1024):
            with self.assertRaises(downloads.DownloadError) as raised:
                downloads.start_custom('someone/Model-GGUF', 'model-Q4_K_M.gguf')
        self.assertEqual(raised.exception.status, 507)
        self.assertEqual(downloads._jobs, [])

    def test_licence_terms_must_be_accepted(self):
        self.hub.licence = 'llama3.2'
        with self.assertRaises(downloads.DownloadError):
            downloads.start_custom('someone/Model-GGUF', 'model-Q4_K_M.gguf')
        with self.assertRaises(downloads.DownloadError):
            downloads.start_recommended('llama-3.2-3b')
        job = downloads.start_custom('someone/Model-GGUF', 'model-Q4_K_M.gguf', accept=True)
        self.assertEqual(self.until(job['id'], 'done', 'failed')['state'], 'done')

    def test_gated_models_are_explained_not_downloaded(self):
        self.hub.gated = True
        with self.assertRaises(downloads.DownloadError) as raised:
            downloads.start_custom('someone/Model-GGUF', 'model-Q4_K_M.gguf')
        self.assertEqual(raised.exception.status, 403)

    def test_pause_resume_and_cancel(self):
        self.hub.delay = 0.02
        job = downloads.start_custom('someone/Model-GGUF', 'model-Q4_K_M.gguf')
        self.until(job['id'], 'downloading')
        wait(0.3)
        downloads.pause(job['id'])
        paused = self.until(job['id'], 'paused')
        part = self.target().with_name('model-Q4_K_M.gguf.part')
        self.assertTrue(0 < part.stat().st_size < len(DATA))
        self.hub.delay = 0
        downloads.resume(job['id'])
        self.assertEqual(self.until(job['id'], 'done', 'failed')['state'], 'done')
        self.assertTrue(self.hub.ranges[-1].startswith('bytes='))
        self.assertEqual(self.target().read_bytes(), DATA)
        self.assertEqual(paused['id'], job['id'])

        self.target().unlink()
        downloads.clear_finished()
        self.hub.delay = 0.02
        job = downloads.start_custom('someone/Model-GGUF', 'model-Q4_K_M.gguf')
        self.until(job['id'], 'downloading')
        wait(0.3)
        downloads.cancel(job['id'])
        self.until(job['id'], 'gone')
        self.assertFalse(part.exists())

    def test_a_download_running_at_shutdown_waits_to_be_resumed(self):
        config.DATA_DIR.mkdir()
        (config.DATA_DIR / 'downloads.json').write_text(json.dumps([{
            'id': 'abcdef123456', 'key': '', 'name': 'model', 'repo': 'someone/Model-GGUF', 'state': 'downloading',
            'files': [{'path': 'model-Q4_K_M.gguf', 'size': len(DATA), 'sha256': SHA}],
            'folder': str(self.target().parent), 'total': len(DATA), 'received': 10, 'speed': 5, 'error': '',
            'licence': 'Apache 2.0', 'licence_url': '', 'accept': False}]), encoding='utf-8')
        downloads.recover()
        self.assertEqual(downloads._jobs[0]['state'], 'paused')
        self.assertIn('Resume', downloads._jobs[0]['error'])

    def test_recommended_models_are_pinned(self):
        for item in downloads.RECOMMENDED:
            with self.subTest(model=item['key']):
                self.assertRegex(item['sha256'], r'^[a-f0-9]{64}$')
                self.assertTrue(item['file'].endswith('.gguf') and item['size'] > 10 ** 9)
                self.assertTrue(item['licence_url'].startswith('https://'))
                self.assertEqual(downloads.parse_repo(item['repo']), item['repo'])


if __name__ == '__main__':
    unittest.main()
