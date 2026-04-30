import pytest
from mcp_common.auth.permissions import Permission, Role, ROLE_PERMISSIONS


def test_permission_values():
    assert Permission.READ.value == "read"
    assert Permission.WRITE.value == "write"
    assert Permission.DELETE.value == "delete"
    assert Permission.ADMIN.value == "admin"


def test_role_reader_has_only_read():
    reader = ROLE_PERMISSIONS["reader"]
    assert Permission.READ in reader
    assert Permission.WRITE not in reader
    assert Permission.DELETE not in reader
    assert Permission.ADMIN not in reader


def test_role_operator_has_read_and_write():
    operator = ROLE_PERMISSIONS["operator"]
    assert Permission.READ in operator
    assert Permission.WRITE in operator
    assert Permission.DELETE not in operator
    assert Permission.ADMIN not in operator


def test_role_admin_has_all_permissions():
    admin = ROLE_PERMISSIONS["admin"]
    for perm in Permission:
        assert perm in admin


def test_permission_from_string():
    assert Permission("read") == Permission.READ
    assert Permission("admin") == Permission.ADMIN


def test_invalid_permission_raises():
    with pytest.raises(ValueError):
        Permission("superuser")
