import html
import re
import shutil
from pathlib import Path
from typing import List, Tuple
from urllib.parse import urlparse

import ebooklib

from ..models.project import Project
from ..models.component import Component, ComponentType
from .component_service import ComponentService
from .project_service import ProjectService

SUPPORTED_IMAGE_FORMATS = {".jpg", ".jpeg", ".png", ".gif"}


def slugify(text: str) -> str:
    """Convert text to a safe filesystem name (lowercase, hyphens)."""
    s = text.lower().strip()
    s = re.sub(r'[^\w\s-]', '', s)
    s = re.sub(r'[-\s]+', '-', s)
    s = s.strip('-')
    return s or "untitled"


class ImportService:
    """Handles importing Markdown and EPUB files into a project."""

    @staticmethod
    def bump_headings(text: str, delta: int) -> str:
        """Increase (delta > 0) or decrease (delta < 0) heading levels.

        Args:
            text: Markdown text with headings.
            delta: Number of levels to adjust (positive = deeper, negative = shallower).

        Returns:
            Markdown text with adjusted heading levels.
        """
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

        Args:
            content: Full markdown content of the book.

        Returns:
            List of (component_type_value, title, markdown_content) tuples.
        """
        lines = content.split('\n')
        h1_positions = []
        for i, line in enumerate(lines):
            stripped = line.strip()
            if re.match(r'^#\s', stripped) and not stripped.startswith('##'):
                h1_positions.append(i)

        num_h1 = len(h1_positions)

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

            h2_positions = []
            for i in range(h1_line + 1, len(lines)):
                stripped = lines[i].strip()
                if re.match(r'^##\s', stripped) and not stripped.startswith('###'):
                    h2_positions.append(i)

            if not h2_positions:
                section = '\n'.join(lines[h1_line:]).strip()
                result.append(("chapter", h1_title, section))
            else:
                between = '\n'.join(lines[h1_line:h2_positions[0]]).strip()
                if between:
                    result.append(("introduction", h1_title, between))

                for i, pos in enumerate(h2_positions):
                    end = h2_positions[i + 1] if i + 1 < len(h2_positions) else len(lines)
                    raw_section = '\n'.join(lines[pos:end])
                    h2_title = lines[pos].strip().lstrip('#').strip()
                    section = ImportService.bump_headings(raw_section, -1).strip()
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
    def process_markdown_images(md_content: str, source_dir: str, project_path: str) -> Tuple[str, List[str]]:
        """Find markdown image references, copy images to project, and rewrite paths.

        Images are copied to project/images/illustrations/ and paths rewritten
        to be project-relative. URLs (http/https) are left untouched.

        Args:
            md_content: Markdown text with image references.
            source_dir: Directory to resolve relative image paths against.
            project_path: Project root path.

        Returns:
            Tuple of (updated_md_content, list_of_imported_filenames).
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
        """Import parsed components into the project, save files, and return count.

        If source_md_path is provided, image references are resolved relative to that file's
        directory, copied to project/images/illustrations/, and paths rewritten.

        Args:
            project_path: Project root path.
            project: Project to add components to.
            content: Full markdown content to parse.
            source_md_path: Optional path to the source markdown file for image resolution.

        Returns:
            Number of components imported.
        """
        import uuid

        parsed = ImportService.parse_imported_markdown(content)
        source_dir = str(Path(source_md_path).parent) if source_md_path else ""
        base_order = max((c.order for c in project.components), default=-1) + 1

        for i, (ctype, title, md_content) in enumerate(parsed):
            try:
                comp_type = ComponentType(ctype)
            except ValueError:
                comp_type = ComponentType.CHAPTER

            if source_dir:
                md_content, _ = ImportService.process_markdown_images(md_content, source_dir, project_path)

            comp = Component(
                id=str(uuid.uuid4()),
                type=comp_type,
                title=title,
                filename=ComponentService.generate_filename(ctype, title),
                order=base_order + i,
                frontmatter={},
                custom_css="",
            )
            project.add_component(comp)
            ComponentService.save_component(project_path, comp, md_content)

        ProjectService.save_project(project)
        return len(parsed)

    @staticmethod
    def html_to_markdown(html_content: str) -> str:
        """Convert basic HTML to markdown.

        Args:
            html_content: HTML string to convert.

        Returns:
            Markdown text.
        """
        text = html_content

        body_match = re.search(
            r'<body[^>]*>(.*?)</body>', text, flags=re.DOTALL | re.IGNORECASE
        )
        if body_match:
            text = body_match.group(1)

        text = re.sub(
            r'<(script|style)[^>]*>.*?</\1>', '', text, flags=re.DOTALL | re.IGNORECASE
        )

        for level in range(6, 0, -1):
            pattern = rf'<h{level}[^>]*>(.*?)</h{level}>'
            replacement = '#' * level + r' \1\n\n'
            text = re.sub(pattern, replacement, text, flags=re.DOTALL | re.IGNORECASE)

        text = re.sub(
            r'<(strong|b)[^>]*>(.*?)</\1>', r'**\2**', text,
            flags=re.DOTALL | re.IGNORECASE,
        )
        text = re.sub(
            r'<(em|i)[^>]*>(.*?)</\1>', r'*\2*', text,
            flags=re.DOTALL | re.IGNORECASE,
        )

        def _img_to_md(m):
            alt = ""
            src = ""
            alt_match = re.search(r'alt="([^"]*)"', m.group(0))
            if alt_match:
                alt = alt_match.group(1)
            src_match = re.search(r'src="([^"]*)"', m.group(0))
            if src_match:
                src = src_match.group(1)
                basename = Path(src).name
            return f'![{alt}](images/illustrations/{basename})'

        text = re.sub(r'<img[^>]*/?>', _img_to_md, text, flags=re.IGNORECASE)

        text = re.sub(
            r'<p[^>]*>(.*?)</p>', r'\1\n\n', text, flags=re.DOTALL | re.IGNORECASE
        )
        text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)

        text = re.sub(
            r'<(div|span|section|article|header|footer|nav|main|aside)[^>]*>(.*?)</\1>',
            r'\2\n', text, flags=re.DOTALL | re.IGNORECASE,
        )

        text = re.sub(
            r'<a[^>]*href="([^"]*)"[^>]*>(.*?)</a>',
            r'[\2](\1)', text, flags=re.DOTALL | re.IGNORECASE,
        )

        text = re.sub(
            r'<li[^>]*>(.*?)</li>',
            r'- \1\n', text, flags=re.DOTALL | re.IGNORECASE,
        )
        text = re.sub(
            r'<(ul|ol)[^>]*>', '', text, flags=re.IGNORECASE,
        )
        text = re.sub(
            r'</(ul|ol)>', '\n', text, flags=re.IGNORECASE,
        )

        text = re.sub(r'<[^>]+>', '', text)

        text = html.unescape(text)

        text = re.sub(r'\n{3,}', '\n\n', text)
        text = text.strip()

        return text

    @staticmethod
    def parse_imported_epub(
        epub_path: str,
    ) -> Tuple[List[Tuple[str, str, str]], List[Tuple[str, bytes]]]:
        """Parse an EPUB file into components and images.

        Args:
            epub_path: Path to the EPUB file.

        Returns:
            Tuple of (components, images) where:
            - components: List of (component_type, title, markdown_content)
            - images: List of (filename, data_bytes)
        """
        book = ebooklib.epub.read_epub(epub_path)

        images: List[Tuple[str, bytes]] = []
        for item in book.get_items_of_type(ebooklib.ITEM_IMAGE):
            name = Path(item.file_name).name
            images.append((name, item.content))

        components: List[Tuple[str, str, str]] = []
        for item_id, __ in book.spine:
            item = book.get_item_with_id(item_id)
            if not item or item.get_type() != ebooklib.ITEM_DOCUMENT:
                continue

            try:
                html_content = item.content.decode('utf-8', errors='replace')
            except Exception:
                continue

            md_content = ImportService.html_to_markdown(html_content)
            if not md_content.strip():
                continue

            title = ""
            h1_match = re.search(r'^#\s+(.*)', md_content, re.MULTILINE)
            if h1_match:
                title = h1_match.group(1).strip()
            if not title:
                title = item.get_name() or ""

            components.append(("chapter", title, md_content))

        return components, images

    @staticmethod
    def import_epub(project_path: str, project: Project, epub_path: str) -> int:
        """Import an EPUB file into the project, saving components and images.

        Args:
            project_path: Project root path.
            project: Project to add components to.
            epub_path: Path to the EPUB file.

        Returns:
            Number of components imported.
        """
        import uuid

        components, images = ImportService.parse_imported_epub(epub_path)

        images_dir = Path(project_path) / "images" / "illustrations"
        images_dir.mkdir(parents=True, exist_ok=True)
        for filename, data in images:
            dest = images_dir / filename
            counter = 1
            stem = dest.stem
            suffix = dest.suffix
            while dest.exists():
                dest = images_dir / f"{stem}_{counter}{suffix}"
                counter += 1
            dest.write_bytes(data)

        base_order = max((c.order for c in project.components), default=-1) + 1

        for i, (ctype, title, md_content) in enumerate(components):
            try:
                comp_type = ComponentType(ctype)
            except ValueError:
                comp_type = ComponentType.CHAPTER

            comp = Component(
                id=str(uuid.uuid4()),
                type=comp_type,
                title=title,
                filename=ComponentService.generate_filename(ctype, title),
                order=base_order + i,
                frontmatter={},
                custom_css="",
            )
            project.add_component(comp)
            ComponentService.save_component(project_path, comp, md_content)

        ProjectService.save_project(project)
        return len(components)
