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


def test_source_cannot_be_recovery_destination(tmp_path: Path) -> None:
    image = tmp_path / "sample.img"
    image.write_bytes(b"data")
    with pytest.raises(ValueError, match="outside"):
        PhotoRecAdapter.validate_inputs(image, image)
