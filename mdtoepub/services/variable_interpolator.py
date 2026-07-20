from typing import Dict, Optional
import re

INTERP_RE = re.compile(r'\{\{(\w+)(?::(\w+))?\}\}')


class VariableInterpolator:
    """Replaces {{key}} and {{key:format}} placeholders with values."""

    @staticmethod
    def interpolate(text: str, variables: Optional[Dict[str, str]] = None) -> str:
        """Replace {{key}} and {{key:format}} placeholders with values from the given dict.

        Supported formats:
          :year  — extract the first 4 digits (year) from a date string

        Args:
            text: Text with placeholders.
            variables: Dict of variable name to value. None or empty dict returns text unchanged.

        Returns:
            Text with placeholders replaced by values.
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
