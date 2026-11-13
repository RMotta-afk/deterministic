# Editor proof of concept: observability record

This record accompanies the raw evidence in [`metrics/editor-2026-11-13/`](../metrics/editor-2026-11-13/). It documents the live, scored run on 2026-11-13 UTC. The metrics folder contains the evaluator's original JSON, ingest manifest and events, and each migration arm's manifest, telemetry, validation, context traces, model responses, and final `server.ts`. `SHA256SUMS` covers the archived evidence files. Fixed-response smoke tests are excluded.

## Case and protocol

- Source: pinned `fixtures/project-editor` submodule at `cd588660d6f30fefbf1ba030e6890f93279dddf1`.
- Scope: `project-editor` backend, with frontend and upstream service retained as contract evidence. Direction: Python to TypeScript.
- Ingestion: project `681cbe488a3e94c4`, revision `a1131142f155762405c5c6843639b5e7d857b1a9fbdb657cc8faa922f4d53fc1:scope:9c0b315aa5f56c2d98c1028ab4b388b193a8cd1a4b1c9783bf364ee9365eedef`, 132 entities, initial cache miss.
- Comparison: four paired attempts, each with one Qdrant vector arm and one FalkorDB graph arm. The first command used `--repeat 3`; a later low-cost check used `--repeat 1`. Both arms used the same source, prompt version `a972bca2f26282b2`, generator, model, 4,000-word estimated context budget, 6,000 maximum completion tokens, and two-retry cap. Arm order is stored in each manifest.
- Provider: OpenAI API, `gpt-5.4-mini` for generation and summaries, `text-embedding-3-small` for embeddings. The provider reported snapshot `gpt-5.4-mini-2026-03-17` for the migration calls. Node `v22.23.5`, TypeScript `7.0.2`, and Python `3.13.18` are recorded in the manifests.
- Validation: executable API contract checks against a controlled records service and the preserved real upstream, plus TypeScript compilation and unchanged frontend proxy checks. A failed arm remains in the denominator.

The commands were:

```sh
docker compose run --rm cli ingest /fixtures/project-editor --scope-file /fixtures/benchmark-scope.json --profile project-editor
docker compose run --rm cli migrate --project 681cbe488a3e94c4 --target typescript --memory both --repeat 3
docker compose run --rm cli migrate --project 681cbe488a3e94c4 --target typescript --memory both --repeat 1
docker compose run --rm cli evaluate --project 681cbe488a3e94c4
```

## Recorded outcomes

| Pair | Qdrant | FalkorDB | Notes |
| --- | --- | --- | --- |
| `c74c5d210afb412985e55d26078cc92e` | Failed, 11/12 contract checks | Passed, 12/12 | Vector arm failed the behavioral `422` check after two retries. |
| `cdab9466f8c84d3bbf248938a499f6d1` | Passed, 12/12 | Passed, 12/12 | Both arms passed. |
| `5c64e5993d924b3abd06f9fb89fe1f64` | Passed, 12/12 | Passed, 12/12 | Both arms passed. |
| `40c5029b0632448ea3a2c428b906a7df` | Passed, 12/12 | Failed, 3/12 | Graph arm failed several API behavior checks after two retries. This is the priced follow-up pair. |

Both arms passed 3 of 4 attempts (75%). No pair was excluded. The following are descriptive means over four arms per memory type; failed arms are included.

| Metric | Qdrant | FalkorDB |
| --- | ---: | ---: |
| Input tokens per arm | 20,222 | 13,925 |
| Output tokens per arm | 4,284 | 3,512 |
| Retrieval latency, ms | 1,732 | 39 |
| End-to-end latency, ms | 29,048 | 19,082 |
| Evidence recall | 0.625 | 0.750 |
| Evidence precision | 0.556 | 0.750 |

The evaluator uses a manually reviewed Editor relevance set defined in `src/deterministic/telemetry/evaluator.py`. Context size is a whitespace-word estimate, while input and output token counts come from provider usage. Retrieval and end-to-end times are wall-clock measurements. See [`evaluation.json`](../metrics/editor-2026-11-13/evaluation.json) for every run, pair delta, retry count, and failure.

## Cost accounting

Only the final pair had pricing values configured when it ran. Its rate-based runtime estimates were $0.03570386 for Qdrant and $0.05295075 for FalkorDB, or **$0.08865461 combined**. The rates were $0.75 per million GPT-5.4 mini input tokens, $4.50 per million output tokens, and $0.02 per million text-embedding-3-small tokens, taken from the [GPT-5.4 mini](https://developers.openai.com/api/docs/models/gpt-5.4-mini) and [embedding model](https://developers.openai.com/api/docs/models/text-embedding-3-small) pricing pages on the run date.

The first three pairs and shared preprocessing have `null` USD fields because those rates were absent when their events were written. The final pair reused the preprocessing cache. The runtime estimates apply the configured standard rates to reported token usage; they are not invoice totals and do not include database hosting, cached-input discounts, or the initial unpriced preprocessing. Do not compute an eight-arm cost-per-success figure from this mixed-price archive.

## Interpretation and retention

This establishes that the pipeline can ingest the pinned backend, execute live paired migrations, preserve failed attempts, and emit comparable telemetry. Four pairs from one repository and one migration direction do not establish a general quality or cost advantage for either memory store. Model output varied enough that each store had one failed arm. The fixed relevance set and single generation task also limit what the context-quality numbers can mean.

The archive intentionally excludes `.env`, API credentials, the DuckDB catalog, service volumes, and the full memory indexes. The retained traces and responses support audit of the recorded runs, while a fresh reproduction requires the pinned submodule, working model access, and the commands above. Do not treat the archived generated code as a deployable migration.
