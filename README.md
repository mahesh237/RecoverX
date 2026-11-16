# RecoverX

RecoverX is a free, local-first desktop data recovery project. The MVP provides a PySide6 dashboard, disk-image selection and validation, scripted PhotoRec scans on disk images, a separate destination workflow, scan cancellation, recovered-file discovery, and automated tests.

## Current status

The application currently supports image-only PhotoRec file carving when PhotoRec/TestDisk is separately installed and on PATH. Physical-device scanning, preview, history, and other engines are not implemented. PhotoRec does not expose a reliable percentage in scripted mode; RecoverX shows an indeterminate scan state and lists files actually created by PhotoRec.

Only non-empty image files with extensions IMG, DD, RAW, DMG, E01, 001, or ISO can currently be selected. Selection checks do not certify that a particular PhotoRec build can parse each format. PhotoRec 7.2 has been verified with raw `.img` input; CI repeats a real JPEG carve against PhotoRec on Ubuntu.

## Requirements

- Windows 10/11
- Python 3.10 or newer (developed with Python 3.11)
- PhotoRec/TestDisk installed separately; obtain it from [CGSecurity](https://www.cgsecurity.org/wiki/TestDisk_Download)

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

Unit tests use temporary files and do not access physical drives. CI also installs PhotoRec on Ubuntu and recovers a generated JPEG fixture from a disposable raw image, writing output to a separate `/dev/shm` filesystem. Set `RECOVERX_RUN_PHOTOREC_TESTS=1`, `RECOVERX_PHOTOREC` (optional executable path), and `RECOVERX_PHOTOREC_TEST_DESTINATION` (a different volume) to run that integration test locally.

## Safety

RecoverX does not format, initialize, repair, or write to source images. The current PhotoRec adapter accepts a regular image file only and refuses a destination on the same storage device. It invokes PhotoRec with a separate output folder. Software read-only handling does not replace a hardware write blocker. Review PhotoRec's recovery options and output before using results.

## Architecture

- `ui/`: PySide6 interface
- `services/`: disk image validation
- `engines/`: isolated external engine adapters
- `core/`: shared application services such as logging
- `tests/`: temporary-file unit tests

See [docs/architecture.md](docs/architecture.md) and [docs/user-manual.md](docs/user-manual.md) for current behavior and limitations.

## Licensing

RecoverX project code is offered under the MIT License; see [LICENSE](LICENSE). Third-party tools are separate programs with their own licenses and are not included in this repository. See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). Verify each tool's license and distribution terms before packaging.
