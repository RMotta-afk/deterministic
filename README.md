# deterministic

The latest [four-pillar live study](metrics/editor-four-pillars-2026-11-14/OBSERVABILITY.pt-BR.md) measured bounded factual hallucination, task accuracy, execution latency, and labelled context-token efficiency across four Editor pairs and a no-memory control. Vector scored 48/48 tasks; graph scored 46/48 while using less time and fewer tokens. The [measurement gate passes](metrics/editor-four-pillars-2026-11-14/measurement_gate.json) for this restricted protocol; it does not establish general graph superiority. See the [protocol](.docs/editor-four-pillars-protocol.pt-BR.md) and archived report for reproduction commands and thesis limitations.

This proof of concept compares Qdrant vector memory with FalkorDB graph memory while migrating the pinned Python backend in `fixtures/project-editor` to a runnable TypeScript API. The React/Vite frontend and upstream records service remain untouched. The blueprint is [.docs/base.md](.docs/base.md); ordered tasks are in [.context/decomposition.json](.context/decomposition.json). `project-intaker` is reserved for later replication.

## Run the Editor proof of concept

1. Start Docker Desktop, initialize the pinned submodule, and copy [.env.example](.env.example) to `.env`. Set a reachable OpenAI-compatible chat and embeddings endpoint, its model IDs, and a key. The endpoint must return chat text and token usage, plus embedding vectors and token usage. Keep the same settings for ingestion and migration.

2. Build and start the services:

```sh
git submodule update --init --recursive
docker compose build cli
docker compose up -d qdrant falkordb
```

3. Ingest the pinned case. This writes the source snapshot, cached natural-language summaries and embeddings, and a ready project in DuckDB:

```sh
docker compose run --rm cli ingest /fixtures/project-editor --scope-file /fixtures/benchmark-scope.json --profile project-editor
```

To download and ingest in one CLI command, replace the local source with `https://github.com/RMotta-afk/project-editor`; the scope profile pins and checks its commit and content. The local command above uses the already initialized submodule and avoids another download.

4. Copy the `Ready: <project-id>` value from ingestion. Run fresh paired attempts and evaluate all outcomes:

```sh
docker compose run --rm cli migrate --project <project-id> --target typescript --memory both --repeat 3
docker compose run --rm cli evaluate --project <project-id>
```

The result is `/data/runs/evaluation/evaluation.json` in the persistent `runs` volume. Each run has its own manifest, context traces, metrics JSONL, validation result, model responses, and generated code. A failed arm remains in the report and in the success-rate denominator. The generated `server.ts` is compiled and tested against a controlled upstream for edge cases, then against Editor's preserved records service for live GET/PUT connectivity. Validation also checks the unchanged frontend's `/api` proxy target.

The first live Editor study and its retained evidence are in [.docs/observability.md](.docs/observability.md), the [PT-BR observability record](.docs/observability.pt-BR.md), the [TCC supplement](.docs/tcc-adendo-evidencias.md), and [metrics/](metrics/README.md). The archive includes failed arms and a checksum list; `.env` and service volumes are excluded.

The first POC uses one backend generation task and a whitespace-word context packing estimate. Provider prompt and completion tokens come from API usage. Shared preprocessing cost is reported separately; runtime provider USD costs require the optional rates in `.env`. No USD price is invented for self-hosted database infrastructure. One repository and one migration direction establish feasibility, not broad long-horizon or language-general results.

The [long-horizon study protocol](.docs/long-horizon-protocol.md) adds a controlled delayed-dependency experiment with two model-backed roles, local controls, and a no-memory ablation. Run its mock commands first; mock scores verify orchestration and are not research results. The live command in that protocol writes a separate per-step report under `/data/runs/study-<session-id>/`.

The archived Editor pairs had zero graph edges and establish pipeline feasibility only. The separate [study plan](.docs/study-plan.md) tracks the remaining evidence needed for the TCC. The controlled study compares one-shot vector retrieval, bounded graph traversal, and a separately labeled metadata-aware vector follow-up challenge; its synthetic fixture cannot establish general superiority on real code.

A [new live Editor pair with real source relations](metrics/editor-live-2026-11-14/) passed 12/12 API checks with graph memory and 10/12 with vector memory. Its [observability gate](metrics/editor-live-2026-11-14/observability_gate.json) reports measured latency and token consumption, while rejecting the uncalibrated hallucination judge and marking real-code relational answer accuracy and the useful-context-token ratio as unmeasured. It is an operational result, not a complete validation of the TCC's four metrics.

The [PT-BR observability comparison](.docs/observability.pt-BR.md) maps the TCC's four proposed metrics to what the runs actually measured. A [revised Section 3 methodology draft](.docs/tcc-secao-3-metodologia.md) is ready to incorporate into the thesis; the source PDF remains unchanged.

The final POC pair adds an evidence-only grounding verdict for each answer and reports unsupported assertions alongside abstentions. It validates opaque route and contract claims in this fixture; free-form hallucination assessment remains outside the measured scope.

## Verify the pipeline without model spending

The controlled fixture tests and a full Docker pair using a fixed mock model response check orchestration. The fixed-response result is **not research evidence**:

```sh
uv sync --group dev
uv run pytest -q
docker compose run --rm -v "${PWD}/tests/support:/support:ro" --entrypoint python cli /support/run_editor_smoke.py
```

The Docker smoke command above uses PowerShell variable syntax. On a POSIX shell, replace `"${PWD}/tests/support:/support:ro"` with `"$PWD/tests/support:/support:ro"`.

Install the commit gate with `uv run pre-commit install`; `uv run pre-commit run --all-files` runs Ruff and pytest. Keep model credentials in the untracked `.env` or a secure runtime secret source; they are not baked into the image.
