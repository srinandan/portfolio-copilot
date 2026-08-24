"""Unit tests for data and identity validation utilities."""

import pytest

from orchestrator.data.validation import validate_user_id


def test_validate_user_id_valid():
    assert validate_user_id("demo_user") == "demo_user"
    assert validate_user_id("user-123") == "user-123"
    assert validate_user_id("USER_456") == "USER_456"
    assert validate_user_id("a") == "a"
    assert validate_user_id("a" * 64) == "a" * 64
    assert validate_user_id("  trimmed_user  ") == "trimmed_user"


@pytest.mark.parametrize(
    "invalid_id",
    [
        "",
        "   ",
        "../traversal",
        "user/subcollection",
        "user\\backslash",
        "user name",
        "user@example.com",
        "user;drop table",
        "user#hash",
        "user$dollar",
        "a" * 65,
        12345,
        None,
    ],
)
def test_validate_user_id_invalid(invalid_id):
    with pytest.raises(ValueError, match="user_id"):
        validate_user_id(invalid_id)
