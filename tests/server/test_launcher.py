"""Tests for ``mcp_common.server.launcher``.

TDD coverage for the canonical MCP server launcher. Splits into four
sections mirroring the plan's TDD tasks:

* ``TestLoadSecrets`` — Task 1.1 (regex/parsing port from
  ``mahavishnu/scripts/launch_mcp_with_secrets.py``)
* ``TestWarmSettingsFeed`` — Task 1.2 (settings.yaml one-shot init
  with ``entities_count > 0`` per ``health/feed.py:202-211``)
* ``TestRunWithUvicornConfig`` — Task 1.3 (transport="http" +
  uvicorn grace timeout wiring)
* ``TestLaunch`` — Task 1.5 (compose: secrets → warm → build_server →
  run_with_uvicorn_config)

The /health=200 contract (plan §1 outcome, REQ-005) hinges on the
``warm_settings_feed`` test that asserts ``entities_count > 0`` (not
just ``cycles_total >= 1``) — see ``mcp_common/health/feed.py:202-211``
for the predicate semantics.
"""

from __future__ import annotations

import inspect
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from mcp_common.health.feed import (
    HealthFeedState,
    StatusValue,
    is_healthy,
)

# ---------------------------------------------------------------------------
# Task 1.1: load_secrets()
# ---------------------------------------------------------------------------


class TestLoadSecrets:
    """Port of the secrets.env parser from ``launch_mcp_with_secrets.py``.

    The launcher accepts an explicit ``secrets_path`` so tests can pass a
    ``tmp_path`` without monkeypatching ``Path.home``. Default remains
    ``~/.config/secrets.env``.
    """

    def test_load_secrets_parses_export_quoted(self, tmp_path: Path) -> None:
        """``export FOO="bar"`` parses to ``{"FOO": "bar"}``."""
        from mcp_common.server.launcher import load_secrets

        secrets_file = tmp_path / "secrets.env"
        secrets_file.write_text('export FOO="bar"\n')

        assert load_secrets(secrets_file) == {"FOO": "bar"}

    def test_load_secrets_handles_missing_file(self, tmp_path: Path) -> None:
        """Returns ``{}`` when the path does not exist."""
        from mcp_common.server.launcher import load_secrets

        missing = tmp_path / "nope.env"
        assert not missing.exists()

        assert load_secrets(missing) == {}

    def test_load_secrets_uppercases_keys(self, tmp_path: Path) -> None:
        """Bare lowercase keys become upper-cased (env convention)."""
        from mcp_common.server.launcher import load_secrets

        secrets_file = tmp_path / "secrets.env"
        secrets_file.write_text("foo='bar'\n")

        assert load_secrets(secrets_file) == {"FOO": "bar"}

    def test_load_secrets_strips_inline_comments_outside_quotes(
        self, tmp_path: Path
    ) -> None:
        """Trailing ``# comment`` is stripped for unquoted values."""
        from mcp_common.server.launcher import load_secrets

        secrets_file = tmp_path / "secrets.env"
        secrets_file.write_text("FOO=bar # comment\n")

        assert load_secrets(secrets_file) == {"FOO": "bar"}

    def test_load_secrets_skips_blank_and_full_line_comments(
        self, tmp_path: Path
    ) -> None:
        """Blank lines and ``# ...`` lines do not produce entries."""
        from mcp_common.server.launcher import load_secrets

        secrets_file = tmp_path / "secrets.env"
        secrets_file.write_text(
            "# top-of-file comment\n"
            "\n"
            "   \n"
            "# another comment\n"
            'export REAL="value"\n'
        )

        assert load_secrets(secrets_file) == {"REAL": "value"}

    def test_load_secrets_handles_single_quotes(self, tmp_path: Path) -> None:
        """Single-quoted values parse the same as double-quoted."""
        from mcp_common.server.launcher import load_secrets

        secrets_file = tmp_path / "secrets.env"
        secrets_file.write_text("export TOKEN='abc123'\n")

        assert load_secrets(secrets_file) == {"TOKEN": "abc123"}

    def test_load_secrets_does_not_strip_comment_inside_quoted_value(
        self, tmp_path: Path
    ) -> None:
        """``FOO="bar#baz"`` keeps the ``#`` (it was inside quotes)."""
        from mcp_common.server.launcher import load_secrets

        secrets_file = tmp_path / "secrets.env"
        secrets_file.write_text('export FOO="bar#baz"\n')

        assert load_secrets(secrets_file) == {"FOO": "bar#baz"}

    def test_load_secrets_multiple_entries(self, tmp_path: Path) -> None:
        """Multiple ``export KEY=...`` lines all land in the result."""
        from mcp_common.server.launcher import load_secrets

        secrets_file = tmp_path / "secrets.env"
        secrets_file.write_text(
            'export ALPHA="one"\n'
            "BETA=two\n"
            "export GAMMA='three with spaces'\n"
        )

        result = load_secrets(secrets_file)
        assert result == {
            "ALPHA": "one",
            "BETA": "two",
            "GAMMA": "three with spaces",
        }

    def test_load_secrets_bare_assignment_without_export(
        self, tmp_path: Path
    ) -> None:
        """``KEY=value`` without the ``export`` prefix is also accepted."""
        from mcp_common.server.launcher import load_secrets

        secrets_file = tmp_path / "secrets.env"
        secrets_file.write_text("BARE=yes\n")

        assert load_secrets(secrets_file) == {"BARE": "yes"}


# ---------------------------------------------------------------------------
# Task 1.2: warm_settings_feed()
# ---------------------------------------------------------------------------


class TestWarmSettingsFeed:
    """Pre-warm ONLY the ``settings`` feed with ``entities_count > 0``.

    Per ``mcp_common/health/feed.py:202-211``, ``is_healthy()`` returns
    ``(False, WARMING_UP, [WARMING_UP_EMPTY_FEED])`` when
    ``entities_count == 0 AND cycles_total >= 1 AND ingester_running``.
    So seeding ``cycles_total`` alone is NOT sufficient for ``/health=200``.
    """

    def test_warm_settings_returns_feed_state_with_entities_count_one(
        self, tmp_path: Path
    ) -> None:
        """CRITICAL: assert ``feed.entities_count == 1``, not cycles_total.

        The whole point of REQ-004 is that the settings feed is a one-shot
        init: ``is_healthy()`` returns HEALTHY only when ``entities_count > 0``.
        Setting only ``cycles_total`` would leave the feed in WARMING_UP and
        ``/health=503``.
        """
        from mcp_common.server.launcher import warm_settings_feed

        settings_file = tmp_path / "settings.yaml"
        settings_file.write_text("name: test\n")

        feed = warm_settings_feed(settings_file)

        assert feed is not None
        assert feed.entities_count == 1

    def test_warm_settings_sets_cycles_total_to_one(
        self, tmp_path: Path
    ) -> None:
        """``cycles_total`` is bumped to ``1`` to mark the one-shot read."""
        from mcp_common.server.launcher import warm_settings_feed

        settings_file = tmp_path / "settings.yaml"
        settings_file.write_text("name: test\n")

        feed = warm_settings_feed(settings_file)

        assert feed is not None
        assert feed.cycles_total == 1

    def test_warm_settings_returns_healthy_status(self, tmp_path: Path) -> None:
        """``is_healthy(feed)`` returns ``StatusValue.HEALTHY`` for /health=200."""
        from mcp_common.server.launcher import warm_settings_feed

        settings_file = tmp_path / "settings.yaml"
        settings_file.write_text("name: test\n")

        feed = warm_settings_feed(settings_file)
        assert feed is not None

        healthy, status, reasons = is_healthy(feed)

        assert healthy is True
        assert status == StatusValue.HEALTHY
        assert reasons == []

    def test_warm_settings_sets_ingester_running(self, tmp_path: Path) -> None:
        """Mark the producer as alive so HNSW-on-DuckDB hardening does not fire."""
        from mcp_common.server.launcher import warm_settings_feed

        settings_file = tmp_path / "settings.yaml"
        settings_file.write_text("name: test\n")

        feed = warm_settings_feed(settings_file)

        assert feed is not None
        assert feed.ingester_running is True

    def test_warm_settings_with_none_path_returns_none(self) -> None:
        """``warm_settings_feed(None)`` → ``None`` (no-op)."""
        from mcp_common.server.launcher import warm_settings_feed

        assert warm_settings_feed(None) is None

    def test_warm_settings_with_missing_path_returns_none(
        self, tmp_path: Path
    ) -> None:
        """Missing settings file → ``None`` (caller should not crash)."""
        from mcp_common.server.launcher import warm_settings_feed

        missing = tmp_path / "absent.yaml"
        assert not missing.exists()

        assert warm_settings_feed(missing) is None

    def test_warm_settings_records_last_updated_timestamp(
        self, tmp_path: Path
    ) -> None:
        """``last_updated_timestamp`` is populated so consumers can detect freshness."""
        from mcp_common.server.launcher import warm_settings_feed

        settings_file = tmp_path / "settings.yaml"
        settings_file.write_text("name: test\n")

        feed = warm_settings_feed(settings_file)
        assert feed is not None
        assert feed.last_updated_timestamp is not None


# ---------------------------------------------------------------------------
# Task 1.3: run_with_uvicorn_config()
# ---------------------------------------------------------------------------


class TestRunWithUvicornConfig:
    """Thin wrapper that calls ``server.run_async(transport='http', ...)``.

    Tests use ``AsyncMock`` for ``server.run_async`` to verify both the
    transport choice and the uvicorn ``timeout_graceful_shutdown`` value
    passes through (REQ-007).
    """

    @pytest.mark.asyncio
    async def test_run_calls_run_async_with_transport_http(self) -> None:
        """``run_async`` is awaited with ``transport='http'``."""
        from mcp_common.server.launcher import run_with_uvicorn_config

        server = MagicMock()
        server.run_async = AsyncMock()

        await run_with_uvicorn_config(server, host="127.0.0.1", port=8680)

        server.run_async.assert_awaited_once()
        kwargs = server.run_async.await_args.kwargs
        assert kwargs["transport"] == "http"
        assert kwargs["host"] == "127.0.0.1"
        assert kwargs["port"] == 8680

    @pytest.mark.asyncio
    async def test_run_includes_grace_timeout_default_30(self) -> None:
        """Default ``timeout_graceful_shutdown=30`` passes through."""
        from mcp_common.server.launcher import run_with_uvicorn_config

        server = MagicMock()
        server.run_async = AsyncMock()

        await run_with_uvicorn_config(server, host="0.0.0.0", port=9000)

        kwargs = server.run_async.await_args.kwargs
        uvicorn_config = kwargs["uvicorn_config"]
        assert uvicorn_config == {"timeout_graceful_shutdown": 30}

    @pytest.mark.asyncio
    async def test_run_accepts_custom_grace_timeout(self) -> None:
        """Custom ``timeout_graceful_shutdown`` passes through verbatim."""
        from mcp_common.server.launcher import run_with_uvicorn_config

        server = MagicMock()
        server.run_async = AsyncMock()

        await run_with_uvicorn_config(
            server,
            host="127.0.0.1",
            port=8680,
            timeout_graceful_shutdown=5,
        )

        kwargs = server.run_async.await_args.kwargs
        assert kwargs["uvicorn_config"] == {"timeout_graceful_shutdown": 5}


# ---------------------------------------------------------------------------
# Task 1.5: launch() compose
# ---------------------------------------------------------------------------


class TestLaunch:
    """End-to-end orchestration: secrets → warm → build_server → run."""

    @pytest.mark.asyncio
    async def test_launch_loads_secrets_then_calls_build_server(
        self, tmp_path: Path, mocker: pytest.MockerFixture
    ) -> None:
        """``secrets_path`` is read BEFORE ``build_server`` is invoked."""
        from mcp_common.server.launcher import launch

        secrets_file = tmp_path / "secrets.env"
        secrets_file.write_text('export TOKEN="abc"\n')

        # Spy on the real loader so we can see the order of operations.
        real_loader = mocker.patch(
            "mcp_common.server.launcher.load_secrets",
            wraps=__import__(
                "mcp_common.server.launcher", fromlist=["load_secrets"]
            ).load_secrets,
        )
        # Spy on the runner
        mocker.patch(
            "mcp_common.server.launcher.run_with_uvicorn_config",
            new=AsyncMock(),
        )

        build_server_calls: list[int] = []
        loader_calls: list[int] = []

        def _track_build() -> object:
            build_server_calls.append(len(loader_calls))
            return MagicMock()

        def _track_loader(path: object) -> dict[str, str]:
            loader_calls.append(1)
            return real_loader(path)  # type: ignore[arg-type]

        mocker.patch(
            "mcp_common.server.launcher.load_secrets", side_effect=_track_loader
        )
        build_server = MagicMock(side_effect=_track_build)

        await launch(
            build_server=build_server,
            component_name="test",
            secrets_path=secrets_file,
        )

        # loader was called (at least once)
        assert loader_calls
        # build_server was called AFTER the loader (≥1 loader call before)
        assert build_server_calls
        assert min(build_server_calls) >= 1

    @pytest.mark.asyncio
    async def test_launch_passes_warm_settings_feed_when_settings_path_provided(
        self, tmp_path: Path, mocker: pytest.MockerFixture
    ) -> None:
        """``warm_settings_feed`` is called when ``settings_path`` is non-None."""
        from mcp_common.server.launcher import launch

        settings_file = tmp_path / "settings.yaml"
        settings_file.write_text("name: test\n")

        warm_spy = mocker.patch(
            "mcp_common.server.launcher.warm_settings_feed",
            return_value=HealthFeedState(
                entities_count=1, cycles_total=1, ingester_running=True
            ),
        )
        mocker.patch(
            "mcp_common.server.launcher.run_with_uvicorn_config",
            new=AsyncMock(),
        )

        await launch(
            build_server=lambda: MagicMock(),
            component_name="test",
            settings_path=settings_file,
        )

        warm_spy.assert_called_once_with(settings_file)

    @pytest.mark.asyncio
    async def test_launch_skips_warm_when_settings_path_is_none(
        self, mocker: pytest.MockerFixture
    ) -> None:
        """``warm_settings_feed`` is NOT called when ``settings_path=None``."""
        from mcp_common.server.launcher import launch

        warm_spy = mocker.patch(
            "mcp_common.server.launcher.warm_settings_feed",
            return_value=None,
        )
        mocker.patch(
            "mcp_common.server.launcher.run_with_uvicorn_config",
            new=AsyncMock(),
        )

        await launch(
            build_server=lambda: MagicMock(),
            component_name="test",
            settings_path=None,
        )

        warm_spy.assert_not_called()

    @pytest.mark.asyncio
    async def test_launch_invokes_run_with_uvicorn_config_default_30(
        self, mocker: pytest.MockerFixture
    ) -> None:
        """Default ``timeout_graceful_shutdown=30`` flows through to the runner."""
        from mcp_common.server.launcher import launch

        run_spy = mocker.patch(
            "mcp_common.server.launcher.run_with_uvicorn_config",
            new=AsyncMock(),
        )

        server = MagicMock(name="server")
        await launch(
            build_server=lambda: server,
            component_name="test",
            host="127.0.0.1",
            port=8681,
        )

        run_spy.assert_awaited_once()
        kwargs = run_spy.await_args.kwargs
        assert kwargs["timeout_graceful_shutdown"] == 30
        # positional args: (server, host, port)
        args = run_spy.await_args.args
        assert args[0] is server
        assert args[1] == "127.0.0.1"
        assert args[2] == 8681

    @pytest.mark.asyncio
    async def test_launch_uses_variadic_build_server_call(
        self, mocker: pytest.MockerFixture
    ) -> None:
        """``build_server`` is called variadically (no positional args).

        REQ-003 requires ``Callable[..., Any]`` so callers can pre-bind
        config, auth_config, providers, etc. inside their closure.
        """
        from mcp_common.server.launcher import launch

        mocker.patch(
            "mcp_common.server.launcher.run_with_uvicorn_config",
            new=AsyncMock(),
        )

        built_server = MagicMock(name="built-server")
        build_server = MagicMock(return_value=built_server)

        await launch(
            build_server=build_server,
            component_name="test",
        )

        build_server.assert_called_once_with()  # no args

    @pytest.mark.asyncio
    async def test_launch_merges_secrets_into_environ(
        self, tmp_path: Path, mocker: pytest.MockerFixture
    ) -> None:
        """Loaded secrets are added to ``os.environ`` via ``setdefault``."""
        import os

        from mcp_common.server.launcher import launch

        secrets_file = tmp_path / "secrets.env"
        secrets_file.write_text('export NEW_SECRET="xyz"\n')
        mocker.patch(
            "mcp_common.server.launcher.run_with_uvicorn_config",
            new=AsyncMock(),
        )

        # Make sure the key isn't already set in the test environment.
        os.environ.pop("NEW_SECRET", None)
        try:
            await launch(
                build_server=lambda: MagicMock(),
                component_name="test",
                secrets_path=secrets_file,
            )

            assert os.environ.get("NEW_SECRET") == "xyz"
        finally:
            os.environ.pop("NEW_SECRET", None)

    @pytest.mark.asyncio
    async def test_launch_signature_is_keyword_only(self) -> None:
        """All ``launch()`` parameters must be keyword-only (REQ-003)."""
        from mcp_common.server.launcher import launch

        sig = inspect.signature(launch)
        for name, param in sig.parameters.items():
            assert param.kind == inspect.Parameter.KEYWORD_ONLY, (
                f"{name} must be keyword-only"
            )


# ---------------------------------------------------------------------------
# Task 1.6: re-exports
# ---------------------------------------------------------------------------


class TestReexports:
    """Verify ``launch`` is exposed from both ``mcp_common.server`` and ``mcp_common``."""

    def test_launch_re_exported_from_mcp_common_server(self) -> None:
        import mcp_common.server as server_mod

        assert hasattr(server_mod, "launch")
        assert "launch" in server_mod.__all__

    def test_launch_re_exported_from_mcp_common_top_level(self) -> None:
        import mcp_common

        assert hasattr(mcp_common, "launch")
        assert "launch" in mcp_common.__all__

    def test_server_module_loads_without_error(self) -> None:
        """Importing ``mcp_common.server`` does not raise."""
        import importlib

        importlib.import_module("mcp_common.server")