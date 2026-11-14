"""Deterministic source entity extraction with source provenance."""

import ast
import hashlib
import posixpath
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
    pending: list[tuple[str, tuple[str, ...], str, int, str]] = []
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
                            (rel, (alias.name,), f"line:{node.lineno}", 0, lang)
                            for alias in node.names
                        )
                    elif isinstance(node, ast.ImportFrom):
                        module = node.module or ""
                        candidates = tuple(
                            f"{module}.{alias.name}".strip(".")
                            for alias in node.names
                            if alias.name != "*"
                        ) + ((module,) if module else ())
                        if candidates:
                            pending.append(
                                (rel, candidates, f"line:{node.lineno}", node.level, lang)
                            )
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
                    pending.append((rel, (imported.group(1),), f"line:{n}", 0, lang))
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
        modules[rel] = module
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
    seen: set[tuple[str, str, str]] = set()
    for source, imports, location, level, language in pending:
        target = _resolve_import(source, imports, level, language, modules)
        source_entity = by_path.get(source)
        if target and source_entity and (source, target.path, location) not in seen:
            seen.add((source, target.path, location))
            relation_id = hashlib.sha256(
                f"{revision}:{source}:{target.path}:{location}".encode()
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


def _resolve_import(
    source: str,
    imports: tuple[str, ...],
    level: int,
    language: str,
    modules: dict[str, Entity],
) -> Entity | None:
    for imported in imports:
        if language == "typescript":
            if not imported.startswith("."):
                continue
            stem = posixpath.normpath(posixpath.join(posixpath.dirname(source), imported))
            candidates = [
                f"{stem}{suffix}" for suffix in (".ts", ".tsx", ".js", "/index.ts", "/index.tsx")
            ]
        elif level:
            base = posixpath.dirname(source)
            for _ in range(level - 1):
                base = posixpath.dirname(base)
            stem = posixpath.normpath(posixpath.join(base, imported.replace(".", "/")))
            candidates = [f"{stem}.py", f"{stem}/__init__.py"]
        else:
            stem = imported.replace(".", "/")
            candidates = [
                path
                for path in modules
                if path.endswith(f"/{stem}.py")
                or path.endswith(f"/{stem}/__init__.py")
                or path in {f"{stem}.py", f"{stem}/__init__.py"}
            ]
        matches = [modules[path] for path in candidates if path in modules]
        if len(matches) == 1:
            return matches[0]
    return None
