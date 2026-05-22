# Session 9: Cypher + NL query + advisor cascade

Branch: `feat/cypher-and-nl-query`
Goal: Let an authenticated user query their analyzed run's Kuzu graph — raw Cypher, canned playbooks, or natural language translated to Cypher via the LLM proxy. Plus an explicit "advise" endpoint that drops a chunk of context into the Pro tier Sonnet → Opus cascade.

## Decisions

- **Read-only enforcement:** server-side validator that rejects any query containing keywords `CREATE`, `MERGE`, `DELETE`, `SET`, `REMOVE`, `DROP`, `CALL` (Cypher's procedure call — could mutate). Whitelist-based: must start with `MATCH`, `WITH`, `UNWIND`, or `RETURN`. Returns 400 on violation.
- **Result shape:** every Cypher endpoint returns `{cypher: str, rows: list[dict], row_count: int, duration_ms: int}`. Same envelope across raw / NL / playbook.
- **NL→Cypher:** Gemini Flash with a fixed system prompt that includes the schema + 4 in-context examples. Crude regex strip to pull cypher out of any backtick fences the model might still produce.
- **Playbooks (5):** dead_functions, top_callers, sinks_via_features, callers_of(name), executed_in_feature(name). Each registered with `slug`, `name`, `description`, `cypher_template`, optional `params` schema.
- **Advise endpoint:** `POST /runs/{rid}/advise {prompt}` → straight pass-through to `LLMRouter.advise(user_id, prompt, prefer_opus=…)`. No automatic chain extraction in MVP — caller supplies the context they want triaged. Cascade rules from Session 5 still apply.

## Layout

```
backend/cypher/
├── __init__.py
├── validate.py        is_read_only(cypher) → bool; raise ValueError on violation
├── runner.py          run_cypher(layout, cypher, params) → CypherResult (opens GraphStore, executes)
├── playbooks.py       PLAYBOOKS dict + render(slug, params) → cypher str
├── nl.py              NLToCypher (Gemini-backed, fixed system prompt)
└── routes.py          POST /runs/{rid}/cypher, /nl, /playbooks/{slug}, /advise; GET /playbooks
```

Routes registered in `backend/main.py`.

## Tasks

1. **[SEQUENTIAL]** Plan doc. Validate / runner / playbooks scaffolding shape locked.
2. **[PARALLEL after 1]** Build `validate.py` + `runner.py` + `playbooks.py` + their tests. Subagent.
3. **[PARALLEL after 1]** Build `nl.py` + tests (pytest-httpx mocked Gemini). Subagent.
4. **[SEQUENTIAL after 2+3]** Build `routes.py` + e2e test that walks Session 6's run path then exercises /cypher, /nl, /playbooks/dead_functions, /advise. Main agent.
5. **[SEQUENTIAL]** Commit + squash-merge.

## Verification

- [ ] `just test` passes — ~10 new tests, ~143 total.
- [ ] Mutation cypher returns 400 with clear error.
- [ ] NL test asserts the prompt sent to Gemini includes the schema description.
- [ ] Playbook list is empty-args queryable; `dead_functions` returns Function nodes with no `EXECUTED_IN` edge.
- [ ] `/advise` falls through to LLMRouter; Pro tier requires vault key (already enforced).

## Out of scope

- Chain extraction (was deferred from Session 6 too).
- Caching of NL→Cypher translations.
- Query budget / per-query quota beyond the free-tier daily counter.
- Cypher parser / linter beyond keyword whitelist (real Kuzu parser would be ideal, but pyparsing-cypher etc. aren't worth pulling in for MVP).
