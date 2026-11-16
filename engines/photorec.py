"""PhotoRec availability and safe command-line adapter.

PhotoRec is interactive on Windows and its CLI switches differ by release.
This adapter detects an installation but intentionally does not guess at
automation flags or claim that a scan completed. Supported versions must be
invoked with the documented command line after validating the installed build.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class EngineStatus:
    available: bool
    executable: Path | None
    version: str | None
    message: str


class PhotoRecAdapter:
    """Detect PhotoRec; keep engine execution explicit and image-scoped."""

    CANDIDATES = ("photorec", "photorec_win", "photorec.exe", "photorec_win.exe")

    def __init__(self, executable: str | Path | None = None) -> None:
        self.executable = Path(executable) if executable else self._find_executable()

    @classmethod
    def _find_executable(cls) -> Path | None:
        for candidate in cls.CANDIDATES:
            found = shutil.which(candidate)
            if found:
                return Path(found)
        return None

    def status(self) -> EngineStatus:
        if self.executable is None or not self.executable.is_file():
            return EngineStatus(False, None, None, "PhotoRec was not found. Install TestDisk from cgsecurity.org and restart RecoverX.")
        try:
            result = subprocess.run([str(self.executable), "/version"], capture_output=True, text=True, timeout=5, check=False)
            output = (result.stdout + " " + result.stderr).strip()
            version = output[:160] if output else None
            return EngineStatus(True, self.executable, version, "PhotoRec executable detected; CLI compatibility must be verified for this build.")
        except (OSError, subprocess.TimeoutExpired) as exc:
            return EngineStatus(True, self.executable, None, f"PhotoRec detected; version check unavailable ({exc}).")

    @staticmethod
    def validate_inputs(image: Path, destination: Path) -> None:
        image = image.expanduser().resolve(strict=True)
        destination = destination.expanduser().resolve(strict=False)
        if not image.is_file():
            raise ValueError("The source must be a disk image file.")
        if image == destination or image in destination.parents:
            raise ValueError("Choose a recovery destination outside the source image.")
        if destination == image.parent and destination.exists():
            raise ValueError("Choose a separate recovery destination folder.")
        if not os.access(image, os.R_OK):
            raise ValueError("The image is not readable.")

    def run(self, image: Path, destination: Path) -> subprocess.Popen[str]:
        """Launch only when compatibility is known; avoid unsafe guessed switches."""
        self.validate_inputs(image, destination)
        status = self.status()
        if not status.available or status.executable is None:
            raise RuntimeError(status.message)
        raise RuntimeError("Automated PhotoRec scanning is unavailable: supported Windows CLI arguments have not yet been verified. No scan was started.")
