from typing import List, Optional, Set, Dict, Tuple
import markdown
from pygments.formatters.html import HtmlFormatter
import re
from ..models.component import ComponentType


PYGMENTS_STYLE = "friendly"

FN_REF_RE = re.compile(r'\[\^(\d+)\]')
FN_DEF_RE = re.compile(r'^(\s*)\[\^(\d+)\]\s*:(.*)$', re.MULTILINE)
ERROR_BASE_KEY = 1000000

MD_IMG_RE = re.compile(r'!\[([^\]]*)\]\(([^)]+)\)')
DECORATIVE_PATH_RE = re.compile(r'(?:^|/)decorative/', re.IGNORECASE)
TABLE_CAPTION_MD_RE = re.compile(r'^<!--\s*Table:\s*(.*?)\s*-->\s*$', re.IGNORECASE)
TABLE_CAPTION_HTML_RE = re.compile(
    r'<!--\s*Table:\s*(.*?)\s*-->\s*'
    r'(<table\b.*?</table>)',
    re.DOTALL | re.IGNORECASE,
)
INTERP_RE = re.compile(r'\{\{(\w+)(?::(\w+))?\}\}')
DEFAULT_LABEL_FIGURE = "Figura"
DEFAULT_LABEL_TABLE = "Tabla"


class MarkdownService:
    def __init__(self, extensions: Optional[List[str]] = None):
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

    FN_SUP_DISPLAY_RE = re.compile(
        r'(id="fnref:)(\d+)("[^>]*>.*?<a[^>]*>)\d+(</a></sup>)'
    )
    FN_LI_VALUE_RE = re.compile(
        r'(<li[^>]*\bid="fn:)(\d+)(")(>)'
    )

    def render(self, markdown_text: str, component_type: ComponentType = ComponentType.CHAPTER, component_id: str = "", start_number: int = 1,
               figure_num_start: int = 0, figure_num_style: str = "arabic",
               table_num_start: int = 0, table_num_style: str = "arabic",
               variables: Optional[Dict[str, str]] = None,
               labels: Optional[Dict[str, str]] = None) -> str:
        cleaned = self._interpolate_variables(markdown_text, variables)
        cleaned = re.sub(r'\{lang=\w+(?:[_-]\w+)*\}', '', cleaned)
        cleaned = self._renumber_footnotes(cleaned, start_number)
        md = markdown.Markdown(extensions=self.extensions,
                               extension_configs=self._extension_configs)
        html = md.convert(cleaned)
        html = self._fix_footnote_display_numbers(html)
        html = self._add_image_captions(html, figure_num_start, figure_num_style, labels=labels)
        html = self._add_table_captions(html, table_num_start, table_num_style, labels=labels)
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
    def _to_roman(num: int) -> str:
        """Convert an integer to Roman numerals."""
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
    def _add_image_captions(html: str, figure_num_start: int = 0, figure_num_style: str = "arabic",
                            labels: Optional[Dict[str, str]] = None) -> str:
        """Wrap <img> tags that have alt text in <figure>/<figcaption>.
        
        When figure_num_start > 0, figures are numbered starting from that value.
        Decorative images (path containing '/decorative/') are never numbered.
        """
        DECORATIVE_HTML_RE = re.compile(r'(?:^|/)decorative/', re.IGNORECASE)
        figure_label = (labels or {}).get("figure", DEFAULT_LABEL_FIGURE)
        next_num = figure_num_start

        def _wrap(m):
            nonlocal next_num
            tag = m.group(0)
            alt_m = re.search(r'alt="([^"]*)"', tag)
            if alt_m and alt_m.group(1).strip():
                alt = alt_m.group(1)
                is_decorative = bool(DECORATIVE_HTML_RE.search(tag))
                if figure_num_start > 0 and not is_decorative:
                    num = next_num
                    next_num += 1
                    if figure_num_style == "roman":
                        num_str = MarkdownService._to_roman(num)
                    else:
                        num_str = str(num)
                    if alt.strip():
                        caption = f"{figure_label} {num_str} - {alt}"
                    else:
                        caption = f"{figure_label} {num_str}"
                    return f'<figure id="fig_{num}">\n{tag}\n<figcaption>{caption}</figcaption>\n</figure>'
                else:
                    return f'<figure>\n{tag}\n<figcaption>{alt}</figcaption>\n</figure>'
            return tag

        html = re.sub(r'<img[^>]+>', _wrap, html)
        html = re.sub(r'<p>\s*(<figure.*?</figure>)\s*</p>', r'\1', html, flags=re.DOTALL)
        return html

    @staticmethod
    def extract_figure_alts(md_text: str) -> list:
        """Extract alt text from markdown image references, skipping decorative images.

        Returns list of (alt_text, image_path) tuples for non-decorative images.
        """
        results = []
        for m in MD_IMG_RE.finditer(md_text):
            alt = m.group(1).strip()
            path = m.group(2)
            if DECORATIVE_PATH_RE.search(path):
                continue
            results.append((alt, path))
        return results

    @staticmethod
    def extract_table_captions(md_text: str) -> list:
        """Extract captions from <!-- Table: caption --> patterns preceding pipe tables.

        Returns list of (caption, None) tuples, skipping those inside code blocks.
        """
        results = []
        lines = md_text.split('\n')
        in_code = False
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith('```'):
                in_code = not in_code
                continue
            if in_code:
                continue
            m = TABLE_CAPTION_MD_RE.match(stripped)
            if m:
                caption = m.group(1).strip()
                for j in range(i + 1, len(lines)):
                    next_line = lines[j].strip()
                    if not next_line or next_line.startswith('```'):
                        if next_line.startswith('```'):
                            break
                        continue
                    if next_line.startswith('|'):
                        results.append((caption, None))
                    break
        return results

    @staticmethod
    def _add_table_captions(html: str, table_num_start: int = 0, table_num_style: str = "arabic",
                            labels: Optional[Dict[str, str]] = None) -> str:
        """Wrap <!-- Table: caption --><table>...</table> in <figure>/<figcaption>.

        When table_num_start > 0, captioned tables are numbered starting from that value.
        Tables without a <!-- Table: --> comment stay as-is.
        """
        table_label = (labels or {}).get("table", DEFAULT_LABEL_TABLE)
        next_num = table_num_start

        def _wrap(m):
            nonlocal next_num
            caption = m.group(1).strip()
            table = m.group(2)
            if table_num_start > 0:
                num = next_num
                next_num += 1
                if table_num_style == "roman":
                    num_str = MarkdownService._to_roman(num)
                else:
                    num_str = str(num)
                if caption:
                    cap_text = f"{table_label} {num_str} - {caption}"
                else:
                    cap_text = f"{table_label} {num_str}"
                return f'<figure id="tab_{num}">\n{table}\n<figcaption>{cap_text}</figcaption>\n</figure>'
            else:
                return f'<figure>\n{table}\n<figcaption>{caption}</figcaption>\n</figure>'

        html = TABLE_CAPTION_HTML_RE.sub(_wrap, html)
        html = re.sub(r'<p>\s*(<figure.*?</figure>)\s*</p>', r'\1', html, flags=re.DOTALL)
        return html

    @staticmethod
    def _interpolate_variables(text: str, variables: Optional[Dict[str, str]] = None) -> str:
        """Replace {{key}} and {{key:format}} placeholders with values from the given dict.

        Supported formats:
          :year  — extract the first 4 digits (year) from a date string
        """
        if not variables:
            return text

        def _replacer(m):
            key = m.group(1)
            fmt = m.group(2)
            value = variables.get(key)
            if value is None:
                return m.group(0)
            if fmt == "year":
                value = value[:4]
            return value

        return INTERP_RE.sub(_replacer, text)

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
