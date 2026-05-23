"""Compatibility entry point for the desktop organizer CLI.

Keep using:

    python organizer.py

The implementation lives in ``desktop_hygiene.organizer`` so the project can
stay organized without making the command harder for beginners.
"""

from __future__ import annotations

from desktop_hygiene.organizer import run_cli


if __name__ == "__main__":
    raise SystemExit(run_cli())
