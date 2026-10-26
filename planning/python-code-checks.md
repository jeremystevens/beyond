# Python code syntax checks

Status: implemented; unreleased after 1.2.0.

## Scope
Completed AI chat replies automatically check closed code fences labelled `python`, `python3` or `py` with the host's Python interpreter. A quiet line under the code toolbar shows **No Python syntax errors found**, a syntax error with a code-block line number, or **Not checked** with a reason. The result tooltip explains that the code was not run and that logic and dependencies were not checked. Source is compiled for syntax in a separate bounded worker; it is never executed, imported, installed or silently rewritten. Copy and Save still contain only the original code. Results persist with the reply and its conversation branches; older and stopped/failed replies have no new check claim.

This first version checks syntax only—not dependencies, undefined names, missing logic, program behavior, security or compatibility with other Python versions. Other languages and unfenced code are not checked. Incomplete/empty blocks, blocks over 100,000 UTF-8 bytes, and work beyond eight blocks or 200,000 total bytes per reply are skipped. The worker has a three-second timeout; failure keeps the reply with a Not checked label. No model request or runtime dependency is added. Streaming stays visible while completion controls remain disabled until the reply is finalized.

## Implementation
app/code_checks.py mirrors the fenced-code renderer and compiles source in an isolated Python process. app/server.py runs it off the event loop only for finished AI replies and stores reports in message stats. The browser binds each result to its block index, language and UTF-8 source fingerprint, displays it with textContent, and keeps verification labels separate from raw reply/code source. No schema migration or public execution endpoint is needed. Normal replies without Python fences start no worker.

## Validation
Tests cover valid/invalid syntax, contextual syntax errors, no execution/import side effects, Unicode/CRLF/fence parity, unsupported/incomplete/oversized blocks, work limits, timeout/failure handling, tray-launch interpreter selection, streamed/saved/branched metadata, original content preservation, browser labels, stale-source rejection and mobile overflow. All eight checker tests, seven chat integration/recovery tests and five JavaScript tests passed. Full Windows/Python 3.14 and Chromium CI passed on 227b187; the user also verified the UI and approved merging. Release VERSION and phase stay unchanged.
