"""Test basic package functionality."""

from mcp_common import __version__


def test_version() -> None:
    """Test that package version is defined."""
    assert __version__ == "0.3.6"
