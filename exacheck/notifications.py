# -*- coding: utf-8 -*-

"""
ExaCheck - ExaBGP Health Checker

Configure and manage notifications/alerting with Apprise
"""

from __future__ import annotations

import queue as _queue
import threading
from os import getpid
from typing import Any, Optional

import apprise
import loguru

from .settings.notifications import Notifications as NotificationSettings


class Notifications:
    """
    Set up Apprise notifications and manage the sending of notifications.

    Notifications are dispatched asynchronously: ``notify`` enqueues a spec
    and returns immediately, while a background thread reads from the queue
    and performs the actual Apprise send. This keeps slow notification
    backends (e.g. an unresponsive Slack webhook) from stalling the worker
    check loop. Callers should invoke :meth:`shutdown` during graceful
    process exit to drain pending notifications before the process dies.
    """

    def __init__(
        self,
        log_context: loguru.Logger,
        configuration: Optional[list[NotificationSettings]] = None,
    ):
        """
        Set up Apprise
        """

        # Set the logging context
        self.log = log_context.bind(subsystem="notification")

        # Async send infrastructure. The thread is created lazily on first
        # use because this object is forked into worker processes, and
        # threads do not survive fork() — each process needs its own.
        self._queue: _queue.Queue[Optional[dict[str, Any]]] = _queue.Queue()
        self._thread: Optional[threading.Thread] = None
        self._thread_pid: Optional[int] = None

        # Check if there is no configuration
        if not configuration:
            # Set noop flag and shortcut setup
            self.noop = True

            # Log shortcut
            self.log.bind(event="debug").debug(
                "No notification configuration defined; skipping setup"
            )

            # Return early
            return

        # Unset noop flag
        self.noop = False

        # Log setup
        self.log.bind(event="debug").debug("Setting up Apprise notification handlers")

        # Perform setup
        self._setup(configuration=configuration)

        # Map event names to Apprise notification levels
        self._types = {
            "announce": apprise.NotifyType.SUCCESS,
            "withdraw": apprise.NotifyType.WARNING,
            "error": apprise.NotifyType.FAILURE,
            "info": apprise.NotifyType.INFO,
        }

    def _setup(self, configuration: list[NotificationSettings]):
        """
        Set up Apprise
        """

        # Create the Apprise asset
        asset = apprise.AppriseAsset(
            app_id="ExaCheck",
            app_desc="ExaCheck - ExaBGP Health Checker",
            app_url="https://exacheck.net",
        )

        # Create Apprise object
        self.apprise = apprise.Apprise(
            asset=asset,
        )

        # Loop over each notification target defined in the configuration file
        for target in configuration:
            # Log setup
            self.log.bind(event="debug").debug(
                "Configuring notification target {name}",
                name=target.name,
            )
            self.log.bind(event="debug").trace(
                "Notification URL: {url}",
                url=target.url,
            )
            self.log.bind(event="debug").trace(
                "Notification target is configured for the following events: {events}",
                events=", ".join(target.events),
            )

            # Check if the target has a list of checks to notify on.
            # Bind to a local so the type narrows from Optional[list[str]] to
            # list[str] for the duration of the branch.
            target_checks = target.checks
            if target_checks:
                # Log there is filtering
                self.log.bind(event="debug").trace(
                    "Notification target will be filtered to the following checks: {checks}",
                    checks=", ".join(target_checks),
                )

                # Create the list of tags for filtering to work
                tags = [
                    f"{check}-{event}"
                    for event in target.events
                    for check in target_checks
                ]

            else:
                # Log there is no filtering
                self.log.bind(event="debug").trace(
                    "Notification target will be used for all checks as no filter is defined",
                )

                # There is no filtering for checks, use the special check name "_all_"
                tags = [f"_all_-{event}" for event in target.events]

            # Check if general events should be logged
            if target.general_events:
                tags = tags + [f"_general_-{event}" for event in target.events]

            # Log tags
            self.log.bind(event="debug").trace(
                "Notification tags: {tags}",
                tags=", ".join(tags),
            )

            # Register the target URL with the tags. Apprise.add returns a
            # bool — False on most validation failures (no exception raised).
            # We check both paths so silent rejections don't masquerade as
            # successful registrations.
            try:
                added = self.apprise.add(str(target.url), tag=tags)
            except Exception as exc:  # pylint: disable=broad-except
                self.log.bind(event="error").error(
                    "Failed to configure notification target {name} with URL {url}; skipping: {error}",
                    name=target.name,
                    url=target.url,
                    error=exc,
                )
                continue
            if not added:
                self.log.bind(event="error").error(
                    "Apprise rejected notification target {name} with URL {url}; "
                    "notifications will not be sent to this target",
                    name=target.name,
                    url=target.url,
                )

    def notify(
        self,
        event: str,
        message: str,
        title: str = "ExaCheck Event",
        check: Optional[str] = None,
        log_context: Optional[loguru.Logger] = None,
    ):
        """
        Enqueue a notification for asynchronous delivery.

        Returns immediately; the actual Apprise send happens on the
        background thread. Use :meth:`shutdown` during graceful process
        exit to drain queued notifications.

        Args:
            event (str): The event type
            title (str): The optional title for the notification
            message (str): The message to send
        """
        # If there is a log context, bind it
        if log_context:
            log = log_context.bind(subsystem="notification")
        else:
            log = self.log

        # If there is no notification configuration, return early
        if self.noop:
            if check:
                log.bind(event="debug").trace(
                    "Notification from check {check} of type {event} will be ignored as there is no notifications configured",
                    check=check,
                    event=event,
                )
            else:
                log.bind(event="debug").trace(
                    "General notification of type {event} will be ignored as there is no notifications configured",
                    event=event,
                )
            return

        # Create the tags for the notification
        if check:
            tags = [f"{check}-{event}", f"_all_-{event}"]
        else:
            tags = [f"_general_-{event}"]

        # Map the event name to its Apprise notification level
        notification_type = self._types.get(event, apprise.NotifyType.INFO)

        log.bind(event="debug").debug(
            "Queueing notification with tags {tags}",
            tags=", ".join(tags),
        )
        log.bind(event="datadump").trace(
            "Notification title: {title}",
            title=title,
        )
        log.bind(event="datadump").trace(
            "Notification message: {message}",
            message=message,
        )

        # Make sure a sender thread exists for this process (lazy on first
        # call, reset after fork()).
        self._ensure_thread()

        self._queue.put(
            {
                "title": title,
                "body": message,
                "tag": tags,
                "notify_type": notification_type,
                "body_format": apprise.NotifyFormat.MARKDOWN,
                # Bound logger captured at enqueue time so the eventual
                # success/failure log retains the caller's check context.
                "_log": log,
            }
        )

    def _ensure_thread(self) -> None:
        """Start the background sender thread for the current process.

        Threads do not survive ``fork``, so the master's thread is invisible
        to forked worker processes. On the first ``notify`` call after a
        fork the PID will not match and a fresh thread + queue is created;
        any items inherited from the parent's queue are discarded since
        they have already been (or will be) sent by the parent.
        """
        pid = getpid()
        if self._thread is not None and self._thread_pid == pid:
            return
        self._queue = _queue.Queue()
        self._thread_pid = pid
        self._thread = threading.Thread(
            target=self._send_loop,
            daemon=True,
            name=f"notifications-{pid}",
        )
        self._thread.start()

    def _send_loop(self) -> None:
        """Background thread loop: pull specs off the queue and send them."""
        while True:
            spec = self._queue.get()
            try:
                if spec is None:
                    # Poison pill — graceful shutdown
                    return
                log = spec.pop("_log")
                try:
                    delivered = self.apprise.notify(**spec)
                except Exception as exc:  # pylint: disable=broad-except
                    log.bind(event="error").error(
                        "Failed to send notification: {error}",
                        error=exc,
                    )
                else:
                    # apprise.notify returns True only if *every* configured
                    # target accepted the notification. False can mean partial
                    # or total failure without a raised exception (e.g. a
                    # webhook returning a non-2xx response).
                    if delivered:
                        log.bind(event="debug").debug("Notification sent")
                    else:
                        log.bind(event="error").error(
                            "One or more notification targets failed to deliver",
                        )
            finally:
                self._queue.task_done()

    def shutdown(self, timeout: float = 5.0) -> None:
        """Drain pending notifications and stop the background thread.

        Best-effort: returns after at most ``timeout`` seconds even if the
        queue is not empty. Safe to call when there is no thread running
        (e.g. on a noop Notifications instance or before any notify call).
        """
        thread = self._thread
        if thread is None or not thread.is_alive():
            return
        self._queue.put(None)
        thread.join(timeout=timeout)
