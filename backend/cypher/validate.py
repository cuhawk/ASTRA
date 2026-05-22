from __future__ import annotations

import re

_FORBIDDEN = (
    "CREATE",
    "MERGE",
    "DELETE",
    "SET",
    "REMOVE",
    "DROP",
    "CALL",
    "DETACH",
    "FOREACH",
)
_ALLOWED_PREFIXES = ("MATCH", "WITH", "UNWIND", "RETURN", "OPTIONAL")

_FORBIDDEN_RE = re.compile(
    r"\b(" + "|".join(_FORBIDDEN) + r")\b",
    re.IGNORECASE,
)
_LINE_COMMENT_RE = re.compile(r"//[^\n]*")
_BLOCK_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)


class CypherForbidden(ValueError):
    pass


def _strip_comments(cypher: str) -> str:
    no_block = _BLOCK_COMMENT_RE.sub(" ", cypher)
    return _LINE_COMMENT_RE.sub(" ", no_block)


def starts_with_allowed_prefix(cypher: str) -> bool:
    stripped = _strip_comments(cypher).lstrip().upper()
    return any(stripped.startswith(p) for p in _ALLOWED_PREFIXES)


def is_read_only(cypher: str) -> bool:
    if not starts_with_allowed_prefix(cypher):
        return False
    stripped = _strip_comments(cypher)
    return _FORBIDDEN_RE.search(stripped) is None


def assert_read_only(cypher: str) -> None:
    stripped = _strip_comments(cypher)
    match = _FORBIDDEN_RE.search(stripped)
    if match:
        raise CypherForbidden(f"forbidden keyword: {match.group(1).upper()}")
    if not starts_with_allowed_prefix(cypher):
        raise CypherForbidden(
            "query must start with MATCH/WITH/UNWIND/RETURN/OPTIONAL"
        )
