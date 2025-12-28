import json
from pathlib import Path

import pytest

from mcp_common.cli.security import atomic_write_json


def test_atomic_write_json_writes_file_with_permissions(tmp_path: Path) -> None:
    target = tmp_path / "snapshot.json"
    data = {"ok": True, "count": 2}

    atomic_write_json(target, data)

    assert json.loads(target.read_text()) == data
    assert (target.stat().st_mode & 0o777) == 0o600


def test_atomic_write_json_cleans_temp_on_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "snapshot.json"
    tmp_path_file = target.with_suffix(".tmp")
    original_replace = Path.replace

    def fake_replace(self: Path, target_path: Path) -> Path:
        if self.name.endswith(".tmp"):
            msg = "boom"
            raise OSError(msg)
        return original_replace(self, target_path)

    monkeypatch.setattr(Path, "replace", fake_replace)

    with pytest.raises(OSError, match="boom"):
        atomic_write_json(target, {"ok": True})

    assert not tmp_path_file.exists()
