import shutil
from pathlib import Path
from typing import List, Optional
from PIL import Image


SUPPORTED_FORMATS = {".jpg", ".jpeg", ".png", ".gif"}


class ImageService:
    """Image validation, optimization, and file operations."""

    @staticmethod
    def validate_image(file_path: str) -> bool:
        """Check if a file is a supported image format.

        Args:
            file_path: Path to the image file.

        Returns:
            True if the file exists and has a supported extension.
        """
        path = Path(file_path)
        if not path.exists():
            return False
        return path.suffix.lower() in SUPPORTED_FORMATS

    @staticmethod
    def get_supported_formats() -> List[str]:
        """Return the list of supported image file extensions.

        Returns:
            List of extension strings (e.g. [".jpg", ".png"]).
        """
        return list(SUPPORTED_FORMATS)

    @staticmethod
    def get_image_info(file_path: str) -> Optional[dict]:
        """Get image metadata (dimensions, format, mode).

        Args:
            file_path: Path to the image file.

        Returns:
            Dict with width, height, format, mode keys, or None on error.
        """
        try:
            with Image.open(file_path) as img:
                return {
                    "width": img.width,
                    "height": img.height,
                    "format": img.format,
                    "mode": img.mode,
                }
        except Exception:
            return None

    @staticmethod
    def optimize_for_epub(
        input_path: str, output_path: str, max_width: int = 1200, quality: int = 85
    ) -> bool:
        """Optimize an image for EPUB: resize if too wide, convert to JPEG.

        Args:
            input_path: Source image path.
            output_path: Destination path for optimized JPEG.
            max_width: Maximum width in pixels (resizes if larger).
            quality: JPEG quality (1-100).

        Returns:
            True on success, False on error.
        """
        try:
            with Image.open(input_path) as img:
                if img.width > max_width:
                    ratio = max_width / img.width
                    new_height = int(img.height * ratio)
                    img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)

                if img.mode == "RGBA":
                    background = Image.new("RGB", img.size, (255, 255, 255))
                    background.paste(img, mask=img.split()[3])
                    img = background
                elif img.mode != "RGB":
                    img = img.convert("RGB")

                img.save(output_path, "JPEG", quality=quality, optimize=True)
                return True
        except Exception:
            return False

    @staticmethod
    def copy_to_project(
        source_path: str, project_images_dir: str, category: str = "illustrations"
    ) -> Optional[str]:
        """Copy an image file to the project's images directory.

        Args:
            source_path: Path to the source image.
            project_images_dir: Path to the project's images directory.
            category: Subdirectory name (e.g. "illustrations" or "decorative").

        Returns:
            Destination path on success, None on error.
        """
        source = Path(source_path)
        if not source.exists():
            return None

        dest_dir = Path(project_images_dir) / category
        dest_dir.mkdir(parents=True, exist_ok=True)

        dest_path = dest_dir / source.name

        try:
            with Image.open(source) as img:
                img.save(dest_path)
            return str(dest_path)
        except Exception:
            return None

    @staticmethod
    def delete_image(image_path: str) -> bool:
        """Delete an image file.

        Args:
            image_path: Path to the image file to delete.

        Returns:
            True on success, False on error.
        """
        path = Path(image_path)
        try:
            path.unlink()
            return True
        except Exception:
            return False

    @staticmethod
    def rename_image(old_path: str, new_name: str) -> Optional[str]:
        """Rename an image file.

        Args:
            old_path: Current path to the image file.
            new_name: New filename (not full path).

        Returns:
            New path on success, None if new name already exists or on error.
        """
        old = Path(old_path)
        new = old.parent / new_name
        if new.exists():
            return None
        try:
            old.rename(new)
            return str(new)
        except Exception:
            return None
