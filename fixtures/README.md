# Benchmark repositories

`project-intaker` and `project-editor` are pinned Git submodules. Initialize them with:

```sh
git submodule update --init --recursive
```

`project-editor` may require GitHub access configured on the host. Use the host's Git credential helper; do not put access tokens in `.gitmodules`, the Docker image, or run logs.

The backend migration boundary for each repository is declared in [benchmark-scope.json](benchmark-scope.json). `migration_roots` are candidate source code; `contract_roots` provide read-only interface and validation evidence; `preserve_roots` remain in the original application. Paths may appear in both the contract and preserve sets because preserved code can still define a contract. Do not edit the submodules as part of a benchmark run.

The small `python/` and `typescript/` fixtures remain smoke tests for the pipeline. They cannot establish the research claim. The two submodules are the real benchmark cases once scoped ingestion, backend migration, and connection tests are implemented. Pin and report their Git commits with every run.
