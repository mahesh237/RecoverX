"""Opt-in real-engine test; CI uses tmpfs and local runs can select another volume."""

from __future__ import annotations

from io import BytesIO
import os
import shutil
import tempfile
from pathlib import Path

import pytest
from PIL import Image

from engines.photorec import PhotoRecAdapter


@pytest.mark.skipif(
    os.environ.get("RECOVERX_RUN_PHOTOREC_TESTS") != "1",
    reason="set RECOVERX_RUN_PHOTOREC_TESTS=1 to run the real PhotoRec integration test",
)
@pytest.mark.skipif(
    not os.environ.get("RECOVERX_PHOTOREC") and not shutil.which("photorec"),
    reason="PhotoRec is not installed",
)
@pytest.mark.skipif(
    not os.environ.get("RECOVERX_PHOTOREC_TEST_DESTINATION") and not Path("/dev/shm").is_dir(),
    reason="set a separate-volume destination or run on a system with /dev/shm",
)
def test_photorec_recovers_jpeg_from_raw_image(tmp_path: Path) -> None:
    image = tmp_path / "jpeg_fixture.img"
    jpeg = BytesIO()
    Image.new("RGB", (128, 128), color=(32, 160, 220)).save(jpeg, format="JPEG", quality=90)
    image.write_bytes(b"recoverx-test-prefix" * 512 + jpeg.getvalue() + b"recoverx-test-suffix" * 512)
    destination_parent = Path(
        os.environ.get("RECOVERX_PHOTOREC_TEST_DESTINATION", "/dev/shm")
    ).resolve(strict=True)
    destination = Path(tempfile.mkdtemp(prefix="recoverx-test-", dir=destination_parent))
    try:
        assert image.stat().st_dev != destination.stat().st_dev
        result = PhotoRecAdapter(os.environ.get("RECOVERX_PHOTOREC")).scan(image, destination)
        assert not result.cancelled
        assert result.return_code == 0
        jpeg_files = [path for path in result.recovered_files if path.suffix.lower() in {".jpg", ".jpeg"}]
        assert jpeg_files, f"PhotoRec completed without recovering a JPEG: {result.output_directory}"
        assert any(path.read_bytes().startswith(b"\xff\xd8") for path in jpeg_files)
    finally:
        shutil.rmtree(destination, ignore_errors=True)
