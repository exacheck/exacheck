# -*- coding: utf-8 -*-

"""
ExaCheck - ExaBGP Health Checker

Tests for the asynchronous notification dispatch — `notify` should enqueue
and return immediately, the background thread should deliver, and
`shutdown` should drain and stop.
"""

import threading
import time
from unittest.mock import MagicMock, patch

import pytest
from loguru import logger

from exacheck.notifications import Notifications
from exacheck.settings.notifications import Notifications as NotificationSettings


def _notifications(noop=False, apprise_mock=None):
    """Build a Notifications object with a single fake target."""
    if noop:
        notifications = Notifications(log_context=logger.bind(check_name="t"), configuration=None)
        return notifications

    config = [
        NotificationSettings(
            name="t",
            url="json://example.com",
            events=["announce", "withdraw", "info", "error"],
        )
    ]
    notifications = Notifications(
        log_context=logger.bind(check_name="t"), configuration=config
    )
    if apprise_mock is not None:
        notifications.apprise = apprise_mock
    return notifications


def test_notify_returns_immediately_even_when_send_is_slow():
    """notify() must not block on apprise.notify."""
    block_event = threading.Event()

    def slow_notify(**kwargs):
        # Block for a long time
        block_event.wait(timeout=30)

    fake_apprise = MagicMock()
    fake_apprise.notify.side_effect = slow_notify
    notifications = _notifications(apprise_mock=fake_apprise)

    try:
        start = time.monotonic()
        notifications.notify(event="info", message="hi", title="t")
        elapsed = time.monotonic() - start
        # Should return well under a second — actually closer to 1ms
        assert elapsed < 0.5, f"notify() blocked for {elapsed:.3f}s"
    finally:
        block_event.set()  # let the worker thread complete
        notifications.shutdown(timeout=2)


def test_notify_eventually_calls_apprise():
    fake_apprise = MagicMock()
    notifications = _notifications(apprise_mock=fake_apprise)
    try:
        notifications.notify(event="info", message="payload", title="ttl")
        # Give the background thread time to run
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            if fake_apprise.notify.called:
                break
            time.sleep(0.01)
        assert fake_apprise.notify.called
        call_kwargs = fake_apprise.notify.call_args.kwargs
        assert call_kwargs["title"] == "ttl"
        assert call_kwargs["body"] == "payload"
        # Tags for a general (non-check) info notification
        assert call_kwargs["tag"] == ["_general_-info"]
    finally:
        notifications.shutdown(timeout=2)


def test_exceptions_in_apprise_do_not_kill_the_thread():
    """A failing notification should be logged and the thread keep running."""
    fake_apprise = MagicMock()
    fake_apprise.notify.side_effect = [RuntimeError("boom"), None]
    notifications = _notifications(apprise_mock=fake_apprise)
    try:
        notifications.notify(event="info", message="first", title="t1")
        notifications.notify(event="info", message="second", title="t2")
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            if fake_apprise.notify.call_count >= 2:
                break
            time.sleep(0.01)
        assert fake_apprise.notify.call_count == 2
        # The thread must still be alive (it survived the RuntimeError)
        assert notifications._thread is not None
        assert notifications._thread.is_alive()
    finally:
        notifications.shutdown(timeout=2)


def test_shutdown_drains_pending_notifications():
    sent = []

    def record(**kwargs):
        sent.append(kwargs["title"])

    fake_apprise = MagicMock()
    fake_apprise.notify.side_effect = record
    notifications = _notifications(apprise_mock=fake_apprise)

    for i in range(5):
        notifications.notify(event="info", message="m", title=f"t{i}")
    notifications.shutdown(timeout=5)

    assert sent == [f"t{i}" for i in range(5)]
    assert not notifications._thread.is_alive()


def test_shutdown_is_safe_when_no_thread_was_started():
    """A noop Notifications instance has no thread; shutdown should still work."""
    notifications = _notifications(noop=True)
    # noop: thread was never started
    assert notifications._thread is None
    notifications.shutdown(timeout=1)  # must not raise


def test_noop_notifications_does_not_start_a_thread():
    notifications = _notifications(noop=True)
    notifications.notify(event="info", message="m", title="t")
    assert notifications._thread is None  # never created
