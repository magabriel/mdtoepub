import re
import shutil
from pathlib import Path
from typing import Optional, Dict, List, Tuple
from urllib.parse import urlparse
from ..models.project import Project
from ..models.component import Component, ComponentType
from .yaml_service import YamlService

SUPPORTED_IMAGE_FORMATS = {".jpg", ".jpeg", ".png", ".gif"}


def slugify(text: str) -> str:
    """Convert text to a safe filesystem name (lowercase, hyphens)."""
    s = text.lower().strip()
    s = re.sub(r'[^\w\s-]', '', s)
    s = re.sub(r'[-\s]+', '-', s)
    s = s.strip('-')
    return s or "untitled"


def _read_css_file(path: Path) -> str:
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


def _write_css_file(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    if content.strip():
        path.write_text(content, encoding="utf-8")
    elif path.exists():
        path.unlink()


def _load_css_from_files(project: Project):
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


class FileService:
    @staticmethod
    def create_project_structure(path: str, project_name: str) -> Project:
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
            "auto_part_title": "none",
            "drop_cap_enabled": True,
            "drop_cap_types": ["chapter"],
            "spell_lang": "es_ES",
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
        yaml_path = Path(project_path) / "project.yaml"
        if not yaml_path.exists():
            return None

        data = YamlService.load(str(yaml_path))
        project = Project(
            name=data.get("name", ""),
            title=data.get("title", ""),
            author=data.get("author", ""),
            language=data.get("language", "es"),
            theme_id=data.get("theme_id", "classic"),
            epub_version=data.get("epub_version", "epub3"),
            auto_chapter_title=data.get("auto_chapter_title", "none"),
            auto_part_title=data.get("auto_part_title", "none"),
            custom_css="",
            type_css_overrides=None,
            drop_cap_enabled=data.get("drop_cap_enabled", True),
            drop_cap_types=data.get("drop_cap_types", ["chapter"]),
            path=project_path,
            export_filename=data.get("export_filename", ""),
            spell_lang=data.get("spell_lang", "es_ES"),
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

        # Load CSS from styles/ files (overrides any inline CSS from project.yaml)
        if project.type_css_overrides is None:
            project.type_css_overrides = {}
        _load_css_from_files(project)

        return project

    @staticmethod
    def save_project(project: Project) -> bool:
        # Write CSS to files first
        _save_css_to_files(project)

        project_data = {
            "name": project.name,
            "title": project.title,
            "author": project.author,
            "language": project.language,
            "theme_id": project.theme_id,
            "epub_version": project.epub_version,
            "auto_chapter_title": project.auto_chapter_title,
            "auto_part_title": project.auto_part_title,
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

    @staticmethod
    def save_component(project_path: str, component: Component, content: str) -> bool:
        try:
            components_dir = Path(project_path) / "components"
            components_dir.mkdir(exist_ok=True)

            file_path = components_dir / component.filename
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            return True
        except Exception:
            return False

    @staticmethod
    def load_component(project_path: str, component: Component) -> str:
        file_path = Path(project_path) / "components" / component.filename
        if not file_path.exists():
            return ""
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()

    @staticmethod
    def generate_filename(component_type: str, title: str) -> str:
        import uuid

        if title:
            slug = title.lower()
            slug = re.sub(r"[^\w\s-]", "", slug)
            slug = re.sub(r"[-\s]+", "_", slug)
            slug = slug.strip("_")
            if slug:
                return f"{slug}.md"

        short_id = uuid.uuid4().hex[:8]
        return f"{component_type}_{short_id}.md"

    @staticmethod
    def _bump_headings(text: str, delta: int) -> str:
        """Increase (delta > 0) or decrease (delta < 0) heading levels."""
        if delta == 0:
            return text

        def _replace(m):
            hashes = m.group(1)
            new_level = len(hashes) + delta
            if new_level < 1:
                return m.group(0)
            return '#' * new_level + m.group(2)

        return re.sub(r'^(#{1,6})(\s+.*)$', _replace, text, flags=re.MULTILINE)

    @staticmethod
    def parse_imported_markdown(content: str) -> List[Tuple[str, str, str]]:
        """Parse a single markdown file (whole book) into components.

        Returns list of (component_type_value, title, markdown_content) tuples.
        """
        lines = content.split('\n')
        # Find positions of all H1 lines (line starts with '# ' but not '## ')
        h1_positions = []
        for i, line in enumerate(lines):
            stripped = line.strip()
            if re.match(r'^#\s', stripped) and not stripped.startswith('##'):
                h1_positions.append(i)

        num_h1 = len(h1_positions)

        # Content before the very first H1 → prologue
        prologue_content = ""
        if h1_positions and h1_positions[0] > 0:
            raw = '\n'.join(lines[:h1_positions[0]]).strip()
            if raw:
                prologue_content = raw

        result: List[Tuple[str, str, str]] = []

        if num_h1 == 0:
            result.append(("chapter", "", content.strip()))
            return result

        if num_h1 == 1:
            h1_line = h1_positions[0]
            h1_title = lines[h1_line].strip().lstrip('#').strip()

            # Find all H2 positions
            h2_positions = []
            for i in range(h1_line + 1, len(lines)):
                stripped = lines[i].strip()
                if re.match(r'^##\s', stripped) and not stripped.startswith('###'):
                    h2_positions.append(i)

            if not h2_positions:
                section = '\n'.join(lines[h1_line:]).strip()
                result.append(("chapter", h1_title, section))
            else:
                # Content between H1 and first H2 → introduction
                between = '\n'.join(lines[h1_line:h2_positions[0]]).strip()
                if between:
                    result.append(("introduction", h1_title, between))

                for i, pos in enumerate(h2_positions):
                    end = h2_positions[i + 1] if i + 1 < len(h2_positions) else len(lines)
                    raw_section = '\n'.join(lines[pos:end])
                    h2_title = lines[pos].strip().lstrip('#').strip()
                    section = FileService._bump_headings(raw_section, -1).strip()
                    result.append(("chapter", h2_title, section))
        else:
            for i, pos in enumerate(h1_positions):
                end = h1_positions[i + 1] if i + 1 < len(h1_positions) else len(lines)
                section = '\n'.join(lines[pos:end]).strip()
                h1_title = lines[pos].strip().lstrip('#').strip()
                result.append(("chapter", h1_title, section))

        if prologue_content:
            result.insert(0, ("prologue", "", prologue_content))

        return result

    @staticmethod
    def _process_markdown_images(md_content: str, source_dir: str, project_path: str) -> Tuple[str, List[str]]:
        """Find markdown image references in md_content, copy images to project,
        and return (updated_md, list_of_imported_filenames).

        Images are copied to project/images/illustrations/ and paths rewritten
        to be project-relative. URLs (http/https) are left untouched.
        """
        images_dir = Path(project_path) / "images" / "illustrations"
        images_dir.mkdir(parents=True, exist_ok=True)
        imported: List[str] = []

        def _replace_img(match):
            alt_text = match.group(1)
            img_path = match.group(2)

            parsed = urlparse(img_path)
            if parsed.scheme in ("http", "https"):
                return match.group(0)

            src = Path(img_path)
            if not src.is_absolute():
                src = Path(source_dir) / img_path
            src = src.resolve()

            if not src.exists() or src.suffix.lower() not in SUPPORTED_IMAGE_FORMATS:
                return match.group(0)

            dest = images_dir / src.name
            counter = 1
            while dest.exists():
                stem = src.stem
                ext = src.suffix
                dest = images_dir / f"{stem}_{counter}{ext}"
                counter += 1

            try:
                shutil.copy2(str(src), str(dest))
                imported.append(dest.name)
                new_path = f"images/illustrations/{dest.name}"
                return f"![{alt_text}]({new_path})"
            except Exception:
                return match.group(0)

        updated = re.sub(r'!\[([^\]]*)\]\(([^)]+)\)', _replace_img, md_content)
        return updated, imported

    @staticmethod
    def import_book(project_path: str, project: Project, content: str, source_md_path: str = "") -> int:
        """Import parsed components into the project, save files, and return count of new components.

        If source_md_path is provided, image references are resolved relative to that file's
        directory, copied to project/images/illustrations/, and paths rewritten.
        """
        import uuid

        parsed = FileService.parse_imported_markdown(content)
        source_dir = str(Path(source_md_path).parent) if source_md_path else ""
        base_order = max((c.order for c in project.components), default=-1) + 1

        for i, (ctype, title, md_content) in enumerate(parsed):
            try:
                comp_type = ComponentType(ctype)
            except ValueError:
                comp_type = ComponentType.CHAPTER

            if source_dir:
                md_content, _ = FileService._process_markdown_images(md_content, source_dir, project_path)

            comp = Component(
                id=str(uuid.uuid4()),
                type=comp_type,
                title=title,
                filename=FileService.generate_filename(ctype, title),
                order=base_order + i,
                frontmatter={},
                custom_css="",
            )
            project.add_component(comp)
            FileService.save_component(project_path, comp, md_content)

        FileService.save_project(project)
        return len(parsed)

    @staticmethod
    def rename_image_references(project_path: str, old_path: str, new_path: str, project) -> int:
        """Rename image references in all component markdown files.

        old_path and new_path are project-relative paths like
        'images/illustrations/foto.jpg'. Returns count of files modified.
        """
        count = 0
        old_escaped = re.escape(old_path)
        for comp in project.components:
            content = FileService.load_component(project_path, comp)
            if not content:
                continue
            new_content, n = re.subn(r'!\[([^\]]*)\]\((' + old_escaped + r')\)',
                                     lambda m: f'![{m.group(1)}]({new_path})',
                                     content)
            if n > 0:
                FileService.save_component(project_path, comp, new_content)
                count += 1
        return count
