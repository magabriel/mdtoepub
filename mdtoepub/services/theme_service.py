import os
import re
import shutil
from pathlib import Path
from typing import List, Optional
from ..models.theme import Theme
from .yaml_service import YamlService


COMPONENT_TYPES = [
    "acknowledgement", "afterword", "appendix", "author",
    "chapter", "conclusion", "cover", "dedication",
    "edition", "epilogue", "foreword", "glossary",
    "introduction", "license", "lof", "lot",
    "part", "preface", "prologue", "title", "toc",
]

BLANK_STYLE_CSS = """/* Base styles */
body {
    font-family: var(--font-serif, Georgia, serif);
    line-height: 1.6;
    margin: 0;
    padding: 0;
}

p {
    text-indent: 1.5em;
    margin: 0;
}

h1, h2, h3, h4, h5, h6 {
    font-family: var(--font-sans, Helvetica, sans-serif);
    font-weight: bold;
    page-break-after: avoid;
}
"""


class ThemeService:
    """Manages theme discovery, creation, cloning, and lifecycle.

    Themes are stored in two locations:
    - Built-in: ``mdtoepub/themes/`` (read-only)
    - Custom: ``~/.config/mdtoepub/themes/`` (full CRUD)
    """

    BUILTIN_DIR = Path(__file__).parent.parent / "themes"
    CUSTOM_DIR = Path.home() / ".config" / "mdtoepub" / "themes"

    @classmethod
    def _ensure_custom_dir(cls) -> Path:
        """Ensure the custom themes directory exists."""
        cls.CUSTOM_DIR.mkdir(parents=True, exist_ok=True)
        return cls.CUSTOM_DIR

    @classmethod
    def list_themes(cls) -> List[Theme]:
        """List all available themes (built-in + custom).

        Returns:
            List of Theme instances.
        """
        themes = []

        if cls.BUILTIN_DIR.exists():
            for d in sorted(cls.BUILTIN_DIR.iterdir()):
                if d.is_dir():
                    theme_yaml = d / "theme.yaml"
                    if theme_yaml.exists():
                        data = YamlService.load(str(theme_yaml))
                        themes.append(Theme(
                            id=data.get("id", d.name),
                            name=data.get("name", d.name),
                            description=data.get("description", ""),
                            is_builtin=True,
                            source_theme_id=data.get("source_theme_id"),
                            author=data.get("author", ""),
                            version=data.get("version", "1.0"),
                            base_style=data.get("base_style", "style.css"),
                            styles=data.get("styles", {}),
                            path=str(d),
                        ))

        cls._ensure_custom_dir()
        for d in sorted(cls.CUSTOM_DIR.iterdir()):
            if d.is_dir():
                theme_yaml = d / "theme.yaml"
                if theme_yaml.exists():
                    data = YamlService.load(str(theme_yaml))
                    themes.append(Theme(
                        id=data.get("id", d.name),
                        name=data.get("name", d.name),
                        description=data.get("description", ""),
                        is_builtin=False,
                        source_theme_id=data.get("source_theme_id"),
                        author=data.get("author", ""),
                        version=data.get("version", "1.0"),
                        base_style=data.get("base_style", "style.css"),
                        styles=data.get("styles", {}),
                        path=str(d),
                    ))

        return themes

    @classmethod
    def get_theme(cls, theme_id: str) -> Optional[Theme]:
        """Get a theme by its ID.

        Args:
            theme_id: Unique theme identifier.

        Returns:
            Theme instance, or None if not found.
        """
        for theme in cls.list_themes():
            if theme.id == theme_id:
                return theme
        return None

    @classmethod
    def get_theme_path(cls, theme_id: str) -> Optional[str]:
        """Get the filesystem path for a theme.

        Args:
            theme_id: Unique theme identifier.

        Returns:
            Path string, or None if theme not found.
        """
        theme = cls.get_theme(theme_id)
        return theme.path if theme else None

    @classmethod
    def is_builtin(cls, theme_id: str) -> bool:
        """Check if a theme is built-in (read-only).

        Args:
            theme_id: Unique theme identifier.

        Returns:
            True if the theme is built-in or not found.
        """
        theme = cls.get_theme(theme_id)
        return theme.is_builtin if theme else True

    @classmethod
    def theme_exists(cls, theme_id: str) -> bool:
        """Check if a theme exists.

        Args:
            theme_id: Unique theme identifier.

        Returns:
            True if the theme exists.
        """
        return cls.get_theme(theme_id) is not None

    @classmethod
    def create_blank(cls, name: str, description: str = "", author: str = "") -> Optional[Theme]:
        """Create a new blank custom theme.

        Args:
            name: Display name for the theme.
            description: Optional description.
            author: Optional author name.

        Returns:
            The created Theme, or None if ID collision or invalid name.
        """
        theme_id = cls._slugify(name)
        if not theme_id:
            return None
        if cls.theme_exists(theme_id):
            return None

        dest = cls._ensure_custom_dir() / theme_id
        dest.mkdir(parents=True, exist_ok=True)

        styles = {t: "style.css" for t in COMPONENT_TYPES}
        yaml_data = {
            "id": theme_id,
            "name": name,
            "description": description,
            "author": author,
            "version": "1.0",
            "base_style": "style.css",
            "styles": styles,
        }
        YamlService.save(yaml_data, str(dest / "theme.yaml"))

        (dest / "style.css").write_text(BLANK_STYLE_CSS, encoding="utf-8")

        return cls.get_theme(theme_id)

    @classmethod
    def clone_theme(cls, source_id: str, new_name: str,
                    description: str = "", author: str = "") -> Optional[Theme]:
        """Clone an existing theme to a new custom theme.

        Args:
            source_id: ID of the theme to clone.
            new_name: Display name for the new theme.
            description: Optional description override.
            author: Optional author override.

        Returns:
            The cloned Theme, or None if source not found or ID collision.
        """
        source = cls.get_theme(source_id)
        if not source:
            return None

        new_id = cls._slugify(new_name)
        if not new_id:
            return None
        if cls.theme_exists(new_id):
            return None

        dest = cls._ensure_custom_dir() / new_id
        shutil.copytree(source.path, dest)

        yaml_path = dest / "theme.yaml"
        data = YamlService.load(str(yaml_path))
        data["id"] = new_id
        data["name"] = new_name
        data["source_theme_id"] = source_id
        if description:
            data["description"] = description
        if author:
            data["author"] = author
        data.pop("is_builtin", None)
        YamlService.save(data, str(yaml_path))

        return cls.get_theme(new_id)

    @classmethod
    def delete_theme(cls, theme_id: str) -> bool:
        """Delete a custom theme. Built-in themes cannot be deleted.

        Args:
            theme_id: ID of the theme to delete.

        Returns:
            True on success, False if theme is built-in or not found.
        """
        theme = cls.get_theme(theme_id)
        if not theme or theme.is_builtin:
            return False
        shutil.rmtree(theme.path)
        return True

    @classmethod
    def rename_theme(cls, theme_id: str, new_name: str) -> bool:
        """Rename a custom theme. Built-in themes cannot be renamed.

        Args:
            theme_id: ID of the theme to rename.
            new_name: New display name.

        Returns:
            True on success, False if theme is built-in or not found.
        """
        theme = cls.get_theme(theme_id)
        if not theme or theme.is_builtin:
            return False
        yaml_path = Path(theme.path) / "theme.yaml"
        data = YamlService.load(str(yaml_path))
        data["name"] = new_name
        YamlService.save(data, str(yaml_path))
        return True

    @classmethod
    def export_theme(cls, theme_id: str, output_path: str) -> bool:
        """Export a theme as a .mdtotheme ZIP file.

        Args:
            theme_id: ID of the theme to export.
            output_path: Destination path for the ZIP file.

        Returns:
            True on success, False on error.
        """
        import tempfile
        import zipfile

        theme = cls.get_theme(theme_id)
        if not theme or not theme.path:
            return False

        theme_dir = Path(theme.path)
        if not theme_dir.is_dir():
            return False

        try:
            with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                for file_path in sorted(theme_dir.rglob('*')):
                    if file_path.is_file():
                        arcname = file_path.relative_to(theme_dir)
                        zf.write(str(file_path), str(arcname))
            return True
        except Exception:
            return False

    @classmethod
    def import_theme(cls, archive_path: str) -> Optional[Theme]:
        """Import a theme from a .mdtotheme ZIP file.

        If a theme with the same ID already exists, a numeric suffix is added.

        Args:
            archive_path: Path to the .mdtotheme ZIP file.

        Returns:
            The imported Theme on success, None on failure.
        """
        import tempfile
        import zipfile

        archive = Path(archive_path)
        if not archive.is_file():
            return None

        try:
            with tempfile.TemporaryDirectory() as tmp:
                with zipfile.ZipFile(str(archive), 'r') as zf:
                    zf.extractall(tmp)

                tmp_path = Path(tmp)
                yaml_file = tmp_path / "theme.yaml"
                if not yaml_file.exists():
                    return None

                data = YamlService.load(str(yaml_file))
                theme_id = data.get("id", "")
                if not theme_id:
                    return None
                if "name" not in data:
                    return None

                if cls.theme_exists(theme_id):
                    base_id = theme_id
                    counter = 1
                    while cls.theme_exists(theme_id):
                        theme_id = f"{base_id}-{counter}"
                        counter += 1
                    data["id"] = theme_id

                cls._ensure_custom_dir()
                dest_dir = cls.CUSTOM_DIR / theme_id
                dest_dir.mkdir(parents=True, exist_ok=True)

                for item in tmp_path.glob('*'):
                    src = tmp_path / item.name
                    dst = dest_dir / item.name
                    if src.is_file():
                        shutil.copy2(str(src), str(dst))

                dest_yaml = dest_dir / "theme.yaml"
                imported = YamlService.load(str(dest_yaml))
                imported["id"] = theme_id
                imported.pop("is_builtin", None)
                YamlService.save(imported, str(dest_yaml))

                return cls.get_theme(theme_id)
        except Exception:
            return None

    @staticmethod
    def _slugify(text: str) -> str:
        """Convert text to a safe theme ID (lowercase, hyphens)."""
        s = text.lower().strip()
        s = re.sub(r'[^\w\s-]', '', s)
        s = re.sub(r'[-\s]+', '-', s)
        s = s.strip('-')
        return s or ""
