# Tender-ERP

Offline-first desktop app that consolidates tender tracking, compliance
tracking, e-stamp accounting, a password vault, and a submission
checklist generator for multiple firms under one operator. Built to
replace four disconnected Excel workbooks with active alerting, RBAC,
and proactive deadline management.

See the full product spec in the conversation history / `docs/` for
the module-by-module requirements. This branch implements **v0.5 +
most of v1.0**: user auth with roles, firm management, tender tracker,
compliance tracker, dashboard with deadline queries, e-stamp ledger,
password vault (AES-256-GCM + Argon2id), checklist generator with
rule library, first-run wizard state machine, audit log, global
search, Excel importer, and backup.

## Tech stack

- **Python 3.11+**
- **PySide6** for the GUI
- **SQLAlchemy 2.x** over **SQLite** (swap URL to `sqlite+pysqlcipher`
  for production encryption-at-rest)
- **argon2-cffi** for password hashing
- **cryptography** for AES-256-GCM vault record encryption
- **openpyxl** for migrating legacy `.xlsx` trackers
- **reportlab** for checklist PDF output
- **plyer** for OS-native desktop notifications

## Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run the GUI

```bash
python -m tender_erp
```

First launch:

1. Prompts you to create the initial admin user.
2. Writes a one-time recovery key to
   `$TENDER_ERP_HOME/admin_recovery_key.txt`. **Move this offline.**
3. The first-run wizard walks you through seeding firms, the
   checklist rule library, and uploading at least one compliance
   document per firm — until all three are done, the checklist
   generator stays disabled.

The app stores everything under `$APPDATA/TenderManager` on Windows
or `~/.tender_erp` elsewhere. Override with `TENDER_ERP_HOME`.

## CLI (headless)

The CLI is handy for migration, scripting, and CI. Same DB as the GUI.

```bash
python -m tender_erp.cli init                       # create tables
python -m tender_erp.cli create-admin \
    --username aadi --full-name "Aadi Pandey" \
    --password "change-me"
python -m tender_erp.cli seed-firms                  # spec §2 firms
python -m tender_erp.cli seed-rules                  # starter rule library
python -m tender_erp.cli dashboard                   # text snapshot
python -m tender_erp.cli import-tenders \
    --firm "Mr. Johnny Care Services (India) Pvt Ltd" \
    02_Mr__Johnny_Tender_Tracker.xlsx
python -m tender_erp.cli import-compliance \
    --firm "Mr. Johnny Care Services (India) Pvt Ltd" \
    03_All_Firms_Compliance_Tracker.xlsx
python -m tender_erp.cli import-estamps \
    --firm "Green Foods" 04_Estamp_Tracker_FY_2026-27.xlsx
python -m tender_erp.cli backup                      # encrypted zip
```

## Tests

```bash
python -m pytest
```

Every test runs against a fresh temporary `TENDER_ERP_HOME` fixture,
so your real DB is never touched.

## Layout

```
tender_erp/
  config.py              # paths, Argon2/session tunables
  db.py                  # SQLAlchemy engine + session_scope
  app.py                 # Qt bootstrap
  cli.py                 # headless CLI
  seed_data.py           # starter rule library + known firms
  wizard_service.py      # first-run wizard state machine
  models/                # ORM models (one file per table group)
  services/
    crypto.py            # Argon2id + AES-GCM (vault + auth hashing)
    auth.py              # authenticate, lockout, session state
    permissions.py       # role gate helpers
    audit.py             # immutable audit log writer
    validators.py        # GSTIN/PAN/normalization, cross-field rules
    dashboard.py         # deadline buckets, MTD e-stamp summary
    checklist.py         # rule matcher, PDF render, instance save
    backup.py            # zip backup + xlsx export
    importer.py          # legacy .xlsx migration
    notifications.py     # plyer desktop alerts
    search.py            # Ctrl+K global search
    vault_service.py     # encrypt/decrypt wrappers for credentials
  ui/                    # PySide6 views (one per module)
tests/                   # pytest, no Qt dependency
```

## Security notes

- **Vault master key is never persisted.** It lives in
  `CurrentSession.vault` only. Losing it = losing the vault. The salt
  does live on disk (`vault.salt`) and must be kept alongside the DB.
- **Re-auth window** on the vault is configurable via
  `SETTINGS.vault_reauth_minutes` (default 5 min). Copying a password
  clears the clipboard after 20 s.
- **Failed logins** lock an account for 15 min after 5 attempts.
- **Idle sessions** auto-logout after 30 min; tuned in `config.py`.
- **Audit log** is append-only at the service layer. The UI never
  issues UPDATE/DELETE on `audit_log`.
- **No plaintext passwords** ever hit the audit log — the recorder
  strips any field ending in `_enc` before JSON-serialising.

## What's intentionally not here (yet)

- Win/Loss analytics (spec §4.2) — next milestone.
- Calendar view (spec §4.3) — next milestone.
- Email digest (spec §3.7 optional).
- SQLCipher-encrypted DB — one-line switch in `db.build_engine` once
  the binding is available in your environment.
- Cloud sync (spec §10: explicitly out of scope for v1).

## Status

`v0.5` + most of `v1.0` is implemented, tested (28 passing tests), and
smoke-run end-to-end through the CLI.
