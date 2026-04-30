import pytest
from mcp_common.auth.identity import KNOWN_SERVICES, verify_issuer, verify_audience
from mcp_common.auth.exceptions import UnknownIssuerError, AudienceMismatchError


def test_known_services_contains_all_bodai():
    expected = {"mahavishnu", "session-buddy", "akosha", "dhara", "crackerjack"}
    assert expected.issubset(KNOWN_SERVICES)


def test_verify_issuer_passes_for_known_service():
    verify_issuer("mahavishnu")  # should not raise


def test_verify_issuer_raises_for_unknown():
    with pytest.raises(UnknownIssuerError, match="fastblocks"):
        verify_issuer("fastblocks")


def test_verify_audience_passes_when_matches():
    verify_audience(claimed="session-buddy", expected="session-buddy")  # should not raise


def test_verify_audience_raises_when_mismatch():
    with pytest.raises(AudienceMismatchError):
        verify_audience(claimed="akosha", expected="session-buddy")
