"""Synthetic local Ollama smoke test with sampled device-wide VRAM usage.

Run with the project venv. Does not change configuration or download models.
The observed maximum is a sampled peak, not an enforced allocation limit.
"""

import json
import subprocess
import threading
import time

import requests


def main():
    model = "qwen2.5:7b-instruct-q4_K_M"
    samples = []
    errors = []
    stop = threading.Event()

    def sample():
        while not stop.is_set():
            try:
                result = subprocess.run(
                    ["/usr/bin/nvidia-smi", "--query-gpu=memory.used",
                     "--format=csv,noheader,nounits"],
                    capture_output=True, text=True, check=True, timeout=3, shell=False,
                )
                samples.append([int(line) for line in result.stdout.splitlines()])
            except (OSError, ValueError, subprocess.SubprocessError):
                errors.append("GPU sample failed")
                return
            stop.wait(0.1)

    with requests.Session() as session:
        session.trust_env = False
        base = "http://127.0.0.1:11434/api/"
        response = session.get(base + "tags", timeout=5, allow_redirects=False)
        response.raise_for_status()
        if model not in {m["name"] for m in response.json()["models"]}:
            raise RuntimeError("Required model is absent; no download attempted")
        worker = threading.Thread(target=sample, daemon=True)
        worker.start()
        try:
            for trial in range(2):
                start = time.monotonic()
                response = session.post(
                    base + "chat",
                    json={"model": model, "stream": False, "keep_alive": "2m",
                          "messages": [{"role": "user", "content":
                                        "In one short sentence, explain what RAM does."}],
                          "options": {"num_ctx": 4096, "num_predict": 64,
                                      "temperature": 0, "seed": 42}},
                    timeout=(3, 120), allow_redirects=False,
                )
                response.raise_for_status()
                data = response.json()
                if not data.get("done") or not data.get("message", {}).get("content"):
                    raise RuntimeError("No completed model reply")
                print(json.dumps({"trial": trial, "wall_s": round(time.monotonic()-start, 3),
                                  **{k: data.get(k) for k in (
                                      "load_duration", "prompt_eval_duration", "eval_duration",
                                      "prompt_eval_count", "eval_count")}}), flush=True)
            response = session.get(base + "ps", timeout=5, allow_redirects=False)
            response.raise_for_status()
            print(json.dumps({"loaded": [{k: m.get(k) for k in (
                "name", "size", "size_vram", "context_length")}
                for m in response.json()["models"] if m.get("name") == model]}))
        finally:
            stop.set()
            worker.join(timeout=4)
            print(json.dumps({"samples": len(samples), "sampling_errors": len(errors),
                              "sampled_peak_mib_by_device":
                              [max(values) for values in zip(*samples)] if samples else []}))
    return 0 if samples and not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
