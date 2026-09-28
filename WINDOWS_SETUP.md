# Windows Quickstart (no Docker, no paid services)

This is the zero-cost local dev path: no Docker, no Postgres, no AWS, and no
Anthropic API key required. The OCR endpoint will be disabled (it needs an
Anthropic key), but the rest of the app — auth, production logging, carbon
calculator, reports, signing, audit trail, dashboard, frontend, PWA — runs
end-to-end with just Python and Node.

## Prerequisites

Install once:

- **Python 3.11, 3.12 or 3.13** — https://www.python.org/downloads/windows/
  - During install, tick **"Add python.exe to PATH"**.
- **Node.js 20 LTS** — https://nodejs.org/
- **Git** — https://git-scm.com/download/win

Verify in a fresh PowerShell window:

```powershell
python --version    # 3.11.x – 3.13.x
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

## Product passports (Phase 3)

The seed also creates a supply chain, a supplier data submission and one
published Digital Product Passport:

- **Products → a product → Life cycle** — per-garment footprint by stage
  (fibre → end of life), each stage labelled with where its data came from
  (factory batches, supplier submission, or a disclosed default factor),
  the primary-data share, automated checks and an ecodesign comparison.
- **Products → Supply chain** — link the spinner / knit mill / dye house
  behind each stage and send them a login-free data request link.
- **Products → Passport** — sign & publish a passport version; print the QR.
- **Suppliers** — your Tier 2–4 facilities and their submissions.
- Public pages (no login): `/passport/<token>` and, for suppliers,
  `/supplier-data/demo-supplier-token`.

Emission factors live in `backend/app/utils/factor_library.py`, each with
its source. Grid electricity (CEA v21.0 for India, Ember 2025 elsewhere),
freight, diesel and water (UK Government GHG Conversion Factors 2025) come
from official publications. Fibres, per-process defaults, chemicals, steam,
trims, packaging and use/end-of-life are still indicative — swap in a
licensed dataset (Textile Exchange, ecoinvent, Higg MSI, supplier EPDs)
before using footprints in public claims.

An existing `greenthread.db` keeps working — the new tables are created on
startup. Re-run `python -m app.jobs.seed_demo` to add the Phase 3 demo data.

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

**`bcrypt` errors (`module 'bcrypt' has no attribute '__about__'`, or
passwords failing to verify)** — `passlib 1.7.4` only works with
`bcrypt==4.0.1`, which is what the requirements pin. If something upgraded
it, run `pip install bcrypt==4.0.1`.

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
