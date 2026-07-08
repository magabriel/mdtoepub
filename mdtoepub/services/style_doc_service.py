import re
from pathlib import Path
from typing import List, Dict, Optional
from ..models.component import ComponentType


STYLE_DOC_PATTERN = re.compile(
    r'/\*\s*@doc\s+(.+?)\s*\*/\s*([^{]+?)\s*\{'
)


DocEntry = Dict[str, str]


class StyleDocService:

    def __init__(self, theme_dir: str):
        self.theme_dir = Path(theme_dir)
        self._cache: Dict[str, List[DocEntry]] = {}

    def get_docs(self, css_file: str) -> List[DocEntry]:
        if css_file in self._cache:
            return self._cache[css_file]

        path = self.theme_dir / css_file
        if not path.exists():
            self._cache[css_file] = []
            return []

        css_text = path.read_text(encoding="utf-8")
        entries = self._parse(css_text)
        self._cache[css_file] = entries
        return entries

    def get_docs_for_type(self, component_type: ComponentType,
                          theme_config: dict) -> List[DocEntry]:
        css_file = theme_config.get("styles", {}).get(component_type.value)
        if css_file:
            return self.get_docs(css_file)
        return []

    def get_docs_from_css(self, css_text: str) -> List[DocEntry]:
        return self._parse(css_text)

    def _parse(self, css_text: str) -> List[DocEntry]:
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
        self._cache.clear()
