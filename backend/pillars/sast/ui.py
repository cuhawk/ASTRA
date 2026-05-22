# vendored-from: https://github.com/cuhawk/tlxkull
# upstream-path: tlx/modules/js_analyzer/ui.py
# upstream-sha:  83cae232b94e7998ef543c72e8e7302617d438a0
# imported-on:   2026-05-22
# license:       proprietary — see upstream repo
# modifications: none

"""Compat shim — ported files import `from ui import C` for ANSI colors.

GFA shipped a `ui.py` with ANSI escape codes; in tlx all output goes
through structlog or the shell. Provide an empty namespace so the
prints in ported files become uncoloured but functional.
"""
from __future__ import annotations


class C:
    RESET = ""
    DIM = ""
    BOLD = ""
    BLACK = ""
    RED = ""
    GREEN = ""
    YELLOW = ""
    BLUE = ""
    MAGENTA = ""
    CYAN = ""
    WHITE = ""
    GREY = ""
