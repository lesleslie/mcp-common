from pathlib import Path

import pytest
import yaml

from mcp_common.config.base import MCPBaseSettings


class LayerSettings(MCPBaseSettings):
    token: str = "default"
    data_dir: Path = Path("data")


def _write_yaml(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data))


def test_layering_respects_priority(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)

    server_yaml = tmp_path / "settings" / "my-server.yaml"
    local_yaml = tmp_path / "settings" / "local.yaml"
    explicit_yaml = tmp_path / "explicit.yaml"

    _write_yaml(server_yaml, {"token": "server"})
    _write_yaml(local_yaml, {"token": "local"})
    _write_yaml(explicit_yaml, {"token": "explicit"})

    monkeypatch.setenv("MY_SERVER_TOKEN", "env")

    settings = LayerSettings.load("my-server", config_path=explicit_yaml)

    assert settings.token == "explicit"


def test_layering_env_overrides_yaml(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)

    server_yaml = tmp_path / "settings" / "test.yaml"
    local_yaml = tmp_path / "settings" / "local.yaml"

    _write_yaml(server_yaml, {"token": "server"})
    _write_yaml(local_yaml, {"token": "local"})

    monkeypatch.setenv("TEST_TOKEN", "env")

    settings = LayerSettings.load("test")

    assert settings.token == "env"


def test_env_prefix_default_normalizes_hyphens(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)

    monkeypatch.setenv("MY_SERVER_TOKEN", "env")

    settings = LayerSettings.load("my-server")

    assert settings.token == "env"


def test_explicit_config_missing_is_ignored(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)

    server_yaml = tmp_path / "settings" / "alpha.yaml"
    _write_yaml(server_yaml, {"token": "server"})

    missing = tmp_path / "missing.yaml"

    settings = LayerSettings.load("alpha", config_path=missing)

    assert settings.token == "server"
