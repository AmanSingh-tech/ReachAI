"""Compatibility import for the original ``uvicorn app.api:app`` command."""

from reachai.api import app

__all__ = ["app"]
