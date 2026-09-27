"""Opt-in synthetic, loopback-only Ollama latency probe. Never records conversations."""

from __future__ import annotations

import argparse
import json
import time

import requests

from ai_os.hardware_profile import local_api_url


def measure(session, endpoint, payload):
    start = time.perf_counter()
    first = None
    final = None
    with session.post(
        endpoint, json=payload, stream=True, timeout=(3, 120), allow_redirects=False
    ) as response:
        response.raise_for_status()
        for line in response.iter_lines(chunk_size=1):
            if time.perf_counter() - start > 180:
                raise TimeoutError("Probe exceeded its total time budget")
            if not line:
                continue
            event = json.loads(line)
            if event.get("error"):
                raise RuntimeError("Ollama reported an error; inspect its local diagnostics")
            content = event.get("response") or event.get("message", {}).get("content")
            if content and first is None:
                first = time.perf_counter() - start
            if event.get("done"):
                final = event
                break
    if final is None:
        raise ValueError("Ollama stream ended without completion metrics")
    result = {
        "wall_s": round(time.perf_counter() - start, 4),
        "first_token_s": round(first, 4) if first is not None else None,
    }
    for key in ("load", "prompt_eval", "eval", "total"):
        result[key + "_s"] = round(final.get(key + "_duration", 0) / 1e9, 4)
    for key in ("prompt_eval_count", "eval_count"):
        result[key] = final.get(key, 0)
    result["tokens_per_s"] = (
        round(result["eval_count"] / result["eval_s"], 2) if result["eval_s"] else None
    )
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--endpoint", default="http://127.0.0.1:11434/api/chat")
    parser.add_argument("--model", default="qwen2.5:7b-instruct-q4_K_M")
    parser.add_argument("--context", type=int, choices=(2048, 4096), default=4096)
    parser.add_argument("--trials", type=int, choices=range(1, 7), default=3)
    parser.add_argument(
        "--cold", action="store_true", help="Unload only the selected model before measuring"
    )
    parser.add_argument(
        "--cpu", action="store_true", help="Explicit CPU baseline; no GPU allocation"
    )
    args = parser.parse_args()
    from ai_os.ai_os_core import system_prompt

    with requests.Session() as session:
        session.trust_env = False
        tags_url = local_api_url(args.endpoint, "tags")
        models = session.get(tags_url, timeout=3, allow_redirects=False).json()["models"]
        if args.model not in {m.get("name") for m in models}:
            parser.error("Requested model is not installed; no download was attempted")
        if args.cold:
            response = session.post(
                tags_url.removesuffix("tags") + "generate",
                json={"model": args.model, "keep_alive": 0},
                timeout=(3, 30),
                allow_redirects=False,
            )
            response.raise_for_status()
        for trial in range(args.trials):
            before = session.get(local_api_url(args.endpoint, "ps"), timeout=3).json()["models"]
            payload = {
                "model": args.model,
                "stream": True,
                "keep_alive": "2m",
                "messages": [
                    {"role": "system", "content": system_prompt()},
                    {"role": "user", "content": "In one short sentence, explain what RAM does."},
                ],
                "options": {
                    "num_ctx": args.context,
                    "num_thread": 8,
                    "num_predict": 64,
                    "temperature": 0,
                    "seed": 42,
                },
            }
            if args.cpu:
                payload["options"]["num_gpu"] = 0
            result = measure(session, args.endpoint, payload)
            after = session.get(local_api_url(args.endpoint, "ps"), timeout=3).json()["models"]
            result.update(
                trial=trial,
                context=args.context,
                model_was_loaded=any(m.get("name") == args.model for m in before),
                loaded=[
                    {k: m.get(k) for k in ("name", "size", "size_vram", "context_length")}
                    for m in after
                ],
            )
            print(json.dumps(result), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
