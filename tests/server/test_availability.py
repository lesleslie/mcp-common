"""Tests for availability check helpers in mcp_common/server/availability.py."""

import importlib
from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def clear_caches():
    """Clear all caches before tests to ensure isolation."""
    # Clear availability check caches before each test
    # Access via sys.modules to avoid importing
    try:
        import sys
        if "mcp_common.server.availability" in sys.modules:
            availability = sys.modules["mcp_common.server.availability"]
            availability.check_serverpanels_available.cache_clear()
            availability.check_security_available.cache_clear()
            availability.check_rate_limiting_available.cache_clear()
            availability.get_availability_status.cache_clear()
    except Exception:
        pass  # Module not yet imported or functions not available

    yield

    # Also clear after each test for cleanup
    try:
        import sys
        if "mcp_common.server.availability" in sys.modules:
            availability = sys.modules["mcp_common.server.availability"]
            availability.check_serverpanels_available.cache_clear()
            availability.check_security_available.cache_clear()
            availability.check_rate_limiting_available.cache_clear()
            availability.get_availability_status.cache_clear()
    except Exception:
        pass


class TestCheckServerpanelsAvailable:
    """Tests for check_serverpanels_available()."""

    def test_returns_true_when_available(self):
        """Should return True when mcp_common.ui module exists."""
        with patch("mcp_common.server.availability.importlib.util.find_spec") as mock_find_spec:
            mock_find_spec.return_value = True  # Module exists

            from mcp_common.server import check_serverpanels_available

            result = check_serverpanels_available()
            assert result is True
            mock_find_spec.assert_called_once_with("mcp_common.ui")

    def test_returns_false_when_not_available(self):
        """Should return False when mcp_common.ui module doesn't exist."""
        with patch("mcp_common.server.availability.importlib.util.find_spec") as mock_find_spec:
            mock_find_spec.return_value = None  # Module doesn't exist

            from mcp_common.server import check_serverpanels_available

            result = check_serverpanels_available()
            assert result is False
            mock_find_spec.assert_called_once_with("mcp_common.ui")

    def test_caches_result(self):
        """Should cache the result to avoid repeated import checks."""
        with patch("mcp_common.server.availability.importlib.util.find_spec") as mock_find_spec:
            mock_find_spec.return_value = True

            from mcp_common.server import check_serverpanels_available

            # Call multiple times
            check_serverpanels_available()
            check_serverpanels_available()
            check_serverpanels_available()

            # Should only call find_spec once due to caching
            assert mock_find_spec.call_count == 1

    def test_cache_can_be_cleared(self):
        """Should allow clearing cache between tests."""
        with patch("mcp_common.server.availability.importlib.util.find_spec") as mock_find_spec:
            from mcp_common.server import check_serverpanels_available

            # First call
            mock_find_spec.return_value = True
            result1 = check_serverpanels_available()
            assert result1 is True
            assert mock_find_spec.call_count == 1

            # Clear cache
            check_serverpanels_available.cache_clear()

            # Second call after cache clear
            # The function should be called again (not use cached value)
            result2 = check_serverpanels_available()
            assert result2 is True  # Same mock value
            assert mock_find_spec.call_count == 2  # Called again!


class TestCheckSecurityAvailable:
    """Tests for check_security_available()."""

    def test_returns_true_when_available(self):
        """Should return True when mcp_common.security module exists."""
        with patch("mcp_common.server.availability.importlib.util.find_spec") as mock_find_spec:
            mock_find_spec.return_value = True

            from mcp_common.server import check_security_available

            result = check_security_available()
            assert result is True
            mock_find_spec.assert_called_once_with("mcp_common.security")

    def test_returns_false_when_not_available(self):
        """Should return False when mcp_common.security module doesn't exist."""
        with patch("mcp_common.server.availability.importlib.util.find_spec") as mock_find_spec:
            mock_find_spec.return_value = None

            from mcp_common.server import check_security_available

            result = check_security_available()
            assert result is False
            mock_find_spec.assert_called_once_with("mcp_common.security")

    def test_caches_result(self):
        """Should cache the result to avoid repeated import checks."""
        with patch("mcp_common.server.availability.importlib.util.find_spec") as mock_find_spec:
            mock_find_spec.return_value = True

            from mcp_common.server import check_security_available

            # Call multiple times
            check_security_available()
            check_security_available()

            # Should only call find_spec once due to caching
            assert mock_find_spec.call_count == 1


class TestCheckRateLimitingAvailable:
    """Tests for check_rate_limiting_available()."""

    def test_returns_true_when_available(self):
        """Should return True when fastmcp rate limiting module exists."""
        with patch("mcp_common.server.availability.importlib.util.find_spec") as mock_find_spec:
            mock_find_spec.return_value = True

            from mcp_common.server import check_rate_limiting_available

            result = check_rate_limiting_available()
            assert result is True
            mock_find_spec.assert_called_once_with(
                "fastmcp.server.middleware.rate_limiting"
            )

    def test_returns_false_when_not_available(self):
        """Should return False when fastmcp rate limiting module doesn't exist."""
        with patch("mcp_common.server.availability.importlib.util.find_spec") as mock_find_spec:
            mock_find_spec.return_value = None

            from mcp_common.server import check_rate_limiting_available

            result = check_rate_limiting_available()
            assert result is False
            mock_find_spec.assert_called_once_with(
                "fastmcp.server.middleware.rate_limiting"
            )


class TestGetAvailabilityStatus:
    """Tests for get_availability_status()."""

    def test_returns_all_availability_status(self):
        """Should return dict with all dependency statuses."""
        with patch("mcp_common.server.availability.importlib.util.find_spec") as mock_find_spec:
            from mcp_common.server import (
                check_rate_limiting_available,
                check_security_available,
                check_serverpanels_available,
                get_availability_status,
            )

            # Clear all caches before test to ensure fresh state
            check_serverpanels_available.cache_clear()
            check_security_available.cache_clear()
            check_rate_limiting_available.cache_clear()
            get_availability_status.cache_clear()

            # Mock different availability for each dependency
            # Return True (or any truthy value) for available modules, None for unavailable
            def side_effect(module_name):
                # Make serverpanels available, others not
                return True if module_name == "mcp_common.ui" else None

            mock_find_spec.side_effect = side_effect

            result = get_availability_status()

            assert isinstance(result, dict)
            assert "serverpanels" in result
            assert "security" in result
            assert "rate_limiting" in result
            assert result["serverpanels"] is True
            assert result["security"] is False
            assert result["rate_limiting"] is False

            # Verify all three modules were checked
            assert mock_find_spec.call_count == 3
            # Verify the correct module names were checked
            calls = [call[0][0] for call in mock_find_spec.call_args_list]
            assert "mcp_common.ui" in calls
            assert "mcp_common.security" in calls
            assert "fastmcp.server.middleware.rate_limiting" in calls

    def test_caches_results(self):
        """Should cache the combined results."""
        with patch("mcp_common.server.availability.importlib.util.find_spec") as mock_find_spec:
            mock_find_spec.return_value = True

            from mcp_common.server import get_availability_status

            # Call multiple times
            get_availability_status()
            get_availability_status()

            # Each dependency check should only be called once
            # (3 dependencies * 2 calls = 6, but caching reduces it to 3)
            assert mock_find_spec.call_count == 3


class TestIntegrationWithActualModules:
    """Integration tests with actual modules (when available)."""

    def test_serverpanels_detection_with_actual_module(self):
        """Should correctly detect ServerPanels when actually available."""
        from mcp_common.server import check_serverpanels_available

        # This test relies on mcp_common.ui actually existing
        # If it doesn't, the test should still pass (just returns False)
        result = check_serverpanels_available()
        assert isinstance(result, bool)

    def test_security_detection_with_actual_module(self):
        """Should correctly detect security module when actually available."""
        from mcp_common.server import check_security_available

        # This test relies on mcp_common.security actually existing
        result = check_security_available()
        assert isinstance(result, bool)

    def test_get_availability_status_returns_consistent_types(self):
        """Should return dict with consistent boolean values."""
        from mcp_common.server import get_availability_status

        result = get_availability_status()

        # All values should be booleans
        assert all(isinstance(v, bool) for v in result.values())
        assert len(result) == 3  # Three dependencies checked
