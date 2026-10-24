# Vendored browser syntax highlighting

Highlight.js 11.11.1, BSD-3-Clause. Retain highlight-LICENSE and the license headers when redistributing these assets. BEYOND loads them locally; no runtime CDN access is used.

| File | Pinned upstream source | SHA-256 |
| --- | --- | --- |
| highlight.min.js | https://raw.githubusercontent.com/highlightjs/cdn-release/11.11.1/build/highlight.min.js | c4a399dd6f488bc97a3546e3476747b3e714c99c57b9473154c6fb8d259b9381 |
| powershell.min.js | https://raw.githubusercontent.com/highlightjs/cdn-release/11.11.1/build/languages/powershell.min.js | 8357484cd585fb36f36d0b3eab33518e7fdfdc2e54f1066a4ce73e505567e166 |
| highlight-LICENSE | https://raw.githubusercontent.com/highlightjs/highlight.js/11.11.1/LICENSE | 6c081431591d9df696c82dc598fe1423765b8a299b200ed00b281afd0f64c490 |

The common bundle supplies common languages; PowerShell is included separately. Unsupported languages remain plain code. Automatic language detection is intentionally disabled. Highlighting is skipped above 100,000 characters to bound browser work, while Copy and Save remain available. The project-owned theme is ../code-blocks.css.
