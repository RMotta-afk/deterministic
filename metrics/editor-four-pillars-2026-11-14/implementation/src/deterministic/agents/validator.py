"""Bounded compiler and behavioral validation."""

import json
import shutil
import subprocess
from pathlib import Path

from pydantic import BaseModel, ConfigDict


class ValidationResult(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    passed: bool
    checks: dict[str, bool]
    output: str
    schema_version: int = 1


def validate(output: Path, target: str, cases: list[dict] | None = None) -> ValidationResult:
    files = list(output.rglob("*.py" if target == "python" else "*.ts"))
    ok = bool(files)
    output_text = ""
    syntax_ok = bool(files)
    behavior_ok = bool(cases)
    if target == "python" and files:
        for file in files:
            result = subprocess.run(
                ["python", "-m", "py_compile", str(file)],
                capture_output=True,
                text=True,
                timeout=10,
            )
            syntax_ok &= result.returncode == 0
            output_text += result.stdout + result.stderr
        if syntax_ok and cases:
            for case in cases:
                module = next((f for f in files if f.stem == case["function"]), files[0])
                script = (
                    "import importlib.util,json,sys; "
                    "s=importlib.util.spec_from_file_location('candidate',sys.argv[1]); "
                    "m=importlib.util.module_from_spec(s); s.loader.exec_module(m); "
                    "cases=json.loads(sys.argv[2]); "
                    "assert all(getattr(m,c['function'])(*c['arguments']) "
                    "== c['expected'] for c in cases)"
                )
                result = subprocess.run(
                    ["python", "-c", script, str(module), json.dumps([case])],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                behavior_ok &= result.returncode == 0
                output_text += result.stdout + result.stderr
    elif target == "typescript" and files:
        # TypeScript compile is used when the pinned compiler is installed.
        if shutil.which("tsc"):
            build_dir = output / ".compiled"
            result = subprocess.run(
                [
                    "tsc",
                    "--target",
                    "ES2020",
                    "--module",
                    "commonjs",
                    "--outDir",
                    str(build_dir),
                    *map(str, files),
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
            syntax_ok &= result.returncode == 0
            output_text += result.stdout + result.stderr
            if syntax_ok and cases:
                for case in cases:
                    js_file = build_dir / (case["function"] + ".js")
                    script = (
                        "const m=require(process.argv[1]); "
                        "const cases=JSON.parse(process.argv[2]); "
                        "for(const c of cases) { "
                        "if(m[c.function](...c.arguments)!==c.expected) process.exit(1); }"
                    )
                    result = subprocess.run(
                        ["node", "-e", script, str(js_file), json.dumps([case])],
                        capture_output=True,
                        text=True,
                        timeout=10,
                    )
                    behavior_ok &= result.returncode == 0
                    output_text += result.stdout + result.stderr
        else:
            syntax_ok = False
            output_text = "TypeScript compiler (tsc) is not installed"
    ok = syntax_ok and behavior_ok
    return ValidationResult(
        passed=ok,
        checks={"syntax_or_compile": bool(syntax_ok), "behavioral": bool(behavior_ok)},
        output=output_text,
    )
