import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from app import code_checks


class CodeCheckTests(unittest.TestCase):
    def check(self, source, language='python'):
        return code_checks.check_reply(f'```{language}\n{source}\n```')[0]

    def test_valid_python_is_checked_without_executing_imports_or_statements(self):
        with tempfile.TemporaryDirectory() as folder:
            marker = Path(folder) / 'must-not-exist'
            result = self.check(f'import package_that_does_not_exist\nopen({str(marker)!r}, "w").write("executed")\nraise RuntimeError("do not run")')
            self.assertEqual(result['status'], 'passed')
            self.assertFalse(marker.exists())

    def test_syntax_and_context_errors_have_block_local_lines(self):
        for source in ['def broken(\n    pass', 'return 1', 'break', 'await run()']:
            with self.subTest(source=source):
                result = self.check(source)
                self.assertEqual(result['status'], 'error')
                self.assertGreaterEqual(result['line'], 1)
                self.assertTrue(result['reason'])

    def test_unicode_crlf_aliases_and_tilde_fences_preserve_source(self):
        source = 'name = "caf\u00e9"\r\n'
        text = '```html\n<p>Hello</p>\n```\n~~~language-py\r\n' + source + '~~~~\r\n'
        result = code_checks.check_reply(text)[0]
        self.assertEqual(result['block'], 2)
        self.assertEqual(result['language'], 'py')
        self.assertEqual(result['fingerprint'], code_checks.fingerprint(source))
        self.assertEqual(result['status'], 'passed')

    def test_unsupported_and_unfenced_code_starts_no_worker(self):
        with patch.object(code_checks.subprocess, 'run') as run:
            self.assertEqual(code_checks.check_reply('print(1)\n```javascript\nconst x = 1;\n```'), [])
        run.assert_not_called()

    def test_empty_incomplete_and_oversized_blocks_are_skipped(self):
        for text in ['```python\n```', '```python\nprint(1)', '```python\n' + 'x' * (code_checks.MAX_BYTES + 1) + '\n```']:
            with self.subTest(text=text[:40]), patch.object(code_checks.subprocess, 'run') as run:
                result = code_checks.check_reply(text)[0]
                self.assertEqual(result['status'], 'skipped')
                run.assert_not_called()

    def test_worker_failure_cannot_discard_an_answer_or_claim_success(self):
        for failure in [subprocess.TimeoutExpired('worker', 3), OSError('unavailable')]:
            with patch.object(code_checks.subprocess, 'run', side_effect=failure):
                self.assertEqual(self.check('print(1)')['status'], 'skipped')

    def test_multiple_blocks_are_independent_and_worker_count_is_bounded(self):
        text = '```python\nx=1\n```\n' * 10
        results = code_checks.check_reply(text)
        self.assertEqual(len(results), 10)
        self.assertEqual(sum(r['status'] == 'passed' for r in results), code_checks.MAX_BLOCKS)
        self.assertEqual(results[-1]['status'], 'skipped')

    def test_tray_launch_uses_console_python_with_hidden_window_and_json_pipes(self):
        with patch.object(code_checks.sys, 'executable', 'C:/Python/pythonw.exe'), patch.object(code_checks.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, '[{"status":"passed"}]')) as run:
            self.assertEqual(self.check('x=1')['status'], 'passed')
        self.assertEqual(Path(run.call_args.args[0][0]).name, 'python.exe')
        self.assertEqual(run.call_args.kwargs['timeout'], 3)
