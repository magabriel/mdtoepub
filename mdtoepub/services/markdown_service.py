from typing import List, Optional
import markdown
from pygments.formatters.html import HtmlFormatter
import re
from ..models.component import ComponentType


PYGMENTS_STYLE = "friendly"


class MarkdownService:
    def __init__(self, extensions: Optional[List[str]] = None):
        self.extensions = extensions or [
            "markdown.extensions.tables",
            "markdown.extensions.fenced_code",
            "markdown.extensions.codehilite",
            "markdown.extensions.toc",
            "markdown.extensions.meta",
            "markdown.extensions.nl2br",
            "markdown.extensions.attr_list",
            "markdown.extensions.def_list",
        ]
        self._extension_configs = {
            "markdown.extensions.codehilite": {
                "css_class": "highlight",
                "pygments_style": PYGMENTS_STYLE,
            },
        }

    def render(self, markdown_text: str, component_type: ComponentType = ComponentType.CHAPTER, component_id: str = "") -> str:
        cleaned = re.sub(r'\{lang=\w+(?:[_-]\w+)*\}', '', markdown_text)
        md = markdown.Markdown(extensions=self.extensions,
                               extension_configs=self._extension_configs)
        html = md.convert(cleaned)
        html = self._add_image_captions(html)
        return self._wrap_in_section(html, component_type, component_id)

    @staticmethod
    def get_code_css() -> str:
        return HtmlFormatter(style=PYGMENTS_STYLE, cssclass="highlight").get_style_defs(".highlight")

    @staticmethod
    def _add_image_captions(html: str) -> str:
        """Wrap <img> tags that have alt text in <figure>/<figcaption>."""
        def _wrap(m):
            tag = m.group(0)
            alt_m = re.search(r'alt="([^"]*)"', tag)
            if alt_m and alt_m.group(1).strip():
                alt = alt_m.group(1)
                return f'<figure>\n{tag}\n<figcaption>{alt}</figcaption>\n</figure>'
            return tag
        html = re.sub(r'<img[^>]+>', _wrap, html)
        # Unwrap <figure> from <p> since figure is block-level
        html = re.sub(r'<p>\s*(<figure>.*?</figure>)\s*</p>', r'\1', html, flags=re.DOTALL)
        return html

    def extract_title(self, markdown_text: str) -> Optional[str]:
        for line in markdown_text.split("\n"):
            stripped = line.strip()
            if stripped.startswith("# "):
                return stripped[2:].strip()
        return None

    def get_extensions(self) -> List[str]:
        return self.extensions.copy()

    def get_extension_configs(self) -> dict:
        return dict(self._extension_configs)

    def _wrap_in_section(self, html: str, component_type: ComponentType, component_id: str = "") -> str:
        css_class = f"component-{component_type.value}"
        id_attr = f' id="{component_id}"' if component_id else ""
        return f'<section class="{css_class}"{id_attr}>\n{html}\n</section>'
