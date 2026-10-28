"""The installed package version, resolved once.

A subpackage is not a separate distribution: it has no version of its own
and no release cadence of its own. The subpackages that used to carry a
literal ``__version__`` were quoting a value from a long-dead scheme --
``"0.4.0"``, hard-coded, and wrong for every release since -- while
nothing read them. A reader who found one had no way to tell a stale
stamp from a live one.

They now resolve the package's version instead. The value cannot go
stale, because there is only one source for it, and it cannot be
mistaken for an independent version, because it comes FROM the package.
"""

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pkg_version

try:
    __version__ = _pkg_version("mcp-common")
except PackageNotFoundError:  # pragma: no cover - dev/source-checkout path
    # The package is being imported from a source checkout rather than
    # from an install, so there is no metadata to read.
    __version__ = "0.0.0+unknown"

__all__ = ["__version__"]
