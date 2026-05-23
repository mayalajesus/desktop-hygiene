# Contributing

This project intentionally stays small: standard-library Python, JSON config, and safe CLI defaults.

## Design Principles

- Dry-run by default. Mutating commands require `--apply`.
- Do not send file contents to AI. Use names, metadata, and folder previews only.
- Treat AI output as untrusted. Normalize and validate before moving anything.
- Keep cleanup conservative. Avoid personal files and skip symlinks/junctions.
- Prefer readable CLI output plus complete logs/reports.

## Local Checks

```powershell
python -m py_compile organizer.py safe_cleaner.py
python organizer.py --doctor --no-ai
python safe_cleaner.py --only temp --older-than-days 9999
```

## Files

- `desktop_hygiene/`: application code.
- `config/rules.json`: base taxonomy and safety rules.
- `config/profiles/`: small overrides for common folders.
- `organizer.py`: beginner-friendly organizer shortcut.
- `safe_cleaner.py`: beginner-friendly cleaner shortcut.
- `pyproject.toml`: Python project identity and optional CLI entry points.
