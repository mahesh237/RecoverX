from __future__ import annotations

import hashlib
import os
import threading
from pathlib import Path

import pytest

from services.recovery_copy import copy_recovered_files


def _mark_destination_as_other_volume(monkeypatch: pytest.MonkeyPatch, destination: Path) -> None:
    original_stat = Path.stat
    resolved_destination = destination.resolve()

    def different_volume(path: Path, *args: object, **kwargs: object) -> os.stat_result:
        result = original_stat(path, *args, **kwargs)
        if path == resolved_destination:
            return os.stat_result((*result[:2], result.st_dev + 1, *result[3:]))
        return result

    monkeypatch.setattr(Path, "stat", different_volume)


def test_copy_verifies_hash_and_avoids_overwrite(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    recovery_root = tmp_path / "recovered"
    destination = tmp_path / "destination"
    image = tmp_path / "source.img"
    recovery_root.mkdir()
    destination.mkdir()
    image.write_bytes(b"test image")
    source = recovery_root / "photo.jpg"
    contents = b"recovered bytes" * 1000
    source.write_bytes(contents)
    (destination / source.name).write_bytes(b"keep existing file")
    _mark_destination_as_other_volume(monkeypatch, destination)

    report = copy_recovered_files(
        [source], recovery_root=recovery_root, source_image=image, destination=destination,
    )

    assert not report.failed
    assert len(report.copied) == 1
    record = report.copied[0]
    assert record.destination.name == "photo (1).jpg"
    assert record.destination.read_bytes() == contents
    assert record.size_bytes == len(contents)
    assert record.sha256 == hashlib.sha256(contents).hexdigest()
    assert (destination / source.name).read_bytes() == b"keep existing file"


def test_copy_refuses_original_image_volume(tmp_path: Path) -> None:
    recovery_root = tmp_path / "recovered"
    destination = tmp_path / "destination"
    image = tmp_path / "source.img"
    recovery_root.mkdir()
    destination.mkdir()
    image.write_bytes(b"test image")
    source = recovery_root / "result.bin"
    source.write_bytes(b"recovered")

    with pytest.raises(ValueError, match="different storage device"):
        copy_recovered_files(
            [source], recovery_root=recovery_root, source_image=image, destination=destination,
        )


def test_copy_refuses_files_outside_current_results(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    recovery_root = tmp_path / "recovered"
    destination = tmp_path / "destination"
    image = tmp_path / "source.img"
    recovery_root.mkdir()
    destination.mkdir()
    image.write_bytes(b"test image")
    outside = tmp_path / "outside.bin"
    outside.write_bytes(b"not a result")
    _mark_destination_as_other_volume(monkeypatch, destination)

    with pytest.raises(ValueError, match="outside the current recovery"):
        copy_recovered_files(
            [outside], recovery_root=recovery_root, source_image=image, destination=destination,
        )


def test_copy_can_be_cancelled_before_start(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    recovery_root = tmp_path / "recovered"
    destination = tmp_path / "destination"
    image = tmp_path / "source.img"
    recovery_root.mkdir()
    destination.mkdir()
    image.write_bytes(b"test image")
    source = recovery_root / "result.bin"
    source.write_bytes(b"recovered")
    _mark_destination_as_other_volume(monkeypatch, destination)
    cancel_event = threading.Event()
    cancel_event.set()

    report = copy_recovered_files(
        [source], recovery_root=recovery_root, source_image=image,
        destination=destination, cancel_event=cancel_event,
    )

    assert report.cancelled
    assert not report.copied
    assert not list(destination.iterdir())
