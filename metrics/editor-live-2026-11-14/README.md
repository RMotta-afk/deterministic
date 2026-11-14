# Project Editor: live paired migration, 14 November 2026 UTC

This package preserves a **new, single live pair** on the pinned Project Editor backend (`cd588660d6f30fefbf1ba030e6890f93279dddf1`). It is separate from the [13 November Editor archive](../editor-2026-11-13/) and the [synthetic long-horizon study](../long-horizon-2026-11-13/). The earlier Editor graph had zero edges; this ingest produced 132 entities and **12 source `IMPORTS` relations**. The experiment compared Qdrant vector retrieval with FalkorDB graph retrieval while generating the same Python-to-TypeScript backend. The frontend and upstream records service were preserved as contract boundaries.

## Reproduction and evidence

```sh
docker compose run --rm cli ingest /fixtures/project-editor --scope-file /fixtures/benchmark-scope.json --profile project-editor
docker compose run --rm cli migrate --project 681cbe488a3e94c4 --target typescript --memory both --repeat 1
docker compose run --rm cli evaluate --project 681cbe488a3e94c4
uv run python -m deterministic.telemetry.tcc_observability metrics/editor-live-2026-11-14
```

The pair ID is `b808b0ab044a4c0c97c7f610152f9341`. [The paired evaluation](pair_evaluation.json) contains **only** this pair; [the full evaluator output](evaluation-all.json) also contains four historical pairs with different configurations and must not be aggregated with it. Both arms used the same source revision, settings signature, model snapshot (`gpt-5.4-mini-2026-03-17`), prompt version, 4,000-word estimated context cap, 6,000 completion-token cap, and two repair attempts. Vector ran first. Shared ingest used `gpt-5.4-mini` for summaries and `text-embedding-3-small` for embeddings. The source contract used for the judge is [frozen here](source-contract.md). The [evidence snapshot](evidence_snapshot.json), [ingest manifest](ingest/manifest.json), generated code, context traces, model responses, validation output, and [checksum list](SHA256SUMS) are retained. The Docker CLI image ID used for the run was `sha256:fa1303254aa5f9de8e88edbf2e320c3067a2f2c99416674e14885e1f7cd1f744`. The result also depends on working-tree code, which has not been committed by request.

## Four TCC observability fields

The [machine-readable gate](observability_gate.json) checks the saved pair, source relations, artifact hashes, blinded judge, and its calibration. `all_four_tcc_metrics_validated` is **false**.

| TCC field | Vector | Graph | What this run establishes |
| --- | ---: | ---: | --- |
| **Taxa de alucinação** | Judge claimed 0/12 contradicted; calibration **failed** | Judge claimed 0/12 contradicted; limited calibration passed | **Not validated.** The vector judge falsely called two behaviorally failing claims supported (`validation_422`, `unchanged_no_put`) and gave one inexact code quote. Executable failures are not automatically hallucinations. The graph judge agreeing on six checked claims does not independently validate all twelve. |
| **Acurácia relacional** | 10/12 behavioral checks; source-path evidence recall 0.625 | 12/12 behavioral checks; source-path evidence recall 0.750 | **Not measured as relational answer accuracy.** Twelve source edges were extracted, but no predeclared, independently labeled multi-hop real-code questions were asked. Contract success and path recall are different outcomes. |
| **Latência de execução** | 44.243 s total; 1.934 s retrieval | 27.407 s total; 0.084 s retrieval | Measured for one pair. Difference: 16.836 s total in favor of graph. Both totals include model, persistence, validation, and repairs; retrieval includes different adapter operations. Shared ingest took 23.941 s separately. No database-engine speed claim follows. |
| **Eficiência de tokens** | 34,938 chat input + 6,443 chat output + 7,503 runtime embedding = **48,884** runtime provider tokens | 33,288 chat input + 6,869 chat output + 0 runtime embedding = **40,157** | **Consumption measured; TCC useful-context ratio not measured.** There are no predeclared token-level relevance labels for the exact context sent. Different token types must not be treated as equal dollars. |

The vector arm failed two behavioral checks after two repairs, while the graph arm passed all 12 after two repairs. Runtime provider cost estimates were **US$0.05534706** (vector) and **US$0.05587650** (graph); graph cost slightly more despite fewer total provider tokens because output and embedding tokens have different rates. Shared ingest cost **US$0.01860039**, reported once outside the arms. The additional two blinded judge calls cost **US$0.01230075** combined, also outside the migration arms. These are provider estimates, excluding database infrastructure.

The graph's success cannot be attributed to simply seeing more source relations. The saved context traces show that graph retrieved 11 of 12 source `IMPORTS` records per context, while vector retrieved all 12. This one paired migration demonstrates a runnable, instrumented pipeline with real graph edges and a favorable behavioral outcome for graph. It does **not** prove the TCC's general claim about long-running multi-agent context, hallucination reduction, relational reasoning on real code, or useful-context-token efficiency. The [PT-BR observability record](../../.docs/observability.pt-BR.md) and [Section 3 methodology draft](../../.docs/tcc-secao-3-metodologia.md) interpret this package alongside the synthetic study.

Credentials, `.env`, live database volumes, and DuckDB state are excluded. `SHA256SUMS` covers raw evidence and the frozen contract, not this explanatory README. Regenerating an answer from the same model may produce different code.
