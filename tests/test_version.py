"""Test basic package functionality."""

from importlib.metadata import version

from mcp_common import __version__


def test_version() -> None:
    """``__version__`` must match the installed distribution version.

    Previously this test hard-coded ``"0.6.0"``, which only passed because
    ``mcp_common/__init__.py`` also hard-coded the same stale string.
    Both drifted out of sync with the real release (0.17.x). Now that
    ``__version__`` is sourced dynamically from package metadata, the
    test should compare against the same source of truth.
    """
    assert __version__ == version("mcp-common")
