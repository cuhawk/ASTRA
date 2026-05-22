from __future__ import annotations

import re

from backend.config import Settings
from backend.llm.base import LLMResponse
from backend.llm.gemini import GeminiClient

_SYSTEM = """\
You translate natural language questions about a static analysis of a JavaScript codebase into Kuzu Cypher queries.

The graph schema is:

Nodes
  Function(id, name, path, kind, start_line, end_line)
  Feature(id, name)

Relationships
  (Function)-[:CALLS]->(Function)
  (Function)-[:EXECUTED_IN]->(Feature)

Rules
- Output ONLY a Kuzu Cypher query. No prose, no markdown fences, no commentary.
- Read-only queries only: MATCH / WITH / UNWIND / RETURN. No CREATE / MERGE / DELETE / SET / REMOVE / CALL.
- Prefer LIMIT 50 unless the user explicitly asks for a count.
- When matching by name, use exact case-sensitive equality.

Examples
Q: which functions are never executed in any feature?
A: MATCH (f:Function) WHERE NOT EXISTS { MATCH (f)-[:EXECUTED_IN]->(:Feature) } RETURN f.name, f.path LIMIT 50

Q: who calls login?
A: MATCH (c:Function)-[:CALLS]->(t:Function {name: 'login'}) RETURN c.name, c.path LIMIT 50

Q: count all functions
A: MATCH (f:Function) RETURN count(f) AS n

Q: functions reachable from a checkout feature
A: MATCH (f:Function)-[:EXECUTED_IN]->(:Feature {name: 'checkout'}) RETURN f.name, f.path LIMIT 50
"""


_FENCE = re.compile(r"^```(?:cypher)?\s*(.*?)\s*```$", re.DOTALL | re.IGNORECASE)


def _strip_fences(text: str) -> str:
    text = text.strip()
    m = _FENCE.match(text)
    return m.group(1).strip() if m else text


class NLToCypher:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def translate(self, prompt: str) -> tuple[str, LLMResponse]:
        """Returns (cypher_str, raw_llm_response). Caller logs via the router /
        validates via backend.cypher.validate."""
        if not self._settings.gemini_api_key:
            from backend.llm.base import LLMError
            raise LLMError("ASTRA_GEMINI_API_KEY not configured", provider="gemini")
        client = GeminiClient(
            api_key=self._settings.gemini_api_key,
            model=self._settings.gemini_model,
            embed_model=self._settings.gemini_embed_model,
        )
        resp = await client.complete(
            prompt, system=_SYSTEM, max_tokens=512, temperature=0.0,
        )
        cypher = _strip_fences(resp.text)
        return cypher, resp
