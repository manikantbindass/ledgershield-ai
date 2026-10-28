# Exact local setup

Use Python 3.12 and Node 24. Clone `https://github.com/manikantbindass/ledgershield-ai.git` and enter its root. Native Windows commands:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock -r requirements-dev.txt
.\.venv\Scripts\python.exe scripts/create_local_tokens.py
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --env-file .env --no-access-log
```

In another terminal:

```powershell
cd frontend
npm ci
npm run dev -- --port 5173 --strictPort
```

For macOS/Linux use `python3.12 -m venv .venv` and `.venv/bin/python` instead of the Windows interpreter path. No database is required for the in-memory demo. Open localhost:5173, then Settings & Audit. Read your local ignored `.env` and enter an operator/admin token; do not paste secrets into logs or commit them. Tokens stay in tab memory. Simulator starts paused and observe-only.

## Optional native SQLite archive

Create `artifacts/`, then set `DATABASE_URL=sqlite:///artifacts/ledger.db` in the terminal environment (PowerShell: `$env:DATABASE_URL='sqlite:///artifacts/ledger.db'`). Run `.venv\Scripts\python.exe -m alembic upgrade head` before restarting the API. Alembic reads the terminal environment, not `.env` automatically. The API's `--env-file .env` loads runtime values. Alternatively PostgreSQL uses `postgresql+psycopg://USER:PASSWORD@HOST:5432/DB`.

Database startup validates migrations; it does not silently create or reset tables. Archives preserve public research records, not a running consensus replica. `/ready` reports whether database archiving is enabled. `/api/v1/archive/{snapshot,event,healing,experiment}` reads archived records. Storage labels on live endpoints remain in_memory.

For Docker and monitoring see deployment.md. Never change the demo bind address to a public interface without deployment security work.
