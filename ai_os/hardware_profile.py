"""Read-only Linux discovery and conservative per-machine inference policy."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import platform
import re
import subprocess
import time
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import psutil
import requests

from ai_os.config import AI_OS_HOME, atomic_json, load_raw_config

GIB = 1024**3
VENDORS = {"0x10de": "NVIDIA", "0x1002": "AMD", "0x8086": "Intel"}


def read_small(path: Path, default: str = "") -> str:
    try:
        with path.open(encoding="utf-8", errors="replace") as file:
            return file.read(4096).strip()
    except OSError:
        return default


def pci_inventory(sys_root: Path = Path("/sys")) -> tuple[list[dict], list[dict]]:
    gpus, accelerators = [], []
    for device in sorted((sys_root / "bus/pci/devices").glob("*"))[:512]:
        kind = read_small(device / "class")
        vendor = read_small(device / "vendor")
        driver = (device / "driver").resolve().name if (device / "driver").is_symlink() else ""
        item = {
            "slot": device.name,
            "vendor": VENDORS.get(vendor, vendor),
            "device_id": read_small(device / "device"),
            "driver": driver,
        }
        if kind.startswith("0x03"):
            value = read_small(device / "mem_info_vram_total", "0")
            item["vram_bytes"] = int(value) if value.isdecimal() else 0
            gpus.append(item)
        elif kind.startswith("0x12") or driver in {"ivpu", "intel_vpu", "amdxdna"}:
            item["inference_support"] = "Not configured; device presence does not prove NPU support"
            accelerators.append(item)
    return gpus, accelerators


def machine_key(snapshot: dict) -> str:
    # No hostnames, serial numbers, MAC addresses or machine-id are collected.
    identity = {
        key: snapshot.get(key) for key in ("architecture", "cpu", "physical_cores", "ram_total")
    }
    identity["gpus"] = [
        {key: gpu.get(key) for key in ("slot", "vendor", "device_id")}
        for gpu in snapshot.get("gpus", [])
    ]
    return hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()[:24]


def discover() -> dict:
    memory = psutil.virtual_memory()
    linux = platform.system() == "Linux"
    arch = platform.machine().lower()
    gpus, accelerators = pci_inventory() if linux else ([], [])
    warnings = []
    if linux and Path("/usr/bin/nvidia-smi").is_file():
        try:
            result = subprocess.run(
                [
                    "/usr/bin/nvidia-smi",
                    "--query-gpu=pci.bus_id,name,memory.total,memory.free",
                    "--format=csv,noheader,nounits",
                ],
                capture_output=True,
                text=True,
                timeout=3,
                check=True,
            )
            for row in csv.reader(result.stdout.splitlines()[:32]):
                if len(row) != 4:
                    continue
                slot, name, total, free = (cell.strip() for cell in row)
                match = next(
                    (
                        gpu
                        for gpu in gpus
                        if gpu["slot"].lower().endswith(slot.lower()[-7:])
                        and gpu["vendor"] == "NVIDIA"
                    ),
                    None,
                )
                if match is not None:
                    match.update(
                        name=name, vram_bytes=int(total) * 1024**2, vram_free=int(free) * 1024**2
                    )
        except (OSError, ValueError, subprocess.SubprocessError):
            warnings.append(
                "NVIDIA memory probe unavailable; memory estimates use system RAM only."
            )
    cpu = platform.processor() or arch
    if linux:
        for line in read_small(Path("/proc/cpuinfo")).splitlines():
            if line.startswith("model name"):
                cpu = line.split(":", 1)[-1].strip()
                break
    snapshot = {
        "platform": platform.system(),
        "architecture": arch,
        "cpu": cpu,
        "physical_cores": psutil.cpu_count(logical=False) or 1,
        "logical_cores": psutil.cpu_count() or 1,
        "ram_total": memory.total,
        "ram_available": memory.available,
        "gpus": gpus,
        "accelerators": accelerators,
        "audio_cards": read_small(Path("/proc/asound/cards")) if linux else "",
        "displays": [
            {"connector": path.parent.name, "status": read_small(path)}
            for path in sorted(Path("/sys/class/drm").glob("card*-*/status"))[:32]
        ]
        if linux
        else [],
        "supported_target": linux and arch in {"x86_64", "amd64"},
        "warnings": warnings,
        "detected_at": time.time(),
    }
    snapshot["machine_key"] = machine_key(snapshot)
    return snapshot


def local_api_url(endpoint: str, resource: str) -> str:
    parsed = urlsplit(endpoint)
    if resource not in {"tags", "ps"} or parsed.port == 0:
        raise ValueError("Invalid inventory resource or port")
    if (
        parsed.scheme != "http"
        or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("Hardware adaptation requires a direct loopback Ollama endpoint.")
    return urlunsplit((parsed.scheme, parsed.netloc, f"/api/{resource}", "", ""))


def inventory(endpoint: str, resource: str) -> list[dict]:
    with requests.Session() as session:
        session.trust_env = False
        with session.get(
            local_api_url(endpoint, resource), timeout=(1, 3), allow_redirects=False, stream=True
        ) as response:
            response.raise_for_status()
            if response.status_code != 200:
                raise ValueError("Unexpected inventory response")
            content = bytearray()
            deadline = time.monotonic() + 5
            for chunk in response.iter_content(8192):
                content.extend(chunk)
                if len(content) > 2 * 1024 * 1024 or time.monotonic() > deadline:
                    raise ValueError("Inventory response exceeds its bounds")
            data = json.loads(content)
    models = data.get("models") if isinstance(data, dict) else None
    if not isinstance(models, list):
        raise ValueError("Invalid Ollama inventory")  # noqa: TRY004 - invalid wire payload
    return [model for model in models[:512] if isinstance(model, dict)]


def validate_override(value: dict) -> dict:
    if not isinstance(value, dict) or set(value) - {"backend", "context_tokens", "threads"}:
        raise ValueError("Unsupported hardware override")
    if value.get("backend", "auto") not in {"auto", "cpu"}:
        raise ValueError("Backend override must be auto or cpu")
    for key, low, high in (("context_tokens", 1024, 8192), ("threads", 1, 64)):
        if key in value and (type(value[key]) is not int or not low <= value[key] <= high):
            raise ValueError(f"{key} must be between {low} and {high}")
    return value


def read_override(home: Path, key: str) -> dict:
    if not re.fullmatch(r"[a-f0-9]{24}", key):
        raise ValueError("Invalid machine profile key")
    try:
        path = home / "hardware/overrides" / f"{key}.json"
        if path.stat().st_size > 4096:
            return {}
        return validate_override(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError, TypeError):
        return {}


def save_override(home: Path, key: str, value: dict) -> None:
    if not re.fullmatch(r"[a-f0-9]{24}", key):
        raise ValueError("Invalid machine profile key")
    atomic_json(home / "hardware/overrides" / f"{key}.json", validate_override(value))


def choose_policy(
    snapshot: dict,
    config: dict,
    models: list[dict],
    running: list[dict],
    override: dict | None = None,
) -> dict:
    override = validate_override({} if override is None else override)
    backend = override.get("backend", config["hardware_backend"])
    driver_ready = any(
        gpu.get("driver") in {"nvidia", "amdgpu", "i915", "xe"} for gpu in snapshot["gpus"]
    )
    cpu_only = backend == "cpu" or not driver_ready
    ram = int(snapshot["ram_total"])
    ram_cap = max(0, ram - 2 * GIB)
    cap = 4096 if ram >= 12 * GIB else 2048 if ram >= 6 * GIB else 1024
    context = min(config["model_context_tokens"], override.get("context_tokens", cap), cap)
    threads = min(override.get("threads", 8), max(1, snapshot["physical_cores"] - 2), 8)
    options = {"num_ctx": context, "num_thread": threads}
    if cpu_only:
        options["num_gpu"] = 0
    policy = {
        "ready": False,
        "model": config["ollama_model"],
        "options": options,
        "backend_policy": "cpu" if cpu_only else "ollama-auto",
        "keep_alive": 0 if ram < 8 * GIB else "2m",
        "concurrent_requests": 1,
        "warnings": list(snapshot.get("warnings", [])),
        "reason": "No allowed installed model fits the conservative memory estimate.",
    }
    candidates = [config["ollama_model"]]
    if config["hardware_allow_model_fallback"]:
        candidates.extend(config["hardware_fallback_models"])
    names = {str(model.get("name", model.get("model", ""))): model for model in models}
    for name in dict.fromkeys(candidates):
        model = names.get(name, names.get(name + ":latest"))
        if (
            model is None
            or model.get("remote_host")
            or model.get("remote_model")
            or type(model.get("size")) is not int
            or model["size"] <= 0
        ):
            continue
        actual_name = str(model.get("name", model.get("model", name)))
        loaded = next(
            (item for item in running if item.get("name", item.get("model")) == actual_name), {}
        )
        resident = max(0, int(loaded.get("size", 0)) - int(loaded.get("size_vram", 0)))
        ram_budget = min(ram_cap, max(0, snapshot["ram_available"] * 0.8 + resident))
        estimate = int(model["size"] * 1.25 + 512 * 1024**2 + context * 128 * 1024)
        # Treat disk size as an estimate, never as proof of exact VRAM consumption.
        if estimate > ram_budget:
            continue
        known_vram = max((int(gpu.get("vram_bytes", 0)) for gpu in snapshot["gpus"]), default=0)
        if not cpu_only and known_vram and estimate > known_vram * 0.85:
            policy["warnings"].append(
                "Model may spill into system RAM; GPU memory is not a hard-enforced limit."
            )
        policy.update(
            ready=True,
            model=actual_name,
            estimated_bytes=estimate,
            reason="Selected an installed model within the estimated RAM budget.",
        )
        if actual_name != config["ollama_model"]:
            policy["warnings"].append(
                f"Using installed fallback {actual_name}; saved model preference is unchanged."
            )
        if loaded:
            policy["observed_acceleration"] = (
                "GPU" if int(loaded.get("size_vram", 0)) > 0 else "CPU"
            )
        else:
            policy["observed_acceleration"] = "Not yet observed for this model"
        return policy
    policy["reason"] += (
        " Install an explicitly chosen smaller model, free RAM, or review manual mode."
    )
    return policy


def refresh_profile(home: Path = AI_OS_HOME) -> dict:
    config = load_raw_config(home)
    snapshot = discover()
    override = read_override(home, snapshot["machine_key"])
    if not snapshot["supported_target"]:
        policy = {"ready": False, "reason": "Automatic adaptation targets x86-64 Linux only."}
    elif config["ai_provider"] != "ollama":
        policy = {
            "ready": False,
            "reason": "Provider-managed hardware; local Ollama adaptation is not applied.",
        }
    elif not config["hardware_auto_adapt"]:
        policy = {
            "ready": False,
            "reason": "Automatic adaptation is disabled; saved manual settings are used.",
        }
    else:
        try:
            models = inventory(config["ollama_url"], "tags")
            try:
                running = inventory(config["ollama_url"], "ps")
            except (requests.RequestException, ValueError):
                running = []
            policy = choose_policy(snapshot, config, models, running, override)
        except (requests.RequestException, ValueError, TypeError, OverflowError) as exc:
            policy = {"ready": False, "reason": f"Cannot plan local inference: {exc}"}
    report = {"version": 1, "hardware": snapshot, "policy": policy, "override": override}
    directory = home / "hardware"
    atomic_json(directory / "profiles" / f"{snapshot['machine_key']}.json", report)
    atomic_json(directory / "current.json", report)
    return report


def runtime_policy(home: Path = AI_OS_HOME) -> dict | None:
    config = load_raw_config(home)
    if (
        not config["hardware_auto_adapt"]
        or config["ai_provider"] != "ollama"
        or platform.system() != "Linux"
    ):
        return None
    policy = refresh_profile(home)["policy"]
    if not policy.get("ready"):
        raise RuntimeError(policy["reason"])
    return policy


@contextmanager
def inference_slot(home: Path):
    """Serialize this installation's requests across hub, voice and CLI processes."""
    directory = home / "run"
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / "inference.lock").open("a+b") as handle:
        if os.name == "posix":
            import fcntl

            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise RuntimeError(
                    "Another REgenOS inference request is running. Try again shortly."
                ) from exc
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        else:
            import msvcrt

            if handle.tell() == 0:
                handle.write(b"0")
                handle.flush()
            handle.seek(0)
            try:
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                raise RuntimeError("Another REgenOS inference request is running.") from exc
            try:
                yield
            finally:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--refresh", action="store_true", help="Rescan and save the current profile"
    )
    parser.parse_args()
    print(json.dumps(refresh_profile(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
