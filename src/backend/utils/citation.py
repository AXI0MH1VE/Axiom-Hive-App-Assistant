"""
Citation utilities: Generate inline citations and full bibliography.
"""

import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


def format_inline_citations(source_ids: List[int], style: str = "inline") -> str:
    """
    Format citation markers.

    Args:
        source_ids: List of source ID numbers
        style: "inline" ([1][2]), "parenthetical" ((1)(2)), "footnote" ([^1][^2])

    Returns:
        Concatenated citation string
    """
    if not source_ids:
        return ""

    markers = []
    for sid in source_ids:
        if style == "inline":
            markers.append(f"[{sid}]")
        elif style == "parenthetical":
            markers.append(f"({sid})")
        elif style == "footnote":
            markers.append(f"[^{sid}]")
        else:
            markers.append(f"[{sid}]")

    return "".join(markers)


def build_bibliography(sources: List[Dict[str, Any]]) -> str:
    """
    Construct numbered bibliography list.

    Args:
        sources: List of source metadata dicts

    Returns:
        Formatted bibliography string
    """
    lines = []
    for i, src in enumerate(sources, 1):
        title = src.get("title", "Untitled")
        author = src.get("author") or src.get("organization", "")
        date = src.get("date", "")
        url = src.get("url", "")
        license_ = src.get("license", "")

        citation = f"[{i}] {title}"
        if author:
            citation += f" — {author}"
        if date:
            citation += f" ({date})"
        if license_:
            citation += f" [{license_}]"
        if url:
            citation += f"\n    {url}"

        lines.append(citation)

    return "\n\n".join(lines)


def extract_citation_ids(text: str) -> List[int]:
    """
    Parse citation markers like [1], [2] from text.

    Returns:
        List of cited IDs in order of appearance
    """
    import re

    ids = []
    matches = re.findall(r"\[(\d+)\]", text)
    for m in matches:
        try:
            ids.append(int(m))
        except ValueError:
            continue
    return ids
