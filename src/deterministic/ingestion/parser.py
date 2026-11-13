"""Deterministic source entity extraction with source provenance."""

import ast
import hashlib
import re
from pathlib import Path

from deterministic.ingestion.schemas import Entity, Relation
from deterministic.ingestion.scope import BenchmarkScope

_TS = re.compile(
    r"^\s*(?:export\s+)?(?:async\s+)?(function|class|interface|type|const|let)\s+(\w+)"
)


def parse_source(root: Path, revision: str, scope: BenchmarkScope | None = None):
    entities: list[Entity] = []
    modules: dict[str, Entity] = {}
    pending: list[tuple[str, str, str]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix not in {
            ".py",
            ".ts",
            ".tsx",
            ".js",
            ".json",
            ".toml",
            ".md",
        }:
            continue
        rel = path.relative_to(root).as_posix()
        role = scope.role_for(rel) if scope else "migrate"
        if role is None:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        lang = (
            "python"
            if path.suffix == ".py"
            else "typescript"
            if path.suffix in {".ts", ".tsx"}
            else "other"
        )
        found = []
        if lang == "python":
            try:
                tree = ast.parse(text)
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        pending.extend(
                            (rel, alias.name.split(".")[0], f"line:{node.lineno}")
                            for alias in node.names
                        )
                    elif isinstance(node, ast.ImportFrom) and node.module:
                        pending.append((rel, node.module.split(".")[0], f"line:{node.lineno}"))
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                        found.append(
                            (
                                "class" if isinstance(node, ast.ClassDef) else "function",
                                node.name,
                                node.lineno,
                                getattr(node, "end_lineno", node.lineno),
                            )
                        )
            except SyntaxError:
                pass
        elif lang == "typescript":
            for n, line in enumerate(text.splitlines(), 1):
                imported = re.match(r"\s*import .* from ['\"]([^'\"]+)['\"]", line)
                if imported:
                    pending.append((rel, Path(imported.group(1)).stem, f"line:{n}"))
            for n, line in enumerate(text.splitlines(), 1):
                match = _TS.match(line)
                if match:
                    kind = {"interface": "type", "const": "variable", "let": "variable"}.get(
                        match[1], match[1]
                    )
                    found.append((kind, match[2], n, n))
        module = Entity(
            entity_id=hashlib.sha256(f"{revision}:{rel}:module".encode()).hexdigest(),
            kind="manifest" if path.name in {"package.json", "pyproject.toml"} else "module",
            name=rel,
            path=rel,
            start_line=1,
            end_line=max(1, len(text.splitlines())),
            content=text,
            language=lang,
            revision=revision,
            role=role,
        )
        entities.append(module)
        modules[Path(rel).stem] = module
        for kind, name, start, end in found:
            snippet = "\n".join(text.splitlines()[start - 1 : end])
            eid = hashlib.sha256(
                f"{revision}:{rel}:{kind}:{name}:{start}:{snippet}".encode()
            ).hexdigest()
            entities.append(
                Entity(
                    entity_id=eid,
                    kind=kind,
                    name=name,
                    path=rel,
                    start_line=start,
                    end_line=end,
                    content=snippet,
                    language=lang,
                    revision=revision,
                    role=role,
                )
            )
    relations = []
    by_path = {entity.path: entity for entity in entities if entity.kind in {"module", "manifest"}}
    for source, imported, location in pending:
        target = modules.get(imported)
        source_entity = by_path.get(source)
        if target and source_entity:
            relation_id = hashlib.sha256(
                f"{revision}:{source}:{imported}:{location}".encode()
            ).hexdigest()
            relations.append(
                Relation(
                    relation_id=relation_id,
                    source_id=source_entity.entity_id,
                    target_id=target.entity_id,
                    kind="IMPORTS",
                    provenance=f"{source}:{location}",
                )
            )
    return entities, relations
