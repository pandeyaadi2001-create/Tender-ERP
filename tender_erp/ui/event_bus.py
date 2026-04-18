"""Global event bus for cross-tab communication (real-time sync)."""

from PySide6.QtCore import QObject, Signal

class EventBus(QObject):
    """Event bus to notify all views when data changes."""
    dataChanged = Signal()

# Global singleton instance
global_bus = EventBus()
