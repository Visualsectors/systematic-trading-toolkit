"""Local screener context I/O over the exact released deterministic engine.

Node 22+ is optional for the toolkit but required for this command. No npm
package, live provider, model service, credential or broker is invoked here.
"""
from __future__ import annotations

from importlib.resources import files
import json
import os
from pathlib import Path
import shutil
import subprocess
from typing import Any

MAX_FILE_BYTES = 16 * 1024 * 1024
MAX_INPUT_BYTES = 64 * 1024 * 1024
DATASET_SCHEMA = "visualsectors-toolkit.context-dataset.v1"


def _pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in items:
        if key in value:
            raise ValueError("context JSON contains duplicate object keys")
        value[key] = item
    return value


def _invalid_constant(_: str) -> None:
    raise ValueError("context JSON contains a non-finite number")


def read_context_json(path: str | Path) -> dict[str, Any]:
    with Path(path).open("rb") as stream:
        payload = stream.read(MAX_FILE_BYTES + 1)
    if len(payload) > MAX_FILE_BYTES:
        raise ValueError("context file exceeds 16 MiB")
    try:
        text = payload.decode("utf-16" if payload.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig")
        value = json.loads(text, object_pairs_hook=_pairs, parse_constant=_invalid_constant)
    except (UnicodeError, RecursionError) as exc:
        raise ValueError("context file must be valid UTF-8 or BOM-marked UTF-16 JSON") from exc
    if not isinstance(value, dict):
        raise ValueError("context JSON root must be an object")
    return value


def load_context_dataset(path: str | Path) -> tuple[dict[str, Any], dict[str, Any]]:
    raw = read_context_json(path)
    required = {"schema_version", "dataset_id", "synthetic", "license", "source",
                "decision_time", "retrieval_spec", "evidence_packet"}
    if set(raw) != required or raw["schema_version"] != DATASET_SCHEMA:
        raise ValueError("context needs visualsectors-toolkit.context-dataset.v1; snapshot-only dataset.v1 cannot supply historical paths or peer/market lineage")
    if type(raw["synthetic"]) is not bool or any(
        not isinstance(raw[name], str) or not raw[name].strip()
        for name in ("dataset_id", "license", "source", "decision_time")
    ):
        raise ValueError("context dataset provenance is invalid")
    spec, packet = raw["retrieval_spec"], raw["evidence_packet"]
    if not isinstance(spec, dict) or not isinstance(packet, dict):
        raise ValueError("context retrieval_spec and evidence_packet must be objects")
    if raw["decision_time"] != spec.get("decision_time") or raw["decision_time"] != packet.get("decision_time"):
        raise ValueError("context dataset decision time differs from its evidence")
    return spec, packet


def run_context(
    spec: dict[str, Any], packet: dict[str, Any], *, mode: str = "computed",
    analysis_input: dict[str, Any] | None = None,
    model_output: dict[str, Any] | None = None,
    request: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if mode not in ("computed", "request", "decision"):
        raise ValueError("invalid context mode")
    if mode != "computed" and analysis_input is None:
        raise ValueError("analyst context requires --analysis-input")
    if mode == "decision" and (model_output is None or request is None):
        raise ValueError("decision validation requires both --model-output and the exact saved --request")
    node = shutil.which("node")
    if node is None:
        raise ValueError("vstoolkit context requires Node.js 22+ on PATH; existing toolkit commands remain Python-only")
    # Do not inherit NODE_OPTIONS, API keys, tokens, loaders or a Python invocation's credentials.
    env = {key: os.environ[key] for key in ("PATH", "SystemRoot", "WINDIR") if key in os.environ}
    env.update({"TZ": "UTC", "LANG": "en_US.UTF-8", "LC_ALL": "en_US.UTF-8"})
    try:
        version = subprocess.run([node, "--version"], capture_output=True, text=True, env=env, timeout=5, check=True)
        major = int(version.stdout.strip().removeprefix("v").split(".")[0])
        if major < 22:
            raise ValueError("vstoolkit context requires Node.js 22+")
        payload = json.dumps({"mode": mode, "spec": spec, "packet": packet,
                              "analysis_input": analysis_input, "model_output": model_output,
                              "request": request}, ensure_ascii=False, allow_nan=False).encode("utf-8")
        if len(payload) > MAX_INPUT_BYTES:
            raise ValueError("context input exceeds 64 MiB")
        engine = Path(str(files("visualsectors_toolkit").joinpath("context_engine/run.mjs")))
        result = subprocess.run([node, "--max-old-space-size=512", str(engine)], input=payload,
                                capture_output=True, env=env, timeout=30, check=False)
    except (subprocess.SubprocessError, RecursionError) as exc:
        raise ValueError("context engine failed or exceeded its bounded execution time") from exc
    if result.returncode != 0:
        message = result.stderr.decode("utf-8", errors="replace")[:500]
        raise ValueError(f"context rejected: {message or 'engine failed'}")
    output = json.loads(result.stdout)
    if not isinstance(output, dict):
        raise ValueError("context engine returned an invalid result")
    return output
