# -*- coding: utf-8 -*-

"""
ExaCheck - ExaBGP Health Checker

Tests for the metric_down feature: when a health check fails, instead of
withdrawing routes completely, re-advertise them at the configured down metric.
Restoring service re-announces them at the normal metric.
"""

from datetime import datetime
from unittest.mock import MagicMock

import pytest
from loguru import logger

from exacheck.checkresult import CheckResult
from exacheck.checkstate import CheckState
from exacheck.settings.check import Check
from exacheck.worker import Worker


def _check(metric=100, metric_down=200, rise=2, fall=2):
    return Check(
        name="t",
        prefixes=["192.0.2.1/32"],
        nexthop="192.0.2.1",
        metric=metric,
        metric_down=metric_down,
        rise=rise,
        fall=fall,
        args={"method": "tcp", "host": "192.0.2.1", "port": 80},
    )


def _worker(check):
    """Construct a Worker without running its check loop."""
    worker = Worker.__new__(Worker)
    worker.log = logger.bind(check_name=check.name, subsystem="worker")
    worker.check = check
    worker.notifications = MagicMock()
    worker.announcer = MagicMock()
    worker.check_state = CheckState(state="startup", advertised=False, current_metric=None)
    worker.check_method = check.args.method
    return worker


def _ok():
    return CheckResult(success=True, message="ok")


def _bad():
    return CheckResult(success=False, message="bad")


def test_fall_with_metric_down_degrades_instead_of_withdrawing():
    worker = _worker(_check(metric=100, metric_down=200, fall=2))
    # Start in "up" state — simulate the worker having already risen
    worker.check_state = CheckState(
        state="up", advertised=True, current_metric=100, up_since=datetime.now()
    )

    # First failure: still falling, no announcer call yet
    worker.failure(_bad())
    assert worker.check_state.state == "falling"
    assert worker.check_state.advertised is True
    assert worker.check_state.current_metric == 100
    worker.announcer.announce.assert_not_called()
    worker.announcer.withdraw.assert_not_called()

    # Second failure: crosses fall threshold. Should DEGRADE, not withdraw.
    worker.failure(_bad())
    assert worker.check_state.state == "down"
    assert worker.check_state.advertised is True
    assert worker.check_state.current_metric == 200
    worker.announcer.announce.assert_called_once_with(metric=200)
    worker.announcer.withdraw.assert_not_called()


def test_fall_without_metric_down_still_withdraws():
    worker = _worker(_check(metric=100, metric_down=None, fall=1))
    worker.check_state = CheckState(
        state="up", advertised=True, current_metric=100, up_since=datetime.now()
    )

    worker.failure(_bad())
    assert worker.check_state.state == "down"
    assert worker.check_state.advertised is False
    assert worker.check_state.current_metric is None
    worker.announcer.withdraw.assert_called_once()
    worker.announcer.announce.assert_not_called()


def test_rise_from_degraded_restores_normal_metric():
    worker = _worker(_check(metric=100, metric_down=200, rise=2))
    # Start in degraded state
    worker.check_state = CheckState(
        state="down",
        advertised=True,
        current_metric=200,
        down_since=datetime.now(),
    )

    # First success: rising, no re-announce yet
    worker.success(_ok())
    assert worker.check_state.state == "rising"
    assert worker.check_state.advertised is True
    assert worker.check_state.current_metric == 200
    worker.announcer.announce.assert_not_called()

    # Second success: crosses rise threshold, re-announce at normal metric
    worker.success(_ok())
    assert worker.check_state.state == "up"
    assert worker.check_state.advertised is True
    assert worker.check_state.current_metric == 100
    worker.announcer.announce.assert_called_once_with(metric=100)


def test_repeated_failures_in_degraded_state_no_extra_announces():
    worker = _worker(_check(metric=100, metric_down=200, fall=1))
    worker.check_state = CheckState(
        state="down",
        advertised=True,
        current_metric=200,
        down_since=datetime.now(),
    )

    worker.failure(_bad())
    worker.failure(_bad())
    worker.failure(_bad())
    # Already in terminal "down" state — no announces or withdraws should fire
    worker.announcer.announce.assert_not_called()
    worker.announcer.withdraw.assert_not_called()
    assert worker.check_state.state == "down"
    assert worker.check_state.advertised is True
    assert worker.check_state.current_metric == 200


def test_disable_file_fully_withdraws_even_when_degraded():
    worker = _worker(_check(metric=100, metric_down=200))
    worker.check_state = CheckState(
        state="down",
        advertised=True,
        current_metric=200,
        down_since=datetime.now(),
    )

    # Simulate a disabled result
    result = CheckResult(success=False, message="disabled", disabled=True)
    worker.failure(result)
    assert worker.check_state.state == "disabled"
    assert worker.check_state.advertised is False
    assert worker.check_state.current_metric is None
    worker.announcer.withdraw.assert_called_once()
