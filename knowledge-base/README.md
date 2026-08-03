# DocumentDB Agent-Kit — Knowledge Base Layer

This is the layer that sits **above** the scripts and skills: it turns a
developer's **natural-language question** into the **exact diagnostic to run**.

```
                 natural-language query
                          │
                          ▼
                 ┌──────────────────┐
                 │  knowledge base   │   kb.json  (single source of truth)
                 │  + router         │   kb-route.sh
                 └────────┬─────────┘
             one hop      │        multi hop (guarded workflow)
        ┌────────────────┘         └───────────────┐
        ▼                                           ▼
  a single script                        step → (result?) → step → … → conclusion
  (scripts/*.sh)                          (scripts/*.sh at each node)
```

Unlike a text-only skill kit (which hands the model prose and hopes it picks the
right approach), this layer gives a **deterministic, explainable routing
decision** and the ready-to-run command — while remaining fully consumable by an
LLM agent for the semantic cases.

## Files

| File | Role |
|------|------|
| `kb.json` | Declarative KB: `tools` (scripts + intents), `routes_one_hop`, `workflow_schema`, and `workflows` (multi-hop, currently one scaffold). Edit this to extend the kit. |
| `kb-route.sh` | CLI wrapper (bash): arg parsing + presence checks; passes inputs to `kb_route.py` via env vars. |
| `kb_route.py` | Routing engine (stdlib python3, no deps): keyword/example scoring → best tool + exact command. Standalone so it can be linted/tested/imported. |
| `kb_route_demo.py` | Teaching/debug aid: prints the full scoring walkthrough (per-tool score + signal breakdown) and how the router lands on the winner. `python3 knowledge-base/kb_route_demo.py [query]`. |
| `README.md` | This file. |

## One-hop routing (implemented)

```bash
# route a question to the right script
bash knowledge-base/kb-route.sh "why are my writes slow?"
bash knowledge-base/kb-route.sh --db mydb "audit my indexes for redundancy"

# machine-readable (for the agent / pipelines)
bash knowledge-base/kb-route.sh --json --db mydb "is my cache hit ratio ok?"

# discovery
bash knowledge-base/kb-route.sh --list        # all tools + example queries
bash knowledge-base/kb-route.sh --workflows   # multi-hop workflows (schema/scaffold)
```

Example:

```
Query: "is my cache hit ratio ok, do I need more shared_buffers"
→ Route: [db-config-advisor]  Config & Cache Advisor   (confidence: high, score 9.5)
  matched: cache, cache hit, shared_buffers
  run: bash scripts/db-config-advisor.sh --db mydb [--json]
```

Currently routed tools (all present DocumentDB diagnostics):

| Tool | Answers questions like |
|------|------------------------|
| `index-redundancy-finder` | "why are writes slow", "which indexes can I drop" |
| `document-bloat-advisor` | "aggregations slow despite indexes", "are my documents too big / TOAST" |
| `db-config-advisor` | "cache hit ratio", "do I need more shared_buffers", "working set" |
| `perf-advisor` | "performance checkup", "missing indexes / collection scans" |
| `data-integrity-check` | "orphaned references", "referential integrity", "type consistency" |

**Routing is deterministic:** the router scores the query against each tool's
`keywords` / `example_queries` in `kb.json` (multi-word phrases weigh more than
single tokens) plus the `routes_one_hop` signal, and returns a ranked result
with a confidence and alternatives. No LLM required; same input → same route.

## Multi-hop workflows (schema + scaffold)

Troubleshooting is rarely one script. The KB models a workflow as a **guarded
diagnostic graph** (an AND/OR decision graph — the classic sequential-diagnosis
structure): each **step** runs a tool; each **edge** is conditional on the
observed result; the agent advances until it reaches a conclusion. This directly
supports "run check A; depending on the result, run B or C" with dependencies
between steps.

The structure is defined in `kb.json → workflow_schema`, and one **illustrative
scaffold** (`slow-writes`, marked `status: scaffold`) shows the shape:

```
slow-writes:
  check_redundant_indexes ──(findings>0)──▶ conclude: drop redundant indexes
                          └(findings=0)──▶ check_document_bloat
                                              ├(bloat)──▶ conclude: split large text
                                              └(none)──▶ check_config ──▶ conclude…
```

> Workflows are intentionally **not yet populated/validated** — this layer only
> provides the skeleton so real troubleshooting graphs can be added over time.
> The agent (or a future traversal script) walks the graph, running the tool at
> each node and matching the reported result to an edge.

## Extending the KB

- **Add a one-hop tool:** append an entry to `tools[]` in `kb.json` with its
  `script`, `invocation`, `keywords`, and `example_queries`. The router picks it
  up automatically — no code change.
- **Add a workflow:** append to `workflows[]` following `workflow_schema`
  (`entry`, `steps`, `depends_on`, guarded `yields`).

## How the agent should use this layer

1. On a natural-language diagnostic question, call `kb-route.sh --json "<query>"`.
2. If `confident`, run the emitted `command` (filling `--db`), then interpret the
   script's measured output for the user.
3. If a multi-hop workflow applies, start at its `entry` step and follow the
   guarded edges using each step's result.
4. If no confident route, fall back to `--list` and ask the user to clarify.
