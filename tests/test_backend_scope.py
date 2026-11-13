"""Backend profiles retain contracts without planning UI migration."""

from deterministic.agents.planner import plan
from deterministic.ingestion.cache import ingest_evidence
from deterministic.ingestion.scope import BenchmarkScope


def test_scoped_evidence_excludes_ui_and_plans_only_backend(tmp_path):
    source = tmp_path / "project-intaker"
    for name in (
        "app/api/intakes/route.ts",
        "app/page.tsx",
        "src/server/create.ts",
        "src/contracts/intake.ts",
        "src/server/create.test.ts",
        "docs/sdd/api-contract.md",
    ):
        path = source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("export function answer() { return 42; }\n", encoding="utf-8")

    scope = BenchmarkScope(
        id="project-intaker",
        path="fixtures/project-intaker",
        commit="a" * 40,
        content_sha256="b" * 64,
        source_language="typescript",
        target_language="python",
        migration_roots=["app/api", "src/server"],
        migration_exclude_globs=["**/*.test.ts"],
        contract_roots=["src/contracts", "docs/sdd/api-contract.md"],
        preserve_roots=["app/page.tsx"],
        connection="Keep the API URL.",
    )
    revision = f"revision:scope:{scope.fingerprint}"
    evidence, hit = ingest_evidence(source, revision, tmp_path / "cache", scope)
    assert not hit
    roles = {entity.path: entity.role for entity in evidence.entities}
    assert "app/page.tsx" not in roles
    assert roles["src/contracts/intake.ts"] == "contract"
    assert roles["docs/sdd/api-contract.md"] == "contract"
    assert roles["src/server/create.test.ts"] == "contract"
    assert roles["app/api/intakes/route.ts"] == "migrate"
    assert {task.source_path for task in plan(evidence, "python")} == {
        "app/api/intakes/route.ts",
        "src/server/create.ts",
    }
