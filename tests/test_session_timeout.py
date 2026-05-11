"""Session timeout & expiry helper tests."""
from __future__ import annotations

from datetime import timedelta

from freezegun import freeze_time

from app.utils.timeouts import expires_at, is_expired, utcnow


def test_is_expired_true_after_ttl_elapses():
    with freeze_time("2026-01-01 00:00:00"):
        deadline = expires_at(180)
    with freeze_time("2026-01-01 00:03:01"):
        assert is_expired(deadline) is True


def test_is_expired_false_within_ttl():
    with freeze_time("2026-01-01 00:00:00"):
        deadline = expires_at(180)
    with freeze_time("2026-01-01 00:02:59"):
        assert is_expired(deadline) is False


def test_is_expired_handles_naive_timestamp_as_utc():
    naive = (utcnow() - timedelta(seconds=300)).replace(tzinfo=None)
    assert is_expired(naive) is True


def test_callback_message_expiry_check_uses_180s():
    """The callback dispatcher considers a message expired after 180s."""
    from app.commands.callbacks import _is_message_expired

    with freeze_time("2026-01-01 00:00:00"):
        now_unix = int(utcnow().timestamp())

    with freeze_time("2026-01-01 00:02:59"):
        assert _is_message_expired(now_unix) is False
    with freeze_time("2026-01-01 00:03:01"):
        assert _is_message_expired(now_unix) is True
