import pytest
import tempfile
from pathlib import Path
from mdtoepub.services.image_service import ImageService


class TestImageService:
    def test_delete_image(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "test.png"
            f.write_bytes(b"fake-png")
            assert f.exists()
            assert ImageService.delete_image(str(f))
            assert not f.exists()

    def test_delete_missing(self):
        assert not ImageService.delete_image("/nonexistent/file.png")

    def test_rename_image(self):
        with tempfile.TemporaryDirectory() as tmp:
            old = Path(tmp) / "old.png"
            old.write_bytes(b"fake-png")
            result = ImageService.rename_image(str(old), "new.png")
            assert result is not None
            assert not old.exists()
            assert Path(result).name == "new.png"

    def test_rename_to_existing(self):
        with tempfile.TemporaryDirectory() as tmp:
            old = Path(tmp) / "old.png"
            old.write_bytes(b"fake-png-1")
            existing = Path(tmp) / "new.png"
            existing.write_bytes(b"fake-png-2")
            result = ImageService.rename_image(str(old), "new.png")
            assert result is None  # rename should fail
