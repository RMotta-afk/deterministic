# deterministic

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

The first live Editor study and its retained evidence are in [.docs/observability.md](.docs/observability.md) and [metrics/](metrics/README.md). The archive includes failed arms and a checksum list; `.env` and service volumes are excluded.

The first POC uses one backend generation task and a whitespace-word context packing estimate. Provider prompt and completion tokens come from API usage. Shared preprocessing cost is reported separately; runtime provider USD costs require the optional rates in `.env`. No USD price is invented for self-hosted database infrastructure. One repository and one migration direction establish feasibility, not broad long-horizon or language-general results.

## Verify the pipeline without model spending

The controlled fixture tests and a full Docker pair using a fixed mock model response check orchestration. The fixed-response result is **not research evidence**:

```sh
uv sync --group dev
uv run pytest -q
docker compose run --rm -v "${PWD}/tests/support:/support:ro" --entrypoint python cli /support/run_editor_smoke.py
```

The Docker smoke command above uses PowerShell variable syntax. On a POSIX shell, replace `"${PWD}/tests/support:/support:ro"` with `"$PWD/tests/support:/support:ro"`.

Install the commit gate with `uv run pre-commit install`; `uv run pre-commit run --all-files` runs Ruff and pytest. Keep model credentials in the untracked `.env` or a secure runtime secret source; they are not baked into the image.
