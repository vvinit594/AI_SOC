"""Stable identifiers and cookie names for Stage 2 authentication."""

from __future__ import annotations

import uuid

# Historical rows are moved here so the first public registrant never inherits them.
LEGACY_WORKSPACE_ID = uuid.UUID("a15ec000-0000-4000-8000-0000000000ce")
LEGACY_WORKSPACE_NAME = "Legacy data (unassigned)"

SESSION_COOKIE_NAME = "aisoc_session"
CSRF_COOKIE_NAME = "aisoc_csrf"
CSRF_HEADER_NAME = "X-CSRF-Token"

LOGIN_MAX_FAILURES_PER_EMAIL_IP = 5
LOGIN_MAX_FAILURES_PER_IP = 20
LOGIN_WINDOW_SECONDS = 15 * 60
SESSION_TTL_SECONDS_DEFAULT = 12 * 60 * 60
RECOVERY_TTL_SECONDS = 30 * 60
