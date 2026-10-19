"""Opt-in synthetic tool-selection comparison. No tool is ever executed or model downloaded."""
import argparse
import json
import time

import requests

from ai_os.ai_os_core import build_tool_registry, system_prompt, parse_tool_call
from ai_os.tool_protocol import active_catalog, normalize_message

CASES = (
    ("greeting", "Hi RE, how are you doing today?", None),
    ("website", "Open YouTube in my default browser.", "open_website"),
    ("programs", "Check which programs are running for my user.", "running_applications"),
    ("command", "Run the exact command uname -r and tell me the result.", "run_command"),
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("models", nargs="+", help="Exact names of already-installed models")
    args = parser.parse_args()
    registry = build_tool_registry()
    allowed = set(registry)
    with requests.Session() as session:
        session.trust_env = False
        response = session.get("http://127.0.0.1:11434/api/tags", timeout=3, allow_redirects=False)
        response.raise_for_status()
        installed = {model["name"] for model in response.json()["models"]}
        for model in args.models:
            if model not in installed:
                print(json.dumps({"model": model, "status": "not_installed_no_download"}))
                continue
            for label, question, expected in CASES:
                start = time.monotonic()
                response = session.post("http://127.0.0.1:11434/api/chat", json={
                    "model": model, "stream": False, "keep_alive": "2m",
                    "messages": [{"role": "system", "content": system_prompt(allowed)},
                                 {"role": "user", "content": question}],
                    "tools": active_catalog(registry, allowed),
                    "options": {"num_ctx": 4096, "num_predict": 128, "temperature": 0, "seed": 42},
                }, timeout=(3, 120), allow_redirects=False)
                response.raise_for_status()
                try:
                    text = normalize_message(response.json()["message"], allowed)
                    call = parse_tool_call(text)
                    actual = call["tool"] if call else None
                    valid = actual == expected and bool(text.strip())
                    if actual == "run_command":
                        valid = valid and call["arguments"].get("command") == ["uname", "-r"]
                except (ValueError, KeyError, TypeError):
                    valid, actual = False, "invalid_protocol"
                print(json.dumps({"model": model, "case": label, "expected_tool": expected,
                                  "selected_tool": actual, "tool_selection_passed": valid,
                                  "wall_s": round(time.monotonic() - start, 3),
                                  "tools_executed": 0}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
