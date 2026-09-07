"""Compatibility import for the application's single auth dependency."""

from security.auth import get_current_user

__all__ = ["get_current_user"]