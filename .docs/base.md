# deterministic — Context Pack and Architectural Specification

## 1. Academic & Project Overview

* **Project Name:** `deterministic`

* **Academic Context:** Undergraduate Capstone Thesis (TCC) in Computer Engineering

* **Thesis Title:** *Structuring Deterministic Memory in Non-Deterministic Systems: A Comparative Analysis of GraphRAG and VectorRAG in Multi-Agent Orchestration.*

* **Core Hypothesis:** In iterative code migration, explicit relational memory may improve correctness, retrieval quality, and token efficiency over a strong vector-memory baseline at a comparable operating cost. The experiment tests this claim; a negative or mixed result is valid.

* **Prototype Philosophy:** **Strict Simplicity & Controlled Isolation.** This is an experimental benchmark prototype. Within a paired case, models, prompts, parsers, shared evidence, validation, and workflow are held constant. The independent variable is memory representation and retrieval (`VectorMemory` vs. `GraphMemory`); differences in setup and runtime cost are measured.

---

## 2. System Architecture & Dual Entrypoints

The system ingests a pinned source repository or controlled local fixture and executes the same code migration workflow through one of two isolated memory entrypoints.

### Initial Language Scope

The first scored proof of concept migrates the pinned **Python `project-editor` backend to TypeScript**. The CLI and controlled fixtures retain both language directions for later work, but `project-intaker` is not part of this first result. Repositories may contain other languages in preserved frontends or contract fixtures; those files are not migration targets.

The Editor migration is a feasibility case. It does not by itself test long-running context. The follow-up study uses a predeclared sequence of dependent, code-shaped tasks with delayed two-hop questions, accumulating task/artifact/validation memory, a fixed context budget, and explicit local-retrieval controls. Two model-backed roles consume retrieved context in each scored step; a deterministic reviewer checks opaque gold answers that never appear in model prompts. A no-memory ablation checks whether prompts alone reveal the answers. Keep this controlled study separate from the live Editor migration report.

The shared parser extracts language-neutral entities and relations while retaining source locations, original signatures, imports, types, and code snippets. Context Packs explain those facts in natural language for the agents, but remain linked to the source evidence. Natural-language summaries are an aid to retrieval and planning, not a lossless intermediate representation of program behavior.

Both memory entrypoints receive the same parsed entities, summaries, embeddings, migration direction, and validation fixtures for a given case. Benchmark results are compared **within each direction** before combining results across directions.

If Cognee is used for graph, chunk, or vector preparation, run its extraction once before either arm, export a versioned Pydantic evidence snapshot, and give both arms the exact same snapshot. Verify every code relation against source provenance and reject missing required edges; model-inferred links may not silently become deterministic facts. Pin compatible Cognee and community-adapter versions and validate the Qdrant/FalkorDB combination before making Cognee a required path. The deterministic parser and shared embedding cache remain the reproducible baseline until that compatibility gate passes.

Keep the small controlled examples and fixed-response Editor mock as smoke tests. They are not thesis evidence. The first scored input is the pinned `fixtures/project-editor` Git submodule. `fixtures/project-intaker` remains available for later replication. Report the submodule commit, scoped file list, target runtime, dependency versions, and executable behavioral checks for every run.

### Pinned Repository Boundaries

`project-intaker` is the **TypeScript → Python** case. Migrate backend behavior from `app/api`, `src/server`, and `src/ai`, excluding test files and evaluation-only material. Keep the Next.js pages and components. Treat `src/contracts` and Prisma as interface and storage evidence. The migrated backend must preserve the existing `/api` URL surface, response shapes and status codes, persistence behavior, and worker lifecycle; thin Next.js route handlers may forward requests to the new Python service. The UI remains in Next.js.

`project-editor` is the **Python → TypeScript** case. Migrate `backend/project_editor`. Keep the React/Vite frontend and the upstream records service. Treat `frontend/src/api.ts`, `frontend/src/contracts.ts`, backend tests, and the upstream API as contract evidence. The migrated backend must preserve the `/api/projects` routes, conflict and uncertain-write behavior, and server-side ownership of the upstream API key. Frontend code and upstream behavior are not migration targets.

Compare vector and graph arms **within the pinned Editor revision and Python-to-TypeScript direction**. One repository establishes feasibility only; it cannot support broad claims about languages or graph memory. Backend correctness includes the upstream connection and browser-facing contract, not merely generated files compiling.

### Fair Paired Comparison

For every case, run both memory arms with the same source evidence and cached evidence summaries, embedding model, agent workflow, model version, prompts, generation settings, tools, task-ordering policy, validation fixtures, retry cap, and stopping rules. Each arm may generate different Context Packs and tasks as a result of retrieval; preserve those outputs for comparison. Give each arm the same maximum retrieved-context budget per step. The first POC uses a whitespace-word packing estimate; report actual provider prompt tokens separately, and do not call the estimate an exact tokenizer count. Run arms in fresh, isolated stores and record model responses; equal settings do not make stochastic generation deterministic.

The vector baseline indexes the same entities and intermediate artifacts with stable IDs and metadata. It may use reproducible metadata filters and context packing in addition to similarity search. The graph arm uses explicit, substantiated edges and bounded traversal. Both arms can persist and retrieve tasks, artifacts, validation feedback, and status. The comparison tests memory representation and retrieval, rather than withholding useful evidence or feedback from one arm.

Before any scored relational comparison, assert nonzero source edges, task/artifact/validation links, and retrieval of a deliberately lexically disjoint two-hop dependency under the shared budget. Record retrieved node and relation IDs at every step. Historical runs without graph edges are pipeline-feasibility evidence only and cannot support a relational-memory effectiveness claim.

Account for ingestion, embeddings, graph construction, vector indexing, reads, writes, generation, and retries. Report shared preprocessing separately. Provider USD cost is reported only when explicit input, output, and embedding rates are configured; self-hosted database infrastructure has latency and write counts but no invented USD price. Repeat paired Editor runs to estimate model variance.

### Shared Pre-Processing & Caching Layer (Cost Control)

Before hitting either memory entrypoint, a shared ingestion pipeline runs once per target repository:

1. **Repo Loader & File Filter:** Loads a pinned revision or fixture and filters relevant source code, configurations, manifests, and tests.

2. **Deterministic Parser & Entity Extractor:** Parses files with language-appropriate syntax tooling to identify contracts, classes, functions, types, imports, source spans, and modules as discrete **Base Entities**. Record uncertain relations instead of inventing edges. Cache any LLM-generated summaries and reuse the exact same output in both arms.

3. **Local Embedding Cache:** Generates embeddings for shared chunks and entities once per content, model, and preprocessing version. The CLI writes them to a persistent cache volume inside the container. Both entrypoints read the same cache. Log this cost even when the cache is reused.

### Container and Runtime Storage

The `Dockerfile` installs and pins the CLI, Python and TypeScript tooling, parsers, and validators; creates writable `/data/cache`, `/data/catalog`, and `/data/runs` directories; and runs the CLI as a non-root user. It must not bake downloaded repositories, generated embeddings, model credentials, or run results into image layers. Docker Compose mounts persistent volumes at those paths and starts the FalkorDB and Qdrant services with their own persistent storage. Rebuilding the image therefore preserves ingestion work and run history.

Use `/data/cache` for pinned repository snapshots, parsed evidence, shared evidence summaries, and embeddings; `/data/catalog/projects.duckdb` for the small local project/run catalog; and `/data/runs/{run_id}` for logs, generated output, validation results, and metrics. Runtime Context Packs and tasks belong to their respective run directories and memory stores. Key cache entries by source revision plus parser, summary, embedding-model, and preprocessing versions. Treat repository content as untrusted input: keep source snapshots separate from output, bound validation subprocesses, and provide credentials at runtime. The CLI is the sole DuckDB catalog writer in the initial prototype.

### Strict CLI Stages

1. **`deterministic ingest <repository-url-or-local-path>`:** Fetch or load the source, resolve and record its exact commit/content revision, filter files, parse the supported source language, generate cited shared evidence summaries and embeddings, and register the ready evidence snapshot in DuckDB. This is the one-command download and ingestion stage. An interrupted ingest remains marked incomplete and can be resumed or rebuilt without presenting a partial project as selectable.
2. **`deterministic migrate`:** List ready indexed snapshots from DuckDB, let the user select one and a target language, then choose `vector`, `graph`, or a paired `both` run. Pressing Enter starts the workflow from the cached snapshot; it does not silently re-ingest. Each arm builds its own isolated Qdrant collection or FalkorDB graph from the same snapshot, with construction cost recorded. Non-interactive flags for project ID, target, and memory arm support repeatable benchmark runs. Each arm gets a run ID and output directory; `both` also records a shared pair ID.
3. **`deterministic evaluate`:** Read the catalog and all completed run manifests, metrics JSONL files, validation results, and generated artifacts. Produce a per-run report and paired VectorMemory/GraphMemory comparisons grouped by project revision and migration direction. Flag missing, incomplete, or incomparable runs instead of silently including them in an aggregate.

Every stage emits human-readable progress and structured JSONL events with timestamps, stage, project ID, operation or run ID, source revision, settings, cache hits, errors, and artifact paths. Each ingest operation and migration run has its own log and manifest under `/data/runs/`. Record status transitions in DuckDB so `ingest` and `migrate` can show what is ready, running, failed, or complete. Run one catalog-writing CLI process at a time in the first prototype. Do not store secrets in logs.

### Validation Schemas and Commit Gate

Use **Pydantic v2** models for all Python data crossing a stage, process, storage, or agent boundary: CLI/run configuration, source snapshots, DuckDB project and run records, parsed entities and relations, shared evidence summaries, Context Packs, Migration Tasks, memory-adapter requests and results, generated-artifact metadata, validation results, run manifests, and telemetry events. Validate untrusted or persisted data when it enters the process (`model_validate` or `model_validate_json`), and serialize through the schema when writing it. Use strict fields, explicit allowed values, forbidden extra fields, and a schema version for durable artifacts. SQL constraints and TypeScript compile checks supplement these schemas; they do not replace boundary validation. Keep implementation-local scratch values lightweight where they do not cross a boundary.

The `.pre-commit-config.yaml` gate runs Ruff lint and format checks, followed by the Python test suite. Install it after setting up the development environment and run it across all files before commits. A passing hook verifies formatting, lint rules, and current tests; the benchmark's behavioral validation remains a separate runtime gate.

---

### Entrypoint A: `run_vector_pipeline` (Baseline — VectorRAG)

* **Storage Engine:** Qdrant (isolated collection/namespace)

* **Ingestion Behavior:**

  * Loads cached embeddings and entity chunks into the Vector DB.

  * Indexes the shared entities and artifacts with stable IDs and metadata; similarity search may be combined with documented metadata filters.

* **Runtime Memory Behavior:**

  * Context Packs, Migration Tasks, generated artifacts, and validation feedback are persisted as retrievable records with IDs, provenance, and status. They are not connected by graph edges.

  * Retrieval uses a documented similarity, metadata-filtering, and context-packing strategy within the same token budget as GraphMemory.

### Entrypoint B: `run_graph_pipeline` (Experimental — GraphRAG)

* **Storage Engine:** FalkorDB (one isolated graph per run).

* **Ingestion Behavior:**

  * Ingests the exact same Base Entities and cached embeddings from the shared layer.

  * Establishes substantiated directed relationships (`IMPORTS`, `CALLS`, `INHERITS_FROM`, `IMPLEMENTS_CONTRACT`, `DEPENDS_ON`) between entities, with provenance for each edge.

* **Runtime Memory Behavior:**

  * Intermediate agent outputs (Context Packs, Migration Tasks, Validation Logs) are dynamically written back into the graph as first-class nodes (`TaskNode`, `ContextSubgraph`, `MigrationArtifact`) and linked directly to the affected `Entity` nodes (`MIGRATES`, `VALIDATES`, `BLOCKS`).

  * Retrieval combines a documented entry-point strategy with bounded graph traversal. It returns a context pack within the shared token budget and records which nodes and edges supported the result.

---

## 3. Standardized Multi-Agent Workflow

For the TCC's research methodology, use the separate Section 3 methodology supplement (local document, excluded from the repository) and [PT-BR observability comparison](observability.pt-BR.md). This architecture section describes the prototype workflow, not a measured conclusion about graph superiority.

Both entrypoints currently execute the same direct Python workflow. Agents interact with memory through the `MemoryAdapter` interface (`retrieve_context()`, `persist_artifact()`), remaining agnostic to whether Vector or Graph is running underneath. A LangGraph state machine was part of the conceptual design but is not implemented in this POC; adding it is not required to test the memory hypothesis.

```text

[Pinned repository / controlled fixture]

      │

      ▼

[Ingest: evidence cache + DuckDB catalog]

      │

      ├──► (Migrate: Qdrant run) ──────┐

      └──► (Migrate: FalkorDB run) ────┤

                                       ▼

                        ┌─────────────────────────────┐

                        │  1. Understanding Agent     │

                        │  (Builds Context Packs)     │

                        └──────────────┬──────────────┘

                                       ▼

                        ┌─────────────────────────────┐

                        │  2. Task Planner Agent      │

                        │  (Creates Migration Tasks)  │

                        │  *Graph: Links Tasks->Nodes │

                        └──────────────┬──────────────┘

                                       ▼

                        ┌─────────────────────────────┐

                        │  3. Builder Agent           │◄───┐

                        │  (Generates Migrated Code)  │    │

                        └──────────────┬──────────────┘    │

                                       ▼                   │ (Retry Loop

                        ┌─────────────────────────────┐    │  on Failure)

                        │  4. Validator & Checker     │────┘

                        │  (Compile/Behavioral Tests) │

                        └──────────────┬──────────────┘

                                       ▼

                        [Migrated Output Repository]

                                       │

                                       ▼

                        [Run logs + metrics JSONL]

                                       │

                                       ▼

                        [Evaluate: paired report]

```

### Agent Roles & Responsibilities

1. **Understanding Agent (Analyst):**

   * Queries the memory layer for core entities and architectural boundaries.

   * Produces a structured Context Pack summarizing the repository's domain, entrypoints, and critical contracts, with links to source evidence.

2. **Task Planner Agent (Decomposer):**

   * Consumes the Context Pack and queries entity dependencies to break the migration into ordered, testable Migration Tasks.

   * **Architectural Divergence Point:** Both arms persist generated tasks. `GraphMemory` also links them to substantiated `Entity` and `Contract` nodes; `VectorMemory` retains their IDs and metadata for retrieval.

3. **Builder Agent (Executor):**

   * Iterates through the Migration Tasks sequentially.

   * Queries `MemoryAdapter` for the required context of task $T_i$, writes the migrated code file, and updates the target output repository.

4. **Validator & Checker Agent (Reviewer):**

   * Checks syntax/compile validity, import resolution, declared contracts, and predefined executable behavioral tests.

   * If validation fails, it emits structured error feedback and routes execution back to the Builder Agent (up to a fixed retry cap).

   * In both arms, validation results update task status and prevent downstream tasks from treating broken dependencies as verified. `GraphMemory` also links results to the affected nodes.

---

## 4. Observability, Telemetry & Evaluation Metrics

To test the thesis, every agent step and database query writes structured telemetry to `/data/runs/{run_id}/metrics.jsonl`, alongside generated code and validator output for failure review.

For the TCC record, retain scored evaluation snapshots, per-arm telemetry and validation, and the final generated source under `metrics/`, with a companion observability note in `.docs/`. Archive failed arms and record source/model versions, pricing assumptions, missing values, and limitations. Exclude credentials and runtime service volumes.

| Metric Category | Metric Name | Operational Definition & How It Is Measured | Research Purpose |

| :--- | :--- | :--- | :--- |

| **Context Efficiency** | **Prompt Token Growth** | Input and retrieved-context tokens at each step, under an equal per-step context budget. | Tests whether either strategy uses fewer tokens over time. |

| **Context Quality** | **Evidence Recall and Precision** | Compare retrieved entities/files with a small manually reviewed relevance set. Generated-code references are a secondary proxy. | Measures whether useful evidence was retrieved without excessive noise. |

| **Memory Drift** | **Contract Error Rate** | Broken imports, unresolved references, incompatible signatures, and violated declared constraints per task. | Tests whether errors increase over task order. |

| **Self-Correction** | **Retry Loop Frequency** | Retry cycles per task, including failed cases in the denominator. | Tests whether either memory strategy reduces rework. |

| **FinOps & Cost** | **Cost per Successful Case ($)** | Report shared ingestion, embeddings, indexing/graph construction, retrieval, writes, generation, and retries separately and in total. | Tests whether any quality gain justifies total system cost. |

| **Performance** | **Retrieval & End-to-End Latency (ms)** | Wall-clock time spent in `MemoryAdapter.retrieve_context()` and `persist_artifact()` vs. LLM generation time. | Captures the honest engineering trade-off: Graph traversal/write overhead vs. fast cosine search. |

| **End-to-End Success** | **Behavioral Success Rate (%)** | Percentage of cases passing predefined executable behavioral tests within the retry budget; report syntax and import failures separately. | Measures migration correctness beyond parseable code. |

---

## 5. Proposed Minimal Directory Structure

Designed for rapid execution and clean separation of concerns:

```text

deterministic/

├── .docs/base.md                # This architectural specification

├── Dockerfile                   # Pinned CLI/runtime tooling and writable data paths

├── .dockerignore                # Exclude runtime data and secrets from image context

├── .pre-commit-config.yaml      # Ruff and test hooks

├── .env.example                 # API keys, FalkorDB and Qdrant connections

├── docker-compose.yml           # CLI, FalkorDB, Qdrant, persistent volumes

├── pyproject.toml               # uv / Python dependencies

├── data/                        # Mounted runtime cache, DuckDB catalog, run outputs

├── src/

│   ├── cli.py                   # `ingest`, `migrate`, `evaluate`

│   ├── catalog.py               # DuckDB project and run catalog

│   ├── ingestion/

│   │   ├── repo_loader.py       # Git clone & file filtering

│   │   ├── parser.py            # Deterministic entity & contract extraction

│   │   └── cache.py             # Shared embedding cache manager

│   ├── memory/

│   │   ├── base.py              # Abstract `MemoryAdapter` protocol

│   │   ├── vector_memory.py     # Baseline VectorRAG implementation

│   │   └── graph_memory.py      # Experimental GraphRAG implementation

│   ├── agents/

│   │   ├── graph.py             # Shared LangGraph workflow state machine

│   │   ├── understanding.py     # Agent 1: Context Pack builder

│   │   ├── planner.py           # Agent 2: Task generator & linker

│   │   ├── builder.py           # Agent 3: Code migration executor

│   │   └── validator.py         # Agent 4: Contract & syntax checker

│   └── telemetry/

│       ├── logger.py            # Decorator for tokens, cost, and latency

│       └── evaluator.py         # Script to compare Vector vs. Graph JSONL runs

```

---

## 6. Prototype Scope Guardrails (KISS Constraints)

1. **Measured Case Size:** The first case is `project-editor`: 5 Python backend source files (~339 lines) at its pinned revision. This is a feasibility proof, not evidence of broad scalability or a language-direction effect. Keep `project-intaker` for later replication.

2. **Behavioral Validation:** Use syntax/compile, import resolution, and static checks where applicable, then run predefined executable tests. Signature parity alone does not establish equivalent behavior across Python and TypeScript. An LLM contract check can add diagnostic evidence but does not decide success.

3. **Strict Isolation:** Never allow `vector_memory.py` and `graph_memory.py` to share runtime state. Each paired run initializes clean namespaces, reads the same versioned ingestion cache, runs the shared workflow, and writes isolated `metrics.jsonl` and generated artifacts.

4. **Real Repository Benchmark:** Score `project-editor` only after the fixed-response smoke run and telemetry pass. Ingest only its declared backend and contract paths, preserve frontend and upstream code, and record unsupported language features or dependencies. A single generated `server.ts` is the minimal target, so this POC measures one backend migration rather than long-horizon task drift.

## 7. Decisions to Pin Before the First Benchmark

The architecture and workflow are set. The first implementation slice must record these concrete choices in its run configuration before results are compared:

1. Supported Python and TypeScript constructs and one controlled fixture in each migration direction, with expected behavioral tests.
2. Exact Python, TypeScript, parser, model, embedding model, Qdrant, and FalkorDB versions.
3. Context token budget, retrieval and packing rules, retry cap, model settings, and repeat count.
4. Run manifest and JSONL event schemas, cache version keys, and the rule for matching comparable vector/graph pairs.

Keep the small fixtures and fixed-response Editor run for pipeline smoke checks. Only live-model Editor runs with the pinned repository, shared summaries and embeddings, and executable contract validation are scored as POC evidence.
