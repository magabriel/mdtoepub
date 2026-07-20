import re
from pathlib import Path
from typing import List, Dict, Optional
from ..models.component import ComponentType


STYLE_DOC_PATTERN = re.compile(
    r'/\*\s*@doc\s+(.+?)\s*\*/\s*([^{]+?)\s*\{'
)


DocEntry = Dict[str, str]


class StyleDocService:
    """Extracts documentation from CSS @doc comments.

    Parses ``/* @doc Description */ .selector {`` patterns from CSS files
    and returns structured documentation entries.
    """

    def __init__(self, theme_dir: str):
        """Initialize with a theme directory path.

        Args:
            theme_dir: Path to the theme directory containing CSS files.
        """
        self.theme_dir = Path(theme_dir)
        self._cache: Dict[str, List[DocEntry]] = {}

    def get_docs(self, css_file: str) -> List[DocEntry]:
        """Get @doc entries from a CSS file, with caching.

        Args:
            css_file: Filename of the CSS file relative to theme_dir.

        Returns:
            List of doc entry dicts with description, selector, label, markdown_hint.
        """
        if css_file in self._cache:
            return self._cache[css_file]

        path = self.theme_dir / css_file
        if not path.exists():
            self._cache[css_file] = []
            return []

        css_text = path.read_text(encoding="utf-8")
        entries = self.parse(css_text)
        self._cache[css_file] = entries
        return entries

    def get_docs_for_type(self, component_type: ComponentType,
                          theme_config: dict) -> List[DocEntry]:
        """Get @doc entries for a specific component type from theme config.

        Args:
            component_type: The component type to get docs for.
            theme_config: Theme configuration dict with "styles" mapping.

        Returns:
            List of doc entry dicts.
        """
        css_file = theme_config.get("styles", {}).get(component_type.value)
        if css_file:
            return self.get_docs(css_file)
        return []

    def get_docs_from_css(self, css_text: str) -> List[DocEntry]:
        """Get @doc entries from CSS text directly.

        Args:
            css_text: CSS content to parse.

        Returns:
            List of doc entry dicts.
        """
        return self.parse(css_text)

    def parse(self, css_text: str) -> List[DocEntry]:
        """Parse @doc annotations from CSS text.

        Args:
            css_text: CSS content to parse.

        Returns:
            List of doc entry dicts with description, selector, label, markdown_hint.
        """
        entries = []
        for match in STYLE_DOC_PATTERN.finditer(css_text):
            description = match.group(1).strip()
            raw_selector = match.group(2).strip()
            label = self._selector_to_label(raw_selector)
            markdown_hint = self._selector_to_markdown_hint(raw_selector)
            entries.append({
                "description": description,
                "selector": raw_selector,
                "label": label,
                "markdown_hint": markdown_hint,
            })
        return entries

    @staticmethod
    def _selector_to_label(selector: str) -> str:
        """Extract a human-readable label from a CSS selector."""
        last_part = selector.split()[-1] if " " in selector else selector
        last_part = re.sub(r':[a-z-]+', '', last_part)
        last_part = last_part.strip()
        if last_part.startswith("."):
            return last_part[1:]
        if last_part.startswith("#"):
            return last_part[1:]
        return last_part

    @staticmethod
    def _selector_to_markdown_hint(selector: str) -> str:
        """Generate a markdown hint for how to apply a CSS selector."""
        parts = selector.split()
        last = parts[-1] if parts else selector
        last = re.sub(r':[a-z-]+', '', last)
        if last.startswith("."):
            return "{" + last + "}"
        if last in ("h1", "h2", "h3", "h4", "h5", "h6"):
            return "# " + last
        if last.startswith("#"):
            return last
        return last

    def invalidate_cache(self):
        """Clear the parsed docs cache."""
        self._cache.clear()
