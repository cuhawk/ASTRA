# vendored-from: https://github.com/cuhawk/tlxkull
# upstream-path: tlx/modules/js_analyzer/prompts/__init__.py
# upstream-sha:  83cae232b94e7998ef543c72e8e7302617d438a0
# imported-on:   2026-05-22
# license:       proprietary — see upstream repo
# modifications: none

"""Prompt management package.

- loader.py:   discover + parse + validate .md prompt files
- rag.py:      separate Chroma collection 'prompts'
- registry.py: assemble system prompts, fetch by id/kind
"""

from .loader import LoaderError, Prompt, load_prompts, parse_frontmatter
from .rag import PromptRAG
from .registry import (
    PromptRegistry,
    get_registry,
    set_registry,
)

__all__ = [
    "Prompt", "load_prompts", "parse_frontmatter", "LoaderError",
    "PromptRAG",
    "PromptRegistry", "get_registry", "set_registry",
]
