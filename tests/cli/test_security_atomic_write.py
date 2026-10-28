import json
import os
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

    def fake_replace(src: object, dst: object) -> None:
        msg = "boom"
        raise OSError(msg)

    monkeypatch.setattr(os, "replace", fake_replace)

    with pytest.raises(OSError, match="boom"):
        atomic_write_json(target, {"ok": True})

    # No temp file left behind, and the destination was never created.
    assert [p for p in tmp_path.iterdir() if p.is_file()] == []
    assert not target.exists()
