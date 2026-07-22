import re
from typing import Dict, List, Optional, Tuple

from ebooklib import epub

from ..models.project import Project
from ..models.component import Component, ComponentType
from .file_service import FileService
from .yaml_service import YamlService
from .header_builder import HeaderBuilder


class TocBuilder:
    """Generates TOC structures: in-book HTML and reader navigation."""

    def __init__(self, project: Project, labels: Dict[str, str], header_builder: HeaderBuilder):
        """Initialize with project, labels, and header builder.

        Args:
            project: The project containing components and configuration.
            labels: Resolved label dictionary.
            header_builder: HeaderBuilder for computing display titles.
        """
        self.project = project
        self.labels = labels
        self.header_builder = header_builder

    @staticmethod
    def slugify(text: str) -> str:
        """Match the default slugify of markdown's toc extension."""
        s = text.lower().strip()
        s = re.sub(r'[^\w\s-]', '', s)
        s = re.sub(r'[-\s]+', '-', s)
        s = s.strip('-')
        return s

    @staticmethod
    def normalize_toc_deep(value, default: int = 2) -> int:
        """Clamp toc_deep to a valid range [1, 6]."""
        try:
            v = int(value)
        except (ValueError, TypeError):
            return default
        return max(1, min(v, 6))

    def toc_class_for_type(self, comp_type: ComponentType) -> str:
        """Return the CSS class for a TOC entry of the given component type.

        Args:
            comp_type: The component type.

        Returns:
            CSS class string.
        """
        return "toc-entry"

    def get_toc_include_filter(self) -> Optional[set]:
        """Read toc_include from the TOC component's frontmatter, if any.

        Returns:
            Set of component type values to include, or None for all.
        """
        for comp in self.project.components:
            if comp.type == ComponentType.TOC:
                content = FileService.load_component(self.project.path, comp)
                if content:
                    frontmatter, _ = YamlService.parse_frontmatter(content)
                    raw = frontmatter.get("toc_include")
                    if isinstance(raw, list):
                        return set(raw)
        return None

    def parse_headings_from_md(self, md_text: str, max_depth: int) -> List[Tuple[int, str, str]]:
        """Parse headings from markdown text.

        Returns list of (level, text, anchor_id) for headings with level <= max_depth.
        Handles attr_list syntax:  ## Title {#custom-id}
        """
        result = []
        heading_re = re.compile(r'^(#{1,6})\s+(.+)$', re.MULTILINE)
        for m in heading_re.finditer(md_text):
            level = len(m.group(1))
            if level > max_depth:
                continue
            raw = m.group(2).strip()
            text = re.sub(r'\s*\{[#.][^\}]*\}', '', raw).strip()
            id_m = re.search(r'\{#([^\s}]+)\}', raw)
            if id_m:
                anchor = id_m.group(1)
            else:
                anchor = self.slugify(text)
            result.append((level, text, anchor))
        return result

    def get_heading_toc_entries(self, comp: Component, toc_deep: int) -> List[str]:
        """Generate TOC lines for headings within a component's content.

        Args:
            comp: The component to scan for headings.
            toc_deep: Maximum heading depth to show.

        Returns:
            List of HTML strings for sub-heading TOC entries.
        """
        content = FileService.load_component(self.project.path, comp)
        if not content:
            return []
        _, md_text = YamlService.parse_frontmatter(content)
        headings = self.parse_headings_from_md(md_text, toc_deep)
        headings = [(l, t, a) for l, t, a in headings if l > 1]
        if not headings:
            return []
        base = comp.filename.replace('.md', '.xhtml')
        lines = []
        for level, text, anchor in headings:
            target = f"{base}#{anchor}"
            indent_px = (level - 1) * 20
            lines.append(f'<p class="toc-sub" style="margin-left:{indent_px}px"><a href="{target}">{text}</a></p>')
        return lines

    def generate_toc_html(self, toc_include: Optional[List[str]] = None, toc_deep: int = 2) -> str:
        """Generate the in-book TOC HTML from project components.

        Args:
            toc_include: Optional list of component type values to include.
            toc_deep: Maximum heading depth to show.

        Returns:
            HTML string for the TOC.
        """
        toc_deep = self.normalize_toc_deep(toc_deep)
        part_map = {p.id: p for p in self.project.get_parts()}
        parts_with_chapters = set()
        for comp in self.project.get_ordered_components():
            if comp.type == ComponentType.CHAPTER and comp.part_id in part_map:
                parts_with_chapters.add(comp.part_id)

        current_part_id = None
        lines = []
        has_entries = False
        chapter_count = 0
        appendix_count = 0
        part_toc_count = 0

        for comp in self.project.get_ordered_components():
            include = toc_include is None or comp.type.value in toc_include
            if not include:
                continue

            if comp.type == ComponentType.PART and comp.id in parts_with_chapters:
                continue

            if comp.type == ComponentType.CHAPTER:
                chapter_count += 1
            elif comp.type == ComponentType.APPENDIX:
                appendix_count += 1
            comp_number = None
            if comp.should_use_numbering():
                comp_number = chapter_count if comp.type == ComponentType.CHAPTER else appendix_count
            _, _, display_title = self.header_builder.get_component_header(comp, comp_number)
            title = display_title or comp.get_display_name(self.labels)

            belongs_to_part = (comp.part_id in part_map
                               and comp.type == ComponentType.CHAPTER)

            if belongs_to_part:
                if comp.part_id != current_part_id:
                    if current_part_id is not None:
                        lines.append('</div>')
                    part = part_map[comp.part_id]
                    part_toc_count += 1
                    _, _, part_display_title = self.header_builder.get_part_header(part, part_toc_count)
                    part_title = part_display_title or part.get_display_name(self.labels)
                    lines.append('<div class="toc-part">')
                    target = f"{part.filename.replace('.md', '.xhtml')}" if part.filename else "#"
                    lines.append(f'<p class="toc-part-heading"><a href="{target}">{part_title}</a></p>')
                    current_part_id = comp.part_id
                    has_entries = True
                if toc_deep >= 2:
                    target = f"{comp.filename.replace('.md', '.xhtml')}#ch_{comp.id}"
                    css_class = self.toc_class_for_type(comp.type)
                    lines.append(f'<p class="{css_class}"><a href="{target}">{title}</a></p>')
                    has_entries = True
                    part_deep = toc_deep - 1
                    if part_deep > 1:
                        lines.extend(self.get_heading_toc_entries(comp, part_deep))
            else:
                if current_part_id is not None:
                    lines.append('</div>')
                    current_part_id = None
                if comp.type == ComponentType.PART:
                    part_toc_count += 1
                    _, _, part_display_title = self.header_builder.get_part_header(comp, part_toc_count)
                    title = part_display_title or comp.get_display_name(self.labels)
                    css_class = "toc-part-standalone"
                else:
                    css_class = self.toc_class_for_type(comp.type)
                target = f"{comp.filename.replace('.md', '.xhtml')}#ch_{comp.id}"
                lines.append(f'<p class="{css_class}"><a href="{target}">{title}</a></p>')
                has_entries = True
                if toc_deep > 1 and comp.type != ComponentType.PART:
                    lines.extend(self.get_heading_toc_entries(comp, toc_deep))

        if current_part_id is not None:
            lines.append('</div>')

        if has_entries:
            lines.insert(0, '<div class="toc-list">')
            lines.append('</div>')
        return "\n".join(lines)

    def build_reader_toc(
        self,
        book: epub.EpubBook,
        chapter_map: Dict[str, epub.EpubHtml],
        part_chapters: Dict[str, epub.EpubHtml],
        toc_filter: Optional[set] = None,
    ) -> None:
        """Build the reader TOC (navigation) for the EPUB.

        Args:
            book: The EPUB book to set the TOC on.
            chapter_map: Component ID to EpubHtml mapping.
            part_chapters: Part ID to EpubHtml mapping.
            toc_filter: Optional set of component type values to include.
        """
        reader_toc_deep = 2
        for c in self.project.components:
            if c.type == ComponentType.TOC:
                cc = FileService.load_component(self.project.path, c)
                if cc:
                    fm, _ = YamlService.parse_frontmatter(cc)
                    reader_toc_deep = self.normalize_toc_deep(fm.get("toc_deep", 2))
                break

        book.toc = []
        current_part_id = None
        current_section = None
        current_children = []

        def _should_include_toc_entry(comp):
            if toc_filter is None:
                return True
            return comp.type.value in toc_filter

        def _add_heading_toc_children(comp, children, deep):
            if deep <= 1:
                return
            content = FileService.load_component(self.project.path, comp)
            if not content:
                return
            _, md_text = YamlService.parse_frontmatter(content)
            headings = self.parse_headings_from_md(md_text, deep)
            base = comp.filename.replace('.md', '.xhtml')
            for level, text, anchor in headings:
                if level <= 1:
                    continue
                link = epub.Link(
                    href=f"{base}#{anchor}",
                    title=text,
                    uid=f"{comp.id}_{anchor}",
                )
                children.append((link, []))

        part_label = self.labels.get("part", "Part")

        for comp in self.project.get_ordered_components():
            if comp.id not in chapter_map:
                continue
            if not _should_include_toc_entry(comp):
                continue
            ch = chapter_map[comp.id]
            part = self.project.get_part(comp.part_id) if comp.part_id else None

            if part and comp.type == ComponentType.CHAPTER:
                if comp.part_id != current_part_id:
                    if current_section is not None:
                        book.toc.append((current_section, current_children))
                    part_ch = part_chapters.get(part.id)
                    href = part_ch.file_name if part_ch else ""
                    current_part_id = part.id
                    current_section = epub.Section(
                        (part_ch.title if part_ch else part.title) or part_label, href
                    )
                    current_children = []
                if reader_toc_deep >= 2:
                    sub_children = []
                    comp_deep = reader_toc_deep - 1
                    _add_heading_toc_children(comp, sub_children, comp_deep)
                    current_children.append((ch, sub_children))
            else:
                if current_section is not None:
                    book.toc.append((current_section, current_children))
                    current_part_id = None
                    current_section = None
                    current_children = []
                sub_children = []
                _add_heading_toc_children(comp, sub_children, reader_toc_deep)
                book.toc.append((ch, sub_children))

        if current_section is not None:
            book.toc.append((current_section, current_children))
