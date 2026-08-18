from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Iterator

from ai_os.tools.system_tools import get_hardware_stats, run_command


@dataclass(frozen=True)
class HardwareEvent:
    kind: str
    summary: str
    before: dict[str, Any] | None
    after: dict[str, Any]


def collect_snapshot() -> dict[str, Any]:
    display = run_command(["sh", "-lc", "command -v xrandr >/dev/null 2>&1 && xrandr --query || true"], approve=True)
    return {
        "hardware": get_hardware_stats(),
        "display_raw": display.stdout,
    }


def diff_snapshots(before: dict[str, Any] | None, after: dict[str, Any]) -> list[HardwareEvent]:
    if before is None:
        return [HardwareEvent("initial_snapshot", "Initial hardware snapshot captured.", None, after)]

    events: list[HardwareEvent] = []
    before_gpu = before.get("hardware", {}).get("nvidia")
    after_gpu = after.get("hardware", {}).get("nvidia")
    if before_gpu != after_gpu:
        events.append(HardwareEvent("gpu_change", "GPU state changed.", before, after))

    if before.get("display_raw") != after.get("display_raw"):
        events.append(HardwareEvent("display_change", "Display topology changed.", before, after))

    before_mem = before.get("hardware", {}).get("memory", {}).get("total_gb")
    after_mem = after.get("hardware", {}).get("memory", {}).get("total_gb")
    if before_mem != after_mem:
        events.append(HardwareEvent("memory_change", "System memory total changed.", before, after))

    return events


def monitor_polling(interval_sec: int = 5) -> Iterator[HardwareEvent]:
    previous: dict[str, Any] | None = None
    while True:
        current = collect_snapshot()
        for event in diff_snapshots(previous, current):
            yield event
        previous = current
        time.sleep(max(1, int(interval_sec)))


if __name__ == "__main__":
    for item in monitor_polling():
        print(json.dumps(item.__dict__, indent=2))

