from typing import Dict, List, Optional, Tuple
import re

MD_IMG_RE = re.compile(r'!\[([^\]]*)\]\(([^)]+)\)')
DECORATIVE_PATH_RE = re.compile(r'(?:^|/)decorative/', re.IGNORECASE)
TABLE_CAPTION_MD_RE = re.compile(r'^<!--\s*Table:\s*(.*?)\s*-->\s*$', re.IGNORECASE)
TABLE_CAPTION_HTML_RE = re.compile(
    r'<!--\s*Table:\s*(.*?)\s*-->\s*'
    r'(<table\b.*?</table>)',
    re.DOTALL | re.IGNORECASE,
)
DEFAULT_LABEL_FIGURE = "Figura"
DEFAULT_LABEL_TABLE = "Tabla"


class CaptionProcessor:
    """Handles figure and table caption generation in HTML."""

    @staticmethod
    def add_image_captions(
        html: str,
        figure_num_start: int = 0,
        figure_num_style: str = "arabic",
        labels: Optional[Dict[str, str]] = None,
        roman_fn=None,
    ) -> str:
        """Wrap <img> tags that have alt text in <figure>/<figcaption>.

        When figure_num_start > 0, figures are numbered starting from that value.
        Decorative images (path containing '/decorative/') are never numbered.

        Args:
            html: Rendered HTML content.
            figure_num_start: Starting number for figures (0 = no numbering).
            figure_num_style: Numbering style ("arabic" or "roman").
            labels: Optional label overrides.
            roman_fn: Function to convert int to Roman numerals (injected dependency).

        Returns:
            HTML with figure/figcaption wrappers.
        """
        DECORATIVE_HTML_RE = re.compile(r'(?:^|/)decorative/', re.IGNORECASE)
        figure_label = (labels or {}).get("figure", DEFAULT_LABEL_FIGURE)
        next_num = figure_num_start

        def _to_roman(n):
            if roman_fn:
                return roman_fn(n)
            return str(n)

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
                    num_str = _to_roman(num) if figure_num_style == "roman" else str(num)
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
    def extract_figure_alts(md_text: str) -> List[Tuple[str, str]]:
        """Extract alt text from markdown image references, skipping decorative images.

        Args:
            md_text: Markdown text to scan.

        Returns:
            List of (alt_text, image_path) tuples for non-decorative images.
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
    def add_table_captions(
        html: str,
        table_num_start: int = 0,
        table_num_style: str = "arabic",
        labels: Optional[Dict[str, str]] = None,
        roman_fn=None,
    ) -> str:
        """Wrap <!-- Table: caption --><table>...</table> in <figure>/<figcaption>.

        When table_num_start > 0, captioned tables are numbered starting from that value.
        Tables without a <!-- Table: --> comment stay as-is.

        Args:
            html: Rendered HTML content.
            table_num_start: Starting number for tables (0 = no numbering).
            table_num_style: Numbering style ("arabic" or "roman").
            labels: Optional label overrides.
            roman_fn: Function to convert int to Roman numerals (injected dependency).

        Returns:
            HTML with table figure/figcaption wrappers.
        """
        table_label = (labels or {}).get("table", DEFAULT_LABEL_TABLE)
        next_num = table_num_start

        def _to_roman(n):
            if roman_fn:
                return roman_fn(n)
            return str(n)

        def _wrap(m):
            nonlocal next_num
            caption = m.group(1).strip()
            table = m.group(2)
            if table_num_start > 0:
                num = next_num
                next_num += 1
                num_str = _to_roman(num) if table_num_style == "roman" else str(num)
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
    def extract_table_captions(md_text: str) -> List[Tuple[str, None]]:
        """Extract captions from <!-- Table: caption --> patterns preceding pipe tables.

        Args:
            md_text: Markdown text to scan.

        Returns:
            List of (caption, None) tuples, skipping those inside code blocks.
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
