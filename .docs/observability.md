# Editor proof of concept: observability record

**Latest completed measurement:** the [four-pillar Editor study](../metrics/editor-four-pillars-2026-11-14/OBSERVABILITY.pt-BR.md) ran four paired sequences and a no-memory control. Vector achieved 48/48 task accuracy and 0/40 scalar factual errors; graph achieved 46/48 and 2/40. Mean arm latency was 33.458 s vs 17.380 s, and labelled-context efficiency was 21.60% vs 37.57% (vector vs graph). The [measurement gate](../metrics/editor-four-pillars-2026-11-14/measurement_gate.json) passes for this bounded source-QA protocol. It uses assistant-reviewed scalar gold and function-level relevance labels, not a calibrated free-form LLM judge or independent human token annotations. The findings do not establish long-horizon graph superiority. This dataset is separate from every historical experiment below.

**New live pair, 2026-11-14 UTC:** [Archived evidence](../metrics/editor-live-2026-11-14/) records a corrected ingest with 12 source `IMPORTS` relations and one paired migration. Graph passed 12/12 behavioral checks; vector passed 10/12. Latency was 27.407 s vs 44.243 s, and runtime provider tokens were 40,157 vs 48,884 (graph vs vector). The blinded hallucination judge falsely marked two failing vector claims as supported, so its raw 0% contradiction rates are **invalid as hallucination estimates**. No independently labeled multi-hop real-code questions or token-level useful-context ratio were measured. The [TCC observability gate](../metrics/editor-live-2026-11-14/observability_gate.json) therefore reports `all_four_tcc_metrics_validated: false`. This new pair is not pooled with the historical results below; see the [PT-BR interpretation](observability.pt-BR.md).

> **Validity correction (2026-11-13):** The archived ingestion produced 132 entities but **zero source relations**. Inspection of the archived FalkorDB run graphs also found **zero edges**. The graph arm therefore did not exercise relationship traversal in these runs. The four pairs remain evidence that the migration pipeline and logging ran, but their quality, token, and latency differences cannot support a claim that graph memory handles long-running or relational context better. The parser and runtime-link defects have since been repaired; the [new real pair](../metrics/editor-live-2026-11-14/) and [synthetic pilot](long-horizon-protocol.md) are reported separately. The archived metrics and checksums are unchanged.

The separate [2026-11-13 controlled retrieval pilot](../metrics/long-horizon-2026-11-13/) found 36/36 correct graph answers versus 9/36 with one-shot vector similarity across three pairs, but a post-hoc ID-aware Qdrant follow-up tied graph at 12/12 in one pair. Both arms recalled prior reviewer state on 33/33 later steps. This tailored synthetic fixture tests two-hop retrieval; it does not establish general long-running or database superiority. Its raw results and limitations are in the linked evidence package and are **not** combined with the Editor migration figures below.

This record accompanies the raw evidence in [`metrics/editor-2026-11-13/`](../metrics/editor-2026-11-13/). It documents the live, scored run on 2026-11-13 UTC. The [PT-BR version](observability.pt-BR.md) and thesis supplement (local document, excluded from the repository) relate it to the [TCC draft](<TCC - Estruturando Memoria Deterministica em Sistemas Nao-Deterministicos.pdf>). The metrics folder contains the evaluator's original JSON, ingest manifest and events, and each migration arm's manifest, telemetry, validation, context traces, model responses, and final `server.ts`. `SHA256SUMS` covers the archived evidence files. Fixed-response smoke tests are excluded.

## Case and protocol

- Source: pinned `fixtures/project-editor` submodule at `cd588660d6f30fefbf1ba030e6890f93279dddf1`.
- Scope: `project-editor` backend, with frontend and upstream service retained as contract evidence. Direction: Python to TypeScript.
- Ingestion: project `681cbe488a3e94c4`, revision `a1131142f155762405c5c6843639b5e7d857b1a9fbdb657cc8faa922f4d53fc1:scope:9c0b315aa5f56c2d98c1028ab4b388b193a8cd1a4b1c9783bf364ee9365eedef`, 132 entities, initial cache miss.
- Comparison: four paired attempts, each with one Qdrant vector arm and one FalkorDB graph arm. The first command used `--repeat 3`; a later low-cost check used `--repeat 1`. Both arms used the same source, prompt version `a972bca2f26282b2`, generator, model, 4,000 whitespace-word context packing limit, 6,000 maximum completion tokens, and two-retry cap. The memory adapter, including representation and retrieval algorithm, was the treatment. Arm order is stored in each manifest.
- Provider: OpenAI API, `gpt-5.4-mini` for generation and summaries, `text-embedding-3-small` for embeddings. The provider reported snapshot `gpt-5.4-mini-2026-03-17` for the migration calls. Node `v22.23.5`, TypeScript `7.0.2`, and Python `3.13.18` are recorded in the manifests.
- Validation: executable API contract checks against a controlled records service and the preserved real upstream, plus TypeScript compilation and unchanged frontend proxy checks. A failed arm remains in the denominator.

The commands were:

```sh
docker compose run --rm cli ingest /fixtures/project-editor --scope-file /fixtures/benchmark-scope.json --profile project-editor
docker compose run --rm cli migrate --project 681cbe488a3e94c4 --target typescript --memory both --repeat 3
docker compose run --rm cli migrate --project 681cbe488a3e94c4 --target typescript --memory both --repeat 1
docker compose run --rm cli evaluate --project 681cbe488a3e94c4
```

## Scope relative to the TCC draft

The PDF's Sections 3 and 4 propose an asynchronous LangGraph/Cognee/Neo4j architecture with continuous knowledge re-evaluation and long sequences of development tasks. The implemented POC uses a direct Python `understand → plan → build → validate` workflow, FalkorDB and Qdrant memory adapters, and one backend generation task with up to two retries. It persists task, artifact, and validation feedback, but does not implement continuous graph pruning or test long-horizon degradation. This experiment compares the two **memory configurations**, not database engines in isolation.

The PDF's Section 3.2 proposes a hallucination judge, multi-hop relational accuracy, and a useful-context-token ratio. None of these was measured directly. The narrower measures below test feasibility and observable migration behavior. The draft's claims of reduced hallucination and guaranteed semantic stability remain hypotheses. Its conceptual and implementation claims need to be separated in the thesis text; the PT-BR supplement (local document, excluded from the repository) provides suggested wording.

## Operational definitions

| Measure | Definition in this archive | Boundary |
| --- | --- | --- |
| Behavioral success | Passing the predefined executable API contract suite within the retry cap; failed arms remain in the denominator. | One source backend and one migration direction. |
| Evidence recall and precision | The evaluator compares module-record paths from `understand_plan` and first `build` retrievals with eight selected Editor paths, then averages the two retrieval scores. | A path-level relevance proxy, not multi-hop answer accuracy or an independently labeled benchmark. |
| Input/output tokens | Provider-reported usage across generation attempts, including retries. | The 4,000 context packing limit is a whitespace-word estimate, not provider token usage or the PDF's useful-context ratio. |
| Retrieval and end-to-end time | Wall-clock milliseconds from memory retrieval events and each terminal run event. | Adapter-specific latency, not isolated database engine speed or sustained-load performance. |
| Runtime USD | Reported tokens multiplied by configured standard rates when present. | An estimate, not invoice or full infrastructure cost. |

Contract-check failures are observable API behavior errors. They are **not** a measured hallucination rate.

## Recorded outcomes

| Pair | Qdrant | FalkorDB | Graph minus vector input tokens | Notes |
| --- | --- | --- | ---: | --- |
| `c74c5d210afb412985e55d26078cc92e` | Failed, 11/12 contract checks | Passed, 12/12 | −21,737 | Vector arm failed the behavioral `422` check after two retries. |
| `cdab9466f8c84d3bbf248938a499f6d1` | Passed, 12/12 | Passed, 12/12 | −11,131 | Both arms passed. |
| `5c64e5993d924b3abd06f9fb89fe1f64` | Passed, 12/12 | Passed, 12/12 | −921 | Both arms passed. |
| `40c5029b0632448ea3a2c428b906a7df` | Passed, 12/12 | Failed, 3/12 | +8,603 | Graph arm failed several API behavior checks after two retries. This is the priced follow-up pair. |

Both arms passed 3 of 4 attempts (75%). No pair was excluded. The following are descriptive arithmetic means over four arms per memory type; failed arms and retries are included. They are not uncertainty estimates.

| Metric | Qdrant | FalkorDB |
| --- | ---: | ---: |
| Input tokens per arm | 20,222 | 13,925 |
| Output tokens per arm | 4,284 | 3,512 |
| Retrieval latency, ms | 1,732 | 39 |
| End-to-end latency, ms | 29,048 | 19,082 |
| Retries per arm | 1.0 | 0.5 |
| Evidence recall | 0.625 | 0.750 |
| Evidence precision | 0.556 | 0.750 |

FalkorDB's mean input use was about 6,297 tokens lower and mean end-to-end time about 10 seconds shorter in this sample. Three pairs favored it on input tokens; the fourth reversed that direction. Retries and model-output variability affect these totals. The retrieval gap also reflects different adapter query methods, including vector query embedding, so it cannot be attributed solely to database engine speed.

The evaluator uses eight selected Editor paths defined in `src/deterministic/telemetry/evaluator.py`. The relevance scores concern retrieved module records, not all prompt content. Context size is a whitespace-word estimate, while input and output token counts come from provider usage. See [`evaluation.json`](../metrics/editor-2026-11-13/evaluation.json) for every run, pair delta, retry count, and failure.

## Cost accounting

Ingestion recorded 9,705 summary input tokens, 2,548 summary output tokens, and 2,504 embedding input tokens; its USD cost is `null`. Only the final pair had pricing values configured when it ran. Its rate-based runtime estimates were $0.03570386 for Qdrant and $0.05295075 for FalkorDB, or **$0.08865461 combined**. The rates were $0.75 per million GPT-5.4 mini input tokens, $4.50 per million output tokens, and $0.02 per million text-embedding-3-small tokens, taken from the [GPT-5.4 mini](https://developers.openai.com/api/docs/models/gpt-5.4-mini) and [embedding model](https://developers.openai.com/api/docs/models/text-embedding-3-small) pricing pages on the run date.

The first three pairs and shared preprocessing have `null` USD fields because those rates were absent when their events were written. The final pair reused the preprocessing cache. The runtime estimates apply the configured standard rates to reported token usage; they are not invoice totals and do not include database hosting, cached-input discounts, or the initial unpriced preprocessing. The evaluator leaves overall cost per success `null`. Do not compute an eight-arm cost-per-success figure or a general cost ranking from this mixed-price archive.

## Interpretation and retention

This establishes that the pipeline can ingest the pinned backend, execute live paired migrations, preserve failed attempts, and emit comparable telemetry. Four pairs from one repository and one migration direction do not establish a general quality or cost advantage for either memory configuration. Model output varied enough that each had one failed arm. The fixed path relevance set and single generation task cannot establish long-horizon context stability, multi-hop reasoning, continuous knowledge re-evaluation, or lower hallucination rates. The PDF's broader claims need separate experiments.

The archive intentionally excludes `.env`, API credentials, the DuckDB catalog, service volumes, and the full memory indexes. The retained traces and responses support audit of the recorded runs, while a fresh reproduction requires the pinned submodule, working model access, and the commands above. Do not treat the archived generated code as a deployable migration.
