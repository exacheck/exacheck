# -*- coding: utf-8 -*-

"""
ExaCheck - ExaBGP Health Checker

Tests for worker termination responsiveness: the wakeup-event-driven sleep
and the SIGALRM-based in-progress-check interruption.
"""

import signal
import threading
import time
from unittest.mock import MagicMock

from loguru import logger

from exacheck.checkresult import CheckResult
from exacheck.checkstate import CheckState
from exacheck.settings.check import Check
from exacheck.sleeper import Sleeper
from exacheck.worker import Worker


def _check():
    return Check(
        name="t",
        prefixes=["192.0.2.1/32"],
        nexthop="192.0.2.1",
        args={"method": "tcp", "host": "192.0.2.1", "port": 80},
    )


def _worker(check):
    worker = Worker(check, MagicMock())
    worker.announcer = MagicMock()
    return worker


def test_sleeper_returns_immediately_when_event_already_set():
    event = threading.Event()
    event.set()
    sleeper = Sleeper(
        interval=60,
        log_context=logger.bind(check_name="t"),
        wakeup_event=event,
    )
    sleeper.finish()  # compute sleep_time
    start = time.monotonic()
    sleeper.sleep()
    elapsed = time.monotonic() - start
    assert elapsed < 0.1, f"sleep() blocked for {elapsed:.3f}s with event set"


def test_sleeper_returns_when_event_is_set_during_sleep():
    """The whole point of the wakeup event — break a long sleep on signal."""
    event = threading.Event()
    sleeper = Sleeper(
        interval=60,
        log_context=logger.bind(check_name="t"),
        wakeup_event=event,
    )
    sleeper.finish()

    # Fire the event from another thread after a short delay
    timer = threading.Timer(0.05, event.set)
    timer.start()
    try:
        start = time.monotonic()
        sleeper.sleep()
        elapsed = time.monotonic() - start
    finally:
        timer.cancel()
    # Should return within ~50ms of when the event was set, well under
    # the 60s configured interval.
    assert elapsed < 0.5, f"sleep() did not wake on event set: {elapsed:.3f}s"


def test_sleeper_falls_back_to_time_sleep_without_event():
    """Backwards compatibility — no event means plain time.sleep."""
    sleeper = Sleeper(
        interval=0.05, log_context=logger.bind(check_name="t"), wakeup_event=None
    )
    sleeper.finish()
    start = time.monotonic()
    sleeper.sleep()
    elapsed = time.monotonic() - start
    # Slept approximately the configured interval (a little slack)
    assert elapsed >= 0.04


def test_cleanup_sets_event_and_flag():
    """_cleanup must set both the termination flag and the wakeup event."""
    worker = _worker(_check())
    assert worker._termination_requested is False
    assert worker._termination_event.is_set() is False
    worker._cleanup(15, None)
    assert worker._termination_requested is True
    assert worker._termination_event.is_set() is True


def test_cleanup_does_not_raise_sigalrm_when_no_handler():
    """If SIGALRM is at its default disposition, _cleanup must NOT raise it.

    Otherwise the default-terminate disposition would kill the process —
    including, in tests, pytest itself.
    """
    # The test environment has not installed a SIGALRM handler, so the
    # default is SIG_DFL. Worker._cleanup should detect that and skip the
    # raise_signal call. If it doesn't, this whole test process dies.
    assert signal.getsignal(signal.SIGALRM) is signal.SIG_DFL
    worker = _worker(_check())
    worker._cleanup(15, None)
    # We're still alive, and the flag/event were set
    assert worker._termination_requested is True


def test_cleanup_raises_sigalrm_when_handler_installed():
    """If a SIGALRM handler is installed, _cleanup should fire it."""
    fired = threading.Event()

    def handler(signum, frame):
        fired.set()

    previous = signal.signal(signal.SIGALRM, handler)
    try:
        worker = _worker(_check())
        worker._cleanup(15, None)
        # The handler should have run synchronously as part of the raise
        assert fired.is_set(), "Expected SIGALRM handler to fire"
    finally:
        signal.signal(signal.SIGALRM, previous)


def test_cleanup_is_idempotent_does_not_reraise_sigalrm():
    """A second _cleanup must not raise SIGALRM again.

    Regression: Ctrl-C on a foreground exacheck delivers SIGINT to the
    process group (worker included) and the master then sends SIGTERM via
    ``worker.terminate()``. The first _cleanup raises SIGALRM which raises
    CheckTimeout, which propagates up to a logging call. If the second
    _cleanup also raised SIGALRM, the new CheckTimeout would fire inside
    Loguru's emit() and produce a "Logging error in Loguru Handler"
    traceback. The flag we already set must short-circuit subsequent
    invocations.
    """
    fired_count = [0]

    def handler(signum, frame):
        fired_count[0] += 1

    previous = signal.signal(signal.SIGALRM, handler)
    try:
        worker = _worker(_check())
        worker._cleanup(15, None)
        worker._cleanup(15, None)  # second signal arrives while we're shutting down
        worker._cleanup(2, None)  # and a third (e.g. SIGINT vs SIGTERM)
        assert fired_count[0] == 1, (
            f"Expected SIGALRM to fire exactly once across three "
            f"_cleanup calls, got {fired_count[0]}"
        )
    finally:
        signal.signal(signal.SIGALRM, previous)
