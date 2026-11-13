"""Generate conservative, traceable placeholder outputs for controlled fixtures."""

import hashlib
import re
from pathlib import Path

from deterministic.agents.model import ChatModel, ModelResult, ModelSettings
from deterministic.agents.planner import MigrationTask
from deterministic.ingestion.schemas import Evidence
from deterministic.memory.base import Record

EDITOR_SYSTEM_PROMPT = (
    "You migrate a Python HTTP backend to one runnable TypeScript file. "
    "Return only source code, without markdown. Use Node 22 built-ins only: "
    "require('node:http'), fetch, URL, and process. Use CommonJS-compatible syntax. "
    "Start with // @ts-nocheck so the standalone compiler needs no external type package. "
    "Listen on 0.0.0.0 and process.env.PORT (default 8080). "
    "Read UPSTREAM_URL and UPSTREAM_API_KEY from environment. "
    "Never send the key to the browser. "
    "Preserve /api/projects GET, /api/projects/:id GET and PUT behavior, including "
    "422 validation, 404 missing, 409 three-way merge conflicts, 502 upstream reads, "
    "and 504 uncertain writes without retrying a PUT. Keep latest linked_companies "
    "on replacement writes. Return only narrow browser projections."
)
EDITOR_PROMPT_VERSION = hashlib.sha256(EDITOR_SYSTEM_PROMPT.encode()).hexdigest()[:16]


def build(
    task: MigrationTask,
    evidence: Evidence,
    output: Path,
    target: str,
    context: list[Record] | None = None,
    model: ChatModel | None = None,
    generations: list[ModelResult] | None = None,
    feedback: str = "",
) -> Path:
    if evidence.scope_id == "project-editor" and target == "typescript":
        if not context:
            raise ValueError("Editor migration requires retrieved context")
        client = model or ChatModel(ModelSettings.from_environment())
        result = client.complete(
            EDITOR_SYSTEM_PROMPT,
            "Target file: server.ts\nRetrieved evidence follows. Use only these records:\n"
            + "\n\n".join(
                f"[id={record.record_id} provenance={','.join(record.provenance)}]\n"
                f"{record.content}"
                for record in context
            )
            + (f"\n\nPrevious validation feedback:\n{feedback}" if feedback else ""),
        )
        code = result.text.strip()
        if code.startswith("```"):
            code = re.sub(r"^```(?:typescript|ts)?\s*|\s*```$", "", code).strip()
        if not code.startswith("// @ts-nocheck"):
            code = "// @ts-nocheck\n" + code
        dest = output / task.target_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(code + "\n", encoding="utf-8")
        if generations is not None:
            generations.append(result)
        return dest
    source = next((e for e in evidence.entities if e.path == task.source_path), None)
    record = next((item for item in (context or []) if task.source_path in item.provenance), None)
    text = record.content if record else source.content if source else ""
    if target == "typescript":
        converted = _python_to_typescript(text)
    else:
        converted = _typescript_to_python(text)
    dest = output / task.target_path
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(converted, encoding="utf-8")
    return dest


def _python_to_typescript(text: str) -> str:
    match = re.search(
        r"(?:async\s+)?def\s+(\w+)\(([^)]*)\)\s*(?:->\s*([^:]+))?:\s*\n\s+return\s+(.+)",
        text,
    )
    if not match:
        raise ValueError("Unsupported Python construct: expected a typed single-return function")
    name, params, result_type, expression = match.groups()
    params = re.sub(r":\s*(int|float|str|bool)", lambda m: ": " + _ts_type(m[1]), params)
    return (
        f"export function {name}({params}): {_ts_type((result_type or 'any').strip())} "
        f"{{ return {expression.strip()}; }}\n"
    )


def _typescript_to_python(text: str) -> str:
    match = re.search(
        r"(?:export\s+)?function\s+(\w+)\(([^)]*)\)\s*(?::\s*([\w\[\]]+))?\s*"
        r"\{\s*return\s+(.+?);\s*\}",
        text,
        re.S,
    )
    if not match:
        raise ValueError("Unsupported TypeScript construct: expected a single-return function")
    name, params, _result_type, expression = match.groups()
    params = re.sub(r":\s*(number|string|boolean)", lambda m: ": " + _py_type(m[1]), params)
    return f"def {name}({params}):\n    return {expression.strip()}\n"


def _ts_type(value: str) -> str:
    return {"int": "number", "float": "number", "str": "string", "bool": "boolean"}.get(
        value, value
    )


def _py_type(value: str) -> str:
    return {"number": "float", "string": "str", "boolean": "bool"}.get(value, value)
