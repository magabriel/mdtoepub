"""Spell-check service with {lang=xx} region markers."""

import re
from typing import List, Tuple, Dict, Set

try:
    import gi
    gi.require_version('GtkSpell', '3.0')
    from gi.repository import GtkSpell
    _HAS_GTKSPELL = True
except (ImportError, ValueError):
    _HAS_GTKSPELL = False


LANG_MARKER_RE = re.compile(r'\{lang=(\w+(?:[_-]\w+)*)\}')
WORD_RE = re.compile(r'\b([^\W\d_]+(?:[-\'][^\W\d_]+)*)\b', re.UNICODE)
FENCE_RE = re.compile(r'^[ ]{0,3}```', re.MULTILINE)


class SpellCheckService:
    """Multi-language spell-check with inline {lang=xx} markers.

    Manages GtkSpell checker instances per language and provides
    word-level spell-checking with support for language regions,
    code block exclusion, and custom dictionaries.
    """

    def __init__(self, default_lang: str = "en_US"):
        """Initialize the spell-check service.

        Args:
            default_lang: Default language code (e.g. "en_US").
        """
        self.default_lang = default_lang
        self._checkers: Dict = {}
        self._global_words: Set[str] = set()

    @property
    def available(self) -> bool:
        """Whether GtkSpell is available on this system."""
        return _HAS_GTKSPELL

    def get_language_list(self) -> List[str]:
        """Return the list of available spell-check languages.

        Returns:
            List of language code strings.
        """
        if not _HAS_GTKSPELL:
            return [self.default_lang]
        try:
            chk = GtkSpell.Checker.new()
            return chk.get_language_list()
        except Exception:
            return [self.default_lang]

    def get_checker(self, lang: str):
        """Get or create a GtkSpell checker for the given language.

        Checkers are cached per language.

        Args:
            lang: Language code (e.g. "en_US").

        Returns:
            GtkSpell.Checker instance, or None if unavailable.
        """
        if not _HAS_GTKSPELL:
            return None
        if lang not in self._checkers:
            try:
                chk = GtkSpell.Checker.new()
                chk.set_language(lang)
                self._checkers[lang] = chk
            except Exception:
                self._checkers[lang] = None
        return self._checkers[lang]

    @staticmethod
    def _find_fenced_blocks(text: str) -> List[Tuple[int, int]]:
        """Find fenced code blocks (```). Returns sorted (start, end) positions."""
        lines = text.split('\n')
        positions = []
        offsets = []
        offset = 0
        for line in lines:
            offsets.append(offset)
            offset += len(line) + 1

        i = 0
        while i < len(lines):
            if FENCE_RE.match(lines[i]):
                start = offsets[i]
                j = i + 1
                while j < len(lines):
                    if FENCE_RE.match(lines[j]):
                        end = offsets[j] + len(lines[j]) + 1
                        positions.append((start, end))
                        i = j + 1
                        break
                    j += 1
                else:
                    positions.append((start, len(text)))
                    break
            else:
                i += 1
        return positions

    @staticmethod
    def _find_inline_code(text: str) -> List[Tuple[int, int]]:
        """Find inline code spans (backtick-delimited). Returns sorted (start, end)."""
        ranges = []
        i = 0
        while i < len(text):
            if text[i] == '`':
                j = i
                while j < len(text) and text[j] == '`':
                    j += 1
                n = j - i
                k = j
                while k <= len(text) - n:
                    if text[k:k + n] == '`' * n:
                        ranges.append((i, k + n))
                        i = k + n
                        break
                    k += 1
                else:
                    i = j
            else:
                i += 1
        return ranges

    @staticmethod
    def _merge_ranges(ranges: List[Tuple[int, int]]) -> List[Tuple[int, int]]:
        """Merge overlapping ranges."""
        if not ranges:
            return []
        sorted_r = sorted(ranges)
        merged = [sorted_r[0]]
        for start, end in sorted_r[1:]:
            if start <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(merged[-1][1], end))
            else:
                merged.append((start, end))
        return merged

    def get_excluded_ranges(self, text: str) -> List[Tuple[int, int]]:
        """Return sorted, merged ranges to exclude from spell-check (code).

        Args:
            text: Full text to scan for code blocks and inline code.

        Returns:
            List of (start, end) ranges to exclude.
        """
        ranges = self._find_fenced_blocks(text) + self._find_inline_code(text)
        return self._merge_ranges(ranges)

    @staticmethod
    def _is_excluded(pos_start: int, pos_end: int,
                     excluded: List[Tuple[int, int]]) -> bool:
        for r_start, r_end in excluded:
            if pos_start >= r_end:
                continue
            if pos_end <= r_start:
                break
            if pos_start >= r_start and pos_end <= r_end:
                return True
            if pos_start < r_end and pos_end > r_start:
                return True
        return False

    def parse_regions(self, text: str,
                      excluded_ranges: List[Tuple[int, int]] = None
                      ) -> List[Tuple[int, int, str]]:
        """Parse {lang=xx} markers into (start, end, lang) regions.

        Markers themselves are excluded from regions.
        Markers inside excluded_ranges (code blocks/spans) are ignored.
        No marker -> default_lang for the whole text.

        Args:
            text: Full text with potential {lang=xx} markers.
            excluded_ranges: Ranges to ignore markers within.

        Returns:
            List of (start, end, language_code) tuples covering the full text.
        """
        if excluded_ranges is None:
            excluded_ranges = []
        regions = []
        pos = 0
        current_lang = self.default_lang
        for match in LANG_MARKER_RE.finditer(text):
            start, end = match.start(), match.end()
            if self._is_excluded(start, end, excluded_ranges):
                continue
            if start > pos:
                regions.append((pos, start, current_lang))
            current_lang = match.group(1)
            pos = end
        if pos < len(text):
            regions.append((pos, len(text), current_lang))
        return regions

    def get_word_positions(self, text: str) -> List[Tuple[int, int, str]]:
        """Find all word positions in text.

        Args:
            text: Text to scan.

        Returns:
            List of (start, end, word) tuples.
        """
        return [(m.start(), m.end(), m.group(1)) for m in WORD_RE.finditer(text)]

    def check_text(self, text: str,
                   ignore_words: Set[str] = set()
                   ) -> List[Tuple[int, int, str, str]]:
        """Check text with language regions.

        Words in code blocks, inline code, ignore_words or global dictionary
        are skipped.

        Args:
            text: Full text to check.
            ignore_words: Set of lowercase words to skip.

        Returns:
            List of (word_start, word_end, word, lang) for misspelled words.
        """
        if not _HAS_GTKSPELL:
            return []
        excluded = self.get_excluded_ranges(text)
        regions = self.parse_regions(text, excluded)
        misspelled = []
        all_ignored = ignore_words | self._global_words

        for r_start, r_end, lang in regions:
            region_text = text[r_start:r_end]
            words = self.get_word_positions(region_text)
            checker = self.get_checker(lang)
            if checker is None:
                continue
            for w_start, w_end, word in words:
                abs_start = r_start + w_start
                abs_end = r_start + w_end
                if self._is_excluded(abs_start, abs_end, excluded):
                    continue
                if word.lower() in all_ignored:
                    continue
                if not checker.check_word(word):
                    misspelled.append((abs_start, abs_end, word, lang))

        return misspelled

    def add_global_word(self, word: str):
        """Add word to the per-user global dictionary (system spell engine).

        Args:
            word: Word to add to the dictionary.
        """
        self._global_words.add(word.lower())
        if _HAS_GTKSPELL:
            for lang, checker in self._checkers.items():
                if checker is not None:
                    try:
                        checker.add_to_dictionary(word)
                    except Exception:
                        pass

    def get_suggestions(self, word: str, lang: str) -> List[str]:
        """Get spelling suggestions for a word.

        Args:
            word: The misspelled word.
            lang: Language code for the checker.

        Returns:
            List of suggested corrections.
        """
        if not _HAS_GTKSPELL:
            return []
        checker = self.get_checker(lang)
        if checker is None:
            return []
        try:
            return checker.get_suggestions(word)
        except Exception:
            return []
