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
from .markdown_service import MarkdownService
from .file_service import FileService
from .yaml_service import YamlService
from .labels_service import resolve_labels as _resolve_labels_fn
from .header_builder import HeaderBuilder
from .toc_builder import TocBuilder
from .footnotes_processor import FootnotesProcessor
from .figure_table_processor import FigureTableProcessor
from .style_manager import StyleManager


class EpubService:
    """Generates EPUB files from a Project using ebooklib.

    Orchestrates the full EPUB generation pipeline: metadata, styles,
    chapters, TOC, footnotes, figures, tables, and spine.
    """

    COVER_ONLY_IMAGE_RE = re.compile(r'^\s*!\[.*?\]\([^)]+\)\s*(\{.*?\})?\s*$')

    def __init__(self, project: Project):
        self.project = project
        self.markdown_service = MarkdownService()
        self._labels: Dict[str, str] = {}
        self._header_builder: Optional[HeaderBuilder] = None
        self._toc_builder: Optional[TocBuilder] = None
        self._footnotes_processor: Optional[FootnotesProcessor] = None
        self._figure_table_processor: Optional[FigureTableProcessor] = None
        self._style_manager: Optional[StyleManager] = None

    @staticmethod
    def is_cover_only_image(md_content: str) -> bool:
        """Check whether the markdown content is a single image (cover-only).

        Args:
            md_content: Markdown text to check.

        Returns:
            True if the content is exactly one image line.
        """
        lines = [l.strip() for l in md_content.strip().split('\n') if l.strip()]
        return len(lines) == 1 and bool(EpubService.COVER_ONLY_IMAGE_RE.match(lines[0]))

    @staticmethod
    def extract_cover_image(md_content: str):
        """Extract alt text and src from a single-image markdown line.

        Args:
            md_content: Markdown text containing an image.

        Returns:
            A tuple (alt, src) or None if no image found.
        """
        m = re.match(r'^\s*!\[(.*?)\]\(([^)]+)\)', md_content.strip())
        if m:
            return (m.group(1), m.group(2).strip())
        return None

    def resolve_labels(self, global_config: Optional[Dict] = None) -> Dict[str, str]:
        """Resolve component labels for the project language.

        Args:
            global_config: Optional global configuration dict for label overrides.

        Returns:
            The resolved labels dictionary.
        """
        self._labels = _resolve_labels_fn(
            self.project.language,
            self.project.labels,
            global_config,
        )
        self._header_builder = HeaderBuilder(self.project, self._labels)
        self._toc_builder = TocBuilder(self.project, self._labels, self._header_builder)
        self._footnotes_processor = FootnotesProcessor(
            self.project, self._labels, self._header_builder, self.markdown_service
        )
        self._figure_table_processor = FigureTableProcessor(self.project, self._labels)
        self._style_manager = StyleManager(self.project)
        return self._labels

    def generate(self, output_path: str, epub_version: str = "epub3",
                 global_config: Optional[Dict] = None) -> Optional[str]:
        """Generate an EPUB file from the project.

        Args:
            output_path: Destination file path for the EPUB.
            epub_version: Either "epub2" or "epub3".
            global_config: Optional global configuration for labels.

        Returns:
            The output file path on success, None on failure.
        """
        try:
            self.resolve_labels(global_config)
            book = self._create_book()
            variables = self._build_variables()
            toc_filter = self._toc_builder.get_toc_include_filter()
            style_items = self._style_manager.create_style_items(book)
            type_css_items, comp_css_items = self._style_manager.create_css_override_items(book)

            footnote_start = self._prescan_footnote_numbers()
            figure_info, figure_start = self._figure_table_processor.prescan_figures()
            table_info, table_start = self._figure_table_processor.prescan_tables()

            part_chapters = self._create_part_chapters(book, style_items)
            chapter_map, collected_footnotes = self._create_component_chapters(
                book, style_items, type_css_items, comp_css_items,
                footnote_start, figure_info, figure_start,
                table_info, table_start, variables,
            )
            self._create_footnotes_chapter_if_needed(
                book, style_items, type_css_items, comp_css_items,
                chapter_map, collected_footnotes, variables,
            )

            ordered_chapters = self._build_ordered_chapters(chapter_map, part_chapters)
            self._toc_builder.build_reader_toc(book, chapter_map, part_chapters, toc_filter)
            self._build_spine(book, ordered_chapters, epub_version)

            return self._write_epub(book, output_path)

        except Exception as e:
            print(f"Error generating EPUB: {e}")
            return None

    def apply_drop_cap(self, html: str) -> str:
        """Wrap the drop-cap chars in the first <p> with <span class=\"drop-cap\">.

        Args:
            html: The rendered HTML content.

        Returns:
            HTML with drop-cap span applied to the first paragraph.
        """
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

    def embed_images(self, book: epub.EpubBook, html_content: str, comp_id: str, embedded: Set[str]) -> None:
        """Find <img> tags in HTML content and embed referenced images into the EPUB.

        Args:
            book: The EPUB book to add images to.
            html_content: HTML string to scan for <img> tags.
            comp_id: Component ID for generating unique image UIDs.
            embedded: Set of already embedded image paths (for deduplication).
        """
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

    # ── Private: generate() helpers ─────────────────────────────────────

    def _create_book(self) -> epub.EpubBook:
        """Create an EpubBook with project metadata."""
        book = epub.EpubBook()
        book.set_identifier(str(uuid.uuid4()))
        book.set_title(self.project.title)
        book.set_language(self.project.language)
        book.add_author(self.project.author)
        book.add_metadata("DC", "publisher", self.project.publisher or "MDToEPUB")
        book.add_metadata("DC", "date", self.project.publication_date or datetime.now().isoformat())
        return book

    def _build_variables(self) -> Dict[str, str]:
        """Build template variables from project metadata."""
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
        return {k: v for k, v in variables.items() if v}

    def _prescan_footnote_numbers(self) -> Dict[str, int]:
        """Count footnote references per component for global renumbering."""
        footnote_start: Dict[str, int] = {}
        running_total = 0
        for component in self.project.get_ordered_components():
            if component.type in (ComponentType.PART, ComponentType.FOOTNOTES):
                continue
            content = FileService.load_component(self.project.path, component)
            if content:
                _, md_text = YamlService.parse_frontmatter(content)
                fn_count = MarkdownService.count_footnote_refs(md_text)
                footnote_start[component.id] = running_total + 1
                running_total += fn_count
        return footnote_start

    def _create_part_chapters(
        self, book: epub.EpubBook, style_items: List[epub.EpubItem]
    ) -> Dict[str, epub.EpubHtml]:
        """Create EPUB chapters for all part components."""
        part_chapters: Dict[str, epub.EpubHtml] = {}
        part_count = 0
        for part_comp in self.project.get_parts():
            part_count += 1
            part_ch = self._create_part_chapter(part_comp, style_items, part_count)
            if part_ch:
                part_chapters[part_comp.id] = part_ch
                book.add_item(part_ch)
                self.embed_images(book, part_ch.content.decode("utf-8"), part_comp.id, set())
        return part_chapters

    def _create_component_chapters(
        self,
        book: epub.EpubBook,
        style_items: List[epub.EpubItem],
        type_css_items: Dict[str, epub.EpubItem],
        comp_css_items: Dict[str, epub.EpubItem],
        footnote_start: Dict[str, int],
        figure_info: list,
        figure_start: Dict[str, int],
        table_info: list,
        table_start: Dict[str, int],
        variables: Dict[str, str],
    ) -> Tuple[Dict[str, epub.EpubHtml], Dict[str, dict]]:
        """Create EPUB chapters for all non-part, non-footnotes components."""
        chapter_map: Dict[str, epub.EpubHtml] = {}
        collected_footnotes: Dict[str, dict] = {}
        footnotes_comp = self._footnotes_processor.get_footnotes_component()
        chapter_count = 0
        appendix_count = 0

        for component in self.project.get_ordered_components():
            if component.type in (ComponentType.PART, ComponentType.FOOTNOTES):
                continue
            if component.type == ComponentType.CHAPTER:
                chapter_count += 1
            elif component.type == ComponentType.APPENDIX:
                appendix_count += 1

            comp_number = None
            if component.should_use_numbering():
                comp_number = chapter_count if component.type == ComponentType.CHAPTER else appendix_count

            chapter_styles = self._style_manager.build_chapter_styles(
                style_items, type_css_items, comp_css_items, component
            )

            chapter = self._create_chapter(
                component, chapter_styles, comp_number,
                footnotes_comp=footnotes_comp,
                collected_footnotes=collected_footnotes,
                start_number=footnote_start.get(component.id, 1),
                figure_num_start=figure_start.get(component.id, 0),
                figure_num_style=self.project.figure_numbering_style,
                figure_info=figure_info if component.type == ComponentType.LOF else None,
                table_num_start=table_start.get(component.id, 0),
                table_num_style=self.project.table_numbering_style,
                table_info=table_info if component.type == ComponentType.LOT else None,
                variables=variables,
            )
            if chapter:
                chapter_map[component.id] = chapter
                book.add_item(chapter)
                self.embed_images(book, chapter.content.decode("utf-8"), component.id, set())

        return chapter_map, collected_footnotes

    def _create_footnotes_chapter_if_needed(
        self,
        book: epub.EpubBook,
        style_items: List[epub.EpubItem],
        type_css_items: Dict[str, epub.EpubItem],
        comp_css_items: Dict[str, epub.EpubItem],
        chapter_map: Dict[str, epub.EpubHtml],
        collected_footnotes: Dict[str, dict],
        variables: Dict[str, str],
    ) -> None:
        """Build the footnotes chapter if a FOOTNOTES component exists."""
        footnotes_comp = self._footnotes_processor.get_footnotes_component()
        if not footnotes_comp:
            return
        fn_styles = self._style_manager.build_chapter_styles(
            style_items, type_css_items, comp_css_items, footnotes_comp
        )
        fn_chapter = self._footnotes_processor.build_footnotes_chapter(
            footnotes_comp, collected_footnotes, fn_styles, variables
        )
        if fn_chapter:
            chapter_map[footnotes_comp.id] = fn_chapter
            book.add_item(fn_chapter)
            self.embed_images(book, fn_chapter.content.decode("utf-8"), footnotes_comp.id, set())

    def _build_ordered_chapters(
        self,
        chapter_map: Dict[str, epub.EpubHtml],
        part_chapters: Dict[str, epub.EpubHtml],
    ) -> List:
        """Order chapters inserting part chapters before their first chapter."""
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
        return ordered_chapters

    def _build_spine(
        self, book: epub.EpubBook, ordered_chapters: List, epub_version: str
    ) -> None:
        """Set the spine and navigation items on the book."""
        book.spine = ordered_chapters
        book.add_item(epub.EpubNcx())
        if epub_version != "epub2":
            book.add_item(epub.EpubNav())

    def _write_epub(self, book: epub.EpubBook, output_path: str) -> Optional[str]:
        """Write the EPUB file to disk."""
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        epub.write_epub(str(output_file), book, {})
        return str(output_file)

    # ── Private: chapter creation ───────────────────────────────────────

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
        """Create an EPUB chapter from a component."""
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
        if component.type == ComponentType.COVER and self.is_cover_only_image(markdown_content):
            return self._create_cover_image_chapter(component, markdown_content)

        # Determine default title from h1 in content
        h1_match = re.search(r'^# (.+)$', markdown_content, re.MULTILINE)
        default_title = h1_match.group(1).strip() if h1_match else ""

        # Get auto-header components
        number_part, title_part, display_title = self._header_builder.get_component_header(
            component, chapter_number
        )

        show_title = frontmatter.get("show_title", True)
        if show_title:
            replaces_title = (self.project.auto_appendix_title if component.type == ComponentType.APPENDIX else self.project.auto_chapter_title) in ("chapter_number", "number")
            if default_title and not title_part and not replaces_title:
                title_part = default_title
            if default_title and title_part and default_title != self._component_label(component):
                title_part = default_title

        # Split title_part into subtitle + title for separate styling
        full_title = title_part
        subtitle_part = ""
        if title_part:
            subtitle_part, title_part = HeaderBuilder.split_title(title_part, frontmatter)

        if number_part and full_title:
            display_title = f"{number_part}: {full_title}"
        elif number_part:
            display_title = number_part
        elif full_title:
            display_title = full_title
        else:
            display_title = default_title or self._component_label(component)

        # Generate HTML based on component type
        if component.type == ComponentType.TOC:
            html_content = self._generate_toc_component_html(
                component, frontmatter, markdown_content
            )
        elif component.type == ComponentType.LOF:
            html_content = self._generate_lof_component_html(
                component, frontmatter, markdown_content, figure_info
            )
        elif component.type == ComponentType.LOT:
            html_content = self._generate_lot_component_html(
                component, frontmatter, markdown_content, table_info
            )
        else:
            html_content = self._generate_standard_chapter_html(
                component, frontmatter, markdown_content,
                h1_match, default_title, show_title,
                number_part, subtitle_part, title_part,
                start_number, figure_num_start, figure_num_style,
                table_num_start, table_num_style, variables,
            )

        # Apply drop cap to non-TOC components
        if (component.type != ComponentType.TOC
                and self.project.drop_cap_enabled
                and component.type.value in self.project.drop_cap_types):
            html_content = self.apply_drop_cap(html_content)

        # Extract footnotes when footnotes component exists
        if footnotes_comp:
            html_content, fn_data = self._footnotes_processor.strip_footnotes_from_html(html_content, component)
            if fn_data and collected_footnotes is not None:
                collected_footnotes[component.id] = {
                    'title': display_title,
                    'footnotes': fn_data,
                }

        return self._wrap_as_epub_chapter(component, display_title, html_content, style_items)

    def _create_cover_image_chapter(
        self, component: Component, md_content: str
    ) -> epub.EpubHtml:
        """Create a cover chapter that displays a single full-page image."""
        img_info = self.extract_cover_image(md_content)
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

    def _generate_toc_component_html(
        self, component: Component, frontmatter: Dict, markdown_content: str
    ) -> str:
        """Generate HTML for a TOC component."""
        toc_deep = TocBuilder.normalize_toc_deep(frontmatter.get("toc_deep", 2))
        toc_filter = self._toc_builder.get_toc_include_filter()
        auto_toc = self._toc_builder.generate_toc_html(toc_filter, toc_deep)
        import markdown
        md = markdown.Markdown(extensions=self.markdown_service.extensions,
                               extension_configs=self.markdown_service.get_extension_configs())
        title_html = md.convert(LANG_MARKER_STRIP_RE.sub('', markdown_content)) if markdown_content.strip() else ""
        title_html = MarkdownService.add_image_captions(title_html, labels=self._labels)
        combined = (title_html + "\n" + auto_toc) if title_html else auto_toc
        return MarkdownService.wrap_in_section(combined, component.type, component.id)

    def _generate_lof_component_html(
        self, component: Component, frontmatter: Dict,
        markdown_content: str, figure_info: Optional[list]
    ) -> str:
        """Generate HTML for a List of Figures component."""
        auto_lof = self._figure_table_processor.generate_lof_html(figure_info) if figure_info else ""
        import markdown
        md = markdown.Markdown(extensions=self.markdown_service.extensions,
                               extension_configs=self.markdown_service.get_extension_configs())
        title_html = md.convert(LANG_MARKER_STRIP_RE.sub('', markdown_content)) if markdown_content.strip() else ""
        title_html = MarkdownService.add_image_captions(title_html, labels=self._labels)
        combined = (title_html + "\n" + auto_lof) if title_html else auto_lof
        return MarkdownService.wrap_in_section(combined, component.type, component.id)

    def _generate_lot_component_html(
        self, component: Component, frontmatter: Dict,
        markdown_content: str, table_info: Optional[list]
    ) -> str:
        """Generate HTML for a List of Tables component."""
        auto_lot = self._figure_table_processor.generate_lot_html(table_info) if table_info else ""
        import markdown
        md = markdown.Markdown(extensions=self.markdown_service.extensions,
                               extension_configs=self.markdown_service.get_extension_configs())
        title_html = md.convert(LANG_MARKER_STRIP_RE.sub('', markdown_content)) if markdown_content.strip() else ""
        title_html = MarkdownService.add_image_captions(title_html, labels=self._labels)
        title_html = MarkdownService.add_table_captions(title_html, labels=self._labels)
        combined = (title_html + "\n" + auto_lot) if title_html else auto_lot
        return MarkdownService.wrap_in_section(combined, component.type, component.id)

    def _generate_standard_chapter_html(
        self,
        component: Component,
        frontmatter: Dict,
        markdown_content: str,
        h1_match,
        default_title: str,
        show_title: bool,
        number_part: str,
        subtitle_part: str,
        title_part: str,
        start_number: int,
        figure_num_start: int,
        figure_num_style: str,
        table_num_start: int,
        table_num_style: str,
        variables: Optional[Dict[str, str]],
    ) -> str:
        """Generate HTML for a standard chapter (not TOC/LOF/LOT/cover-image)."""
        header_html = self._header_builder.build_header_html(number_part, subtitle_part, title_part)
        if header_html:
            if h1_match:
                markdown_content = (markdown_content[:h1_match.start()]
                                    + markdown_content[h1_match.end():])
                markdown_content = markdown_content.strip()
            markdown_content = header_html + markdown_content
        elif show_title:
            if not default_title:
                markdown_content = f"# {self._component_label(component)}\n\n{markdown_content}"
        else:
            if h1_match:
                markdown_content = (markdown_content[:h1_match.start()]
                                    + markdown_content[h1_match.end():])
                markdown_content = markdown_content.strip()

        return self.markdown_service.render(
            markdown_content, component.type, component.id, start_number,
            figure_num_start, figure_num_style,
            table_num_start, table_num_style,
            variables=variables,
            labels=self._labels,
        )

    def _wrap_as_epub_chapter(
        self,
        component: Component,
        display_title: str,
        html_content: str,
        style_items: Optional[List[epub.EpubItem]],
    ) -> epub.EpubHtml:
        """Wrap rendered HTML content in an EpubHtml chapter object."""
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

    # ── Private: utilities ──────────────────────────────────────────────

    def _component_label(self, component: Component) -> str:
        """Return the display name for a component using resolved labels."""
        return component.get_display_name(self._labels)

    def _create_part_chapter(
        self, component: Component, style_items: List[epub.EpubItem] = None,
        part_number: Optional[int] = None,
    ) -> Optional[epub.EpubHtml]:
        """Create an EPUB chapter for a part component."""
        content = FileService.load_component(self.project.path, component)
        markdown_content = f"# {component.title}"
        frontmatter = {}
        if content:
            frontmatter, md_text = YamlService.parse_frontmatter(content)
            if md_text.strip():
                markdown_content = md_text

        number_part, title_part, display_title = self._header_builder.get_part_header(
            component, part_number
        )

        show_title = frontmatter.get("show_title", True)
        h1_match = re.search(r'^# (.+)$', markdown_content, re.MULTILINE)
        default_title = h1_match.group(1).strip() if h1_match else ""

        if show_title:
            replaces_title = self.project.auto_part_title in ("part_number", "number", "word_part")
            if default_title and not title_part and not replaces_title:
                title_part = default_title
            if default_title and title_part and default_title != self._component_label(component):
                title_part = default_title

        subtitle_part = ""
        if title_part:
            subtitle_part, title_part = HeaderBuilder.split_title(title_part, frontmatter)

        header_html = self._header_builder.build_header_html(number_part, subtitle_part, title_part)
        if header_html:
            if h1_match:
                markdown_content = (markdown_content[:h1_match.start()]
                                    + markdown_content[h1_match.end():])
                markdown_content = markdown_content.strip()
            markdown_content = header_html + markdown_content
        elif show_title and not default_title:
            markdown_content = f"# {self._component_label(component)}\n\n{markdown_content}"
        elif not show_title and h1_match:
            markdown_content = (markdown_content[:h1_match.start()]
                                + markdown_content[h1_match.end():])
            markdown_content = markdown_content.strip()

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
