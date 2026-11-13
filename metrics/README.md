# Research metrics archive

This directory keeps scored proof-of-concept evidence under version control for the TCC. The current study is documented in [`.docs/observability.md`](../.docs/observability.md), with its raw snapshot in [`editor-2026-11-13/`](editor-2026-11-13/).

Each dated snapshot should contain the unmodified `evaluation.json`, ingestion manifest and events, per-arm manifests, `metrics.jsonl`, validation, context traces, model responses, final generated source, and a `SHA256SUMS` file. Include failed arms. Keep credentials, `.env`, service volumes, and unrelated smoke-test runs out of Git. Write a companion observability note with the source commit, model and rates, commands, results, missing values, and limits before publishing a new snapshot.

To check this snapshot's file integrity from its directory, run `sha256sum -c SHA256SUMS` with a SHA-256 utility. The checksum list covers the raw evidence, not the explanatory Markdown.
