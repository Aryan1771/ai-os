from pathlib import Path

from ai_os.config import ensure_runtime_tree


def test_initialization_stays_inside_selected_runtime(tmp_path, monkeypatch):
    home = tmp_path / "isolated-runtime"
    made = []
    original = Path.mkdir

    def track(path, *args, **kwargs):
        made.append(path)
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "mkdir", track)
    ensure_runtime_tree(home)
    assert made and all(path.is_relative_to(home) for path in made)
    assert (home / "config.json").is_file()
    assert (home / "data/private").is_dir()


def test_initialization_preserves_existing_configuration_and_assets(tmp_path):
    ensure_runtime_tree(tmp_path)
    config = tmp_path / "config.json"
    config.write_text('{"memory_enabled":false}')
    asset = tmp_path / "models/synthetic-model.bin"
    asset.write_bytes(b"local test asset")
    ensure_runtime_tree(tmp_path)
    assert config.read_text() == '{"memory_enabled":false}'
    assert asset.read_bytes() == b"local test asset"
