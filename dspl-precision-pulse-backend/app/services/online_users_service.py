"""
Simple in-memory tracking of currently logged-in users.
Updated by auth login/logout routes and SocketIO user_logged_out events.
"""
import threading

_lock = threading.Lock()
_online_emails: set = set()


def mark_online(email: str) -> None:
    with _lock:
        _online_emails.add(email)


def mark_offline(email: str) -> None:
    with _lock:
        _online_emails.discard(email)


def get_online_emails() -> set:
    with _lock:
        return set(_online_emails)
