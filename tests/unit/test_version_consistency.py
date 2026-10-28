"""The package version must have exactly one source.

Three subpackages used to carry a literal ``__version__ = "0.4.0"`` —
a value from a scheme that had been dead for many releases. Nothing read
them, and a reader who found one had no way to tell a stale stamp from a
live one: the only way to find out was to compare it against the
installed metadata and notice the gap.

The fix is not "update the literal". The fix is that a subpackage has no
version of its own, so it quotes the package's. These tests pin that
property, because a hard-coded number will always find its way back.
"""

from __future__ import annotations

import re
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pkg_version
from pathlib import Path

import pytest

import mcp_common
import mcp_common.code_graph
import mcp_common.server

_PACKAGE_ROOT = Path(mcp_common.__file__).parent


def _installed_version() -> str | None:
    try:
        return _pkg_version("mcp-common")
    except PackageNotFoundError:  # pragma: no cover - source-checkout path
        return None


class TestTheVersionHasOneSource:
    def test_the_package_reports_the_installed_version(self) -> None:
        installed = _installed_version()
        if installed is None:
            pytest.skip("mcp-common is not installed in this environment")
        assert mcp_common.__version__ == installed

    @pytest.mark.parametrize(
        "subpackage",
        [mcp_common.server, mcp_common.code_graph],
        ids=["server", "code_graph"],
    )
    def test_a_subpackage_quotes_the_package(self, subpackage: object) -> None:
        """A subpackage is not a separate distribution."""
        assert subpackage.__version__ == mcp_common.__version__

    def test_no_module_hard_codes_a_version(self) -> None:
        """No module may carry a literal version again.

        This is the drift guard. A hard-coded number is always one
        release away from being wrong, and the wrongness is invisible
        until somebody compares it against the installed metadata.
        """
        pattern = re.compile(
            r"^__version__\s*=\s*[\"'][^\"']+[\"']",
            re.MULTILINE,
        )
        offenders = [
            str(path.relative_to(_PACKAGE_ROOT))
            for path in sorted(_PACKAGE_ROOT.rglob("*.py"))
            if "__pycache__" not in path.parts
            and pattern.search(path.read_text(encoding="utf-8"))
        ]
        assert not offenders, (
            "these modules hard-code a version; use "
            "`from mcp_common._version import __version__` instead: "
            f"{offenders}"
        )
