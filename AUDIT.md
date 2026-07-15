# RuralFindMe — Code Audit

Date: 2026-07-15
Scope: Full repo read-only audit (Python/PySide6 desktop app + React/Vite frontend + PyInstaller packaging).

## Resolution Update — 2026-07-15

The findings in this audit have now been addressed:

- WebEngine file requests and navigation are restricted to the resolved `frontend/dist` directory; network schemes remain blocked.
- Search, validation, analyzer, and export failures no longer forward exception values or local paths. Diagnostics record only exception types and basename-only stack locations.
- Export paths are validated defensively, OCR rasterization has dimension/pixel/time bounds, and malformed bundled JSON raises a clear `ConfigurationError`.
- Table continuation evidence is capped and footer-aware, allocation dates are selected nearest the recognized title, and confidence/manual-review thresholds share one source of truth.
- Direct tests now cover the WebEngine URL policy and exchange contract, close cleanup, picker target validation, analyzer orchestration, OCR/extractor behavior, status classification, confidence scoring, configuration loading, diagnostics, export validation, document classification, and fixture usage.
- Vite is pinned exactly, `npm audit` explicitly gates Windows builds, and the portable package version is read from `app/__init__.py`. The private frontend package uses `0.0.0` rather than duplicating the application version.
- `fixtures/anonymized_records.json` is documented and exercised by tests; `CONTRIBUTING.md` documents security boundaries and required checks.
- Root `dist/`, `.venv-build/`, PyInstaller work, pytest caches, and Python bytecode were removed (about 1.35 GB). `frontend/dist` remains available for the desktop runtime.
- Git was initialized on branch `main`. No initial commit was created automatically.

Validation completed with **62 passing Python tests**, a passing frontend typecheck and production build, and **0 npm audit vulnerabilities**.

The sections below are retained as the original audit record and rationale for these changes.

## Architecture Overview

- `app/main.py` boots `QApplication`, installs crash logging (`app/diagnostics.py`), forces software OpenGL (GPU/ANGLE crash workaround), and either runs an isolated file-picker helper subprocess (`--file-picker-helper`) or shows `app/web_window.py:WebMainWindow`.
- `app/web_window.py` builds a `QWebEngineView` restricted to `file:/qrc:/data:/blob:` schemes (`LocalOnlyInterceptor`, `LocalPage.acceptNavigationRequest`), loads `frontend/dist/index.html`, and bridges to `app/bridge.py:DesktopBridge` via a polled (250ms) command/event queue instead of direct WebChannel calls from DOM handlers — a documented workaround for a Windows COM re-entrancy crash (see `docs/WEBCHANNEL.md`).
- `app/bridge.py` holds app state (`ValidationReport`/`DocumentAnalysis`/`SearchResult`) and dispatches `QRunnable` workers (`DocumentBatchWorker`, `SearchWorker`) off the UI thread. It never sends raw file paths to the frontend.
- `app/bridge_serialization.py` converts dataclasses to JSON-safe dicts, masking IDs (`mask_id`) and scrubbing ID-like tokens from evidence text before it reaches JS.
- `app/pdf/*`: `validator.py` (structural checks, password/corruption detection, category classification), `document_classifier.py` (title/date/profession extraction), `table_parser.py` (PyMuPDF table extraction → `DoctorRecord`), `analyzer.py` (validate→extract→OCR-fallback orchestration), `ocr.py` (shells out to `tesseract`).
- `app/search/*`: `normalizer.py`, `record_matcher.py` (exact-ID → exact-name → fuzzy cascade), `status_classifier.py` (keyword-driven status detection), `classifier.py` (assembles `SearchResult`), `confidence.py` (scoring).
- `app/export/result_exporter.py` writes a masked plain-text summary to a user-chosen path via native `QFileDialog`.
- `frontend/src` (React+TS+Vite) talks to Python only through `frontend/src/bridge.ts` (typed command/event queue, no direct WebChannel object exposure).
- Packaging: `build_windows.spec` / `build_macos.spec` (PyInstaller) driven by `scripts/build_windows.ps1` / `scripts/build_macos.sh`, zipped by `scripts/make_portable.ps1`.

Overall the bridge design is unusually security-conscious for this app class: ID masking, path scrubbing, restricted navigation, strict CSP, cancelled downloads, cookie/cache clearing on close.

---

## 1. Security

| # | File:Line | Problem | Suggested Fix |
|---|-----------|---------|----------------|
| 1 | `app/web_window.py:65` | `LocalContentCanAccessFileUrls` is enabled alongside `JavascriptEnabled`. If XSS were ever introduced (e.g. via a compromised npm dependency), injected script could read arbitrary `file://` URLs the process can access, not just the app bundle. | Scope file access via a custom scheme handler instead of blanket `file:` access, if feasible. Low urgency given the strict CSP and no injection sink currently found. |
| 2 | `app/export/result_exporter.py:67-70` | `export_result` writes to a path taken verbatim from the caller. Currently the path always originates from a native `QFileDialog` (safe today), but there's no validation if this function is ever called from a different entry point (e.g. a future scripting/API surface). | Add defensive path validation in `export_result` itself rather than relying on the caller always being the save dialog. |
| 3 | `app/pdf/ocr.py:18-25` | `pixmap.tobytes("png")` loads OCR page image fully into memory with no size cap — a maliciously crafted PDF with huge page dimensions could cause high memory use (local DoS). | Cap max page pixel dimensions before rasterizing, or catch `MemoryError` around the OCR path. Low severity for a single-user local tool. |

**Verified as sound (no action needed):** CSP in `frontend/index.html:8` is strict and matches `docs/WEBCHANNEL.md`; picker temp-file handling in `app/bridge.py:225-247` + `app/main.py:43-49` validates paths correctly against traversal/symlink tricks; no hardcoded secrets/tokens found anywhere in `app/config`, `app/config/settings.py`, or `frontend/src`; `tesseract` invocation uses `shutil.which` + fixed timeout with no `shell=True` (no injection risk); no XSS sinks (`innerHTML`, `eval`, `dangerouslySetInnerHTML`) found in `frontend/src/bridge.ts` or elsewhere.

---

## 2. Correctness / Code Quality

| # | File:Line | Problem | Suggested Fix |
|---|-----------|---------|----------------|
| 1 | `app/bridge.py:86-87` (`SearchWorker.run`) | Broad `except Exception as exc: ... emit(str(exc))` forwards the raw exception string to the UI. If an underlying exception (e.g. `OSError` from `fitz.open`) embeds a local file path, it leaks the path to the frontend — contradicting the "never send local paths" invariant enforced elsewhere. No test covers this path being scrubbed. | Narrow the caught exceptions and scrub/replace messages the same way `DocumentBatchWorker` does, instead of forwarding `str(exc)` directly. |
| 2 | `app/pdf/analyzer.py:37-38` + `51-75` | `PdfAnalyzer.analyze` raises `ValueError` including filenames (fine), but if `fitz.open` itself raises (e.g. concurrent file modification), a raw `fitz`/`OSError` message propagates straight into the `SearchWorker` catch-all above — same path-leak vector as #1. | Wrap `fitz.open` calls with a handler that raises a sanitized error message, consistent with `DocumentBatchWorker`'s approach. |
| 3 | `app/bridge.py:106-111` (`DocumentBatchWorker.run`) | Bare `except Exception` swallows all errors including unrelated bugs (e.g. `MemoryError`, programming errors), converting them to a generic message with no logging. | Narrow to expected exception types (`OSError`, `fitz` errors, `ValueError`) and log the real exception via `app/diagnostics.py` before showing the generic message. |
| 4 | `app/pdf/table_parser.py:141-159` | The continuation-row heuristic glues any unrecognized row's text onto the last record's `raw_text` whenever markers like "reporte de"/"fecha de generacion" don't match. A differently worded footer in a future round could pollute record evidence text. | Broaden/generalize the footer marker list, or cap how many trailing rows can be absorbed into `raw_text`. |
| 5 | `app/search/classifier.py:57` vs `app/search/confidence.py:32-37` | Confidence threshold `0.60` (classifier) and bands `0.70`/`0.90` (confidence label) are magic numbers defined independently; changing one without the other could desync "requires manual review" vs. displayed confidence label. | Derive both from one shared threshold constant/config. |
| 6 | `app/pdf/document_classifier.py:39-41` | `DATE_RE.search(text)` takes the *first* date found anywhere in the preview text, not necessarily the one near the title — a stray earlier date (e.g. in a disclaimer) could misattribute `allocation_date`. No test covers multi-date previews. | Anchor the date search closer to the title match, or take the last/most-title-proximate date instead of the first. |
| 7 | `app/config/settings.py:16-18` (`load_json_config`) | No error handling for a missing or malformed JSON config file. A corrupted `parser_config.json`/`status_keywords.json` in a broken install (e.g. partial PyInstaller bundle) raises an unhandled `FileNotFoundError`/`JSONDecodeError` deep in validator/classifier code, unlike most other failure paths in this codebase. | Wrap the load in try/except and surface a clear user-facing error consistent with the rest of the app's error handling. |

**Noted but not a bug:** `app/search/record_matcher.py:42-53` marks exact-name matches as `AMBIGUOUS` even when unique — this is deliberate per `docs/ASSUMPTIONS.md:3`, not a defect.

---

## 3. Testing Gaps

~35 tests total across `test_bridge.py`, `test_classifier.py`, `test_export.py`, `test_normalizer.py`, `test_table_parser.py`, `test_validator.py`. Coverage is real for validator/table-parser (built on genuine PyMuPDF documents) but thin/indirect elsewhere.

**Modules with zero direct or indirect coverage:**
- `app/main.py` — the file-picker helper's temp-path validation logic (security-relevant) is untested.
- `app/web_window.py` — no tests for `LocalOnlyInterceptor`, navigation allowlisting, the poll/exchange JSON contract, or `closeEvent` cookie/cache cleanup. **This is the most security-relevant untested file.**
- `app/pdf/extractor.py` — OCR-trigger threshold and page extraction untested.
- `app/pdf/ocr.py` — no mock of `subprocess.run`; tesseract failure/timeout paths unverified.
- `app/pdf/analyzer.py` — real orchestration logic is bypassed in `test_bridge.py` via monkeypatching, so it never actually runs under test.
- `app/search/status_classifier.py` — keyword cascade has no direct unit test (only exercised indirectly via pre-set `detected_status` fixtures that bypass the function).
- `app/search/confidence.py` — scoring formula untested.
- `app/diagnostics.py`, `app/config/settings.py` — untested, including the missing-file gap noted above.
- `app/pdf/document_classifier.py` — `classify_document_text` untested directly (only `compare_allocation_rounds` covered).

**Recommendation:** add at least one end-to-end test that builds a real three-document set through `PdfAnalyzer.analyze` → `search_records` → `bridge_serialization`, and direct unit tests for `status_classifier.py` and `confidence.py` since they encode the app's core business logic.

---

## 4. Dependencies & Build

| # | File:Line | Problem | Suggested Fix |
|---|-----------|---------|----------------|
| 1 | `frontend/package.json:29` | `vite` is pinned with caret (`^6.4.3`) while every other dependency is exact — the one loose specifier in the frontend manifest. | Pin to an exact version for reproducible builds, consistent with the rest of the file. |
| 2 | `scripts/build_windows.ps1:16` | `npm audit` runs but its exit code isn't explicitly checked (`$ErrorActionPreference = "Stop"` doesn't reliably gate on a native command's nonzero exit in this context) — vulnerabilities found won't fail the build. | Explicitly check `$LASTEXITCODE` after `npm audit` and fail the build if desired. |
| 3 | `scripts/make_portable.ps1:4`, `app/__init__.py:3`, `frontend/package.json:4` | App version string is duplicated in three places; bumping the version requires manually editing all three or the zip filename goes stale. | Read the version from a single source of truth (e.g. `app/__init__.py`) in the packaging script instead of hardcoding it. |
| 4 | project root | `dist/` (~717 MB) and `.venv-build/` (~640 MB) sit in the project root — ~1.3 GB of build output. `.gitignore` already covers both, but since git isn't initialized yet, nothing currently prevents them from being copied/zipped/staged accidentally. | Delete or move these out of the repo root before running `git init`; regenerate on demand via `scripts/build_windows.ps1`. |

**Good practices confirmed:** `requirements.txt` pins all Python deps to exact versions; PyInstaller specs correctly exclude unused heavy scientific-stack packages (`pandas`, `numpy`, `PIL`) that PyMuPDF optionally imports.

---

## 5. Documentation

- `docs/WEBCHANNEL.md` and `docs/ASSUMPTIONS.md` were spot-checked against the actual code and found **accurate** — no stale claims identified.
- `README.md` cites specific dataset figures (from `docs/PARSER_SPEC.md`) that can't be independently verified since the real source PDFs aren't checked in — not a doc bug, but nothing in CI re-validates these numbers if `parser_config.json` aliases change. Worth a manual spot-check when the parser config changes.
- No `CONTRIBUTING.md` or "known gaps" doc exists to tell future contributors which modules are untested (see Testing Gaps above) before they touch `web_window.py` or `ocr.py`.
- `fixtures/anonymized_records.json` exists but nothing in `tests/`, `README.md`, or `docs/` references it — either dead data that should be removed, or an intended fixture that was never wired up. Worth clarifying its purpose.

---

## 6. Project Hygiene

1. **This directory is not a git repository.** No commit history, no diffing, no reverting, no branching — this is the single largest hygiene risk given ~1.3 GB of build artifacts and dependencies currently sitting alongside source. **Recommendation: initialize git now**, after cleaning up the items below, before making further changes.
2. **`__pycache__` directories exist throughout `app/` and `tests/`.** Harmless at runtime, already covered by `.gitignore`, but should be deleted now to keep the working tree clean ahead of the first commit.
3. **`dist/` and `.venv-build/` (~1.3 GB combined) sit in the project root** — bloats every full-directory copy/backup/IDE index. Move outside the repo root or delete and regenerate on demand.
4. **`.pytest_cache/` is also present at the root**, already gitignored — same "clean up now" note applies.

---

## Priority Summary

**Do first:**
1. Fix the path-leak vector in `SearchWorker`/`PdfAnalyzer` (Correctness #1, #2) — real information-disclosure bug, contradicts the app's own stated invariant.
2. Clean up `dist/`, `.venv-build/`, `__pycache__`, `.pytest_cache` and initialize git (Hygiene #1-4) — foundational, blocks safe iteration on everything else.
3. Add tests for `web_window.py`'s navigation allowlist and the file-picker helper's path validation (Testing) — these guard the app's actual security boundary and currently have zero coverage.

**Do soon:**
4. Wrap `load_json_config` with error handling (Correctness #7).
5. Add direct unit tests for `status_classifier.py` and `confidence.py` (Testing) — core business logic, currently only indirectly exercised.
6. Pin `vite` exactly and fix the `npm audit` exit-code gate (Build #1, #2).

**Nice to have:**
7. Scope `LocalContentCanAccessFileUrls` more tightly (Security #1).
8. Deduplicate the version string across three files (Build #3).
9. Clarify or remove `fixtures/anonymized_records.json` (Docs).
