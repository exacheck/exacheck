# -*- coding: utf-8 -*-

"""
ExaCheck - ExaBGP Health Checker

Tests for the configuration reload behaviour: content-hash based change
detection, the field-level diff classifier that decides between a worker
restart and an in-place update, and the worker's in-place config apply.
"""

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from loguru import logger

from exacheck import worker as worker_module
from exacheck.checkstate import CheckState
from exacheck.configuration import Configuration
from exacheck.exacheck import ExaCheck, _OPERATIONAL_FIELDS, _ROUTE_FIELDS
from exacheck.notifications import Notifications
from exacheck.settings.check import Check
from exacheck.settings.notifications import Notifications as NotificationSettings
from exacheck.worker import NotificationsUpdate, Worker


@pytest.fixture
def mock_announcer(monkeypatch):
    """Replace Announcer in the worker module with a mock-returning factory.

    Worker._apply_new_config constructs a fresh Announcer, so the announcer
    mock on the helper-built worker would be discarded. This fixture lets the
    test inspect calls on the *latest* Announcer instance.
    """
    instances = []

    class _MockAnnouncer:
        def __init__(self, *args, **kwargs):
            self.announce = MagicMock()
            self.withdraw = MagicMock()
            instances.append(self)

    monkeypatch.setattr(worker_module, "Announcer", _MockAnnouncer)
    return instances


# ----- helpers -----------------------------------------------------------------


def _check(name="t", metric=100, metric_down=None, prefixes=None, **overrides):
    base = dict(
        name=name,
        prefixes=prefixes or ["192.0.2.1/32"],
        nexthop="192.0.2.1",
        metric=metric,
        metric_down=metric_down,
        args={"method": "tcp", "host": "192.0.2.1", "port": 80},
    )
    base.update(overrides)
    return Check(**base)


def _worker(check, config_queue=None):
    """Construct a Worker for inspection (does not run the loop)."""
    worker = Worker(check, MagicMock(), config_queue)
    worker.announcer = MagicMock()
    return worker


# ----- field-level diff classifier --------------------------------------------


def test_classify_description_change_is_cosmetic():
    old = _check(description="before")
    new = _check(description="after")
    op, rt = ExaCheck._classify_check_change(old, new)
    assert (op, rt) == (False, False)


def test_classify_metric_change_is_route_only():
    op, rt = ExaCheck._classify_check_change(_check(metric=100), _check(metric=200))
    assert (op, rt) == (False, True)


def test_classify_metric_down_change_is_route_only():
    op, rt = ExaCheck._classify_check_change(
        _check(metric_down=None), _check(metric_down=300)
    )
    assert (op, rt) == (False, True)


def test_classify_interval_change_is_operational():
    op, rt = ExaCheck._classify_check_change(_check(interval=5), _check(interval=15))
    assert op is True


def test_classify_args_change_is_operational():
    old = Check(
        name="t",
        prefixes=["192.0.2.1/32"],
        nexthop="192.0.2.1",
        args={"method": "tcp", "host": "192.0.2.1", "port": 80},
    )
    new = Check(
        name="t",
        prefixes=["192.0.2.1/32"],
        nexthop="192.0.2.1",
        args={"method": "tcp", "host": "192.0.2.1", "port": 81},
    )
    op, _ = ExaCheck._classify_check_change(old, new)
    assert op is True


def test_classify_field_sets_are_disjoint_and_complete():
    """All non-cosmetic Check fields belong to exactly one bucket."""
    cosmetic = {"name", "description"}
    classified = set(_OPERATIONAL_FIELDS) | set(_ROUTE_FIELDS)
    assert set(_OPERATIONAL_FIELDS).isdisjoint(_ROUTE_FIELDS)
    all_fields = set(Check.model_fields.keys())
    assert all_fields == classified | cosmetic, (
        f"Unclassified Check fields: {all_fields - classified - cosmetic}"
    )


# ----- worker in-place apply --------------------------------------------------


def test_apply_new_config_reannounces_when_up(mock_announcer):
    worker = _worker(_check(metric=100))
    worker.check_state = CheckState(
        state="up", advertised=True, current_metric=100, up_since=datetime.now()
    )
    new = _check(metric=150)
    worker._apply_new_config(new)
    # The Announcer is rebuilt inside _apply_new_config, so we look at the
    # most recently constructed mock.
    mock_announcer[-1].announce.assert_called_once_with(metric=150)
    assert worker.check_state.current_metric == 150
    assert worker.check_state.state == "up"
    assert worker.check_state.advertised is True


def test_apply_new_config_uses_metric_down_when_degraded(mock_announcer):
    worker = _worker(_check(metric=100, metric_down=200))
    worker.check_state = CheckState(
        state="down",
        advertised=True,
        current_metric=200,
        down_since=datetime.now(),
    )
    new = _check(metric=100, metric_down=250)
    worker._apply_new_config(new)
    mock_announcer[-1].announce.assert_called_once_with(metric=250)
    assert worker.check_state.current_metric == 250
    assert worker.check_state.state == "down"


def test_apply_new_config_withdraws_when_metric_down_removed(mock_announcer):
    worker = _worker(_check(metric=100, metric_down=200))
    worker.check_state = CheckState(
        state="down",
        advertised=True,
        current_metric=200,
        down_since=datetime.now(),
    )
    new = _check(metric=100, metric_down=None)
    worker._apply_new_config(new)
    mock_announcer[-1].withdraw.assert_called_once()
    mock_announcer[-1].announce.assert_not_called()
    assert worker.check_state.advertised is False
    assert worker.check_state.current_metric is None


def test_apply_new_config_skips_emit_when_not_advertised(mock_announcer):
    worker = _worker(_check(metric=100))
    worker.check_state = CheckState(
        state="down", advertised=False, current_metric=None
    )
    worker._apply_new_config(_check(metric=150))
    mock_announcer[-1].announce.assert_not_called()
    mock_announcer[-1].withdraw.assert_not_called()


def test_apply_new_config_preserves_rise_fall_counters():
    """In-place update must NOT reset rise/fall — the whole point is no churn."""
    worker = _worker(_check(metric=100))
    worker.check_state = CheckState(
        state="rising",
        advertised=False,
        current_metric=None,
        rise=2,
        down_since=datetime.now(),
    )
    worker._apply_new_config(_check(metric=100, metric_down=300))
    # Not advertised, no announce call, and rise count preserved on the state
    # held by the worker (which is still the pre-update state because we
    # short-circuit when not advertised).
    assert worker.check_state.rise == 2


# ----- worker queue draining --------------------------------------------------


def test_drain_pending_config_applies_only_latest(mock_announcer):
    """If multiple updates queue up, only the most recent should be applied."""
    queue = MagicMock()
    from queue import Empty
    items = iter([_check(metric=110), _check(metric=120), _check(metric=130)])

    def side_effect():
        try:
            return next(items)
        except StopIteration:
            raise Empty

    queue.get_nowait.side_effect = side_effect

    worker = _worker(_check(metric=100), config_queue=queue)
    worker.check_state = CheckState(
        state="up", advertised=True, current_metric=100, up_since=datetime.now()
    )
    worker._drain_pending_config()
    # Only the last update should have driven the announce
    mock_announcer[-1].announce.assert_called_once_with(metric=130)


def test_drain_pending_config_noop_when_queue_is_none():
    worker = _worker(_check(metric=100), config_queue=None)
    worker._drain_pending_config()
    worker.announcer.announce.assert_not_called()


# ----- configuration content-hash polling -------------------------------------


def test_is_modified_detects_content_change(tmp_path: Path):
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "checks:\n"
        "  - name: t\n"
        "    prefixes: [192.0.2.1/32]\n"
        "    nexthop: 192.0.2.1\n"
        "    args: {method: tcp, host: 192.0.2.1, port: 80}\n"
    )
    config = Configuration(log_context=logger.bind(check_name="t"), file=config_path)

    # Same content, no change
    assert config.is_modified() is False

    # Touching the file changes mtime but not content — should not report modified
    import os, time
    new_time = time.time() + 100
    os.utime(config_path, (new_time, new_time))
    assert config.is_modified() is False

    # Actually changing content should report modified
    config_path.write_text(config_path.read_text() + "\n# comment added\n")
    assert config.is_modified() is True


def test_load_file_dispatches_yaml_and_json(tmp_path: Path):
    """The parser dispatch table must handle both formats."""
    yaml_cfg = tmp_path / "config.yaml"
    yaml_cfg.write_text(
        "checks:\n"
        "  - name: t\n"
        "    prefixes: [192.0.2.1/32]\n"
        "    nexthop: 192.0.2.1\n"
        "    args: {method: tcp, host: 192.0.2.1, port: 80}\n"
    )
    json_cfg = tmp_path / "config.json"
    json_cfg.write_text(
        '{"checks": [{"name": "t", "prefixes": ["192.0.2.1/32"], '
        '"nexthop": "192.0.2.1", "args": {"method": "tcp", '
        '"host": "192.0.2.1", "port": 80}}]}'
    )

    yaml_loaded = Configuration(log_context=logger.bind(check_name="t"), file=yaml_cfg)
    json_loaded = Configuration(log_context=logger.bind(check_name="t"), file=json_cfg)
    # Both should parse to the equivalent settings (same checks)
    assert yaml_loaded.settings.checks[0].name == "t"
    assert json_loaded.settings.checks[0].name == "t"
    assert yaml_loaded.settings.checks[0].prefixes == json_loaded.settings.checks[0].prefixes


def test_load_file_uppercase_extension(tmp_path: Path):
    """Extension matching must be case-insensitive."""
    cfg = tmp_path / "config.YAML"
    cfg.write_text(
        "checks:\n"
        "  - name: t\n"
        "    prefixes: [192.0.2.1/32]\n"
        "    nexthop: 192.0.2.1\n"
        "    args: {method: tcp, host: 192.0.2.1, port: 80}\n"
    )
    loaded = Configuration(log_context=logger.bind(check_name="t"), file=cfg)
    assert loaded.settings.checks[0].name == "t"


def test_load_file_unsupported_extension_exits(tmp_path: Path):
    """An unsupported extension must raise SystemExit (no partial state)."""
    cfg = tmp_path / "config.toml"
    cfg.write_text("[checks]\nname = 't'\n")
    with pytest.raises(SystemExit):
        Configuration(log_context=logger.bind(check_name="t"), file=cfg)


def test_reload_failure_does_not_hotloop_on_same_broken_bytes(tmp_path: Path):
    """After a failed reload, is_modified() should return False on the same bytes."""
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "checks:\n"
        "  - name: t\n"
        "    prefixes: [192.0.2.1/32]\n"
        "    nexthop: 192.0.2.1\n"
        "    args: {method: tcp, host: 192.0.2.1, port: 80}\n"
    )
    config = Configuration(log_context=logger.bind(check_name="t"), file=config_path)

    # Break the file
    config_path.write_text("this: is: not: valid: yaml: at: all:\n")
    assert config.is_modified() is True
    assert config.reload() is False
    # Next poll on the SAME broken bytes should NOT report modified — content
    # hash now matches what we just rejected.
    assert config.is_modified() is False


# ----- in-place notifications config update -----------------------------------


def test_apply_new_notifications_drains_old_and_replaces():
    worker = _worker(_check())
    old_notifications = worker.notifications  # MagicMock from the helper

    worker._apply_new_notifications(None)  # noop config

    # Old object was shut down (drained) before being dropped
    old_notifications.shutdown.assert_called_once_with(timeout=3)
    # And replaced with a fresh, real Notifications instance
    assert worker.notifications is not old_notifications
    assert isinstance(worker.notifications, Notifications)
    # No configuration → noop
    assert worker.notifications.noop is True


def test_apply_new_notifications_with_real_config():
    worker = _worker(_check())
    new_config = [
        NotificationSettings(
            name="t",
            url="json://example.com",
            events=["announce", "withdraw", "info", "error"],
        )
    ]
    worker._apply_new_notifications(new_config)
    assert worker.notifications.noop is False
    # The new Apprise instance has one configured target
    assert len(worker.notifications.apprise) == 1
    worker.notifications.shutdown(timeout=1)


def test_drain_dispatches_check_and_notifications_messages(mock_announcer):
    """Both message types on the queue should be applied correctly."""
    from queue import Empty
    queue = MagicMock()
    new_check = _check(metric=200)
    notifications_msg = NotificationsUpdate(configuration=None)
    items = iter([notifications_msg, new_check])

    def side_effect():
        try:
            return next(items)
        except StopIteration:
            raise Empty

    queue.get_nowait.side_effect = side_effect

    worker = _worker(_check(metric=100), config_queue=queue)
    old_notifications = worker.notifications
    worker.check_state = CheckState(
        state="up", advertised=True, current_metric=100, up_since=datetime.now()
    )
    worker._drain_pending_config()

    # Notifications were rebuilt
    old_notifications.shutdown.assert_called_once_with(timeout=3)
    assert worker.notifications is not old_notifications
    # Check was applied (route re-announce at metric 200)
    mock_announcer[-1].announce.assert_called_once_with(metric=200)
    assert worker.check.metric == 200


def test_drain_ignores_unknown_message_types(mock_announcer):
    """An unrecognised queue payload should log a warning and be ignored."""
    from queue import Empty
    queue = MagicMock()
    items = iter(["this is not a Check or NotificationsUpdate"])

    def side_effect():
        try:
            return next(items)
        except StopIteration:
            raise Empty

    queue.get_nowait.side_effect = side_effect

    worker = _worker(_check(), config_queue=queue)
    worker.check_state = CheckState(
        state="up", advertised=True, current_metric=100, up_since=datetime.now()
    )
    # Should not raise — unknown messages are logged and discarded.
    worker._drain_pending_config()
    # No announce, no withdraw, no notifications rebuild
    mock_announcer[-1].announce.assert_not_called()
    mock_announcer[-1].withdraw.assert_not_called()
