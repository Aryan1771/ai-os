from __future__ import annotations

import json
import shutil
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
    display = run_command(["xrandr", "--query"]) if shutil.which("xrandr") else None
    return {
        "hardware": get_hardware_stats(),
        "display_raw": display.stdout if display and display.ok else "",
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


def monitor_udev() -> Iterator[HardwareEvent]:
    """Yield device add/remove/change events when optional pyudev is installed."""
    try:
        import pyudev
    except ImportError as exc:
        raise RuntimeError("pyudev is not installed in the AI-OS virtual environment.") from exc

    context = pyudev.Context()
    monitor = pyudev.Monitor.from_netlink(context)
    monitor.filter_by(subsystem="block")
    for device in iter(monitor.poll, None):
        yield HardwareEvent(
            kind="udev_device_change",
            summary=f"{device.action}: {device.device_node or device.sys_name}",
            before=None,
            after={
                "action": device.action,
                "device_node": device.device_node,
                "subsystem": device.subsystem,
                "sys_name": device.sys_name,
            },
        )


if __name__ == "__main__":
    for item in monitor_polling():
        print(json.dumps(item.__dict__, indent=2))
