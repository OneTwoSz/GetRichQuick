# Windows Quickstart (no Docker, no paid services)

This is the zero-cost local dev path: no Docker, no Postgres, no AWS, and no
Anthropic API key required. The OCR endpoint will be disabled (it needs an
Anthropic key), but the rest of the app — auth, production logging, carbon
calculator, reports, signing, audit trail, dashboard, frontend, PWA — runs
end-to-end with just Python and Node.

## Prerequisites

Install once:

- **Python 3.11 or 3.12** — https://www.python.org/downloads/windows/
  - During install, tick **"Add python.exe to PATH"**.
- **Node.js 20 LTS** — https://nodejs.org/
- **Git** — https://git-scm.com/download/win

Verify in a fresh PowerShell window:

```powershell
python --version    # 3.11.x or 3.12.x
node --version      # v20.x
npm --version
```

## 1. Backend setup

From the repo root (`C:\Users\sabar\Documents\repos\GetRichQuick`):

```powershell
cd backend

# Create and activate a virtualenv
python -m venv .venv
.\.venv\Scripts\Activate.ps1
# If activation is blocked: Set-ExecutionPolicy -Scope CurrentUser RemoteSigned

# Install the Windows-friendly dependency set (skips weasyprint and psycopg2)
pip install --upgrade pip
pip install -r requirements-windows.txt
```

**Why a separate requirements file?** `weasyprint` needs the GTK runtime on
Windows and `psycopg2-binary` is only needed if you use Postgres. Both are
omitted from `requirements-windows.txt`. The app detects WeasyPrint isn't
installed and saves the rendered report as **HTML** instead of PDF — the
download endpoint serves the HTML automatically. Signing, anchoring, and
verify all keep working because they operate on canonical JSON, not the PDF
bytes.

## 2. Configure environment

Copy the example env file into `backend\.env`:

```powershell
# Still inside backend\
copy ..\.env.example .env
```

Open `backend\.env` and edit two values:

```
DATABASE_URL=sqlite:///./greenthread.db
SECRET_KEY=dev-only-secret-replace-me-with-openssl-rand-hex-32
REPORTS_DIR=./reports
```

The defaults in `.env.example` already use SQLite, so usually just setting
`SECRET_KEY` to anything non-empty is enough. Leave `ANTHROPIC_API_KEY=`
blank — only the OCR upload is affected.

## 3. Seed demo data

```powershell
# From backend\, with the venv still active
python -m app.jobs.seed_demo
```

Output should end with:

```
done. login at /login with demo@greenthread.app / demo1234
```

This creates `backend\greenthread.db` (SQLite file), one demo factory in
Tiruppur, ~45 production records over the last 90 days, and 6 chemicals
(one of which fails ZDHC compliance, so the dashboard shows a real
non-empty alert).

The script is **idempotent** — re-running won't create duplicates, but it
*will* reset the demo password.

## 4. Run the backend

```powershell
# Still in backend\, venv active
uvicorn app.main:app --reload
```

Server is up at http://localhost:8000. API docs at http://localhost:8000/docs.

## 5. Run the frontend

In a **second** PowerShell window (leave the backend running):

```powershell
cd C:\Users\sabar\Documents\repos\GetRichQuick\frontend
npm install
npm run dev
```

Frontend at http://localhost:5173.

## 6. Log in

- **Email:** `demo@greenthread.app`
- **Password:** `demo1234`

You should land on a dashboard with real numbers, a 3-month production
history, a chemicals page with one ZDHC-flagged entry, and the Generate
Report button — which will now produce a sustainability report (HTML on
Windows-without-GTK; PDF anywhere WeasyPrint installs).

## What is NOT working in this setup

| Feature | Status | How to enable |
|---|---|---|
| OCR (bill upload extraction) | Disabled | Set `ANTHROPIC_API_KEY=...` in `.env`. Costs ~$0.003 per page. |
| PDF download | HTML fallback | Install WeasyPrint + GTK runtime, *or* run via Docker. |
| Bitcoin anchoring | Disabled until you run the cron job | `python -m app.jobs.anchor_daily` once you have the `ots` CLI. |
| KMS-backed signing | Falls back to local Ed25519 | Leave `REPORT_SIGNING_PROVIDER=local`. |

Local Ed25519 signing **is** working — keys are stored in the SQLite DB
and the verify page (`/verify/<report_id>`) will return a green checkmark
for signature validity.

## Troubleshooting

**`ModuleNotFoundError: No module named 'sqlalchemy'`** — the venv isn't
activated. Run `.\.venv\Scripts\Activate.ps1` again.

**`bcrypt` import errors on Python 3.13** — pin to 3.11 or 3.12. The
`passlib[bcrypt]==1.7.4` pin we ship doesn't support 3.13 yet.

**`Set-ExecutionPolicy ... blocked`** — open PowerShell as a regular user
and run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`. Don't use
`-Scope LocalMachine`.

**`OperationalError: no such table: users`** — the seed script wasn't run,
or it crashed early. Delete `backend\greenthread.db` and re-run
`python -m app.jobs.seed_demo`.

**Port 8000 or 5173 already in use** — change `BACKEND_PORT` in `.env`
and pass `--port 8001` to uvicorn; for the frontend, `npm run dev -- --port 5174`.

**WeasyPrint install fails** — that's expected on Windows without GTK.
Stick with `requirements-windows.txt`. The app falls back to HTML.

## Switching to Docker / Postgres later

Nothing in this setup blocks moving to Docker. The `docker-compose.yml`
is unchanged and reads its own DATABASE_URL from `.env` (the commented
Postgres block in `.env.example`). Just install Docker Desktop, swap the
`DATABASE_URL`, and `docker-compose up`.
