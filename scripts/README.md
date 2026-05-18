# Scripts Layout

This repository now keeps operational scripts under `scripts/` by purpose instead of mixing ad hoc files at the top level.

## Primary directories

- `launchers/`: start, stop, restart, and local runtime entrypoints.
- `maintenance/`: cleanup, diagnostics, and repair scripts.
- `packaging/`: packaged build and service build workflows.
- `release/`: release preparation scripts.
- `tests/`: manual and integration verification scripts moved from the old `Test/` folder.
- `dev/`: developer utilities and one-off local helpers.
- `fixes/`: targeted repair scripts.
- `utilities/`: shared inspection or support scripts.
- `legacy/`: archived historical entrypoints kept for reference only.

## Root entrypoints

Use the repo-root wrappers for the common lifecycle commands:

```powershell
.\start.bat
.\stop.bat
```

More targeted launchers live under `scripts\launchers\`.
