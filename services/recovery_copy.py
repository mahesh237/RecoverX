"""Safe copy and integrity verification for PhotoRec result files."""

from __future__ import annotations

import hashlib
import logging
import os
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Callable, Iterable

log = logging.getLogger(__name__)
CHUNK_SIZE = 1024 * 1024


@dataclass(frozen=True)
class CopyRecord:
    source: Path
    destination: Path
    size_bytes: int
    sha256: str


@dataclass(frozen=True)
class CopyFailure:
    source: Path
    message: str


@dataclass(frozen=True)
class CopyReport:
    copied: tuple[CopyRecord, ...]
    failed: tuple[CopyFailure, ...]
    cancelled: bool


def _reserve_destination(directory: Path, filename: str) -> tuple[Path, BinaryIO]:
    name = Path(filename)
    for index in range(10_000):
        candidate_name = filename if index == 0 else f"{name.stem} ({index}){name.suffix}"
        candidate = directory / candidate_name
        try:
            handle = candidate.open("xb")
            return candidate, handle
        except FileExistsError:
            continue
    raise FileExistsError(f"Could not choose a non-conflicting name for {filename}.")


def copy_recovered_files(
    files: Iterable[Path],
    *,
    recovery_root: Path,
    source_image: Path,
    destination: Path,
    cancel_event: threading.Event | None = None,
    on_progress: Callable[[int, int, Path], None] | None = None,
) -> CopyReport:
    """Copy selected result files to a different device and verify each hash."""
    recovery_root = recovery_root.expanduser().resolve(strict=True)
    source_image = source_image.expanduser().resolve(strict=True)
    destination = destination.expanduser().resolve(strict=True)
    if not recovery_root.is_dir():
        raise ValueError("The recovery results folder is unavailable.")
    if not destination.is_dir() or not os.access(destination, os.W_OK):
        raise ValueError("Choose an existing writable destination folder.")
    if not source_image.is_file():
        raise ValueError("The original disk image is unavailable.")
    if destination.stat().st_dev == source_image.stat().st_dev:
        raise ValueError("Choose a copy destination on a different storage device from the original image.")
    if destination == recovery_root or recovery_root in destination.parents:
        raise ValueError("Choose a copy destination outside the PhotoRec results folder.")

    selected: list[Path] = []
    seen: set[Path] = set()
    for path in files:
        if path.is_symlink():
            raise ValueError(f"Recovered result is a symbolic link and cannot be copied: {path}")
        resolved = path.expanduser().resolve(strict=True)
        if not resolved.is_file() or not resolved.is_relative_to(recovery_root):
            raise ValueError(f"Selected file is outside the current recovery results: {path}")
        if resolved not in seen:
            selected.append(resolved)
            seen.add(resolved)
    if not selected:
        raise ValueError("Select at least one recovered file to copy.")

    copied: list[CopyRecord] = []
    failed: list[CopyFailure] = []
    cancelled = False
    total = len(selected)
    for index, source in enumerate(selected, start=1):
        if cancel_event is not None and cancel_event.is_set():
            cancelled = True
            break
        if on_progress is not None:
            on_progress(index, total, source)
        target: Path | None = None
        try:
            source_digest = hashlib.sha256()
            size = 0
            target, output = _reserve_destination(destination, source.name)
            with output:
                with source.open("rb") as input_stream:
                    while chunk := input_stream.read(CHUNK_SIZE):
                        if cancel_event is not None and cancel_event.is_set():
                            cancelled = True
                            raise InterruptedError("Copy cancelled.")
                        output.write(chunk)
                        source_digest.update(chunk)
                        size += len(chunk)
                    output.flush()
                    os.fsync(output.fileno())

            copied_digest = hashlib.sha256()
            copied_size = 0
            with target.open("rb") as copied_stream:
                while chunk := copied_stream.read(CHUNK_SIZE):
                    copied_digest.update(chunk)
                    copied_size += len(chunk)
            expected_hash = source_digest.hexdigest()
            if copied_size != size or copied_digest.hexdigest() != expected_hash:
                raise OSError("Copied file failed size or SHA-256 verification.")
            record = CopyRecord(source, target, size, expected_hash)
            copied.append(record)
            log.info("Verified recovery copy: source=%s destination=%s bytes=%d sha256=%s", source, target, size, expected_hash)
        except Exception as exc:
            if target is not None:
                target.unlink(missing_ok=True)
            failed.append(CopyFailure(source, str(exc)))
            log.exception("Could not copy recovered file %s", source)
            if isinstance(exc, InterruptedError):
                cancelled = True
                break

    return CopyReport(tuple(copied), tuple(failed), cancelled)
