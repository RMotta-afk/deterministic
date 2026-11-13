"""The benchmark oracle must accept a known-good API implementation."""

import shutil
from pathlib import Path

import pytest

from deterministic.agents.editor_contract import validate_editor


def test_reference_editor_contract(tmp_path: Path):
    if not shutil.which("tsc") or not shutil.which("node"):
        pytest.skip("Node and TypeScript are provided by the Docker runtime")
    source = Path(__file__).parent / "support" / "editor_reference.ts"
    (tmp_path / "server.ts").write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    result = validate_editor(tmp_path)
    assert result.passed, result.output
    assert len(result.checks) == 12
