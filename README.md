# RecoverX

RecoverX is a free, local-first desktop data recovery project. This repository currently contains an early MVP shell: a PySide6 dashboard, disk-image selection and validation, PhotoRec detection, logging, and basic automated tests.

## Current status

The application is **not yet a working recovery tool**. PhotoRec is not bundled or installed automatically. The adapter detects a PhotoRec executable, but scanning is deliberately disabled until the supported Windows command-line workflow and read-only behavior are verified. No progress or recovery results are fabricated. Physical-device scanning, result browsing, previews, and recovery history are not implemented.

Only non-empty image files with extensions IMG, DD, RAW, DMG, E01, 001, or ISO can currently be selected. This validates the selection flow; it does not assert support by PhotoRec for every image format.

## Requirements

- Windows 10/11
- Python 3.10 or newer (developed with Python 3.11)
- PhotoRec/TestDisk is optional for engine detection; obtain it from [CGSecurity](https://www.cgsecurity.org/wiki/TestDisk_Download)

## Setup and run

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
python main.py
```

If PowerShell blocks environment activation, run the environment interpreter directly:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe main.py
```

## Tests

```powershell
python -m pytest
```

Tests use temporary files and do not access physical drives.

## Safety

RecoverX does not format, initialize, repair, or write to storage devices. The current MVP only accepts image paths and has no scanner enabled. When scanning is implemented, recovered files must go to a separate destination. Software read-only handling does not replace a hardware write blocker.

## Architecture

- `ui/`: PySide6 interface
- `services/`: disk image validation
- `engines/`: isolated external engine adapters
- `core/`: shared application services such as logging
- `tests/`: temporary-file unit tests

See [docs/architecture.md](docs/architecture.md) and [docs/user-manual.md](docs/user-manual.md) for current behavior and limitations.

## Licensing

RecoverX project code is offered under the MIT License; see [LICENSE](LICENSE). Third-party tools are separate programs with their own licenses and are not included in this repository. See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). Verify each tool's license and distribution terms before packaging.
