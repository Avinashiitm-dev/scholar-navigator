"""Deterministic half of the source checker. No network, no API keys."""
import re

_LINK = re.compile(r"\[([^\]]*)\]\([^)]*\)")


def norm(text: str) -> str:
    text = _LINK.sub(r"\1", text)                 # [label](url) -> label
    text = re.sub(r"[*_`#>|]", "", text)           # markdown noise
    return re.sub(r"\s+", " ", text).strip().casefold()


def quote_in_page(quote: str, page: str, min_len: int = 20) -> bool:
    q = norm(quote)
    return len(q) >= min_len and q in norm(page)
