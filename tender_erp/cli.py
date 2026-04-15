"""Headless CLI for scripting, testing and migration.

Exposed subcommands:

* ``init``             – initialise the DB and create all tables.
* ``create-admin``     – create an admin account non-interactively.
* ``seed-rules``       – insert the starter checklist rule library.
* ``seed-firms``       – create the firms listed in the spec.
* ``dashboard``        – print the dashboard snapshot as text.
* ``import-tenders``   – import a tender .xlsx for a given firm name.
* ``import-compliance`` – import a compliance .xlsx for a given firm.
* ``import-estamps``   – import an e-stamp .xlsx for a given firm.
* ``backup``           – run a manual backup.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .db import init_db, session_scope
from .models.firm import Firm
from .models.user import Role


def _cmd_init(_args: argparse.Namespace) -> int:
    init_db()
    print("DB initialised.")
    return 0


def _cmd_create_admin(args: argparse.Namespace) -> int:
    init_db()
    from .services import auth

    with session_scope() as session:
        user = auth.create_user(
            session,
            username=args.username,
            full_name=args.full_name,
            password=args.password,
            role=Role.ADMIN.value,
        )
        print(f"Created admin user #{user.id} ({user.username}).")
    return 0


def _cmd_seed_rules(_args: argparse.Namespace) -> int:
    init_db()
    from .seed_data import seed_checklist_rules

    with session_scope() as session:
        added = seed_checklist_rules(session)
    print(f"Seeded {added} checklist rules.")
    return 0


def _cmd_seed_firms(_args: argparse.Namespace) -> int:
    init_db()
    from .seed_data import seed_known_firms

    with session_scope() as session:
        firms = seed_known_firms(session)
    print(f"Seeded {len(firms)} firms.")
    return 0


def _cmd_dashboard(_args: argparse.Namespace) -> int:
    init_db()
    from .services import dashboard

    with session_scope() as session:
        snap = dashboard.build_snapshot(session)
    print(f"=== Dashboard @ {snap.generated_at.isoformat(timespec='seconds')} ===")
    print(f"Firms: {snap.firm_count}")
    print(f"Tenders due (next 7 days): {len(snap.tenders_7d)}")
    for row in snap.tenders_7d:
        print(
            f"  [{row.due_date}] {row.firm_name} – {row.bid_no or '-'} – {row.organisation or '-'}"
        )
    print(f"Tenders due (8–30 days): {len(snap.tenders_8_to_30d)}")
    print(f"Compliance expiring (60 days): {len(snap.compliance_60d)}")
    for d in snap.compliance_60d:
        print(f"  [{d.expiry_date}] {d.firm.name if d.firm else '-'} – {d.document_name}")
    print(f"DSC expiring (90 days): {len(snap.dsc_90d)}")
    print(f"Pending past-due tenders: {len(snap.pending_status)}")
    print(f"Decision-required queue: {len(snap.decision_required)}")
    print(
        f"E-stamps MTD: {snap.estamp_mtd.count} stamps, "
        f"₹{snap.estamp_mtd.total_spent:,.2f} "
        f"(last FY same month: ₹{snap.estamp_mtd.vs_same_month_last_fy:,.2f})"
    )
    return 0


def _resolve_firm(session, name: str) -> Firm:
    firm = session.query(Firm).filter(Firm.name == name).first()
    if firm is None:
        raise SystemExit(f"no firm named {name!r}; run seed-firms or create it first")
    return firm


def _cmd_import_tenders(args: argparse.Namespace) -> int:
    init_db()
    from .services.importer import import_tenders_xlsx

    with session_scope() as session:
        firm = _resolve_firm(session, args.firm)
        count = import_tenders_xlsx(session, Path(args.path), firm)
    print(f"Imported {count} tender rows.")
    return 0


def _cmd_import_compliance(args: argparse.Namespace) -> int:
    init_db()
    from .services.importer import import_compliance_xlsx

    with session_scope() as session:
        firm = _resolve_firm(session, args.firm)
        count = import_compliance_xlsx(session, Path(args.path), firm)
    print(f"Imported {count} compliance rows.")
    return 0


def _cmd_import_estamps(args: argparse.Namespace) -> int:
    init_db()
    from .services.importer import import_estamps_xlsx

    with session_scope() as session:
        firm = _resolve_firm(session, args.firm)
        count = import_estamps_xlsx(session, Path(args.path), firm)
    print(f"Imported {count} e-stamp rows.")
    return 0


def _cmd_backup(_args: argparse.Namespace) -> int:
    init_db()
    from .services import backup

    out = backup.manual_backup(label="cli")
    print(f"Backup written: {out}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tender-erp-cli")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init").set_defaults(func=_cmd_init)

    p_admin = sub.add_parser("create-admin")
    p_admin.add_argument("--username", required=True)
    p_admin.add_argument("--full-name", required=True)
    p_admin.add_argument("--password", required=True)
    p_admin.set_defaults(func=_cmd_create_admin)

    sub.add_parser("seed-rules").set_defaults(func=_cmd_seed_rules)
    sub.add_parser("seed-firms").set_defaults(func=_cmd_seed_firms)
    sub.add_parser("dashboard").set_defaults(func=_cmd_dashboard)

    for name, func in (
        ("import-tenders", _cmd_import_tenders),
        ("import-compliance", _cmd_import_compliance),
        ("import-estamps", _cmd_import_estamps),
    ):
        p = sub.add_parser(name)
        p.add_argument("--firm", required=True)
        p.add_argument("path")
        p.set_defaults(func=func)

    sub.add_parser("backup").set_defaults(func=_cmd_backup)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
