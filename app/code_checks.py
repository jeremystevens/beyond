"""Bounded syntax checks of labelled Python fences. Generated source is never executed."""
import json
import re
import subprocess
import sys
from pathlib import Path

MAX_BYTES = 100_000
MAX_TOTAL_BYTES = 200_000
MAX_BLOCKS = 8
LANGUAGES = {'python', 'python3', 'py'}


def fingerprint(source):
    value = 2166136261
    for byte in source.encode('utf-8'):
        value = ((value ^ byte) * 16777619) & 0xffffffff
    return f'{value:08x}'


def blocks(text):
    """Match the web renderer's fence rules; retain source and index across all languages."""
    fence = None
    source = []
    index = 0
    for line in re.findall(r'[^\r\n]*(?:\r\n|\n|\r|$)', text):
        if not line:
            continue
        body = re.sub(r'(?:\r\n|\n|\r)$', '', line)
        if fence:
            closing = re.fullmatch(r' {0,3}(`+|~+)[ \t]*', body)
            if closing and closing[1][0] == fence[0][0] and len(closing[1]) >= len(fence[0]):
                yield index, fence[1], ''.join(source), True
                fence = None
                source = []
            else:
                source.append(line)
        else:
            opening = re.fullmatch(r' {0,3}(`{3,}|~{3,})([^\r\n]*)', body)
            if opening and line.endswith(('\r', '\n')) and not (opening[1][0] == '`' and '`' in opening[2]):
                index += 1
                language = (opening[2].strip().split() or [''])[0].lower()
                language = re.sub(r'^language-', '', language)[:40]
                fence = (opening[1], language)
    if fence:
        yield index, fence[1], ''.join(source), False


def check_reply(text):
    reports, pending = [], []
    total = 0
    for index, language, source, closed in blocks(text):
        if language not in LANGUAGES:
            continue
        report = {'block': index, 'language': language, 'fingerprint': fingerprint(source), 'status': 'skipped'}
        size = len(source.encode('utf-8'))
        if not closed:
            report['reason'] = 'Incomplete code fence'
        elif not source.strip():
            report['reason'] = 'Empty code block'
        elif len(pending) >= MAX_BLOCKS or size > MAX_BYTES or total + size > MAX_TOTAL_BYTES:
            report['reason'] = 'Check size limit reached'
        else:
            total += size
            pending.append(source)
            report['status'] = 'pending'
        reports.append(report)
    if not pending:
        return reports
    executable = Path(sys.executable)
    if executable.name.lower() == 'pythonw.exe':
        executable = executable.with_name('python.exe')  # tray launches still need worker JSON pipes
    try:
        result = subprocess.run([str(executable), '-I', '-S', str(Path(__file__).resolve()), '--worker'],
                                input=json.dumps(pending), text=True, encoding='utf-8', capture_output=True,
                                timeout=3, check=True,
                                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        checked = json.loads(result.stdout)
        if len(checked) != len(pending):
            raise ValueError('Invalid check results')
        checked = iter(checked)
        for report in reports:
            if report['status'] == 'pending':
                report.update(next(checked))
    except (OSError, subprocess.SubprocessError, ValueError, TypeError):
        for report in reports:
            if report['status'] == 'pending':
                report.update(status='skipped', reason='Syntax checker unavailable or timed out')
    return reports


def worker():
    # No import, eval or exec of generated code. compile() checks syntax/context but never runs the result.
    sources = json.loads(sys.stdin.read(MAX_TOTAL_BYTES * 6 + 1024))
    results = []
    for source in sources:
        try:
            compile(source, '<generated-code>', 'exec', dont_inherit=True)
            results.append({'status': 'passed', 'python': f'{sys.version_info.major}.{sys.version_info.minor}'})
        except SyntaxError as exc:
            results.append({'status': 'error', 'reason': exc.msg[:180], 'line': exc.lineno, 'column': exc.offset,
                            'python': f'{sys.version_info.major}.{sys.version_info.minor}'})
        except (ValueError, OverflowError, RecursionError, MemoryError):
            results.append({'status': 'skipped', 'reason': 'Code could not be safely parsed'})
    print(json.dumps(results))


if __name__ == '__main__' and sys.argv[1:] == ['--worker']:
    worker()
