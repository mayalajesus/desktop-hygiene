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

- `organizer.py`: AI-assisted file/folder organization, profiles, reports, undo.
- `safe_cleaner.py`: conservative Windows temp/cache cleaner.
- `rules.json`: base configuration.
- `profiles/`: small overrides for common folders.

