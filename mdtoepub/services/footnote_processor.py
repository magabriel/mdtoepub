from typing import Dict, List, Set

import re

FN_REF_RE = re.compile(r'\[\^(\d+)\]')
FN_DEF_RE = re.compile(r'^(\s*)\[\^(\d+)\]\s*:(.*)$', re.MULTILINE)
ERROR_BASE_KEY = 1000000


class FootnoteProcessor:
    """Handles footnote renumbering, counting, and display fixing in Markdown/HTML."""

    FN_SUP_DISPLAY_RE = re.compile(
        r'(id="fnref:)(\d+)("[^>]*>.*?<a[^>]*>)\d+(</a></sup>)'
    )
    FN_LI_VALUE_RE = re.compile(
        r'(<li[^>]*\bid="fn:)(\d+)(")(>)'
    )

    @staticmethod
    def count_footnote_refs(text: str) -> int:
        """Count unique footnote references that have matching definitions.

        Args:
            text: Markdown text to analyze.

        Returns:
            Number of unique footnote references with definitions.
        """
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
    def renumber_footnotes(text: str, start_number: int = 1) -> str:
        """Renumber footnote references sequentially starting from start_number.

        Footnotes are renumbered in the order they appear in the text.
        References without matching definitions are replaced with error markers.

        Args:
            text: Markdown text with footnote references.
            start_number: Starting number for sequential renumbering.

        Returns:
            Markdown text with renumbered footnotes.
        """
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
    def fix_footnote_display_numbers(html: str) -> str:
        """Fix footnote display numbers in rendered HTML.

        Ensures sup tags and li tags show the correct footnote numbers.

        Args:
            html: Rendered HTML with footnotes.

        Returns:
            HTML with corrected footnote display numbers.
        """
        html = FootnoteProcessor.FN_SUP_DISPLAY_RE.sub(
            r'\1\2\3\2\4', html
        )
        def _li_replacer(m):
            num = int(m.group(2))
            if num >= ERROR_BASE_KEY:
                return m.group(0)
            return f'{m.group(1)}{m.group(2)}{m.group(3)} value="{m.group(2)}"{m.group(4)}'
        html = FootnoteProcessor.FN_LI_VALUE_RE.sub(_li_replacer, html)
        return html
