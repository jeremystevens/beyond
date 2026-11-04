"""Run a small set of isolated chat checks against Beyond's loaded local model."""
import argparse
import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from tempfile import TemporaryDirectory
from time import perf_counter
from unittest.mock import patch

import httpx

from app import config


CASES = {
    'bullets': 'List exactly these two items as exactly two bullet points: apples; pears. No introduction.',
    'json': 'Return only a valid JSON object with exactly two keys: name is the string Nora and count is the number 3. No code fence.',
    'budget': ('A repair costs $250 and a replacement costs $550. My budget was $600, but it is now $400. '
               'Using only the current budget, give exactly two bullet points, one per option, stating '
               'whether it fits and either the money remaining or the amount over budget.'),
    'weather-routing': ('Only restart the R-7 if its light is steady amber AND its temperature is below 40°C. '
                        'Its light is steady amber, but its temperature is exactly 40°C. Should it be restarted? '
                        'Explain in one sentence.'),
    'web-routing': 'Maya was booked for Tuesday, then moved to Thursday at 10 a.m. Using the latest correction, when is Maya booked?',
}
_BULLET = re.compile(r'^[-*+]\s+(.+)$')


def validate(case, answer):
    """Return a failure reason for a completed reply, or None."""
    if case in ('bullets', 'budget'):
        bullets = [_BULLET.fullmatch(line.strip()) for line in answer.splitlines() if line.strip()]
        if len(bullets) != 2 or not all(bullets):
            return 'Expected exactly two bullet lines with no surrounding text.'
        items = [item[1].lower() for item in bullets]
        if case == 'bullets' and items != ['apples', 'pears']:
            return 'Expected apples and pears in order.'
        if case == 'budget' and not (
            any(item.startswith('repair:') and '$150.00 remains' in item for item in items)
            and any(item.startswith('replacement:') and '$150.00 over budget' in item for item in items)
        ):
            return 'Expected $150 remaining for repair and $150 over budget for replacement.'
    elif case == 'json':
        try:
            fields = json.loads(answer, object_pairs_hook=list)
        except ValueError:
            return 'The whole reply is not valid JSON.'
        expected = {'name': 'Nora', 'count': 3}
        if (not isinstance(fields, list) or len(fields) != 2
                or not all(isinstance(field, tuple) for field in fields)
                or dict(fields) != expected or type(dict(fields)['count']) is not int):
            return 'Expected only the requested string and integer fields.'
    elif case == 'weather-routing':
        if not re.search(r"^\W*no\b|\b(?:should not|shouldn't|do not|don't|must not)\b", answer, re.I) or '40' not in answer:
            return 'Expected no restart at exactly 40 degrees.'
    elif case == 'web-routing':
        if not re.search(r'\bThursday\b', answer, re.I) or not re.search(r'\b10(?::00)?\s*a\.?m\b', answer, re.I):
            return 'Expected Thursday at 10 a.m.'
    return None


async def loaded_model(client, port):
    response = await client.get(f'http://127.0.0.1:{port}/api/models', timeout=15)
    response.raise_for_status()
    state = response.json()
    engine = state['engine']
    if state['busy'] or engine['state'] != 'ok' or not engine.get('port') or not engine.get('model'):
        raise RuntimeError('Beyond needs an idle, ready built-in model.')
    return engine


async def run_cases(client, port, selected, report, output):
    # Import path-bound modules after config.DATA_DIR is set to a temporary folder.
    from app import chats, engine, followups, learning, memory, rules, search_history, server, settings

    for module in (chats, followups, learning, memory, rules, search_history):
        module.initialize()
    settings.save({'auto_lookup': True, 'auto_facts': False, 'speech_enabled': False, 'recall': False})

    def block_lookup(*args, **kwargs):
        raise RuntimeError('Unexpected automatic lookup was blocked.')

    transport = httpx.ASGITransport(app=server.app, client=('127.0.0.1', 5000))
    async with httpx.AsyncClient(transport=transport, base_url='http://beyond.test') as chat:
        for case in selected:
            row = {'case': case, 'prompt': CASES[case]}
            start = perf_counter()
            try:
                model = await loaded_model(client, port)
                identity = {'name': model['model'], 'port': model['port']}
                if identity != report['model']:
                    raise RuntimeError('The loaded model changed during the smoke test.')
                url = f"http://127.0.0.1:{model['port']}"
                with patch.object(engine, '_server', return_value=(url, '')), \
                     patch.object(engine.builtin_engine, 'status', return_value=model), \
                     patch.object(server.lookups, 'run', side_effect=block_lookup), \
                     patch.object(server.notify, 'show'):
                    response = await chat.post('/api/chat/stream', json={'content': CASES[case]})
                response.raise_for_status()
                events = [json.loads(line) for line in response.text.splitlines() if line]
                row['events'] = events
                raw = ''.join(event['text'] for event in events if event['type'] == 'token')
                final = next((event['text'] for event in reversed(events) if event['type'] == 'replace'), raw).strip()
                row.update(streamed=raw, final=final)
                if any(event['type'] in ('error', 'lookup') for event in events):
                    raise RuntimeError('The stream reported an error or an unexpected lookup.')
                if not any(event['type'] == 'done' for event in events):
                    raise RuntimeError('The stream did not complete.')
                chat_id = next(event['id'] for event in events if event['type'] == 'chat')
                row['stored'] = chats.get(chat_id)['messages'][-1]['content']
                if row['stored'] != final:
                    raise RuntimeError('Final reply differs from the saved reply.')
                row['failure'] = validate(case, final)
            except (httpx.HTTPError, RuntimeError, ValueError, KeyError, StopIteration) as exc:
                row['failure'] = str(exc)
            row['seconds'] = round(perf_counter() - start, 2)
            report['cases'].append(row)
            output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
            result = f"FAIL - {row['failure']}" if row['failure'] else 'PASS'
            print(f"{case}: {result} ({row['seconds']:.2f}s)", flush=True)


async def run(args):
    async with httpx.AsyncClient(trust_env=False) as client:
        model = await loaded_model(client, args.port)
        started = datetime.now(timezone.utc)
        output = args.output or config.DATA_DIR / 'model-validation' / f"smoke-{started:%Y%m%dT%H%M%S%fZ}.json"
        output.parent.mkdir(parents=True, exist_ok=True)
        report = {'started_utc': started.isoformat(), 'model': {'name': model['model'], 'port': model['port']}, 'cases': []}
        print(f"Model: {model['model']}\nReport: {output.resolve()}", flush=True)
        with TemporaryDirectory(prefix='beyond-model-smoke-') as temporary:
            with patch.object(config, 'DATA_DIR', Path(temporary)):
                await run_cases(client, args.port, args.case or CASES, report, output)
    failures = sum(bool(row['failure']) for row in report['cases'])
    print(f"{len(report['cases']) - failures}/{len(report['cases'])} passed.", flush=True)
    return bool(failures)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=7770, help='Port of the running Beyond instance.')
    parser.add_argument('--case', action='append', choices=CASES, help='Run a selected case (repeatable).')
    parser.add_argument('--output', type=Path, help='Report path (default: data/model-validation/smoke-*.json).')
    args = parser.parse_args()
    try:
        return asyncio.run(run(args))
    except (httpx.HTTPError, RuntimeError, ValueError, OSError, KeyError) as exc:
        parser.exit(2, f'Model smoke test could not finish: {exc}\n')


if __name__ == '__main__':
    raise SystemExit(main())
