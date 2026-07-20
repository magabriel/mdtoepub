from typing import List, Optional, Dict
from pathlib import Path
import markdown
from pygments.formatters.html import HtmlFormatter
import re
from ..models.component import ComponentType
from .footnote_processor import FootnoteProcessor
from .caption_processor import CaptionProcessor
from .variable_interpolator import VariableInterpolator


PYGMENTS_STYLE = "friendly"


class MarkdownService:
    """Converts Markdown to HTML using Python-Markdown with extensions.

    Handles rendering, footnote processing, figure/table captions,
    and variable interpolation.
    """

    def __init__(self, extensions: Optional[List[str]] = None):
        """Initialize the Markdown service.

        Args:
            extensions: List of markdown extension paths. Uses defaults if None.
        """
        self.extensions = extensions or [
            "markdown.extensions.tables",
            "markdown.extensions.fenced_code",
            "markdown.extensions.codehilite",
            "markdown.extensions.toc",
            "markdown.extensions.meta",
            "markdown.extensions.attr_list",
            "markdown.extensions.def_list",
            "markdown.extensions.footnotes",
        ]
        self._extension_configs = {
            "markdown.extensions.codehilite": {
                "css_class": "highlight",
                "pygments_style": PYGMENTS_STYLE,
            },
        }
        self._footnote_processor = FootnoteProcessor()
        self._caption_processor = CaptionProcessor()
        self._variable_interpolator = VariableInterpolator()

    def render(
        self,
        markdown_text: str,
        component_type: ComponentType = ComponentType.CHAPTER,
        component_id: str = "",
        start_number: int = 1,
        figure_num_start: int = 0,
        figure_num_style: str = "arabic",
        table_num_start: int = 0,
        table_num_style: str = "arabic",
        variables: Optional[Dict[str, str]] = None,
        labels: Optional[Dict[str, str]] = None,
    ) -> str:
        """Render Markdown text to HTML wrapped in a section element.

        Processing pipeline:
        1. Interpolate {{variables}}
        2. Strip {lang=xx} markers
        3. Renumber footnotes sequentially
        4. Convert Markdown to HTML
        5. Fix footnote display numbers
        6. Add figure captions
        7. Add table captions
        8. Wrap in <section class="component-{type}">

        Args:
            markdown_text: Raw Markdown text.
            component_type: ComponentType for section CSS class.
            component_id: Optional component ID for section id attribute.
            start_number: Starting footnote number for global renumbering.
            figure_num_start: Starting figure number (0 = no numbering).
            figure_num_style: Figure numbering style ("arabic" or "roman").
            table_num_start: Starting table number (0 = no numbering).
            table_num_style: Table numbering style ("arabic" or "roman").
            variables: Optional dict for {{key}} interpolation.
            labels: Optional label overrides for captions.

        Returns:
            Rendered HTML string wrapped in a section element.
        """
        cleaned = self._variable_interpolator.interpolate(markdown_text, variables)
        cleaned = re.sub(r'\{lang=\w+(?:[_-]\w+)*\}', '', cleaned)
        cleaned = self._footnote_processor.renumber_footnotes(cleaned, start_number)
        md = markdown.Markdown(extensions=self.extensions,
                               extension_configs=self._extension_configs)
        html = md.convert(cleaned)
        html = self._footnote_processor.fix_footnote_display_numbers(html)
        html = self._caption_processor.add_image_captions(
            html, figure_num_start, figure_num_style,
            labels=labels, roman_fn=self.to_roman
        )
        html = self._caption_processor.add_table_captions(
            html, table_num_start, table_num_style,
            labels=labels, roman_fn=self.to_roman
        )
        return self.wrap_in_section(html, component_type, component_id)

    def extract_title(self, markdown_text: str) -> Optional[str]:
        """Extract the first H1 heading from Markdown text.

        Args:
            markdown_text: Markdown text to scan.

        Returns:
            The heading text (without #), or None if no H1 found.
        """
        for line in markdown_text.split("\n"):
            stripped = line.strip()
            if stripped.startswith("# "):
                return stripped[2:].strip()
        return None

    def get_extensions(self) -> List[str]:
        """Return a copy of the configured markdown extensions list.

        Returns:
            List of extension paths.
        """
        return self.extensions.copy()

    def get_extension_configs(self) -> dict:
        """Return a copy of the configured extension settings.

        Returns:
            Dict of extension path to config dict.
        """
        return dict(self._extension_configs)

    @staticmethod
    def wrap_in_section(html: str, component_type: ComponentType, component_id: str = "") -> str:
        """Wrap HTML content in a <section> element with component CSS class.

        Args:
            html: HTML content to wrap.
            component_type: ComponentType for CSS class name.
            component_id: Optional ID attribute.

        Returns:
            HTML wrapped in <section class="component-{type}">.
        """
        css_class = f"component-{component_type.value}"
        id_attr = f' id="{component_id}"' if component_id else ""
        return f'<section class="{css_class}"{id_attr}>\n{html}\n</section>'

    @staticmethod
    def get_code_css() -> str:
        """Return Pygments CSS for code syntax highlighting.

        Returns:
            CSS string for code highlighting.
        """
        return HtmlFormatter(style=PYGMENTS_STYLE, cssclass="highlight").get_style_defs(".highlight")

    @staticmethod
    def to_roman(num: int) -> str:
        """Convert an integer to Roman numerals.

        Args:
            num: Integer to convert (1-3999).

        Returns:
            Roman numeral string. Returns the number as string if out of range.
        """
        if num < 1 or num > 3999:
            return str(num)
        vals = [(1000, 'M'), (900, 'CM'), (500, 'D'), (400, 'CD'),
                (100, 'C'), (90, 'XC'), (50, 'L'), (40, 'XL'),
                (10, 'X'), (9, 'IX'), (5, 'V'), (4, 'IV'), (1, 'I')]
        result = []
        for v, s in vals:
            while num >= v:
                result.append(s)
                num -= v
        return ''.join(result)

    @staticmethod
    def to_word(num: int, language: str = "en") -> str:
        """Convert an integer to a word (ordinal, feminine) in the given language.

        Uses gettext translations. Supports 1-10. Falls back to the number
        itself for out-of-range values.

        Args:
            num: Integer to convert.
            language: Language code (e.g. "en", "es").

        Returns:
            Word representation (e.g. "First", "Segunda") or number as string.
        """
        import gettext as _gettext
        locale_dir = str(Path(__file__).parent.parent / "locale")
        t = _gettext.translation("mdtoepub", locale_dir, languages=[language], fallback=True)

        words = [
            "",
            t.gettext("First"),
            t.gettext("Second"),
            t.gettext("Third"),
            t.gettext("Fourth"),
            t.gettext("Fifth"),
            t.gettext("Sixth"),
            t.gettext("Seventh"),
            t.gettext("Eighth"),
            t.gettext("Ninth"),
            t.gettext("Tenth"),
        ]

        if 1 <= num < len(words):
            return words[num]
        return str(num)

    # Delegate methods for backward compatibility with tests and external callers

    @staticmethod
    def count_footnote_refs(text: str) -> int:
        """Count unique footnote references that have matching definitions.

        Args:
            text: Markdown text to analyze.

        Returns:
            Number of unique footnote references with definitions.
        """
        return FootnoteProcessor.count_footnote_refs(text)

    @staticmethod
    def add_image_captions(
        html: str,
        figure_num_start: int = 0,
        figure_num_style: str = "arabic",
        labels: Optional[Dict[str, str]] = None,
    ) -> str:
        """Wrap <img> tags that have alt text in <figure>/<figcaption>.

        Args:
            html: Rendered HTML content.
            figure_num_start: Starting number for figures (0 = no numbering).
            figure_num_style: Numbering style ("arabic" or "roman").
            labels: Optional label overrides.

        Returns:
            HTML with figure/figcaption wrappers.
        """
        return CaptionProcessor.add_image_captions(
            html, figure_num_start, figure_num_style,
            labels=labels, roman_fn=MarkdownService.to_roman
        )

    @staticmethod
    def add_table_captions(
        html: str,
        table_num_start: int = 0,
        table_num_style: str = "arabic",
        labels: Optional[Dict[str, str]] = None,
    ) -> str:
        """Wrap <!-- Table: caption --><table>...</table> in <figure>/<figcaption>.

        Args:
            html: Rendered HTML content.
            table_num_start: Starting number for tables (0 = no numbering).
            table_num_style: Numbering style ("arabic" or "roman").
            labels: Optional label overrides.

        Returns:
            HTML with table figure/figcaption wrappers.
        """
        return CaptionProcessor.add_table_captions(
            html, table_num_start, table_num_style,
            labels=labels, roman_fn=MarkdownService.to_roman
        )

    @staticmethod
    def extract_figure_alts(md_text: str) -> list:
        """Extract alt text from markdown image references, skipping decorative images.

        Args:
            md_text: Markdown text to scan.

        Returns:
            List of (alt_text, image_path) tuples for non-decorative images.
        """
        return CaptionProcessor.extract_figure_alts(md_text)

    @staticmethod
    def extract_table_captions(md_text: str) -> list:
        """Extract captions from <!-- Table: caption --> patterns preceding pipe tables.

        Args:
            md_text: Markdown text to scan.

        Returns:
            List of (caption, None) tuples, skipping those inside code blocks.
        """
        return CaptionProcessor.extract_table_captions(md_text)
