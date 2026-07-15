# Contributing to RuralFindMe

RuralFindMe processes sensitive local documents, so changes should preserve three boundaries:

1. Never expose local paths or unmasked identification values to the React frontend.
2. Keep WebEngine requests inside the bundled frontend directory and the explicitly allowed local schemes.
3. Keep PDF parsing and OCR off the UI thread, with bounded resource use and user-safe failure messages.

## Before submitting a change

Run:

```powershell
python -m pytest
cd frontend
npm ci
npm run typecheck
npm run build
npm audit
```

Changes to `app/web_window.py`, `app/main.py`, `app/bridge.py`, OCR, serialization, or export paths should include a focused security regression test. Parser changes should use fictitious records such as `fixtures/anonymized_records.json`; never commit official PDFs or real identifiers.

The application version has one source of truth: `app/__init__.py`. The portable packaging script reads it automatically. The private frontend package intentionally uses version `0.0.0` because it is not released independently.

Generated directories (`dist/`, `.venv-build/`, `.pytest_cache/`, `__pycache__/`) do not belong in source control and can be regenerated from the documented build commands.
