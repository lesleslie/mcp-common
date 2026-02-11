"""Tests for WebSocket JWT authentication."""

from __future__ import annotations

import pytest
from datetime import UTC, datetime, timedelta

from mcp_common.websocket.auth import (
    WebSocketAuthenticator,
    generate_test_token,
)


@pytest.mark.unit
class TestWebSocketAuthenticator:
    """Test WebSocketAuthenticator class."""

    def test_create_token(self):
        """Test creating a JWT token."""
        auth = WebSocketAuthenticator(secret="test-secret")
        token = auth.create_token({
            "user_id": "user123",
            "permissions": ["read", "write"]
        })

        assert isinstance(token, str)
        assert len(token) > 0
        # JWT tokens have 3 parts separated by dots
        assert token.count(".") == 2

    def test_verify_valid_token(self):
        """Test verifying a valid JWT token."""
        auth = WebSocketAuthenticator(secret="test-secret")
        original_payload = {
            "user_id": "user123",
            "permissions": ["read", "write"]
        }

        token = auth.create_token(original_payload)
        payload = auth.verify_token(token)

        assert payload is not None
        assert payload["user_id"] == "user123"
        assert payload["permissions"] == ["read", "write"]
        assert "exp" in payload
        assert "iat" in payload

    def test_verify_invalid_token(self):
        """Test that invalid tokens are rejected."""
        auth = WebSocketAuthenticator(secret="test-secret")

        payload = auth.verify_token("invalid-token")
        assert payload is None

    def test_verify_token_with_wrong_secret(self):
        """Test that tokens signed with different secret are rejected."""
        auth1 = WebSocketAuthenticator(secret="secret-one")
        auth2 = WebSocketAuthenticator(secret="secret-two")

        token = auth1.create_token({"user_id": "user123"})
        payload = auth2.verify_token(token)

        assert payload is None

    def test_token_expiry(self):
        """Test that expired tokens are rejected."""
        auth = WebSocketAuthenticator(
            secret="test-secret",
            token_expiry=1  # 1 second expiry
        )

        token = auth.create_token({"user_id": "user123"})

        # Token should be valid immediately
        payload = auth.verify_token(token)
        assert payload is not None

        # Wait for token to expire
        import time
        time.sleep(2)

        # Token should now be expired
        payload = auth.verify_token(token)
        assert payload is None

    def test_authenticate_connection_success(self):
        """Test authenticating a connection with valid token."""
        auth = WebSocketAuthenticator(secret="test-secret")
        token = auth.create_token({
            "user_id": "user123",
            "permissions": ["read", "write"]
        })

        payload = auth.authenticate_connection(token)
        assert payload is not None
        assert payload["user_id"] == "user123"

    def test_authenticate_connection_invalid_token(self):
        """Test authenticating a connection with invalid token."""
        auth = WebSocketAuthenticator(secret="test-secret")

        payload = auth.authenticate_connection("invalid-token")
        assert payload is None

    def test_authenticate_connection_with_permissions(self):
        """Test authenticating with required permissions."""
        auth = WebSocketAuthenticator(secret="test-secret")
        token = auth.create_token({
            "user_id": "user123",
            "permissions": ["read", "write", "admin"]
        })

        # Should succeed with matching permissions
        payload = auth.authenticate_connection(
            token,
            required_permissions=["read", "write"]
        )
        assert payload is not None

        # Should fail with missing permissions
        payload = auth.authenticate_connection(
            token,
            required_permissions=["read", "delete"]
        )
        assert payload is None

    def test_custom_algorithm(self):
        """Test creating authenticator with custom algorithm."""
        auth = WebSocketAuthenticator(
            secret="test-secret",
            algorithm="HS256"
        )
        assert auth.algorithm == "HS256"


@pytest.mark.unit
class TestGenerateTestToken:
    """Test generate_test_token utility function."""

    def test_generate_test_token_default(self):
        """Test generating a test token with default parameters."""
        token = generate_test_token("user123")

        assert isinstance(token, str)
        assert len(token) > 0

        # Verify it can be decoded with the default secret
        auth = WebSocketAuthenticator(secret="test-secret")
        payload = auth.verify_token(token)

        assert payload is not None
        assert payload["user_id"] == "user123"
        assert payload["permissions"] == ["read"]

    def test_generate_test_token_with_permissions(self):
        """Test generating a test token with custom permissions."""
        token = generate_test_token(
            "user123",
            permissions=["read", "write", "admin"]
        )

        auth = WebSocketAuthenticator(secret="test-secret")
        payload = auth.verify_token(token)

        assert payload is not None
        assert payload["permissions"] == ["read", "write", "admin"]

    def test_generate_test_token_custom_secret(self):
        """Test generating a test token with custom secret."""
        token = generate_test_token("user123", secret="custom-secret")

        # Should fail with default secret
        auth1 = WebSocketAuthenticator(secret="test-secret")
        payload1 = auth1.verify_token(token)
        assert payload1 is None

        # Should succeed with custom secret
        auth2 = WebSocketAuthenticator(secret="custom-secret")
        payload2 = auth2.verify_token(token)
        assert payload2 is not None


@pytest.mark.unit
class TestTokenClaims:
    """Test token claim structure."""

    def test_token_contains_standard_claims(self):
        """Test that tokens contain standard JWT claims."""
        auth = WebSocketAuthenticator(secret="test-secret")
        token = auth.create_token({"user_id": "user123"})

        payload = auth.verify_token(token)

        # Check iat (issued at) claim
        assert "iat" in payload
        iat_ts = payload["iat"]
        assert isinstance(iat_ts, (int, float))
        assert iat_ts > 0

        # Check exp (expiry) claim
        assert "exp" in payload
        exp_ts = payload["exp"]
        assert isinstance(exp_ts, (int, float))
        assert exp_ts > iat_ts

    def test_token_expiry_time(self):
        """Test that token expiry is set correctly."""
        auth = WebSocketAuthenticator(
            secret="test-secret",
            token_expiry=3600  # 1 hour
        )
        before = datetime.now(UTC)
        token = auth.create_token({"user_id": "user123"})

        payload = auth.verify_token(token)

        exp = datetime.fromtimestamp(payload["exp"], UTC)
        expected_expiry = before + timedelta(seconds=3600)

        # Allow 1 second tolerance
        time_diff = abs((exp - expected_expiry).total_seconds())
        assert time_diff < 1.0


@pytest.mark.unit
class TestAuthErrorHandling:
    """Test error handling in authentication."""

    def test_malformed_token(self):
        """Test handling of malformed tokens."""
        auth = WebSocketAuthenticator(secret="test-secret")

        # Missing parts
        assert auth.verify_token("only.two") is None
        assert auth.verify_token("onlyone") is None

        # Empty token
        assert auth.verify_token("") is None

    def test_token_with_invalid_signature(self):
        """Test that tokens with tampered signatures are rejected."""
        auth = WebSocketAuthenticator(secret="test-secret")
        token = auth.create_token({"user_id": "user123"})

        # Tamper with token by changing signature
        parts = token.split(".")
        if len(parts) == 3:
            tampered_token = f"{parts[0]}.{parts[1]}.tamperedsignature"
            payload = auth.verify_token(tampered_token)
            assert payload is None

    def test_authenticate_without_authenticator_configured(self):
        """Test authenticate method when authenticator is not configured."""
        # This is handled in WebSocketServer class
        # Here we just verify authenticator's own error handling
        auth = WebSocketAuthenticator(secret="test-secret")

        # Valid token
        token = auth.create_token({"user_id": "user123"})
        assert auth.authenticate_connection(token) is not None

        # Invalid token
        assert auth.authenticate_connection("invalid") is None
