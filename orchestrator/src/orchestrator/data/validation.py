"""Data and identity validation utilities."""

import re

USER_ID_REGEX = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")


def validate_user_id(user_id: str) -> str:
    """Validates and sanitizes user_id against directory traversal and invalid characters.

    Enforces safe identifier charset ^[a-zA-Z0-9_-]{1,64}$ to prevent BOLA, IDOR,
    and Firestore document path traversal attacks (SEC-02, SEC-06).
    """
    if not isinstance(user_id, str):
        raise ValueError(f"user_id must be a string, got {type(user_id).__name__}")
    trimmed = user_id.strip()
    if not trimmed or not USER_ID_REGEX.match(trimmed):
        raise ValueError(f"Invalid user_id format: {user_id!r}. Must match ^[a-zA-Z0-9_-]{{1,64}}$")
    return trimmed
