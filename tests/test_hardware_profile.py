import json
from copy import deepcopy

import pytest

from ai_os import ai_os_core as core
from ai_os import hardware_profile as hw
from ai_os.config import DEFAULT_CONFIG, load_raw_config
from ai_os.hub_bridge import dispatch
from ai_os.settings_store import save_settings


def snapshot(ram=16, available=12, driver="nvidia"):
    return {
        "platform": "Linux",
        "architecture": "x86_64",
        "cpu": "Test CPU",
        "physical_cores": 8,
        "ram_total": ram * hw.GIB,
        "ram_available": available * hw.GIB,
        "supported_target": True,
        "gpus": [
            {
                "slot": "0000:01:00.0",
                "vendor": "Test",
                "device_id": "123",
                "driver": driver,
                "vram_bytes": 8 * hw.GIB,
            }
        ],
        "warnings": [],
    }


def models():
    return [
        {"name": DEFAULT_CONFIG["ollama_model"], "size": 4700000000},
        {"name": DEFAULT_CONFIG["hardware_fallback_models"][0], "size": 2000000000},
    ]


@pytest.mark.parametrize("driver", ["nvidia", "amdgpu", "i915", "xe"])
def test_gpu_driver_is_only_a_hint(driver):
    policy = hw.choose_policy(snapshot(driver=driver), DEFAULT_CONFIG, models(), [])
    assert policy["ready"] and policy["backend_policy"] == "ollama-auto"
    assert "num_gpu" not in policy["options"]
    assert policy["observed_acceleration"] == "Not yet observed for this model"


def test_cpu_and_bounded_resources():
    policy = hw.choose_policy(snapshot(driver=""), DEFAULT_CONFIG, models(), [])
    assert policy["options"] == {"num_ctx": 4096, "num_thread": 6, "num_gpu": 0}
    assert policy["backend_policy"] == "cpu"
    policy = hw.choose_policy(
        snapshot(), DEFAULT_CONFIG, models(), [], {"backend": "cpu", "threads": 1}
    )
    assert policy["options"]["num_thread"] == 1 and policy["options"]["num_gpu"] == 0


def test_fallback_requires_opt_in_and_installed_model():
    config = deepcopy(DEFAULT_CONFIG)
    assert not hw.choose_policy(snapshot(8, 6), config, models(), [])["ready"]
    config["hardware_allow_model_fallback"] = True
    policy = hw.choose_policy(snapshot(8, 6), config, models(), [])
    assert policy["ready"] and policy["model"] == models()[1]["name"]
    assert policy["options"]["num_ctx"] == 2048
    assert config["ollama_model"] == DEFAULT_CONFIG["ollama_model"]
    assert not hw.choose_policy(snapshot(8, 6), config, models()[:1], [])["ready"]


def test_cloud_models_and_insufficient_ram_are_rejected():
    cloud = [{**models()[0], "remote_host": "https://example.com"}]
    assert not hw.choose_policy(snapshot(), DEFAULT_CONFIG, cloud, [])["ready"]
    assert not hw.choose_policy(snapshot(2, 1), DEFAULT_CONFIG, models(), [])["ready"]


def test_resident_cpu_model_is_counted_once():
    loaded = [{**models()[0], "size_vram": 0}]
    policy = hw.choose_policy(snapshot(16, 4), DEFAULT_CONFIG, models(), loaded)
    assert policy["ready"] and policy["observed_acceleration"] == "CPU"


def test_profile_key_ignores_free_ram_and_driver():
    original = snapshot()
    changed = snapshot(available=3, driver="")
    assert hw.machine_key(original) == hw.machine_key(changed)
    changed["cpu"] = "Different CPU"
    assert hw.machine_key(original) != hw.machine_key(changed)


@pytest.mark.parametrize(
    "value",
    [
        {"backend": "cuda"},
        {"threads": True},
        {"threads": 100},
        {"context_tokens": 0},
        {"command": "reboot"},
        None,
    ],
)
def test_invalid_overrides(value):
    with pytest.raises(ValueError):
        hw.validate_override(value)


def test_override_isolation_and_paths(tmp_path):
    first, second = "a" * 24, "b" * 24
    hw.save_override(tmp_path, first, {"backend": "cpu"})
    assert hw.read_override(tmp_path, first) == {"backend": "cpu"}
    assert hw.read_override(tmp_path, second) == {}
    with pytest.raises(ValueError):
        hw.save_override(tmp_path, "../../config", {})
    with pytest.raises(ValueError):
        hw.read_override(tmp_path, "../../config")


@pytest.mark.parametrize(
    "endpoint",
    [
        "https://example.com/api/chat",
        "http://user@localhost",
        "http://localhost:0",
        "http://localhost?x=1",
    ],
)
def test_inventory_is_loopback_only(endpoint):
    with pytest.raises(ValueError):
        hw.local_api_url(endpoint, "tags")


def test_pci_discovery(tmp_path):
    devices = tmp_path / "bus/pci/devices"
    for slot, kind, vendor in [
        ("0000:01:00.0", "0x030000", "0x1002"),
        ("0000:02:00.0", "0x120000", "0x8086"),
    ]:
        device = devices / slot.replace(":", "_")
        device.mkdir(parents=True)
        (device / "class").write_text(kind)
        (device / "vendor").write_text(vendor)
        (device / "device").write_text("0x1234")
    gpus, accelerators = hw.pci_inventory(tmp_path)
    assert gpus[0]["vendor"] == "AMD"
    assert "does not prove NPU support" in accelerators[0]["inference_support"]


def test_refresh_and_confirmation(tmp_path, monkeypatch):
    device = snapshot()
    device["machine_key"] = hw.machine_key(device)
    monkeypatch.setattr(hw, "discover", lambda: device)
    monkeypatch.setattr(
        hw, "inventory", lambda _url, resource: models() if resource == "tags" else []
    )
    report = dispatch({"action": "hardware"}, tmp_path)["report"]
    assert report["policy"]["ready"]
    with pytest.raises(PermissionError):
        dispatch({"action": "hardware_override", "override": {"backend": "cpu"}}, tmp_path)
    result = dispatch(
        {"action": "hardware_override", "override": {"backend": "cpu"}, "confirmed": True}, tmp_path
    )
    assert result["report"]["policy"]["backend_policy"] == "cpu"
    assert json.loads((tmp_path / "hardware/current.json").read_text())["override"] == {
        "backend": "cpu"
    }


def test_inventory_failure_blocks_adaptation(tmp_path, monkeypatch):
    device = snapshot()
    device["machine_key"] = hw.machine_key(device)
    monkeypatch.setattr(hw, "discover", lambda: device)
    monkeypatch.setattr(hw.platform, "system", lambda: "Linux")

    def unavailable(*_args):
        raise hw.requests.ConnectionError("offline")

    monkeypatch.setattr(hw, "inventory", unavailable)
    with pytest.raises(RuntimeError, match="Cannot plan"):
        hw.runtime_policy(tmp_path)
    save_settings({"hardware_auto_adapt": False}, tmp_path, human_confirmed=True)
    assert hw.runtime_policy(tmp_path) is None


def test_request_lock_releases_after_error(tmp_path):
    with pytest.raises(ValueError), hw.inference_slot(tmp_path):
        with pytest.raises(RuntimeError), hw.inference_slot(tmp_path):
            pytest.fail("Concurrent request was admitted")
        raise ValueError("request failed")
    with hw.inference_slot(tmp_path):
        pass


def test_policy_reaches_request_payload(tmp_path, monkeypatch):
    policy = hw.choose_policy(snapshot(), DEFAULT_CONFIG, models(), [], {"backend": "cpu"})
    monkeypatch.setattr(core, "runtime_policy", lambda _home: policy)
    calls = []

    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {"message": {"content": "Hello"}}

    def post(*args, **kwargs):
        calls.append(kwargs["json"])
        return Response()

    monkeypatch.setattr(core.requests, "post", post)
    assert core.ask_ollama("hello", set(), tmp_path) == "Hello"
    assert calls[0]["options"]["num_gpu"] == 0
    assert calls[0]["keep_alive"] == "2m"
    assert load_raw_config(tmp_path)["ollama_model"] == DEFAULT_CONFIG["ollama_model"]


def test_fallback_setting_validation_and_consent(tmp_path):
    with pytest.raises(ValueError):
        save_settings({"hardware_fallback_models": ["bad name"]}, tmp_path, human_confirmed=True)
    with pytest.raises(PermissionError):
        save_settings({"hardware_allow_model_fallback": True}, tmp_path)
