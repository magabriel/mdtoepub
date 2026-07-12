from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
import uuid
import re
from datetime import datetime
from urllib.parse import urlparse

from ebooklib import epub

LANG_MARKER_STRIP_RE = re.compile(r'\{lang=\w+(?:[_-]\w+)*\}')

IMAGE_MIME_MAP = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
}

from ..models.project import Project
from ..models.component import Component, ComponentType, COMPONENT_TYPE_LABELS
from .markdown_service import MarkdownService, ERROR_BASE_KEY
from .file_service import FileService
from .yaml_service import YamlService
from .theme_service import ThemeService
from .labels_service import resolve_labels


class EpubService:
    COVER_ONLY_IMAGE_RE = re.compile(r'^\s*!\[.*?\]\([^)]+\)\s*(\{.*?\})?\s*$')
    SUBTITLE_SEPARATOR_RE = re.compile(r'\s+[-–—]\s+')

    FOOTNOTE_DIV_RE = re.compile(
        r'<div class="footnote">.*?<ol>(.*?)</ol>.*?</div>',
        re.DOTALL,
    )
    LI_FN_RE = re.compile(
        r'<li[^>]*\bid="fn:(\d+)"[^>]*>(.*?)</li>',
        re.DOTALL,
    )
    SUP_FN_REF_RE = re.compile(
        r'href="#fn:(\d+)"',
    )
    FN_BACKLINK_RE = re.compile(
        r'href="#fnref:(\d+)"',
    )

    @staticmethod
    def _is_cover_only_image(md_content: str) -> bool:
        lines = [l.strip() for l in md_content.strip().split('\n') if l.strip()]
        return len(lines) == 1 and bool(EpubService.COVER_ONLY_IMAGE_RE.match(lines[0]))

    def _part_label(self) -> str:
        return self._labels.get("part", "Parte")

    def _component_label(self, component: Component) -> str:
        return component.get_display_name(self._labels)

    @staticmethod
    def _extract_cover_image(md_content: str):
        m = re.match(r'^\s*!\[(.*?)\]\(([^)]+)\)', md_content.strip())
        if m:
            return (m.group(1), m.group(2).strip())
        return None

    @staticmethod
    def _split_title(title: str, frontmatter: Optional[Dict] = None) -> Tuple[str, str]:
        """Split title into (subtitle, title) on SUBTITLE_SEPARATOR_RE.
        Returns ("", original_title) if no split occurs or if
        frontmatter['split_title'] is False.
        """
        if frontmatter is not None and not frontmatter.get("split_title", True):
            return "", title
        m = EpubService.SUBTITLE_SEPARATOR_RE.search(title)
        if m:
            subtitle = title[:m.start()].strip()
            rest = title[m.end():].strip()
            if subtitle and rest:
                return subtitle, rest
        return "", title

    def __init__(self, project: Project):
        self.project = project
        self.markdown_service = MarkdownService()
        self._labels: Dict[str, str] = {}

    def _resolve_labels(self, global_config: Optional[Dict] = None) -> Dict[str, str]:
        self._labels = resolve_labels(
            self.project.language,
            self.project.labels,
            global_config,
        )
        return self._labels

    def _create_css_item(self, uid: str, filename: str, css_text: str) -> epub.EpubItem:
        return epub.EpubItem(
            uid=uid,
            file_name=filename,
            media_type="text/css",
            content=css_text.encode("utf-8"),
        )

    def _get_toc_include_filter(self) -> Optional[set]:
        """Read toc_include from the TOC component's frontmatter, if any."""
        for comp in self.project.components:
            if comp.type == ComponentType.TOC:
                content = FileService.load_component(self.project.path, comp)
                if content:
                    frontmatter, _ = YamlService.parse_frontmatter(content)
                    raw = frontmatter.get("toc_include")
                    if isinstance(raw, list):
                        return set(raw)
        return None

    def _get_footnotes_component(self) -> Optional[Component]:
        for c in self.project.components:
            if c.type == ComponentType.FOOTNOTES:
                return c
        return None

    def _embed_images(self, book: epub.EpubBook, html_content: str, comp_id: str, embedded: Set[str]) -> None:
        """Find <img> tags in HTML content and embed referenced images into the EPUB."""
        img_re = re.compile(r'<img[^>]+src="([^"]+)"')
        for m in img_re.finditer(html_content):
            src = m.group(1)
            parsed = urlparse(src)
            if parsed.scheme in ("http", "https"):
                continue
            if src in embedded:
                continue
            img_path = Path(self.project.path) / src
            if not img_path.exists():
                continue
            mime = IMAGE_MIME_MAP.get(img_path.suffix.lower())
            if not mime:
                continue
            img_item = epub.EpubImage(
                uid=f"img_{comp_id}_{len(embedded)}",
                file_name=src,
                media_type=mime,
                content=img_path.read_bytes(),
            )
            book.add_item(img_item)
            embedded.add(src)

    def generate(self, output_path: str, epub_version: str = "epub3",
                 global_config: Optional[Dict] = None) -> Optional[str]:
        try:
            self._resolve_labels(global_config)
            book = epub.EpubBook()

            book.set_identifier(str(uuid.uuid4()))
            book.set_title(self.project.title)
            book.set_language(self.project.language)
            book.add_author(self.project.author)

            book.add_metadata("DC", "publisher", self.project.publisher or "MDToEPUB")
            book.add_metadata("DC", "date", self.project.publication_date or datetime.now().isoformat())

            variables = {
                "title": self.project.title,
                "subtitle": self.project.subtitle,
                "author": self.project.author,
                "isbn": self.project.isbn,
                "publisher": self.project.publisher,
                "edition": self.project.edition,
                "publication_date": self.project.publication_date,
                "language": self.project.language,
            }
            # Strip empty values so {{key}} passes through as-is
            variables = {k: v for k, v in variables.items() if v}

            self._toc_filter = self._get_toc_include_filter()
            stylesheet = self._load_stylesheet()
            style_items = []
            if stylesheet:
                style_item = self._create_css_item("style", "style/default.css", stylesheet)
                book.add_item(style_item)
                style_items.append(style_item)

            # Pre-create type-level CSS items
            type_css_items: Dict[str, epub.EpubItem] = {}
            for type_name, css in self.project.type_css_overrides.items():
                if css.strip():
                    item = self._create_css_item(
                        f"type_{type_name}",
                        f"style/type_{type_name}.css",
                        css,
                    )
                    book.add_item(item)
                    type_css_items[type_name] = item

            # Pre-create component-level CSS items
            comp_css_items: Dict[str, epub.EpubItem] = {}
            for component in self.project.components:
                if component.custom_css.strip():
                    item = self._create_css_item(
                        f"comp_{component.id}",
                        f"style/comp_{component.id}.css",
                        component.custom_css,
                    )
                    book.add_item(item)
                    comp_css_items[component.id] = item

            chapter_map = {}
            part_chapters: Dict[str, epub.EpubHtml] = {}
            embedded_images: Set[str] = set()
            footnotes_comp = self._get_footnotes_component()
            collected_footnotes: Dict[str, dict] = {}

            part_count_for_header = 0
            for part_comp in self.project.get_parts():
                part_count_for_header += 1
                part_ch = self._create_part_chapter(part_comp, style_items, part_count_for_header)
                if part_ch:
                    part_chapters[part_comp.id] = part_ch
                    book.add_item(part_ch)
                    self._embed_images(book, part_ch.content.decode("utf-8"), part_comp.id, embedded_images)

            # First pass: count footnote references per component for global renumbering
            footnote_start: Dict[str, int] = {}
            running_total = 0
            for component in self.project.get_ordered_components():
                if component.type in (ComponentType.PART, ComponentType.FOOTNOTES):
                    continue
                content = FileService.load_component(self.project.path, component)
                if content:
                    _, md_text = YamlService.parse_frontmatter(content)
                    fn_count = MarkdownService._count_footnote_refs(md_text)
                    footnote_start[component.id] = running_total + 1
                    running_total += fn_count

            # Pre-scan figure info for LOF generation and figure numbering
            figure_info = []
            figure_start: Dict[str, int] = {}
            running_fig_total = 0
            if self.project.figure_numbering:
                for component in self.project.get_ordered_components():
                    if component.type in (ComponentType.PART, ComponentType.FOOTNOTES,
                                          ComponentType.LOF, ComponentType.TOC, ComponentType.COVER):
                        continue
                    content = FileService.load_component(self.project.path, component)
                    if content:
                        _, md_text = YamlService.parse_frontmatter(content)
                        alts = MarkdownService.extract_figure_alts(md_text)
                        if alts:
                            figure_start[component.id] = running_fig_total + 1
                            for alt, _ in alts:
                                running_fig_total += 1
                                figure_info.append((running_fig_total, alt, component.filename))

            # Pre-scan table info for LOT generation and table numbering
            table_info = []
            table_start: Dict[str, int] = {}
            running_tab_total = 0
            if self.project.table_numbering:
                for component in self.project.get_ordered_components():
                    if component.type in (ComponentType.PART, ComponentType.FOOTNOTES,
                                          ComponentType.LOT, ComponentType.TOC, ComponentType.COVER):
                        continue
                    content = FileService.load_component(self.project.path, component)
                    if content:
                        _, md_text = YamlService.parse_frontmatter(content)
                        captions = MarkdownService.extract_table_captions(md_text)
                        if captions:
                            table_start[component.id] = running_tab_total + 1
                            for caption, _ in captions:
                                running_tab_total += 1
                                table_info.append((running_tab_total, caption, component.filename))

            chapter_count = 0
            for component in self.project.get_ordered_components():
                if component.type == ComponentType.PART:
                    continue
                if component.type == ComponentType.FOOTNOTES:
                    continue
                if component.should_use_numbering():
                    chapter_count += 1
                chapter_styles = list(style_items)
                type_item = type_css_items.get(component.type.value)
                if type_item:
                    chapter_styles.append(type_item)
                comp_item = comp_css_items.get(component.id)
                if comp_item:
                    chapter_styles.append(comp_item)
                start_num = footnote_start.get(component.id, 1)

                fig_start = figure_start.get(component.id, 0)

                tab_start = table_start.get(component.id, 0)

                chapter = self._create_chapter(component, chapter_styles, chapter_count if component.should_use_numbering() else None,
                                               footnotes_comp=footnotes_comp, collected_footnotes=collected_footnotes,
                                               start_number=start_num,
                                               figure_num_start=fig_start,
                                               figure_num_style=self.project.figure_numbering_style,
                                               figure_info=figure_info if component.type == ComponentType.LOF else None,
                                               table_num_start=tab_start,
                                               table_num_style=self.project.table_numbering_style,
                                               table_info=table_info if component.type == ComponentType.LOT else None,
                                               variables=variables)
                if chapter:
                    chapter_map[component.id] = chapter
                    book.add_item(chapter)
                    self._embed_images(book, chapter.content.decode("utf-8"), component.id, embedded_images)

            # Build footnotes chapter if footnotes component exists
            if footnotes_comp:
                fn_styles = list(style_items)
                fn_type_item = type_css_items.get(footnotes_comp.type.value)
                if fn_type_item:
                    fn_styles.append(fn_type_item)
                fn_comp_item = comp_css_items.get(footnotes_comp.id)
                if fn_comp_item:
                    fn_styles.append(fn_comp_item)
                fn_chapter = self._build_footnotes_chapter(
                    footnotes_comp, collected_footnotes, fn_styles, variables
                )
                if fn_chapter:
                    chapter_map[footnotes_comp.id] = fn_chapter
                    book.add_item(fn_chapter)
                    self._embed_images(book, fn_chapter.content.decode("utf-8"), footnotes_comp.id, embedded_images)

            ordered_chapters = []
            seen_parts = set()

            for comp in self.project.get_ordered_components():
                part = self.project.get_part(comp.part_id) if comp.part_id else None
                if part and comp.type == ComponentType.CHAPTER and part.id not in seen_parts:
                    seen_parts.add(part.id)
                    if part.id in part_chapters:
                        ordered_chapters.append(part_chapters[part.id])
                if comp.id in chapter_map:
                    ordered_chapters.append(chapter_map[comp.id])

            # Read toc_deep from TOC component for reader TOC depth control
            reader_toc_deep = 2
            for c in self.project.components:
                if c.type == ComponentType.TOC:
                    cc = FileService.load_component(self.project.path, c)
                    if cc:
                        fm, _ = YamlService.parse_frontmatter(cc)
                        reader_toc_deep = self._normalize_toc_deep(fm.get("toc_deep", 2))
                    break

            book.toc = []
            current_part_id = None
            current_section = None
            current_children = []

            def _should_include_toc_entry(comp):
                if self._toc_filter is None:
                    return True
                return comp.type.value in self._toc_filter

            def _add_heading_toc_children(comp, children, deep):
                if deep <= 1:
                    return
                content = FileService.load_component(self.project.path, comp)
                if not content:
                    return
                _, md_text = YamlService.parse_frontmatter(content)
                headings = self._parse_headings_from_md(md_text, deep)
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
                            part.title or self._part_label(), href
                        )
                        current_children = []
                    # Chapter is at depth 2 (part is depth 1)
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

            if epub_version == "epub2":
                book.spine = ordered_chapters
                book.add_item(epub.EpubNcx())
            else:
                book.spine = ordered_chapters
                book.add_item(epub.EpubNcx())
                book.add_item(epub.EpubNav())

            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)

            epub.write_epub(str(output_file), book, {})
            return str(output_file)

        except Exception as e:
            print(f"Error generating EPUB: {e}")
            return None

    def _get_component_header(
        self, component: Component, chapter_number: Optional[int] = None
    ) -> Tuple[str, str, str]:
        """Returns (number_part, title_part, display_title) for a component."""
        show_title = component.frontmatter.get("show_title", True)
        number_part = ""
        title_part = ""

        mode = self.project.auto_chapter_title
        if mode != "none" and show_title:
            if component.should_use_numbering() and chapter_number is not None:
                label = self._labels.get("chapter", "Capítulo") if component.type == ComponentType.CHAPTER else self._labels.get("appendix", "Apéndice")
                if mode == "chapter_number":
                    number_part = f"{label} {chapter_number}"
                elif mode == "number":
                    number_part = str(chapter_number)
                elif mode == "chapter_number_with_title":
                    number_part = f"{label} {chapter_number}"
                    title_part = self._component_label(component)
                elif mode == "number_with_title":
                    number_part = str(chapter_number)
                    title_part = self._component_label(component)

        if show_title and not number_part and not title_part:
            title_part = self._component_label(component)

        if number_part and title_part:
            display_title = f"{number_part}: {title_part}"
        elif number_part:
            display_title = number_part
        elif title_part:
            display_title = title_part
        else:
            display_title = ""
        return number_part, title_part, display_title

    def _get_part_header(
        self, component: Component, part_number: Optional[int] = None
    ) -> Tuple[str, str, str]:
        """Returns (number_part, title_part, display_title) for a part component."""
        show_title = component.frontmatter.get("show_title", True)
        number_part = ""
        title_part = ""

        mode = self.project.auto_part_title
        if mode != "none" and show_title:
            if part_number is not None:
                label = self._labels.get("part", "Parte")
                if mode == "part_number":
                    number_part = f"{label} {part_number}"
                elif mode == "number":
                    number_part = str(part_number)
                elif mode == "part_number_with_title":
                    number_part = f"{label} {part_number}"
                    title_part = self._component_label(component)
                elif mode == "number_with_title":
                    number_part = str(part_number)
                    title_part = self._component_label(component)

        if show_title and not number_part and not title_part:
            title_part = self._component_label(component)

        if number_part and title_part:
            display_title = f"{number_part}: {title_part}"
        elif number_part:
            display_title = number_part
        elif title_part:
            display_title = title_part
        else:
            display_title = ""
        return number_part, title_part, display_title

    def _apply_drop_cap(self, html: str) -> str:
        """Wrap the drop-cap chars in the first <p> with <span class=\"drop-cap\">."""
        def first_p_replacer(m):
            inner = m.group(1)
            text_only = re.sub(r'<[^>]+>', '', inner)
            if not text_only:
                return m.group(0)

            drop = ''
            for ch in text_only:
                drop += ch
                if ch.isalnum():
                    break
            if not drop or not drop[-1].isalnum():
                return m.group(0)

            result = []
            in_tag = False
            drop_pos = 0
            inserted = False

            for ch in inner:
                if ch == '<':
                    in_tag = True
                    result.append(ch)
                elif ch == '>':
                    in_tag = False
                    result.append(ch)
                elif not in_tag and not inserted:
                    if drop_pos == 0:
                        result.append('<span class="drop-cap">')
                    result.append(ch)
                    drop_pos += 1
                    if drop_pos >= len(drop):
                        result.append('</span>')
                        inserted = True
                else:
                    result.append(ch)

            return '<p>' + ''.join(result) + '</p>'

        return re.sub(r'<p>(.*?)</p>', first_p_replacer, html, count=1, flags=re.DOTALL)

    def _build_header_html(self, number_part: str, subtitle_part: str, title_part: str) -> str:
        parts = []
        if number_part:
            parts.append(f'  <span class="header-number">{number_part}</span>')
        if subtitle_part:
            parts.append(f'  <span class="header-subtitle">{subtitle_part}</span>')
        if title_part:
            parts.append(f'  <span class="header-title">{title_part}</span>')
        if not parts:
            return ""
        if len(parts) == 1:
            return f'<h1 class="component-header">{parts[0].strip()}</h1>\n'
        return '<h1 class="component-header">\n' + '\n'.join(parts) + '\n</h1>\n'

    @staticmethod
    def _slugify(text: str) -> str:
        """Match the default slugify of markdown's toc extension."""
        s = text.lower().strip()
        s = re.sub(r'[^\w\s-]', '', s)
        s = re.sub(r'[-\s]+', '-', s)
        s = s.strip('-')
        return s

    @staticmethod
    def _normalize_toc_deep(value, default: int = 2) -> int:
        try:
            v = int(value)
        except (ValueError, TypeError):
            return default
        return max(1, min(v, 6))

    def _parse_headings_from_md(self, md_text: str, max_depth: int) -> List[Tuple[int, str, str]]:
        """Parse headings from markdown text.

        Returns list of (level, text, anchor_id) for headings with level <= max_depth.
        Level 1 = H1, level 2 = H2, etc.
        Handles attr_list syntax:  ## Title {#custom-id}
        """
        result = []
        heading_re = re.compile(r'^(#{1,6})\s+(.+)$', re.MULTILINE)
        for m in heading_re.finditer(md_text):
            level = len(m.group(1))
            if level > max_depth:
                continue
            raw = m.group(2).strip()
            # Strip attr_list extensions: {#id .class key=val}
            text = re.sub(r'\s*\{[#.][^\}]*\}', '', raw).strip()
            # Try to extract explicit id from {#id}
            id_m = re.search(r'\{#([^\s}]+)\}', raw)
            if id_m:
                anchor = id_m.group(1)
            else:
                anchor = self._slugify(text)
            result.append((level, text, anchor))
        return result

    def _generate_toc_html(self, toc_include: Optional[List[str]] = None, toc_deep: int = 2) -> str:
        toc_deep = self._normalize_toc_deep(toc_deep)
        part_map = {p.id: p for p in self.project.get_parts()}
        # Precompute which parts have at least one chapter
        parts_with_chapters = set()
        for comp in self.project.get_ordered_components():
            if comp.type == ComponentType.CHAPTER and comp.part_id in part_map:
                parts_with_chapters.add(comp.part_id)

        current_part_id = None
        lines = []
        has_entries = False
        chapter_count = 0
        part_toc_count = 0

        for comp in self.project.get_ordered_components():
            include = toc_include is None or comp.type.value in toc_include
            if not include:
                continue

            # PARTs with chapters are handled via the belongs_to_part branch below
            if comp.type == ComponentType.PART and comp.id in parts_with_chapters:
                continue

            if comp.should_use_numbering():
                chapter_count += 1
            _, _, display_title = self._get_component_header(comp, chapter_count if comp.should_use_numbering() else None)
            title = display_title or self._component_label(comp)

            belongs_to_part = (comp.part_id in part_map
                               and comp.type == ComponentType.CHAPTER)

            if belongs_to_part:
                if comp.part_id != current_part_id:
                    if current_part_id is not None:
                        lines.append('</div>')
                    part = part_map[comp.part_id]
                    part_toc_count += 1
                    _, _, part_display_title = self._get_part_header(part, part_toc_count)
                    part_title = part_display_title or self._component_label(part)
                    lines.append('<div class="toc-part">')
                    target = f"{part.filename.replace('.md', '.xhtml')}" if part.filename else "#"
                    lines.append(f'<p class="toc-part-heading"><a href="{target}">{part_title}</a></p>')
                    current_part_id = comp.part_id
                    has_entries = True
                # Chapter is at depth 2 (part is depth 1)
                if toc_deep >= 2:
                    target = f"{comp.filename.replace('.md', '.xhtml')}#ch_{comp.id}"
                    css_class = self._toc_class_for_type(comp.type)
                    lines.append(f'<p class="{css_class}"><a href="{target}">{title}</a></p>')
                    has_entries = True
                    # Chapter consumes one level; sub-headings start at depth 3+
                    part_deep = toc_deep - 1
                    if part_deep > 1:
                        lines.extend(self._get_heading_toc_entries(comp, part_deep))
            else:
                if current_part_id is not None:
                    lines.append('</div>')
                    current_part_id = None
                # PART without chapters: standalone entry
                if comp.type == ComponentType.PART:
                    part_toc_count += 1
                    _, _, part_display_title = self._get_part_header(comp, part_toc_count)
                    title = part_display_title or self._component_label(comp)
                    css_class = "toc-part-standalone"
                else:
                    css_class = self._toc_class_for_type(comp.type)
                target = f"{comp.filename.replace('.md', '.xhtml')}#ch_{comp.id}"
                lines.append(f'<p class="{css_class}"><a href="{target}">{title}</a></p>')
                has_entries = True
                if toc_deep > 1 and comp.type != ComponentType.PART:
                    lines.extend(self._get_heading_toc_entries(comp, toc_deep))

        if current_part_id is not None:
            lines.append('</div>')

        if has_entries:
            lines.insert(0, '<div class="toc-list">')
            lines.append('</div>')
        return "\n".join(lines)

    def _get_heading_toc_entries(self, comp: Component, toc_deep: int) -> List[str]:
        """Generate TOC lines for headings within a component's content."""
        content = FileService.load_component(self.project.path, comp)
        if not content:
            return []
        _, md_text = YamlService.parse_frontmatter(content)
        headings = self._parse_headings_from_md(md_text, toc_deep)
        # Skip H1: the component-level entry already covers it
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

    def _collect_figure_info(self) -> list:
        """Scan all components and collect info about figures.

        Returns list of (fig_num, caption, component_filename) tuples
        for all non-decorative images with alt text.
        """
        figure_info = []
        fig_num = 0
        for component in self.project.get_ordered_components():
            if component.type in (ComponentType.PART, ComponentType.FOOTNOTES,
                                  ComponentType.LOF, ComponentType.TOC, ComponentType.COVER):
                continue
            content = FileService.load_component(self.project.path, component)
            if not content:
                continue
            _, md_text = YamlService.parse_frontmatter(content)
            alts = MarkdownService.extract_figure_alts(md_text)
            for alt, _ in alts:
                fig_num += 1
                figure_info.append((fig_num, alt, component.filename))
        return figure_info

    def _generate_lof_html(self, figure_info: list) -> str:
        """Generate the List of Figures HTML from collected figure info."""
        if not figure_info:
            return ""
        use_roman = self.project.figure_numbering_style == "roman"
        figure_label = self._labels.get("figure", "Figura")
        lines = ['<div class="lof-list">', '<ul>']
        for fig_num, caption, filename in figure_info:
            href = f"{filename.replace('.md', '.xhtml')}#fig_{fig_num}"
            if use_roman:
                num_str = MarkdownService._to_roman(fig_num)
            else:
                num_str = str(fig_num)
            if caption:
                text = f"{figure_label} {num_str} - {caption}"
            else:
                text = f"{figure_label} {num_str}"
            lines.append(f'<li class="lof-entry"><a href="{href}">{text}</a></li>')
        lines.append('</ul>')
        lines.append('</div>')
        return "\n".join(lines)

    def _generate_lot_html(self, table_info: list) -> str:
        """Generate the List of Tables HTML from collected table info."""
        if not table_info:
            return ""
        use_roman = self.project.table_numbering_style == "roman"
        table_label = self._labels.get("table", "Tabla")
        lines = ['<div class="lot-list">', '<ul>']
        for tab_num, caption, filename in table_info:
            href = f"{filename.replace('.md', '.xhtml')}#tab_{tab_num}"
            if use_roman:
                num_str = MarkdownService._to_roman(tab_num)
            else:
                num_str = str(tab_num)
            if caption:
                text = f"{table_label} {num_str} - {caption}"
            else:
                text = f"{table_label} {num_str}"
            lines.append(f'<li class="lot-entry"><a href="{href}">{text}</a></li>')
        lines.append('</ul>')
        lines.append('</div>')
        return "\n".join(lines)

    def _toc_class_for_type(self, comp_type: ComponentType) -> str:
        return "toc-entry"

    def _create_chapter(
        self, component: Component, style_items: List[epub.EpubItem] = None,
        chapter_number: Optional[int] = None,
        footnotes_comp: Optional[Component] = None,
        collected_footnotes: Optional[Dict[str, dict]] = None,
        start_number: int = 1,
        figure_num_start: int = 0,
        figure_num_style: str = "arabic",
        figure_info: Optional[list] = None,
        table_num_start: int = 0,
        table_num_style: str = "arabic",
        table_info: Optional[list] = None,
        variables: Optional[Dict[str, str]] = None,
    ) -> Optional[epub.EpubHtml]:
        content = FileService.load_component(self.project.path, component)
        if not content:
            if component.type in (ComponentType.LOF, ComponentType.LOT, ComponentType.TOC):
                frontmatter = {}
                markdown_content = f"# {self._component_label(component)}\n\n"
            else:
                return None
        else:
            frontmatter, markdown_content = YamlService.parse_frontmatter(content)

        # Special handling for COVER with only one image
        if component.type == ComponentType.COVER and self._is_cover_only_image(markdown_content):
            img_info = self._extract_cover_image(markdown_content)
            if img_info:
                alt, src = img_info
                display_title = self._component_label(component)
                chapter = epub.EpubHtml(
                    title=display_title,
                    file_name=f"{component.filename.replace('.md', '.xhtml')}",
                    lang=self.project.language,
                )
                chapter.content = f"""<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml">
<head><title>{display_title}</title></head>
<body style="margin:0;padding:0;text-align:center;height:100%;">
<img src="{src}" alt="{alt}" style="max-width:100%;max-height:100%;width:100%;height:100%;object-fit:contain;"/>
</body>
</html>""".encode("utf-8")
                return chapter

        # Determine default title from h1 in content, or fallback to component title
        h1_match = re.search(r'^# (.+)$', markdown_content, re.MULTILINE)
        default_title = h1_match.group(1).strip() if h1_match else ""

        # Get auto-header components (number + title)
        number_part, title_part, display_title = self._get_component_header(
            component, chapter_number
        )

        show_title = frontmatter.get("show_title", True)
        if show_title:
            # Use h1 as title_part if found and no title_part from header
            # (but not for modes that replace the title entirely with just a number)
            replaces_title = self.project.auto_chapter_title in ("chapter_number", "number")
            if default_title and not title_part and not replaces_title:
                title_part = default_title

            # Override title_part with h1 when both exist (h1 takes precedence)
            if default_title and title_part and default_title != self._component_label(component):
                title_part = default_title

        # Split title_part into subtitle + title for separate styling
        full_title = title_part
        subtitle_part = ""
        if title_part:
            subtitle_part, title_part = EpubService._split_title(title_part, frontmatter)

        if number_part and full_title:
            display_title = f"{number_part}: {full_title}"
        elif number_part:
            display_title = number_part
        elif full_title:
            display_title = full_title
        else:
            display_title = default_title or self._component_label(component)

        if component.type == ComponentType.TOC:
            toc_deep = self._normalize_toc_deep(frontmatter.get("toc_deep", 2))
            auto_toc = self._generate_toc_html(self._toc_filter, toc_deep)
            import markdown
            md = markdown.Markdown(extensions=self.markdown_service.extensions,
                                   extension_configs=self.markdown_service.get_extension_configs())
            title_html = md.convert(LANG_MARKER_STRIP_RE.sub('', markdown_content)) if markdown_content.strip() else ""
            title_html = MarkdownService._add_image_captions(title_html, labels=self._labels)
            combined = (title_html + "\n" + auto_toc) if title_html else auto_toc
            html_content = self.markdown_service._wrap_in_section(combined, component.type, component.id)
        elif component.type == ComponentType.LOF:
            auto_lof = self._generate_lof_html(figure_info) if figure_info else ""
            import markdown
            md = markdown.Markdown(extensions=self.markdown_service.extensions,
                                   extension_configs=self.markdown_service.get_extension_configs())
            title_html = md.convert(LANG_MARKER_STRIP_RE.sub('', markdown_content)) if markdown_content.strip() else ""
            title_html = MarkdownService._add_image_captions(title_html, labels=self._labels)
            combined = (title_html + "\n" + auto_lof) if title_html else auto_lof
            html_content = self.markdown_service._wrap_in_section(combined, component.type, component.id)
        elif component.type == ComponentType.LOT:
            auto_lot = self._generate_lot_html(table_info) if table_info else ""
            import markdown
            md = markdown.Markdown(extensions=self.markdown_service.extensions,
                                   extension_configs=self.markdown_service.get_extension_configs())
            title_html = md.convert(LANG_MARKER_STRIP_RE.sub('', markdown_content)) if markdown_content.strip() else ""
            title_html = MarkdownService._add_image_captions(title_html, labels=self._labels)
            title_html = MarkdownService._add_table_captions(title_html, labels=self._labels)
            combined = (title_html + "\n" + auto_lot) if title_html else auto_lot
            html_content = self.markdown_service._wrap_in_section(combined, component.type, component.id)
        else:
            header_html = self._build_header_html(number_part, subtitle_part, title_part)
            show_title = frontmatter.get("show_title", True)
            if header_html:
                # Remove h1 from content to avoid duplication
                if h1_match:
                    markdown_content = (markdown_content[:h1_match.start()]
                                        + markdown_content[h1_match.end():])
                    markdown_content = markdown_content.strip()
                markdown_content = header_html + markdown_content
            elif show_title:
                if not default_title:
                    # No user h1, no header: prepend title as h1
                    markdown_content = f"# {self._component_label(component)}\n\n{markdown_content}"
            # else show_title=False, no header: just render content as-is
            html_content = self.markdown_service.render(markdown_content, component.type, component.id, start_number,
                                                          figure_num_start, figure_num_style,
                                                          table_num_start, table_num_style,
                                                          variables=variables,
                                                          labels=self._labels)

        # Apply drop cap to non-TOC components
        if (component.type != ComponentType.TOC
                and self.project.drop_cap_enabled
                and component.type.value in self.project.drop_cap_types):
            html_content = self._apply_drop_cap(html_content)

        # Extract footnotes when footnotes component exists
        if footnotes_comp:
            html_content, fn_data = self._strip_footnotes_from_html(html_content, component)
            if fn_data and collected_footnotes is not None:
                collected_footnotes[component.id] = {
                    'title': display_title,
                    'footnotes': fn_data,
                }

        chapter = epub.EpubHtml(
            title=display_title,
            file_name=f"{component.filename.replace('.md', '.xhtml')}",
            lang=self.project.language,
        )

        full_html = f"""<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">
<head>
    <title>{display_title}</title>
</head>
<body>
{html_content}
</body>
</html>"""

        chapter.content = full_html.encode("utf-8")

        if style_items:
            for item in style_items:
                chapter.add_item(item)

        return chapter

    def _strip_footnotes_from_html(self, html: str, component: Component) -> tuple:
        """Extract footnotes from rendered HTML and remove them.
        
        Returns (cleaned_html, list_of_(namespaced_id, li_inner_html)).
        """
        fn_div_match = EpubService.FOOTNOTE_DIV_RE.search(html)
        if not fn_div_match:
            return html, []

        ol_content = fn_div_match.group(1)
        ch_fn_base = component.filename.replace('.md', '')
        fn_filename = self._get_footnotes_component().filename.replace('.md', '.xhtml')

        footnotes = []
        for li_match in EpubService.LI_FN_RE.finditer(ol_content):
            orig_num = li_match.group(1)
            li_inner = li_match.group(2)
            namespaced_id = f"fn:{ch_fn_base}-{orig_num}"

            # Rewrite backlinks: href="#fnref:X" -> href="{ch_fn_base}.xhtml#fnref:X"
            li_inner = EpubService.FN_BACKLINK_RE.sub(
                f'href="{ch_fn_base}.xhtml#fnref:\\1"', li_inner
            )

            footnotes.append((namespaced_id, li_inner))

        # Remove footnote div from HTML
        html = EpubService.FOOTNOTE_DIV_RE.sub('', html)

        # Rewrite sup references: href="#fn:X" -> href="{fn_filename}#fn:{ch_fn_base}-X"
        html = EpubService.SUP_FN_REF_RE.sub(
            lambda m: f'href="{fn_filename}#fn:{ch_fn_base}-{m.group(1)}"', html
        )

        return html, footnotes

    def _build_footnotes_chapter(
        self, component: Component, collected: Dict[str, dict],
        style_items: List[epub.EpubItem] = None,
        variables: Optional[Dict[str, str]] = None,
    ) -> Optional[epub.EpubHtml]:
        """Build the footnotes chapter with user content + collected footnotes."""
        content = FileService.load_component(self.project.path, component)
        display_title = self._component_label(component)

        if content:
            frontmatter, markdown_content = YamlService.parse_frontmatter(content)
        else:
            frontmatter = {}
            markdown_content = f"# {display_title}\n\n"

        # Render user content with header
        h1_match = re.search(r'^# (.+)$', markdown_content, re.MULTILINE)
        default_title = h1_match.group(1).strip() if h1_match else ""
        show_title = frontmatter.get("show_title", True)

        header_html = self._build_header_html("", "", display_title if show_title else "")
        if header_html:
            if h1_match:
                markdown_content = (markdown_content[:h1_match.start()]
                                    + markdown_content[h1_match.end():])
                markdown_content = markdown_content.strip()
            markdown_content = header_html + markdown_content
        elif show_title and not default_title:
            markdown_content = f"# {display_title}\n\n{markdown_content}"

        user_html = self.markdown_service.render(markdown_content, component.type, component.id,
                                                  variables=variables, labels=self._labels)

        # Build flat footnotes collection in document order, no chapter grouping
        if collected:
            fn_parts = ['<ol class="footnotes-collection">']
            for data in collected.values():
                for namespaced_id, li_inner in data['footnotes']:
                    value_num = namespaced_id.rsplit('-', 1)[1]
                    if int(value_num) >= ERROR_BASE_KEY:
                        fn_parts.append(f'<li id="{namespaced_id}">{li_inner}</li>')
                    else:
                        fn_parts.append(f'<li id="{namespaced_id}" value="{value_num}">{li_inner}</li>')
            fn_parts.append('</ol>')
            fn_collection = '\n'.join(fn_parts)
            # Insert footnotes collection before closing </section>
            sep = '</section>'
            if sep in user_html:
                full_html_content = user_html.replace(sep, fn_collection + '\n' + sep, 1)
            else:
                full_html_content = user_html + '\n' + fn_collection
        else:
            full_html_content = user_html

        chapter = epub.EpubHtml(
            title=display_title,
            file_name=f"{component.filename.replace('.md', '.xhtml')}",
            lang=self.project.language,
        )

        full_html = f"""<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">
<head>
    <title>{display_title}</title>
</head>
<body>
{full_html_content}
</body>
</html>"""

        chapter.content = full_html.encode("utf-8")

        if style_items:
            for item in style_items:
                chapter.add_item(item)

        return chapter

    def _create_part_chapter(
        self, component: Component, style_items: List[epub.EpubItem] = None,
        part_number: Optional[int] = None,
    ) -> Optional[epub.EpubHtml]:
        content = FileService.load_component(self.project.path, component)
        markdown_content = f"# {component.title}"
        frontmatter = {}
        if content:
            frontmatter, md_text = YamlService.parse_frontmatter(content)
            if md_text.strip():
                markdown_content = md_text

        number_part, title_part, display_title = self._get_part_header(
            component, part_number
        )

        show_title = frontmatter.get("show_title", True)
        h1_match = re.search(r'^# (.+)$', markdown_content, re.MULTILINE)
        default_title = h1_match.group(1).strip() if h1_match else ""

        if show_title:
            replaces_title = self.project.auto_part_title in ("part_number", "number")
            if default_title and not title_part and not replaces_title:
                title_part = default_title
            if default_title and title_part and default_title != self._component_label(component):
                title_part = default_title

        subtitle_part = ""
        if title_part:
            subtitle_part, title_part = EpubService._split_title(title_part, frontmatter)

        header_html = self._build_header_html(number_part, subtitle_part, title_part)
        if header_html:
            if h1_match:
                markdown_content = (markdown_content[:h1_match.start()]
                                    + markdown_content[h1_match.end():])
                markdown_content = markdown_content.strip()
            markdown_content = header_html + markdown_content
        elif show_title and not default_title:
            markdown_content = f"# {self._component_label(component)}\n\n{markdown_content}"

        import markdown
        md = markdown.Markdown(extensions=self.markdown_service.extensions,
                               extension_configs=self.markdown_service.get_extension_configs())
        html = md.convert(LANG_MARKER_STRIP_RE.sub('', markdown_content))

        chapter = epub.EpubHtml(
            title=display_title or self._component_label(component),
            file_name=f"{component.filename.replace('.md', '.xhtml')}",
            lang=self.project.language,
        )

        full_html = f"""<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">
<head>
    <title>{display_title or self._component_label(component)}</title>
</head>
<body>
<section class="component-part">
{html}
</section>
</body>
</html>"""

        chapter.content = full_html.encode("utf-8")

        if style_items:
            for item in style_items:
                chapter.add_item(item)

        return chapter

    def _load_stylesheet(self) -> Optional[str]:
        theme_path = ThemeService.get_theme_path(self.project.theme_id)
        if not theme_path:
            return None

        theme_dir = Path(theme_path)

        theme_yaml_path = theme_dir / "theme.yaml"
        theme_config = {}
        if theme_yaml_path.exists():
            import yaml
            with open(theme_yaml_path) as f:
                theme_config = yaml.safe_load(f) or {}

        css_parts = []

        # Level 1: Theme base
        style_path = theme_dir / "style.css"
        if style_path.exists():
            css_parts.append(style_path.read_text(encoding="utf-8"))

        # Level 1: Theme component CSS
        for css_file in theme_config.get("styles", {}).values():
            comp_style_path = theme_dir / css_file
            if comp_style_path.exists():
                css_parts.append(comp_style_path.read_text(encoding="utf-8"))

        # Level 2: Book-level custom CSS
        if self.project.custom_css:
            css_parts.append(self.project.custom_css)

        # Level 3: Pygments code syntax CSS
        css_parts.append(MarkdownService.get_code_css())

        return "\n".join(css_parts) if css_parts else None
