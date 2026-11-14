# Research metrics archive

**Latest:** [Editor four-pillar study](editor-four-pillars-2026-11-14/OBSERVABILITY.pt-BR.md), with four scored pairs, one no-memory control, frozen labels, exact token accounting, source-grounded scalar factual errors, full call logs, implementation snapshot and checksums. Its measurement gate passes under the documented restricted definitions. The results show better accuracy for vector and lower latency/token consumption for graph; do not pool this dataset with earlier migration or synthetic runs.

This directory keeps scored proof-of-concept evidence under version control for the TCC. The current study is documented in the [English observability record](../.docs/observability.md), its [PT-BR version](../.docs/observability.pt-BR.md), and a thesis supplement (local document, excluded from the repository), with the raw snapshot in [`editor-2026-11-13/`](editor-2026-11-13/).

The [long-horizon evidence package](long-horizon-2026-11-13/) contains a separate synthetic retrieval study. Its diagnostic prompt run, scored one-shot pairs, no-memory ablation, and post-hoc stronger vector challenge must be interpreted separately. See the [protocol](../.docs/long-horizon-protocol.md) and the package README for the exact boundaries.

The [new live Editor pair](editor-live-2026-11-14/) contains a corrected ingest with 12 source relations, paired migration artifacts, a blinded claim audit, independent calibration checks, and a machine-readable [TCC observability gate](editor-live-2026-11-14/observability_gate.json). The graph arm passed the behavioral contract while the vector arm failed two checks, but the claim judge failed calibration and the real-code relational accuracy and useful-context ratio remain unmeasured. Keep this pair separate from the historical Editor archive and synthetic pilot.

Each dated snapshot should contain the unmodified `evaluation.json`, ingestion manifest and events, per-arm manifests, `metrics.jsonl`, validation, context traces, model responses, final generated source, and a `SHA256SUMS` file. Include failed arms. Keep credentials, `.env`, service volumes, and unrelated smoke-test runs out of Git. Write a companion observability note with the source commit, model and rates, commands, results, missing values, and limits before publishing a new snapshot.

To check this snapshot's file integrity from its directory, run `sha256sum -c SHA256SUMS` with a SHA-256 utility. The checksum list covers the raw evidence, not the explanatory Markdown.
