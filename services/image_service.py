"""Disk-image selection helpers."""

from pathlib import Path

SUPPORTED_IMAGE_SUFFIXES = {".img", ".dd", ".raw", ".dmg", ".e01", ".001", ".iso"}


def validate_image(path: Path) -> Path:
    resolved = path.expanduser().resolve(strict=True)
    if not resolved.is_file():
        raise ValueError("Select a disk image file.")
    if resolved.suffix.lower() not in SUPPORTED_IMAGE_SUFFIXES:
        raise ValueError("Unsupported image extension. Choose IMG, DD, RAW, DMG, E01, 001, or ISO.")
    if not resolved.stat().st_size:
        raise ValueError("The selected image is empty.")
    return resolved
