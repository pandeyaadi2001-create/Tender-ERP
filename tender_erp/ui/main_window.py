"""Main application window — tabbed shell (spec §3.7)."""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QInputDialog,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QTabWidget,
)

from ..config import APP_NAME, SETTINGS
from ..db import session_scope
from ..services import backup, notifications
from ..services.auth import CurrentSession
from ..services.search import global_search
from .checklist_rules_view import ChecklistRulesView
from .compliance_view import ComplianceView
from .dashboard_view import DashboardView
from .estamps_view import EstampsView
from .firms_view import FirmsView
from .tenders_view import TendersView
from .users_view import UsersView
from .vault_view import VaultView


class MainWindow(QMainWindow):
    def __init__(self, session_state: CurrentSession) -> None:
        super().__init__()
        self.session_state = session_state
        self.setWindowTitle(f"{APP_NAME} — {session_state.user.full_name} ({session_state.user.role})")
        self.resize(1280, 800)

        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        self.dashboard = DashboardView()
        self.firms = FirmsView()
        self.tenders = TendersView()
        self.compliance = ComplianceView()
        self.estamps = EstampsView()
        self.rules = ChecklistRulesView()

        self.tabs.addTab(self.dashboard, "Dashboard")
        self.tabs.addTab(self.firms, "Firms")
        self.tabs.addTab(self.tenders, "Tenders")
        self.tabs.addTab(self.compliance, "Compliance")
        self.tabs.addTab(self.estamps, "E-Stamps")
        self.tabs.addTab(self.rules, "Checklist Rules")

        if session_state.user.is_admin:
            self.vault = VaultView(session_state)
            self.users = UsersView()
            self.tabs.addTab(self.vault, "Vault")
            self.tabs.addTab(self.users, "Users")

        self._build_menu()

        # Idle timeout watcher — touches on every user action.
        self._idle_timer = QTimer(self)
        self._idle_timer.timeout.connect(self._check_idle)
        self._idle_timer.start(60_000)

        # Initial desktop alerts (best-effort).
        try:
            with session_scope() as session:
                notifications.fire_due_alerts(session)
        except Exception:
            pass

    def _build_menu(self) -> None:
        menubar = self.menuBar()
        file_menu = menubar.addMenu("&File")

        search_action = QAction("&Search...", self)
        search_action.setShortcut(QKeySequence("Ctrl+K"))
        search_action.triggered.connect(self._global_search)
        file_menu.addAction(search_action)

        refresh_action = QAction("&Refresh dashboard", self)
        refresh_action.setShortcut(QKeySequence("F5"))
        refresh_action.triggered.connect(self.dashboard.refresh)
        file_menu.addAction(refresh_action)

        file_menu.addSeparator()
        backup_action = QAction("&Backup now", self)
        backup_action.triggered.connect(self._backup_now)
        file_menu.addAction(backup_action)

        file_menu.addSeparator()
        lock_action = QAction("&Lock and logout", self)
        lock_action.triggered.connect(self.close)
        file_menu.addAction(lock_action)

    def _check_idle(self) -> None:
        if self.session_state.is_expired():
            QMessageBox.information(
                self,
                "Session expired",
                f"Idle for more than {SETTINGS.session_timeout_minutes} min. Logging out.",
            )
            self.close()
        else:
            self.session_state.touch()

    def _global_search(self) -> None:
        query, ok = QInputDialog.getText(
            self, "Search", "Search bid no / organisation / certificate:"
        )
        if not ok or not query.strip():
            return
        with session_scope() as session:
            results = global_search(session, query)
        if not results:
            QMessageBox.information(self, "Search", "No results.")
            return
        msg = "\n".join(f"[{r.kind}] {r.title} — {r.subtitle}" for r in results[:30])
        QMessageBox.information(self, "Search results", msg)

    def _backup_now(self) -> None:
        try:
            out = backup.manual_backup(label="manual")
        except Exception as exc:
            QMessageBox.warning(self, "Backup failed", str(exc))
            return
        QMessageBox.information(self, "Backup created", f"Saved: {out}")
