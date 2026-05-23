"""Compatibility entry point for the safe Windows cleaner CLI.

Keep using:

    python safe_cleaner.py

The implementation lives in ``desktop_hygiene.safe_cleaner``.
"""

from __future__ import annotations

from desktop_hygiene.safe_cleaner import run_cli


if __name__ == "__main__":
    raise SystemExit(run_cli())
