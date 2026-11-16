import os
import io
import threading
from pathlib import Path

import pytest

from services.image_service import validate_image
from engines.photorec import PhotoRecAdapter


def test_valid_image_is_resolved(tmp_path: Path) -> None:
    image = tmp_path / "sample.img"
    image.write_bytes(b"disk image")
    assert validate_image(image) == image.resolve()


def test_empty_image_is_rejected(tmp_path: Path) -> None:
    image = tmp_path / "empty.dd"
    image.touch()
    with pytest.raises(ValueError, match="empty"):
        validate_image(image)


def test_unsupported_extension_is_rejected(tmp_path: Path) -> None:
    image = tmp_path / "notes.txt"
    image.write_text("not an image")
    with pytest.raises(ValueError, match="Unsupported"):
        validate_image(image)


def test_missing_image_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        validate_image(tmp_path / "missing.img")


def test_source_file_cannot_be_destination(tmp_path: Path) -> None:
    image = tmp_path / "sample.img"
    image.write_bytes(b"data")
    with pytest.raises(ValueError, match="existing folder"):
        PhotoRecAdapter.validate_inputs(image, image)


def test_same_storage_device_is_rejected(tmp_path: Path) -> None:
    image = tmp_path / "source.img"
    destination = tmp_path / "recovered"
    image.write_bytes(b"data")
    destination.mkdir()
    with pytest.raises(ValueError, match="different storage device"):
        PhotoRecAdapter.validate_inputs(image, destination)


def test_photo_rec_command_uses_documented_image_script(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    image = tmp_path / "source.img"
    destination = tmp_path / "other-volume"
    executable = tmp_path / "photorec.exe"
    image.write_bytes(b"disk image")
    destination.mkdir()
    executable.touch()

    original_stat = Path.stat

    def different_volume(path: Path, *args: object, **kwargs: object) -> os.stat_result:
        result = original_stat(path, *args, **kwargs)
        if path == destination:
            return os.stat_result((*result[:2], result.st_dev + 1, *result[3:]))
        return result

    monkeypatch.setattr(Path, "stat", different_volume)
    adapter = PhotoRecAdapter(executable)
    run_directory = destination / "RecoverX_test"
    command = adapter.build_command(image, destination, run_directory)
    assert command == [
        str(executable), "/log", "/logname", str(run_directory / "photorec.log"),
        "/d", str(run_directory), "/cmd", str(image), "partition_none,fileopt,everything,enable,search",
    ]


def test_cancel_terminates_running_process(tmp_path: Path) -> None:
    class FakeProcess:
        terminated = False

        @staticmethod
        def poll() -> None:
            return None

        def terminate(self) -> None:
            self.terminated = True

    adapter = PhotoRecAdapter(tmp_path / "photorec.exe")
    process = FakeProcess()
    adapter._process = process  # type: ignore[assignment]
    adapter.cancel()
    assert process.terminated


def test_scan_reports_cancel_requested_before_output(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    image = tmp_path / "source.img"
    destination = tmp_path / "destination"
    executable = tmp_path / "photorec.exe"
    image.write_bytes(b"disk image")
    destination.mkdir()
    executable.touch()
    adapter = PhotoRecAdapter(executable)
    monkeypatch.setattr(adapter, "validate_inputs", lambda source, target: (source, target))
    monkeypatch.setattr(adapter, "build_command", lambda source, target, output: [str(executable)])

    class FakeProcess:
        stdout = io.StringIO("")

        def __init__(self) -> None:
            self.terminated = False

        def terminate(self) -> None:
            self.terminated = True

        @staticmethod
        def wait(timeout: int | None = None) -> int:
            return -15

    process = FakeProcess()
    monkeypatch.setattr("engines.photorec.subprocess.Popen", lambda *args, **kwargs: process)
    cancel_event = threading.Event()
    cancel_event.set()

    result = adapter.scan(image, destination, cancel_event=cancel_event)

    assert result.cancelled
    assert process.terminated
