#!/usr/bin/env python3
"""Check the installed CLI contract without creating threads or doing inference."""

import json
from pathlib import Path
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import agent_server


def main() -> None:
    version = subprocess.check_output(
        [agent_server.CODEX_BIN, "--version"], text=True, timeout=10,
    ).strip()
    with tempfile.TemporaryDirectory(prefix="agentsfleet-codex-schema-") as temp:
        subprocess.run(
            [agent_server.CODEX_BIN, "app-server", "generate-json-schema",
             "--experimental", "--out", temp], check=True, timeout=30,
        )
        def schema(name):
            return json.loads((Path(temp) / name).read_text())

        requests = schema("ClientRequest.json")
        methods = {
            method
            for variant in requests["oneOf"]
            for method in variant["properties"]["method"].get("enum", [])
        }
        required = {
            "model/list", "thread/start", "thread/resume", "thread/fork",
            "thread/turns/list", "thread/compact/start", "turn/start",
            "turn/steer", "turn/interrupt", "thread/goal/get",
        }
        checks = {
            "native_methods": required <= methods,
            "compact_thread_id": "threadId" in schema("v2/ThreadCompactStartParams.json")["required"],
            "automatic_compaction_item": any(
                "contextCompaction" in item.get("properties", {}).get("type", {}).get("enum", [])
                for item in schema("v2/ItemCompletedNotification.json")["definitions"]["ThreadItem"]["oneOf"]
            ),
            "token_usage_window": "modelContextWindow" in schema("v2/ThreadTokenUsageUpdatedNotification.json")["definitions"]["ThreadTokenUsage"]["properties"],
        }
    catalog = agent_server.discover_codex_catalog()
    checks["live_native_catalog"] = catalog["model_source"] == "codex app-server model/list"
    checks["nonempty_catalog"] = len(catalog["models"]) > 1
    print(json.dumps({
        "codex_version": version, "checks": checks,
        "models": [model["value"] for model in catalog["models"] if model["value"]],
        "default_model": catalog["default_model"],
        "default_effort": catalog["default_effort"],
        "default_service_tier": catalog["default_service_tier"],
        "inference_tested": False,
    }, indent=2))
    if not all(checks.values()):
        raise SystemExit("Codex compatibility checks failed")


if __name__ == "__main__":
    main()
