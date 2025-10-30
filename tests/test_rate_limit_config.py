"""Tests for rate limiting configuration module.

Phase 3.3 M1: Test rate limit configuration profiles and server configs.
"""

import pytest

from mcp_common.middleware import (
    PROFILES,
    SERVER_CONFIGS,
    RateLimitConfig,
    RateLimitProfile,
    create_custom_config,
    get_config_for_server,
    get_profile_config,
)


class TestRateLimitProfile:
    """Tests for RateLimitProfile enum."""

    def test_profile_values(self) -> None:
        """Test that all profile values are defined."""
        assert RateLimitProfile.CONSERVATIVE == "conservative"
        assert RateLimitProfile.MODERATE == "moderate"
        assert RateLimitProfile.AGGRESSIVE == "aggressive"

    def test_profile_members(self) -> None:
        """Test that enum has exactly 3 members."""
        assert len(RateLimitProfile) == 3
        assert set(RateLimitProfile) == {
            RateLimitProfile.CONSERVATIVE,
            RateLimitProfile.MODERATE,
            RateLimitProfile.AGGRESSIVE,
        }


class TestRateLimitConfig:
    """Tests for RateLimitConfig dataclass."""

    def test_create_valid_config(self) -> None:
        """Test creating a valid configuration."""
        config = RateLimitConfig(
            max_requests_per_second=10.0,
            burst_capacity=20,
            global_limit=True,
            description="Test config",
        )

        assert config.max_requests_per_second == 10.0
        assert config.burst_capacity == 20
        assert config.global_limit is True
        assert config.description == "Test config"

    def test_config_defaults(self) -> None:
        """Test default values for optional parameters."""
        config = RateLimitConfig(
            max_requests_per_second=5.0,
            burst_capacity=15,
        )

        assert config.global_limit is True  # Default
        assert config.description == ""  # Default

    def test_config_is_frozen(self) -> None:
        """Test that config is immutable (frozen dataclass)."""
        config = RateLimitConfig(
            max_requests_per_second=10.0,
            burst_capacity=20,
        )

        with pytest.raises(AttributeError):
            config.max_requests_per_second = 15.0  # type: ignore[misc]

    def test_validate_positive_rate(self) -> None:
        """Test validation rejects non-positive request rates."""
        with pytest.raises(ValueError, match="must be positive"):
            RateLimitConfig(
                max_requests_per_second=0.0,
                burst_capacity=10,
            )

        with pytest.raises(ValueError, match="must be positive"):
            RateLimitConfig(
                max_requests_per_second=-5.0,
                burst_capacity=10,
            )

    def test_validate_burst_capacity(self) -> None:
        """Test validation rejects invalid burst capacity."""
        with pytest.raises(ValueError, match="at least 1"):
            RateLimitConfig(
                max_requests_per_second=10.0,
                burst_capacity=0,
            )

        with pytest.raises(ValueError, match="at least 1"):
            RateLimitConfig(
                max_requests_per_second=10.0,
                burst_capacity=-5,
            )

    def test_validate_burst_vs_rate(self) -> None:
        """Test validation warns when burst < rate."""
        with pytest.raises(ValueError, match="should be >= max_requests_per_second"):
            RateLimitConfig(
                max_requests_per_second=20.0,
                burst_capacity=10,  # Too small
            )


class TestPredefinedProfiles:
    """Tests for predefined rate limiting profiles."""

    def test_profiles_exist(self) -> None:
        """Test that all profiles are defined in PROFILES dict."""
        assert len(PROFILES) == 3
        assert RateLimitProfile.CONSERVATIVE in PROFILES
        assert RateLimitProfile.MODERATE in PROFILES
        assert RateLimitProfile.AGGRESSIVE in PROFILES

    def test_conservative_profile(self) -> None:
        """Test conservative profile configuration."""
        config = PROFILES[RateLimitProfile.CONSERVATIVE]

        assert config.max_requests_per_second == 5.0
        assert config.burst_capacity == 15
        assert config.global_limit is True
        assert "Conservative" in config.description

    def test_moderate_profile(self) -> None:
        """Test moderate profile configuration."""
        config = PROFILES[RateLimitProfile.MODERATE]

        assert config.max_requests_per_second == 10.0
        assert config.burst_capacity == 20
        assert config.global_limit is True
        assert "Moderate" in config.description

    def test_aggressive_profile(self) -> None:
        """Test aggressive profile configuration."""
        config = PROFILES[RateLimitProfile.AGGRESSIVE]

        assert config.max_requests_per_second == 15.0
        assert config.burst_capacity == 40
        assert config.global_limit is True
        assert "Aggressive" in config.description

    def test_profile_ordering(self) -> None:
        """Test that profiles are ordered by throughput."""
        conservative = PROFILES[RateLimitProfile.CONSERVATIVE]
        moderate = PROFILES[RateLimitProfile.MODERATE]
        aggressive = PROFILES[RateLimitProfile.AGGRESSIVE]

        assert conservative.max_requests_per_second < moderate.max_requests_per_second
        assert moderate.max_requests_per_second < aggressive.max_requests_per_second

        assert conservative.burst_capacity < moderate.burst_capacity
        assert moderate.burst_capacity < aggressive.burst_capacity


class TestServerConfigs:
    """Tests for server-specific configurations."""

    def test_all_servers_configured(self) -> None:
        """Test that all 9 Phase 3 servers are configured."""
        expected_servers = {
            "acb",
            "fastblocks",
            "session-mgmt-mcp",
            "crackerjack",
            "opera-cloud-mcp",
            "unifi-mcp",
            "raindropio-mcp",
            "mailgun-mcp",
            "excalidraw-mcp",
        }

        assert set(SERVER_CONFIGS.keys()) == expected_servers

    def test_core_infrastructure_configs(self) -> None:
        """Test core infrastructure servers use aggressive profile."""
        acb_config = SERVER_CONFIGS["acb"]
        fastblocks_config = SERVER_CONFIGS["fastblocks"]

        # Both should use aggressive profile values
        assert acb_config.max_requests_per_second == 15.0
        assert acb_config.burst_capacity == 40

        assert fastblocks_config.max_requests_per_second == 15.0
        assert fastblocks_config.burst_capacity == 40

    def test_email_api_config(self) -> None:
        """Test email API uses conservative profile."""
        mailgun_config = SERVER_CONFIGS["mailgun-mcp"]

        assert mailgun_config.max_requests_per_second == 5.0
        assert mailgun_config.burst_capacity == 15
        assert "email" in mailgun_config.description.lower()

    def test_standard_api_configs(self) -> None:
        """Test standard APIs use moderate rates."""
        moderate_servers = [
            "session-mgmt-mcp",
            "opera-cloud-mcp",
            "unifi-mcp",
        ]

        for server_name in moderate_servers:
            config = SERVER_CONFIGS[server_name]
            assert 10.0 <= config.max_requests_per_second <= 12.0
            assert 16 <= config.burst_capacity <= 20

    def test_crackerjack_burst_capacity(self) -> None:
        """Test crackerjack has higher burst for test/lint operations."""
        config = SERVER_CONFIGS["crackerjack"]

        assert config.max_requests_per_second == 12.0
        assert config.burst_capacity == 35  # Higher than standard
        assert "test" in config.description.lower() or "lint" in config.description.lower()

    def test_all_configs_valid(self) -> None:
        """Test that all server configs pass validation."""
        for server_name, config in SERVER_CONFIGS.items():
            # Should not raise any validation errors
            assert config.max_requests_per_second > 0
            assert config.burst_capacity >= 1
            assert config.burst_capacity >= config.max_requests_per_second
            assert config.description  # Should have description


class TestHelperFunctions:
    """Tests for helper functions."""

    def test_get_config_for_server_success(self) -> None:
        """Test getting config for existing server."""
        config = get_config_for_server("acb")

        assert isinstance(config, RateLimitConfig)
        assert config.max_requests_per_second == 15.0

    def test_get_config_for_server_unknown(self) -> None:
        """Test getting config for unknown server raises KeyError."""
        with pytest.raises(KeyError):
            get_config_for_server("unknown-server")

    def test_get_profile_config_success(self) -> None:
        """Test getting config for profile."""
        config = get_profile_config(RateLimitProfile.MODERATE)

        assert isinstance(config, RateLimitConfig)
        assert config.max_requests_per_second == 10.0

    def test_create_custom_config_valid(self) -> None:
        """Test creating custom configuration."""
        config = create_custom_config(
            max_requests_per_second=25.0,
            burst_capacity=60,
            global_limit=False,
            description="Custom high-throughput",
        )

        assert config.max_requests_per_second == 25.0
        assert config.burst_capacity == 60
        assert config.global_limit is False
        assert config.description == "Custom high-throughput"

    def test_create_custom_config_defaults(self) -> None:
        """Test custom config uses defaults for optional params."""
        config = create_custom_config(
            max_requests_per_second=10.0,
            burst_capacity=20,
        )

        assert config.global_limit is True  # Default
        assert config.description == ""  # Default

    def test_create_custom_config_invalid(self) -> None:
        """Test creating invalid custom config raises ValueError."""
        with pytest.raises(ValueError):
            create_custom_config(
                max_requests_per_second=-5.0,
                burst_capacity=10,
            )


class TestPhase3Integration:
    """Integration tests verifying Phase 3 server configurations."""

    def test_phase3_rate_limit_consistency(self) -> None:
        """Test that all Phase 3 servers have consistent rate limit patterns."""
        # Core infrastructure: 15 req/sec, 40 burst
        assert SERVER_CONFIGS["acb"].max_requests_per_second == 15.0
        assert SERVER_CONFIGS["fastblocks"].max_requests_per_second == 15.0

        # Email API: 5 req/sec, 15 burst
        assert SERVER_CONFIGS["mailgun-mcp"].max_requests_per_second == 5.0

        # Standard APIs: 8-12 req/sec
        assert 8.0 <= SERVER_CONFIGS["raindropio-mcp"].max_requests_per_second <= 12.0
        assert 10.0 <= SERVER_CONFIGS["opera-cloud-mcp"].max_requests_per_second <= 12.0

    def test_server_config_immutability(self) -> None:
        """Test that server configs cannot be modified after creation."""
        config = get_config_for_server("acb")

        with pytest.raises(AttributeError):
            config.max_requests_per_second = 100.0  # type: ignore[misc]

    @pytest.mark.parametrize(
        "server_name",
        [
            "acb",
            "fastblocks",
            "session-mgmt-mcp",
            "crackerjack",
            "opera-cloud-mcp",
            "unifi-mcp",
            "raindropio-mcp",
            "mailgun-mcp",
            "excalidraw-mcp",
        ],
    )
    def test_server_has_description(self, server_name: str) -> None:
        """Test that all servers have meaningful descriptions."""
        config = get_config_for_server(server_name)

        assert config.description
        assert len(config.description) > 20  # Meaningful description
