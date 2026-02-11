"""TLS configuration and certificate management for WebSocket servers.

This module provides TLS/SSL support for secure WebSocket (WSS) connections,
including certificate generation, SSL context creation, and configuration
management.
"""

from __future__ import annotations

import logging
import os
import ssl
import tempfile
from datetime import datetime, timedelta, UTC
from pathlib import Path
from typing import Any

from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend

logger = logging.getLogger(__name__)


def generate_self_signed_cert(
    common_name: str = "localhost",
    dns_names: list[str] | None = None,
    valid_days: int = 365,
) -> tuple[str, str]:
    """Generate a self-signed certificate for development/testing.

    Args:
        common_name: Common name (CN) for the certificate
        dns_names: List of DNS names to include (Subject Alternative Names)
        valid_days: Number of days the certificate is valid

    Returns:
        Tuple of (cert_file_path, key_file_path)

    Example:
        >>> cert_path, key_path = generate_self_signed_cert("localhost")
        >>> print(f"Cert: {cert_path}, Key: {key_path}")
    """
    # Generate private key
    key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend(),
    )

    # Build certificate subject
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
        x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "California"),
        x509.NameAttribute(NameOID.LOCALITY_NAME, "San Francisco"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Development"),
        x509.NameAttribute(NameOID.COMMON_NAME, common_name),
    ])

    # Build certificate
    cert = x509.CertificateBuilder().subject_name(
        subject
    ).issuer_name(
        issuer
    ).public_key(
        key.public_key()
    ).serial_number(
        x509.random_serial_number()
    ).not_valid_before(
        datetime.now(UTC)
    ).not_valid_after(
        datetime.now(UTC) + timedelta(days=valid_days)
    ).add_extension(
        x509.SubjectAlternativeName(
            [x509.DNSName(dns) for dns in (dns_names or [common_name])]
        ),
        critical=False,
    ).sign(key, hashes.SHA256(), default_backend())

    # Write to temporary files
    cert_file = tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.pem')
    key_file = tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.pem')

    try:
        # Write certificate
        cert_file.write(cert.public_bytes(serialization.Encoding.PEM))
        cert_file_path = cert_file.name

        # Write private key
        key_file.write(key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        ))
        key_file_path = key_file.name

        logger.info(
            f"Generated self-signed certificate: {cert_file_path}, "
            f"key: {key_file_path} (valid for {valid_days} days)"
        )

        return cert_file_path, key_file_path

    except Exception as e:
        # Clean up on error
        cert_file.close()
        key_file.close()
        os.unlink(cert_file.name)
        os.unlink(key_file.name)
        raise RuntimeError(f"Failed to generate self-signed certificate: {e}") from e
    finally:
        cert_file.close()
        key_file.close()


def create_ssl_context(
    cert_file: str | Path | None = None,
    key_file: str | Path | None = None,
    ca_file: str | Path | None = None,
    verify_client: bool = False,
    cert_reqs: int = ssl.CERT_NONE,
) -> ssl.SSLContext:
    """Create SSL context for secure WebSocket (WSS).

    Args:
        cert_file: Path to certificate file (PEM format)
        key_file: Path to private key file (PEM format)
        ca_file: Path to CA file for client verification
        verify_client: Whether to verify client certificates
        cert_reqs: Certificate requirements (ssl.CERT_NONE, CERT_OPTIONAL, CERT_REQUIRED)

    Returns:
        Configured SSL context

    Raises:
        FileNotFoundError: If cert or key files don't exist
        ssl.SSLError: If SSL context creation fails

    Example:
        >>> ssl_context = create_ssl_context(
        ...     cert_file="/path/to/cert.pem",
        ...     key_file="/path/to/key.pem"
        ... )
        >>> # Use with websockets.serve(ssl=ssl_context)
    """
    cert_path = Path(cert_file) if cert_file else None
    key_path = Path(key_file) if key_file else None

    # Create SSL context
    ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)

    # Load certificate and key if provided
    if cert_path and key_path:
        if not cert_path.exists():
            raise FileNotFoundError(f"Certificate file not found: {cert_path}")
        if not key_path.exists():
            raise FileNotFoundError(f"Key file not found: {key_path}")

        ssl_context.load_cert_chain(str(cert_path), str(key_path))
        logger.info(f"Loaded SSL certificate: {cert_path}")

    # Set certificate verification mode
    if verify_client or ca_file:
        ssl_context.verify_mode = cert_reqs if cert_reqs != ssl.CERT_NONE else ssl.CERT_REQUIRED

        # Load CA for client verification
        if ca_file:
            ca_path = Path(ca_file)
            if not ca_path.exists():
                raise FileNotFoundError(f"CA file not found: {ca_path}")
            ssl_context.load_verify_locations(str(ca_path))
            logger.info(f"Loaded CA certificate for client verification: {ca_path}")

    # Set secure cipher suites (TLS 1.2+)
    ssl_context.set_ciphers(
        'ECDHE-ECDSA-AES128-GCM-SHA256:'
        'ECDHE-RSA-AES128-GCM-SHA256:'
        'ECDHE-ECDSA-AES256-GCM-SHA384:'
        'ECDHE-RSA-AES256-GCM-SHA384:'
        'ECDHE-ECDSA-CHACHA20-POLY1305:'
        'ECDHE-RSA-CHACHA20-POLY1305'
    )

    # Set minimum TLS version to 1.2
    ssl_context.minimum_version = ssl.TLSVersion.TLSv1_2

    # Set ECDH curve for forward secrecy
    try:
        ssl_context.set_ecdh_curve('prime256v1')
    except (ssl.SSLError, AttributeError) as e:
        logger.debug(f"Could not set ECDH curve: {e}")

    return ssl_context


def get_tls_config_from_env(
    prefix: str = "WEBSOCKET",
) -> dict[str, str | bool | None]:
    """Get TLS configuration from environment variables.

    Environment variables:
        {prefix}_TLS_ENABLED: Enable TLS ("true" or "false")
        {prefix}_CERT_FILE: Path to certificate file
        {prefix}_KEY_FILE: Path to private key file
        {prefix}_CA_FILE: Path to CA file (optional)
        {prefix}_VERIFY_CLIENT: Verify client certificates ("true" or "false")

    Args:
        prefix: Environment variable prefix (default: "WEBSOCKET")

    Returns:
        Dictionary with TLS configuration

    Example:
        >>> config = get_tls_config_from_env("MAHAVISHNU")
        >>> print(config)
        {'tls_enabled': True, 'cert_file': '/path/to/cert.pem', ...}
    """
    return {
        "tls_enabled": os.getenv(f"{prefix}_TLS_ENABLED", "false").lower() == "true",
        "cert_file": os.getenv(f"{prefix}_CERT_FILE"),
        "key_file": os.getenv(f"{prefix}_KEY_FILE"),
        "ca_file": os.getenv(f"{prefix}_CA_FILE"),
        "verify_client": os.getenv(f"{prefix}_VERIFY_CLIENT", "false").lower() == "true",
    }


def create_development_ssl_context(
    common_name: str = "localhost",
    dns_names: list[str] | None = None,
) -> tuple[ssl.SSLContext, str, str]:
    """Create SSL context with auto-generated self-signed certificate.

    This is a convenience function for development that generates a temporary
    self-signed certificate and creates an SSL context from it.

    Args:
        common_name: Common name for the certificate
        dns_names: Additional DNS names for SAN

    Returns:
        Tuple of (ssl_context, cert_file_path, key_file_path)

    Note:
        The certificate files are temporary and will be deleted on program exit.
        For production, use proper certificates with create_ssl_context().

    Example:
        >>> ctx, cert, key = create_development_ssl_context("localhost")
        >>> # Use ctx with websockets.serve(ssl=ctx)
    """
    cert_path, key_path = generate_self_signed_cert(
        common_name=common_name,
        dns_names=dns_names,
        valid_days=365,
    )

    ssl_context = create_ssl_context(
        cert_file=cert_path,
        key_file=key_path,
    )

    logger.info(
        f"Created development SSL context with self-signed cert "
        f"(CN={common_name}, cert={cert_path})"
    )

    return ssl_context, cert_path, key_path


def validate_certificate(
    cert_file: str | Path,
    check_expiry: bool = True,
    min_days_remaining: int = 30,
) -> dict[str, Any]:
    """Validate a certificate file and check its properties.

    Args:
        cert_file: Path to certificate file
        check_expiry: Check if certificate is expired or expiring soon
        min_days_remaining: Minimum days before expiration warning

    Returns:
        Dictionary with validation results

    Example:
        >>> result = validate_certificate("/path/to/cert.pem")
        >>> if not result["valid"]:
        ...     print(f"Certificate invalid: {result['error']}")
    """
    cert_path = Path(cert_file)
    result: dict[str, Any] = {
        "valid": False,
        "expired": False,
        "expiring_soon": False,
        "subject": None,
        "issuer": None,
        "not_valid_before": None,
        "not_valid_after": None,
        "days_remaining": None,
        "error": None,
    }

    try:
        # Load certificate
        with open(cert_path, "rb") as f:
            cert_data = f.read()
            cert = x509.load_pem_x509_certificate(cert_data, default_backend())

        # Extract certificate info
        result["subject"] = cert.subject.rfc4514_string()
        result["issuer"] = cert.issuer.rfc4514_string()
        result["not_valid_before"] = cert.not_valid_before.isoformat()
        result["not_valid_after"] = cert.not_valid_after.isoformat()

        # Check expiration
        now = datetime.now(UTC)
        expiry = cert.not_valid_after.replace(tzinfo=None)

        if now > cert.not_valid_after:
            result["expired"] = True
            result["valid"] = False
            result["error"] = "Certificate has expired"
        elif check_expiry:
            days_remaining = (expiry - now.replace(tzinfo=None)).days
            result["days_remaining"] = days_remaining

            if days_remaining < min_days_remaining:
                result["expiring_soon"] = True
                result["error"] = f"Certificate expires in {days_remaining} days"

        # Certificate is valid
        if not result["expired"] and not result["expiring_soon"]:
            result["valid"] = True

    except FileNotFoundError:
        result["error"] = f"Certificate file not found: {cert_path}"
    except Exception as e:
        result["error"] = f"Failed to validate certificate: {e}"

    return result
