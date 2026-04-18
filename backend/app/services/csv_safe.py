"""CSV formula-injection neutraliser (CWE-1236).

Excel / LibreOffice evaluate cells whose value starts with `= + - @` or
various whitespace characters as formulas. Any user-sourced value going
into a CSV export must be run through `csv_safe` first.
"""

from __future__ import annotations

_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def csv_safe(value) -> str:
    if value is None:
        return ""
    s = str(value)
    if s and s[0] in _FORMULA_PREFIXES:
        return "'" + s
    return s
