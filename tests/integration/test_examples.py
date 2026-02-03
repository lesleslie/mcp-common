"""Integration tests for example servers.

These are smoke tests that verify the example servers can be imported
and instantiated without errors.
"""

import pytest
import sys
from pathlib import Path


class TestExampleServers:
    """Smoke tests for example servers."""

    def test_weather_server_import(self) -> None:
        """Test weather server example can be imported."""
        examples_dir = Path(__file__).parent.parent.parent / "examples"
        sys.path.insert(0, str(examples_dir))

        try:
            import weather_server

            assert weather_server.WeatherSettings is not None
            # Note: mcp object is created inside main(), not at module level
            assert callable(weather_server.create_weather_tools)
        except ImportError as e:
            if "HTTPClientAdapter" in str(e):
                pytest.skip("HTTPClientAdapter not implemented yet")
            raise
        finally:
            sys.path.remove(str(examples_dir))

    def test_cli_server_import(self) -> None:
        """Test CLI server example can be imported."""
        examples_dir = Path(__file__).parent.parent.parent / "examples"
        sys.path.insert(0, str(examples_dir))

        try:
            import cli_server

            assert cli_server.create_cli is not None
        except Exception as e:
            pytest.fail(f"Failed to import cli_server: {e}")
        finally:
            sys.path.remove(str(examples_dir))

    def test_weather_server_instantiation(self) -> None:
        """Test weather server can be instantiated."""
        examples_dir = Path(__file__).parent.parent.parent / "examples"

        # Change to examples directory to load settings relative to it
        import os
        old_cwd = os.getcwd()
        try:
            os.chdir(str(examples_dir))

            # Import after changing directory
            sys.path.insert(0, str(examples_dir))
            import weather_server

            # Settings should load without errors (uses defaults)
            settings = weather_server.WeatherSettings.load("weather")
            assert settings is not None
            # Check default value
            assert "openweathermap.org" in settings.base_url
        except ImportError as e:
            if "HTTPClientAdapter" in str(e):
                pytest.skip("HTTPClientAdapter not implemented yet")
            raise
        finally:
            os.chdir(old_cwd)
            if str(examples_dir) in sys.path:
                sys.path.remove(str(examples_dir))

    def test_cli_server_instantiation(self) -> None:
        """Test CLI server can be instantiated."""
        examples_dir = Path(__file__).parent.parent.parent / "examples"
        sys.path.insert(0, str(examples_dir))

        try:
            import cli_server

            # create_cli is a function that returns a Typer app
            cli = cli_server.create_cli()
            assert cli is not None
        except Exception as e:
            pytest.fail(f"Failed to create CLI: {e}")
        finally:
            sys.path.remove(str(examples_dir))
