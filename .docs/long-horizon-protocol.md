# Long-horizon memory study protocol (pre-run)

## Question and scope

This controlled study tests whether a **bounded, provenance-backed graph traversal** retains code-shaped dependency facts better than a normal vector similarity baseline as agent state grows. It complements the pinned Project Editor migration, which is a single generation task. It cannot isolate database engine performance from retrieval strategy and cannot establish general superiority from one synthetic scenario.

The hypothesis is that graph retrieval will improve exact-answer accuracy on delayed, two-hop dependency questions under the same context packing limit. The local questions are controls: both arms should answer them. A no-memory arm checks that the opaque answers are unavailable from prompts alone. Every outcome, including null or reversed differences, is reportable.

## Locked fixture and workflow

- Fixture: [`fixtures/long-horizon.json`](../fixtures/long-horizon.json), schema version 1. It contains 12 opaque route → handler → contract chains and 12 questions in a fixed order: three local handler questions and nine two-hop contract-token questions. Each answer token is unique and absent from its public question. The fixture is synthetic and intentionally stresses relation traversal; it is not a sample of real repository tasks.
- Shared preparation: turn each chain into three source records and two provenance-bearing relation records, 60 records total. Generate embeddings once and cache a versioned Pydantic snapshot. Both arms receive exactly those records and vectors. No answer key is sent to either model role.
- Memory arms: a fresh Qdrant collection or FalkorDB graph per run. Qdrant uses vector similarity plus the same supplied anchor record. FalkorDB uses that anchor and at most two bounded relationship hops. Both receive the same public task, source records, prompts, model, and 100-whitespace-word, 12-record context limit. Relationship records are visible to the vector arm as text and metadata. The two retrieval algorithms are the treatment.
- Agent handoffs: each step creates a task; an Analyst reads retrieved context and passes a candidate plus the preceding reviewer's pass/fail state to a Builder; the Builder replies with an opaque ID/token; a deterministic Reviewer checks exact equality against hidden gold. Both arms receive the same explicit anchor IDs for the route and, after step zero, the previous validation. Analyst summary, answer, validation, and their links persist before the next step. No retries. The corpus is fixed at the start; agent state accumulates over 12 steps. Record prior-state retrieval and Analyst state accuracy separately from answer accuracy.
- Model setting: the live mode uses the same configured OpenAI-compatible chat model for Analyst and Builder and the configured embedding model. Mock mode uses a deterministic evidence-only solver to test orchestration; its scores are **not thesis evidence**.
- Paired order: `--repeat 3` runs three fresh vector/graph pairs and alternates which arm runs first. Preprocessing is shared; runtime embeddings, generation, and retrieval are measured per arm. A separate `--memory none` run is the prompt-leakage ablation.

## Gates and outcomes

Before paid scoring, require the pinned Editor parser to produce nonzero source relations, the Docker smoke test to find actual import and runtime edges in FalkorDB, a lexically disjoint two-hop retrieval test to pass, the no-memory mock to answer 0/12, and the full test suite to pass. Preserve the historical 2026-11-13 Editor results as **pipeline feasibility only**: their graph arms had zero edges.

Primary outcome: exact-answer accuracy on the nine two-hop questions, reported by arm and by pair. Secondary outcomes: accuracy on the three local controls; evidence recall for the predeclared route/edge/handler/edge/contract path; accuracy and recall by step index; context words; provider input/output tokens; runtime embedding tokens; retrieval and end-to-end milliseconds; and runtime USD estimate when rates are configured. Shared embedding cost is reported separately. Missing model usage or pricing must remain `null`, never zero.

The three scored live pairs after the diagnostic run are a low-cost pilot, not a significance test. Report the per-step records and pair deltas before discussing averages. Do not interpret a graph advantage on this tailored two-hop fixture as proof of fewer hallucinations, long-term context stability in general, or a database-only speed advantage. Replication on independent code repositories and harder evolving tasks is required for the central thesis.

## Diagnostic pilot excluded from scored pairs

The first live pair on 2026-11-13 used prompt version `ff7e22c30270bf0b` and is archived separately at [`metrics/long-horizon-2026-11-13/diagnostic-prompt-v1`](../metrics/long-horizon-2026-11-13/diagnostic-prompt-v1/). Vector answered 1/12 and graph 2/12, even though graph evidence recall was 1.0 on every step. The Analyst often identified the correct candidate, but the Builder returned `UNKNOWN` after receiving both the task and a two-line handoff. This revealed a handoff prompt failure rather than a retrieval-only outcome. The Builder now receives only a normalized Analyst candidate; Analyst candidate accuracy and final answer accuracy are recorded separately. The diagnostic pair remains visible but is excluded from the revised scored protocol. No retroactive alteration of its raw results is permitted.

## Post-hoc stronger vector challenge

The primary vector comparator above is one-shot similarity search with the same explicit route and previous-validation anchors. After seeing its first scored results, a separate `vector_followup` strategy was added. It reads the route's explicit handler ID and the handler's explicit contract ID from retrieved text, then fetches those point IDs from Qdrant. It receives the same records, context limit, model and prompts. The matching graph arm uses its normal two-hop traversal. This challenge is labeled **post-hoc** and must not be pooled with the predeclared three one-shot pairs. It tests whether simple exact-ID follow-ups in a vector store can recover the same path. The implementation is specific to the fixture's opaque ID grammar and does not establish general vector performance.

## Reproduction

```sh
docker compose build cli
docker compose up -d qdrant falkordb
docker compose run --rm cli study --scenario /fixtures/long-horizon.json --mode mock --memory both --repeat 1
docker compose run --rm cli study --scenario /fixtures/long-horizon.json --mode mock --memory none --repeat 1
docker compose run --rm cli study --scenario /fixtures/long-horizon.json --mode live --memory both --repeat 3
docker compose run --rm cli study --scenario /fixtures/long-horizon.json --mode live --memory none --repeat 1
docker compose run --rm cli study --scenario /fixtures/long-horizon.json --mode live --memory strong --repeat 1
```

Each command writes a separate `/data/runs/study-<session-id>/study_evaluation.json` and per-arm `run.json`, `steps.jsonl`, `metrics.jsonl`, `agent_responses.jsonl`, and memory records. Archive scored live sessions only after checking credentials and file integrity.

## Cognee integration decision

Cognee can produce graph and vector data in one ingestion pipeline, with separate storage layers and community Qdrant/FalkorDB adapters. It is **not yet the required path** here: the current FalkorDB adapter release `0.4.0` conflicts with Cognee `1.6.8` during dependency resolution; a compatible resolution selects Cognee `1.4.2` and a much larger dependency set. Before switching, pin a compatible combination, prove that one `cognify` pass exports the exact same versioned evidence to both arms, and verify every code edge against source provenance. Cognee extraction itself must not become an uncontrolled difference between arms. The current deterministic parser and shared embeddings keep this pilot reproducible.
