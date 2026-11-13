# deterministic

The architecture is documented in [.docs/base.md](.docs/base.md), and the ordered build tasks are in [.context/decomposition.json](.context/decomposition.json). The ingestion and migration pipeline is under development.

## Development checks

```sh
uv sync --group dev
uv run pre-commit install
uv run pre-commit run --all-files
```

The commit hook runs Ruff lint, Ruff formatting, and pytest. Cross-stage and persisted Python records must use strict, versioned Pydantic v2 schemas as described in the blueprint.
