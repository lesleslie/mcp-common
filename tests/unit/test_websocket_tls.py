"""Branch-focused tests for mcp_common.websocket.tls."""

from __future__ import annotations

import os
import ssl
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from mcp_common.websocket import tls


class _FakeTempFile:
    def __init__(self, name: str) -> None:
        self.name = name
        self.writes: list[bytes] = []
        self.closed = False

    def write(self, data: bytes) -> None:
        self.writes.append(data)

    def close(self) -> None:
        self.closed = True


class _FakeKey:
    def __init__(self, private_bytes_result: bytes = b"key-bytes") -> None:
        self.private_bytes_result = private_bytes_result

    def public_key(self) -> object:
        return object()

    def private_bytes(self, **kwargs: object) -> bytes:
        return self.private_bytes_result


class _FakeCert:
    def __init__(self, payload: bytes = b"cert-bytes", *, raise_on_bytes: bool = False) -> None:
        self.payload = payload
        self.raise_on_bytes = raise_on_bytes

    def public_bytes(self, encoding: object) -> bytes:
        if self.raise_on_bytes:
            raise RuntimeError("write failed")
        return self.payload


class _FakeBuilder:
    def __init__(self, cert: _FakeCert) -> None:
        self.cert = cert

    def subject_name(self, subject: object) -> _FakeBuilder:
        return self

    def issuer_name(self, issuer: object) -> _FakeBuilder:
        return self

    def public_key(self, public_key: object) -> _FakeBuilder:
        return self

    def serial_number(self, serial: object) -> _FakeBuilder:
        return self

    def not_valid_before(self, value: datetime) -> _FakeBuilder:
        return self

    def not_valid_after(self, value: datetime) -> _FakeBuilder:
        return self

    def add_extension(self, extension: object, critical: bool) -> _FakeBuilder:
        return self

    def sign(self, key: object, algorithm: object, backend: object) -> _FakeCert:
        return self.cert


class _FakeSSLContext:
    def __init__(self, protocol: int) -> None:
        self.protocol = protocol
        self.loaded_cert_chain: tuple[str, str] | None = None
        self.loaded_verify_locations: list[str] = []
        self.ciphers: str | None = None
        self.minimum_version: ssl.TLSVersion | None = None
        self.verify_mode: int | None = None
        self.ecdh_curve: str | None = None
        self.raise_ecdh_error = False

    def load_cert_chain(self, certfile: str, keyfile: str) -> None:
        self.loaded_cert_chain = (certfile, keyfile)

    def load_verify_locations(self, cafile: str) -> None:
        self.loaded_verify_locations.append(cafile)

    def set_ciphers(self, ciphers: str) -> None:
        self.ciphers = ciphers

    def set_ecdh_curve(self, curve: str) -> None:
        if self.raise_ecdh_error:
            raise AttributeError("curve unavailable")
        self.ecdh_curve = curve


def test_generate_self_signed_cert_success(monkeypatch: pytest.MonkeyPatch) -> None:
    cert_file = _FakeTempFile("/tmp/fake-cert.pem")
    key_file = _FakeTempFile("/tmp/fake-key.pem")
    fake_key = _FakeKey()
    fake_cert = _FakeCert()
    files = iter([cert_file, key_file])

    monkeypatch.setattr(tls.rsa, "generate_private_key", lambda **kwargs: fake_key)
    monkeypatch.setattr(tls.x509, "CertificateBuilder", lambda: _FakeBuilder(fake_cert))
    monkeypatch.setattr(tls.tempfile, "NamedTemporaryFile", lambda **kwargs: next(files))

    cert_path, key_path = tls.generate_self_signed_cert("localhost", ["localhost"], 7)

    assert cert_path == cert_file.name
    assert key_path == key_file.name
    assert cert_file.writes == [b"cert-bytes"]
    assert key_file.writes == [b"key-bytes"]


def test_generate_self_signed_cert_cleans_up_on_error(monkeypatch: pytest.MonkeyPatch) -> None:
    cert_file = _FakeTempFile("/tmp/fake-cert.pem")
    key_file = _FakeTempFile("/tmp/fake-key.pem")
    fake_key = _FakeKey()
    fake_cert = _FakeCert(raise_on_bytes=True)
    unlink = MagicMock()
    files = iter([cert_file, key_file])

    monkeypatch.setattr(tls.rsa, "generate_private_key", lambda **kwargs: fake_key)
    monkeypatch.setattr(tls.x509, "CertificateBuilder", lambda: _FakeBuilder(fake_cert))
    monkeypatch.setattr(tls.tempfile, "NamedTemporaryFile", lambda **kwargs: next(files))
    monkeypatch.setattr(tls.os, "unlink", unlink)

    with pytest.raises(RuntimeError, match="Failed to generate self-signed certificate"):
        tls.generate_self_signed_cert("localhost")

    assert cert_file.closed is True
    assert key_file.closed is True
    assert unlink.call_count == 2


def test_create_ssl_context_success(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    cert_file = tmp_path / "cert.pem"
    key_file = tmp_path / "key.pem"
    ca_file = tmp_path / "ca.pem"
    cert_file.write_text("cert")
    key_file.write_text("key")
    ca_file.write_text("ca")

    ctx = _FakeSSLContext(ssl.PROTOCOL_TLS_SERVER)
    monkeypatch.setattr(tls.ssl, "SSLContext", lambda protocol: ctx)

    result = tls.create_ssl_context(
        cert_file=cert_file,
        key_file=key_file,
        ca_file=ca_file,
        verify_client=True,
        cert_reqs=ssl.CERT_OPTIONAL,
    )

    assert result is ctx
    assert ctx.loaded_cert_chain == (str(cert_file), str(key_file))
    assert ctx.loaded_verify_locations == [str(ca_file)]
    assert ctx.verify_mode == ssl.CERT_OPTIONAL
    assert ctx.ciphers is not None
    assert ctx.minimum_version == ssl.TLSVersion.TLSv1_2
    assert ctx.ecdh_curve == "prime256v1"


def test_create_ssl_context_missing_cert_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    ctx = _FakeSSLContext(ssl.PROTOCOL_TLS_SERVER)
    monkeypatch.setattr(tls.ssl, "SSLContext", lambda protocol: ctx)

    with pytest.raises(FileNotFoundError, match="Certificate file not found"):
        tls.create_ssl_context(cert_file=tmp_path / "missing.pem", key_file=tmp_path / "key.pem")


def test_create_ssl_context_missing_key_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    cert_file = tmp_path / "cert.pem"
    cert_file.write_text("cert")
    ctx = _FakeSSLContext(ssl.PROTOCOL_TLS_SERVER)
    monkeypatch.setattr(tls.ssl, "SSLContext", lambda protocol: ctx)

    with pytest.raises(FileNotFoundError, match="Key file not found"):
        tls.create_ssl_context(cert_file=cert_file, key_file=tmp_path / "missing-key.pem")


def test_create_ssl_context_missing_ca_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    cert_file = tmp_path / "cert.pem"
    key_file = tmp_path / "key.pem"
    cert_file.write_text("cert")
    key_file.write_text("key")

    ctx = _FakeSSLContext(ssl.PROTOCOL_TLS_SERVER)
    monkeypatch.setattr(tls.ssl, "SSLContext", lambda protocol: ctx)

    with pytest.raises(FileNotFoundError, match="CA file not found"):
        tls.create_ssl_context(cert_file=cert_file, key_file=key_file, ca_file=tmp_path / "missing-ca.pem")


def test_create_ssl_context_verify_client_without_ca(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    cert_file = tmp_path / "cert.pem"
    key_file = tmp_path / "key.pem"
    cert_file.write_text("cert")
    key_file.write_text("key")

    ctx = _FakeSSLContext(ssl.PROTOCOL_TLS_SERVER)
    monkeypatch.setattr(tls.ssl, "SSLContext", lambda protocol: ctx)

    result = tls.create_ssl_context(cert_file=cert_file, key_file=key_file, verify_client=True)

    assert result is ctx
    assert ctx.verify_mode == ssl.CERT_REQUIRED
    assert ctx.loaded_verify_locations == []


def test_create_ssl_context_ignores_ecdh_curve_errors(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    cert_file = tmp_path / "cert.pem"
    key_file = tmp_path / "key.pem"
    cert_file.write_text("cert")
    key_file.write_text("key")

    ctx = _FakeSSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.raise_ecdh_error = True
    monkeypatch.setattr(tls.ssl, "SSLContext", lambda protocol: ctx)

    result = tls.create_ssl_context(cert_file=cert_file, key_file=key_file)

    assert result is ctx
    assert ctx.ecdh_curve is None


def test_get_tls_config_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WS_TLS_ENABLED", "true")
    monkeypatch.setenv("WS_CERT_FILE", "/tmp/cert.pem")
    monkeypatch.setenv("WS_KEY_FILE", "/tmp/key.pem")
    monkeypatch.setenv("WS_CA_FILE", "/tmp/ca.pem")
    monkeypatch.setenv("WS_VERIFY_CLIENT", "true")

    assert tls.get_tls_config_from_env("WS") == {
        "tls_enabled": True,
        "cert_file": "/tmp/cert.pem",
        "key_file": "/tmp/key.pem",
        "ca_file": "/tmp/ca.pem",
        "verify_client": True,
    }


def test_create_development_ssl_context(monkeypatch: pytest.MonkeyPatch) -> None:
    ctx = _FakeSSLContext(ssl.PROTOCOL_TLS_SERVER)
    monkeypatch.setattr(tls, "generate_self_signed_cert", lambda common_name, dns_names, valid_days=365: ("/tmp/cert.pem", "/tmp/key.pem"))
    monkeypatch.setattr(tls, "create_ssl_context", lambda cert_file, key_file: ctx)

    result_ctx, cert_path, key_path = tls.create_development_ssl_context(
        common_name="localhost",
        dns_names=["localhost", "127.0.0.1"],
    )

    assert result_ctx is ctx
    assert cert_path == "/tmp/cert.pem"
    assert key_path == "/tmp/key.pem"


class _FakeName:
    def __init__(self, value: str) -> None:
        self.value = value

    def rfc4514_string(self) -> str:
        return self.value


class _FakeCertificate:
    def __init__(
        self,
        not_valid_before: datetime,
        not_valid_after: datetime,
    ) -> None:
        self.subject = _FakeName("subject")
        self.issuer = _FakeName("issuer")
        self.not_valid_before = not_valid_before
        self.not_valid_after = not_valid_after


def test_validate_certificate_file_not_found(tmp_path: Path) -> None:
    result = tls.validate_certificate(tmp_path / "missing.pem")

    assert result["valid"] is False
    assert "Certificate file not found" in result["error"]


def test_validate_certificate_expired(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    cert_file = tmp_path / "cert.pem"
    cert_file.write_bytes(b"pem")
    now = datetime.now(UTC)
    fake_cert = _FakeCertificate(now - timedelta(days=10), now - timedelta(days=1))

    monkeypatch.setattr(tls.x509, "load_pem_x509_certificate", lambda data, backend: fake_cert)

    result = tls.validate_certificate(cert_file)

    assert result["expired"] is True
    assert result["valid"] is False
    assert result["error"] == "Certificate has expired"


def test_validate_certificate_expiring_soon(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    cert_file = tmp_path / "cert.pem"
    cert_file.write_bytes(b"pem")
    now = datetime.now(UTC)
    fake_cert = _FakeCertificate(now - timedelta(days=1), now + timedelta(days=5))

    monkeypatch.setattr(tls.x509, "load_pem_x509_certificate", lambda data, backend: fake_cert)

    result = tls.validate_certificate(cert_file, min_days_remaining=30)

    assert result["expiring_soon"] is True
    assert result["days_remaining"] == 4 or result["days_remaining"] == 5
    assert result["valid"] is False
    assert "expires in" in result["error"]


def test_validate_certificate_valid(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    cert_file = tmp_path / "cert.pem"
    cert_file.write_bytes(b"pem")
    now = datetime.now(UTC)
    fake_cert = _FakeCertificate(now - timedelta(days=1), now + timedelta(days=90))

    monkeypatch.setattr(tls.x509, "load_pem_x509_certificate", lambda data, backend: fake_cert)

    result = tls.validate_certificate(cert_file)

    assert result["valid"] is True
    assert result["error"] is None


def test_validate_certificate_skip_expiry_check(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    cert_file = tmp_path / "cert.pem"
    cert_file.write_bytes(b"pem")
    now = datetime.now(UTC)
    fake_cert = _FakeCertificate(now - timedelta(days=1), now + timedelta(days=90))

    monkeypatch.setattr(tls.x509, "load_pem_x509_certificate", lambda data, backend: fake_cert)

    result = tls.validate_certificate(cert_file, check_expiry=False)

    assert result["valid"] is True
    assert result["days_remaining"] is None


def test_validate_certificate_general_error(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    cert_file = tmp_path / "cert.pem"
    cert_file.write_bytes(b"pem")

    def raise_error(*args: object, **kwargs: object) -> object:
        raise ValueError("bad cert")

    monkeypatch.setattr(tls.x509, "load_pem_x509_certificate", raise_error)

    result = tls.validate_certificate(cert_file)

    assert result["valid"] is False
    assert "Failed to validate certificate" in result["error"]
