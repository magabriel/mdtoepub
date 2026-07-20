from typing import Dict, Optional, Tuple

from ..models.project import Project
from ..models.component import Component, ComponentType
from .markdown_service import MarkdownService


class HeaderBuilder:
    """Builds component and part headers with auto-numbering support.

    Responsible for generating the display title, number part, and HTML
    header for chapters, appendices, and parts based on project configuration.
    """

    SUBTITLE_SEPARATOR_RE = __import__('re').compile(r'\s+[-–—]\s+')

    def __init__(self, project: Project, labels: Dict[str, str]):
        """Initialize with project config and resolved labels.

        Args:
            project: The project containing auto-title and numbering settings.
            labels: Resolved label dictionary (e.g. {"chapter": "Chapter"}).
        """
        self.project = project
        self.labels = labels

    def _component_label(self, component: Component) -> str:
        """Return the display name for a component using resolved labels."""
        return component.get_display_name(self.labels)

    def get_component_header(
        self, component: Component, chapter_number: Optional[int] = None
    ) -> Tuple[str, str, str]:
        """Compute the header parts for a chapter or appendix component.

        Args:
            component: The component to generate a header for.
            chapter_number: The sequential number for this component (if applicable).

        Returns:
            A tuple of (number_part, title_part, display_title).
            - number_part: The auto-numbering string (e.g. "Chapter 1").
            - title_part: The title text.
            - display_title: Combined display string.
        """
        show_title = component.frontmatter.get("show_title", True)
        number_part = ""
        title_part = ""

        mode = self.project.auto_chapter_title
        num_style = self.project.chapter_numbering_style
        if component.type == ComponentType.APPENDIX:
            mode = self.project.auto_appendix_title
            num_style = self.project.appendix_numbering_style
        if mode != "none" and show_title:
            if component.should_use_numbering() and chapter_number is not None:
                label = self.labels.get("chapter", "Capítulo") if component.type == ComponentType.CHAPTER else self.labels.get("appendix", "Apéndice")
                num_str = str(chapter_number)
                if num_style == "roman":
                    num_str = MarkdownService._to_roman(chapter_number)
                if mode == "chapter_number":
                    number_part = f"{label} {num_str}"
                elif mode == "number":
                    number_part = num_str
                elif mode == "chapter_number_with_title":
                    number_part = f"{label} {num_str}"
                    title_part = self._component_label(component)
                elif mode == "number_with_title":
                    number_part = num_str
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

    def get_part_header(
        self, component: Component, part_number: Optional[int] = None
    ) -> Tuple[str, str, str]:
        """Compute the header parts for a part component.

        Args:
            component: The part component to generate a header for.
            part_number: The sequential number for this part.

        Returns:
            A tuple of (number_part, title_part, display_title).
        """
        show_title = component.frontmatter.get("show_title", True)
        number_part = ""
        title_part = ""

        mode = self.project.auto_part_title
        num_style = self.project.part_numbering_style
        if mode != "none" and show_title:
            if part_number is not None:
                label = self.labels.get("part", "Parte")
                num_str = str(part_number)
                if num_style == "roman":
                    num_str = MarkdownService._to_roman(part_number)
                elif num_style == "word":
                    num_str = MarkdownService._to_word(part_number, self.project.language)
                if mode == "part_number":
                    number_part = f"{label} {num_str}" if num_style != "word" else num_str
                elif mode == "number":
                    number_part = num_str
                elif mode == "part_number_with_title":
                    number_part = f"{label} {num_str}" if num_style != "word" else num_str
                    title_part = self._component_label(component)
                elif mode == "number_with_title":
                    number_part = num_str
                    title_part = self._component_label(component)
                elif mode == "word_part":
                    word = MarkdownService._to_word(part_number, self.project.language)
                    number_part = f"{word} {label.lower()}"
                elif mode == "word_part_with_title":
                    word = MarkdownService._to_word(part_number, self.project.language)
                    number_part = f"{word} {label.lower()}"
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

    def build_header_html(self, number_part: str, subtitle_part: str, title_part: str) -> str:
        """Build an <h1 class="component-header"> from its parts.

        Args:
            number_part: The auto-numbering string (e.g. "Chapter 1").
            subtitle_part: The subtitle text (from title splitting).
            title_part: The main title text.

        Returns:
            HTML string for the header, or empty string if all parts are empty.
        """
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
    def split_title(title: str, frontmatter: Optional[Dict] = None) -> Tuple[str, str]:
        """Split title into (subtitle, title) on a dash separator.

        Uses the pattern ``<space><dash><space>`` (en-dash, em-dash, or hyphen).

        Args:
            title: The full title string.
            frontmatter: Optional frontmatter dict. If ``split_title`` is False,
                the title is returned unchanged.

        Returns:
            A tuple of (subtitle, title). If no split occurs or splitting is
            disabled, returns ("", original_title).
        """
        if frontmatter is not None and not frontmatter.get("split_title", True):
            return "", title
        m = HeaderBuilder.SUBTITLE_SEPARATOR_RE.search(title)
        if m:
            subtitle = title[:m.start()].strip()
            rest = title[m.end():].strip()
            if subtitle and rest:
                return subtitle, rest
        return "", title
