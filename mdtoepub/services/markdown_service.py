from typing import List, Optional, Set, Dict, Tuple
import markdown
from pygments.formatters.html import HtmlFormatter
import re
from ..models.component import ComponentType


PYGMENTS_STYLE = "friendly"

FN_REF_RE = re.compile(r'\[\^(\d+)\]')
FN_DEF_RE = re.compile(r'^(\s*)\[\^(\d+)\]\s*:(.*)$', re.MULTILINE)
ERROR_BASE_KEY = 1000000


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
            "markdown.extensions.footnotes",
        ]
        self._extension_configs = {
            "markdown.extensions.codehilite": {
                "css_class": "highlight",
                "pygments_style": PYGMENTS_STYLE,
            },
        }

    FN_SUP_DISPLAY_RE = re.compile(
        r'(id="fnref:)(\d+)("[^>]*>.*?<a[^>]*>)\d+(</a></sup>)'
    )
    FN_LI_VALUE_RE = re.compile(
        r'(<li[^>]*\bid="fn:)(\d+)(")(>)'
    )

    def render(self, markdown_text: str, component_type: ComponentType = ComponentType.CHAPTER, component_id: str = "", start_number: int = 1) -> str:
        cleaned = re.sub(r'\{lang=\w+(?:[_-]\w+)*\}', '', markdown_text)
        cleaned = self._renumber_footnotes(cleaned, start_number)
        md = markdown.Markdown(extensions=self.extensions,
                               extension_configs=self._extension_configs)
        html = md.convert(cleaned)
        html = self._fix_footnote_display_numbers(html)
        html = self._add_image_captions(html)
        return self._wrap_in_section(html, component_type, component_id)

    @staticmethod
    def _fix_footnote_display_numbers(html: str) -> str:
        html = MarkdownService.FN_SUP_DISPLAY_RE.sub(
            r'\1\2\3\2\4', html
        )
        def _li_replacer(m):
            num = int(m.group(2))
            if num >= ERROR_BASE_KEY:
                return m.group(0)
            return f'{m.group(1)}{m.group(2)}{m.group(3)} value="{m.group(2)}"{m.group(4)}'
        html = MarkdownService.FN_LI_VALUE_RE.sub(_li_replacer, html)
        return html

    @staticmethod
    def _count_footnote_refs(text: str) -> int:
        lines = text.split('\n')

        defined: Set[int] = set()
        ref_order: List[int] = []
        in_code = False
        for line in lines:
            if line.strip().startswith('```'):
                in_code = not in_code
                continue
            if in_code:
                continue
            def_keys = set()
            for m in FN_DEF_RE.finditer(line):
                k = int(m.group(2))
                defined.add(k)
                def_keys.add(k)
            for m in FN_REF_RE.finditer(line):
                k = int(m.group(1))
                if k not in def_keys:
                    ref_order.append(k)

        count = 0
        seen: Set[int] = set()
        for key in ref_order:
            if key in defined and key not in seen:
                seen.add(key)
                count += 1
        return count

    @staticmethod
    def _renumber_footnotes(text: str, start_number: int = 1) -> str:
        lines = text.split('\n')

        defined: Set[int] = set()
        ref_order: List[int] = []
        in_code = False
        for line in lines:
            if line.strip().startswith('```'):
                in_code = not in_code
                continue
            if in_code:
                continue
            for m in FN_DEF_RE.finditer(line):
                defined.add(int(m.group(2)))
            for m in FN_REF_RE.finditer(line):
                ref_order.append(int(m.group(1)))

        mapping: Dict[int, int] = {}
        errors: Set[int] = set()
        next_num = start_number
        for key in ref_order:
            if key in defined:
                if key not in mapping:
                    mapping[key] = next_num
                    next_num += 1
            else:
                errors.add(key)

        def _replacer(m):
            key = int(m.group(1))
            if key in mapping:
                return f'[^{mapping[key]}]'
            if key in errors:
                return f'<sup class="fn-error" style="background:yellow;padding:0 2px">[{key}?]</sup>'
            return m.group(0)

        in_code = False
        result = []
        for line in lines:
            if line.strip().startswith('```'):
                in_code = not in_code
                result.append(line)
                continue
            if in_code:
                result.append(line)
                continue
            def_m = FN_DEF_RE.match(line)
            if def_m:
                indent, old_key_str, rest = def_m.group(1), def_m.group(2), def_m.group(3)
                old_key = int(old_key_str)
                if old_key in mapping:
                    rest = FN_REF_RE.sub(_replacer, rest)
                    result.append(f'{indent}[^{mapping[old_key]}]:{rest}')
                else:
                    result.append(line)
            else:
                result.append(FN_REF_RE.sub(_replacer, line))

        text = '\n'.join(result)

        if errors:
            for i, key in enumerate(sorted(errors)):
                ek = ERROR_BASE_KEY + i
                text += f'\n\n<span style="display:none">[^{ek}]</span>\n'
                text += f'[^{ek}]: <span style="background:yellow">Nota [{key}] no definida.</span>\n'

        return text

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
