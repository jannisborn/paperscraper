from typing import List

import httpx

doi_pattern = r"\b10\.\d{4,9}/[-._;()/:A-Z0-9]+\b"


def check_overlap(n1: str, n2: str) -> bool:
    """
    Check whether two author names are identical.
    TODO: This can be made more robust

    Args:
        n1: first name
        n2: second name

    Returns:
        bool: Whether names are identical.
    """
    # remove initials and check for name intersection
    s1 = {w for w in n1.lower().replace(".", "").split() if len(w) > 1}
    s2 = {w for w in n2.lower().replace(".", "").split() if len(w) > 1}
    return len(s1 | s2) == len(s1)
