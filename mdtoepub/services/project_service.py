from pathlib import Path
from typing import Optional, Dict

from ..models.project import Project
from .yaml_service import YamlService


def _read_css_file(path: Path) -> str:
    """Read a CSS file, returning empty string if it doesn't exist."""
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


def _write_css_file(path: Path, content: str):
    """Write CSS content to a file. Removes the file if content is empty."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if content.strip():
        path.write_text(content, encoding="utf-8")
    elif path.exists():
        path.unlink()


def _load_css_from_files(project: Project):
    """Load CSS from styles/ directory into project attributes."""
    styles_dir = Path(project.path) / "styles"

    project.custom_css = _read_css_file(styles_dir / "book.css")

    types_dir = styles_dir / "types"
    if types_dir.exists():
        for css_file in types_dir.glob("*.css"):
            type_name = css_file.stem
            project.type_css_overrides[type_name] = css_file.read_text(encoding="utf-8")

    comp_dir = styles_dir / "components"
    if comp_dir.exists():
        comp_css: Dict[str, str] = {}
        for css_file in comp_dir.glob("*.css"):
            comp_css[css_file.stem] = css_file.read_text(encoding="utf-8")
        for component in project.components:
            component.custom_css = comp_css.get(component.id, "")


def _save_css_to_files(project: Project):
    """Save CSS from project attributes to styles/ directory."""
    styles_dir = Path(project.path) / "styles"
    styles_dir.mkdir(parents=True, exist_ok=True)

    _write_css_file(styles_dir / "book.css", project.custom_css)

    types_dir = styles_dir / "types"
    types_dir.mkdir(exist_ok=True)
    for type_name, css in project.type_css_overrides.items():
        _write_css_file(types_dir / f"{type_name}.css", css)
    for existing in types_dir.glob("*.css"):
        if existing.stem not in project.type_css_overrides:
            existing.unlink()

    comp_dir = styles_dir / "components"
    comp_dir.mkdir(exist_ok=True)
    for component in project.components:
        _write_css_file(comp_dir / f"{component.id}.css", component.custom_css)
    for existing in comp_dir.glob("*.css"):
        if existing.stem not in {c.id for c in project.components}:
            existing.unlink()


class ProjectService:
    """Manages project creation, loading, and saving."""

    @staticmethod
    def create_project_structure(path: str, project_name: str) -> Project:
        """Create a new project directory structure with default configuration.

        Args:
            path: Parent directory path.
            project_name: Name of the project (used as directory name).

        Returns:
            A new Project instance with default settings.
        """
        project_path = Path(path) / project_name
        project_path.mkdir(parents=True, exist_ok=True)
        (project_path / "components").mkdir(exist_ok=True)
        (project_path / "images" / "illustrations").mkdir(parents=True, exist_ok=True)
        (project_path / "images" / "decorative").mkdir(parents=True, exist_ok=True)
        (project_path / "styles" / "types").mkdir(parents=True, exist_ok=True)
        (project_path / "styles" / "components").mkdir(parents=True, exist_ok=True)
        (project_path / "output").mkdir(exist_ok=True)

        project = Project(
            name=project_name,
            path=str(project_path),
        )

        project_data = {
            "name": project.name,
            "title": project.title,
            "author": project.author,
            "language": project.language,
            "theme_id": project.theme_id,
            "epub_version": project.epub_version,
            "auto_chapter_title": "none",
            "chapter_numbering_style": "arabic",
            "auto_appendix_title": "none",
            "appendix_numbering_style": "arabic",
            "auto_part_title": "none",
            "part_numbering_style": "arabic",
            "drop_cap_enabled": True,
            "drop_cap_types": ["chapter"],
            "spell_lang": "en_US",
            "spell_words": [],
            "edition": "",
            "publication_date": "",
            "isbn": "",
            "publisher": "",
            "subtitle": "",
            "figure_numbering": False,
            "figure_numbering_style": "arabic",
            "table_numbering": False,
            "table_numbering_style": "arabic",
            "labels": {},
            "components": [],
            "parts": [],
        }

        YamlService.save(project_data, str(project_path / "project.yaml"))
        return project

    @staticmethod
    def load_project(project_path: str) -> Optional[Project]:
        """Load a project from a project.yaml file.

        Args:
            project_path: Directory containing project.yaml.

        Returns:
            Project instance, or None if project.yaml doesn't exist.
        """
        yaml_path = Path(project_path) / "project.yaml"
        if not yaml_path.exists():
            return None

        data = YamlService.load(str(yaml_path))
        project = Project(
            name=data.get("name", ""),
            title=data.get("title", ""),
            author=data.get("author", ""),
            language=data.get("language", "en"),
            theme_id=data.get("theme_id", "classic"),
            epub_version=data.get("epub_version", "epub3"),
            auto_chapter_title=data.get("auto_chapter_title", "none"),
            chapter_numbering_style=data.get("chapter_numbering_style", "arabic"),
            auto_appendix_title=data.get("auto_appendix_title", "none"),
            appendix_numbering_style=data.get("appendix_numbering_style", "arabic"),
            auto_part_title=data.get("auto_part_title", "none"),
            part_numbering_style=data.get("part_numbering_style", "arabic"),
            custom_css="",
            type_css_overrides=None,
            drop_cap_enabled=data.get("drop_cap_enabled", True),
            drop_cap_types=data.get("drop_cap_types", ["chapter"]),
            path=project_path,
            export_filename=data.get("export_filename", ""),
            spell_lang=data.get("spell_lang", "en_US"),
            spell_words=data.get("spell_words", []),
            edition=data.get("edition", ""),
            publication_date=data.get("publication_date", ""),
            isbn=data.get("isbn", ""),
            publisher=data.get("publisher", ""),
            subtitle=data.get("subtitle", ""),
            figure_numbering=data.get("figure_numbering", False),
            figure_numbering_style=data.get("figure_numbering_style", "arabic"),
            table_numbering=data.get("table_numbering", False),
            table_numbering_style=data.get("table_numbering_style", "arabic"),
            labels=data.get("labels", {}),
        )

        from ..models.component import Component, ComponentType

        for comp_data in data.get("components", []):
            type_str = comp_data.get("type", "chapter")
            try:
                component_type = ComponentType(type_str)
            except ValueError:
                component_type = ComponentType.CHAPTER
            component = Component(
                id=comp_data.get("id", ""),
                type=component_type,
                title=comp_data.get("title", ""),
                filename=comp_data.get("filename", ""),
                order=comp_data.get("order", 0),
                part_id=comp_data.get("part_id"),
                frontmatter=comp_data.get("frontmatter", {}),
                custom_css="",
            )
            project.components.append(component)

        if project.type_css_overrides is None:
            project.type_css_overrides = {}
        _load_css_from_files(project)

        return project

    @staticmethod
    def save_project(project: Project) -> bool:
        """Save project configuration to project.yaml and CSS files.

        Args:
            project: Project to save.

        Returns:
            True on success.
        """
        _save_css_to_files(project)

        project_data = {
            "name": project.name,
            "title": project.title,
            "author": project.author,
            "language": project.language,
            "theme_id": project.theme_id,
            "epub_version": project.epub_version,
            "auto_chapter_title": project.auto_chapter_title,
            "chapter_numbering_style": project.chapter_numbering_style,
            "auto_appendix_title": project.auto_appendix_title,
            "appendix_numbering_style": project.appendix_numbering_style,
            "auto_part_title": project.auto_part_title,
            "part_numbering_style": project.part_numbering_style,
            "drop_cap_enabled": project.drop_cap_enabled,
            "drop_cap_types": project.drop_cap_types,
            "export_filename": project.export_filename,
            "spell_lang": project.spell_lang,
            "spell_words": project.spell_words,
            "edition": project.edition,
            "publication_date": project.publication_date,
            "isbn": project.isbn,
            "publisher": project.publisher,
            "subtitle": project.subtitle,
            "figure_numbering": project.figure_numbering,
            "figure_numbering_style": project.figure_numbering_style,
            "table_numbering": project.table_numbering,
            "table_numbering_style": project.table_numbering_style,
            "labels": project.labels if project.labels else {},
            "components": [
                {
                    "id": c.id,
                    "type": c.type.value,
                    "title": c.title,
                    "filename": c.filename,
                    "order": c.order,
                    "part_id": c.part_id,
                    "frontmatter": c.frontmatter,
                }
                for c in project.components
            ],
        }

        yaml_path = Path(project.path) / "project.yaml"
        return YamlService.save(project_data, str(yaml_path))
