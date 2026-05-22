# -*- coding: utf-8 -*-

"""
ExaCheck - ExaBGP Health Checker

Health check work class - handles the tasks of running the health check
and announcing or withdrawing routes as needed.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from queue import Empty as QueueEmpty
from signal import (
    SIG_DFL,
    SIG_IGN,
    SIGALRM,
    SIGINT,
    SIGTERM,
    getsignal,
    raise_signal,
    signal,
)
from threading import Event
from typing import Optional
import sys

from loguru import logger

from . import methods
from .announcer import Announcer
from .checkexecutor import CheckExecutor
from .checkresult import CheckResult
from .checkstate import CheckState
from .procname import ProcName
from .settings.check import Check
from .settings.notifications import Notifications as NotificationSettings
from .sleeper import Sleeper
from .notifications import Notifications


@dataclass(frozen=True)
class NotificationsUpdate:
    """IPC envelope: replace the worker's Notifications with this config.

    Pushed onto a worker's config queue by the master when the notifications
    section of the configuration file changes. Without this, a forked worker
    keeps using its pre-fork copy of the Apprise instance and silently
    delivers notifications to the old URLs.
    """

    configuration: Optional[list[NotificationSettings]]


# pylint: disable=too-few-public-methods,too-many-instance-attributes
class Worker:
    """
    The ExaCheck worker process for a health check; the worker will call the checks and handle
    route advertisement/withdrawal as needed.

    The class is intentionally split into ``__init__`` (data setup, side-effect
    free apart from constructing an Announcer) and ``run`` (the process loop,
    which installs signal handlers, sets the process title, and never returns
    normally). The module-level :func:`worker_main` is the multiprocessing
    target — it instantiates a Worker and immediately calls ``run``.
    """

    def __init__(
        self,
        check: Check,
        notifications: Notifications,
        config_queue: Optional[object] = None,
    ):
        """Set up worker state without starting the check loop.

        ``config_queue`` is an optional ``multiprocessing.Queue`` used by the
        master to push in-place Check updates without restarting the worker.
        """
        self.log = logger.bind(check_name=check.name, subsystem="worker")
        self.check: Check = check
        self.notifications = notifications
        self.config_queue = config_queue
        self.announcer = Announcer(check=self.check, log_context=self.log)
        self.check_state = CheckState(
            state="startup",
            advertised=False,
            current_metric=None,
        )
        self.check_method = check.args.method
        # Set to True (and event set) by the signal handler; checked at the
        # top of every iteration of run(). All shutdown I/O happens from the
        # main loop, never from the signal handler itself.
        self._termination_requested = False
        # Used to break Sleeper.sleep() out of its wait when shutdown is
        # requested — time.sleep retries on EINTR (PEP 475) and would
        # otherwise hold the loop for up to a full check interval.
        self._termination_event = Event()
        # procname is created in run() so that constructing a Worker for
        # tests does not mutate the test process's title via setproctitle().
        self.procname: Optional[ProcName] = None

        self.log.bind(event="info").info("ExaCheck worker object created")

    def run(self) -> None:
        """
        Run the health check process loop.

        Never returns under normal operation — exits via ``sys.exit`` inside
        ``_shutdown`` when SIGINT/SIGTERM is received.
        """
        # Process title manager (lives for the life of the process)
        self.procname = ProcName(
            base=f"ExaCheck Worker [{self.check.name}]",
            log_context=self.log,
        )
        # procname stays non-None for the lifetime of run(); the Optional
        # declaration on __init__ exists so tests can construct a Worker
        # without mutating the test process's title via setproctitle.
        assert self.procname is not None
        self.procname.update(message="Startup")

        # Default SIGALRM to a no-op. CheckExecutor swaps in its
        # CheckTimeout-raising handler for the duration of each check and
        # restores SIG_IGN afterwards, so a stray SIGALRM (including the
        # one fired by _cleanup to interrupt an in-progress check) is
        # harmless when no check is actively running.
        signal(SIGALRM, SIG_IGN)

        # Create the check executor
        executor = CheckExecutor(method=self._build_method(), log_context=self.log)

        # Signal handlers only set a flag — actual cleanup runs from the
        # main loop to avoid I/O in signal-handler context.
        signal(SIGINT, self._cleanup)
        signal(SIGTERM, self._cleanup)

        # Start infinite loop
        while True:
            # Honour any pending termination request before doing more work.
            # Calling _shutdown invokes sys.exit which terminates the loop.
            if self._termination_requested:
                self._shutdown()

            # Apply any pending in-place config updates from the master before
            # starting this iteration.
            self._drain_pending_config()

            # Log start of health check
            self.log.bind(event="debug").debug("Health check loop start")

            # Create the sleeper object and start timer. Passing the
            # termination event lets a SIGTERM break the sleep immediately
            # instead of waiting up to a full interval.
            sleeper = Sleeper(
                interval=self.check.interval,
                log_context=self.log,
                wakeup_event=self._termination_event,
            )

            # Update process name
            self.procname.update(
                message="Performing health check",
                status=self._procname_status,
            )

            # Test if the check has a disable file and if that disable file exists
            if self.check.disable and self.check.disable.exists():
                # The disable file exists
                self.log.bind(event="info").info(
                    "Health check is disabled by disable file '{disable_file}'; no health check executing",
                    disable_file=self.check.disable,
                )

                # Create the check result
                result = CheckResult(
                    success=False,
                    message=f"Health check is disabled by disable file '{self.check.disable}'",
                    disabled=True,
                )

                # Call the failure handler
                self._failure(result=result)

            else:
                # Perform the health check
                result = executor.execute()

            # Check the result
            if result.success:
                # Call the success handler
                self._success(result=result)
            else:
                # Call the failure handler
                self._failure(result=result)

            # Finish the sleep timer
            sleeper.finish()

            # Update process name
            self.procname.update(
                message=f"Sleeping for {sleeper.sleep_time:.3f} seconds",
                status=self._procname_status,
            )

            # Sleep for the remaining time
            sleeper.sleep()

    def _build_method(self) -> methods.Base:
        """
        Construct and return a check-method instance for the requested type.

        Allocates a new instance every call, so do not invoke from a hot path.
        ``run()`` calls this exactly once when building the CheckExecutor.
        """
        try:
            cls = methods.get(self.check_method)
        except KeyError as exc:
            self.log.bind(event="error").critical(
                "No health check method '{method}' available",
                method=self.check_method,
            )
            raise NotImplementedError(
                f"Could not get check method: {self.check_method}"
            ) from exc

        return cls(
            log_context=self.log,
            args=self.check.args,
        )

    def _success(self, result: CheckResult) -> None:
        """
        Called when the health check returns a successful status
        """
        # Get existing check state object
        state = self.check_state

        # Already fully up at the normal metric: nothing to do.
        # When metric_down is configured, "advertised" alone is not sufficient
        # — a degraded service is also advertised. The "up" state name is what
        # discriminates a healthy advertisement from a degraded one.
        if state.advertised and state.state == "up":
            self.log.bind(event="debug").info(
                "Health check successful and prefixes are already advertised"
            )
            self.check_state = CheckState(
                state="up",
                advertised=True,
                current_metric=state.current_metric,
                last_result=result,
                up_since=state.up_since,
            )
            return

        # Otherwise the service is either fully down, degraded, rising, or in
        # startup. Increment the rise counter.
        rise = (state.rise or 0) + 1

        # Check if the service has risen
        if rise >= self.check.rise:
            # Re-announce at the normal metric. This call is the same regardless
            # of whether the previous state was fully down (fresh announce) or
            # degraded (re-announce with restored metric); the announcer is
            # idempotent and ExaBGP treats a second announce as an attribute
            # update.
            was_degraded = (
                state.advertised and state.current_metric != self.check.metric
            )
            if was_degraded:
                self.log.bind(event="announce").success(
                    "Health check successful and service has risen; metric will be restored to normal"
                )
            else:
                self.log.bind(event="announce").success(
                    "Health check successful and service has risen; prefixes will be advertised"
                )
            self._announce(restored=was_degraded)
            self.check_state = CheckState(
                state="up",
                advertised=True,
                current_metric=self.check.metric,
                last_result=result,
                up_since=datetime.now(),
            )
            return

        # The service does not meet minimum requirements to rise yet.
        # Preserve the current advertised/metric state — we're only counting
        # successes, not changing what's on the wire.
        self.log.bind(event="info").info(
            "Health check successful but service has not risen yet",
        )
        self.check_state = CheckState(
            state="rising",
            advertised=state.advertised,
            current_metric=state.current_metric,
            last_result=result,
            down_since=state.down_since,
            rise=rise,
        )

    def _failure(self, result: CheckResult) -> None:
        """
        Called when the health check returns a failed status
        """
        # Get existing check state object
        state = self.check_state

        # Check if the failure is due to the service being disabled.
        # A disable file is a manual override — the routes are fully withdrawn
        # regardless of whether metric_down is configured.
        if result.disabled:
            if state.advertised:
                self.log.bind(event="withdraw").warning(
                    "Service has been disabled; prefixes will be withdrawn"
                )
                self._withdraw()
                since = datetime.now()
            else:
                since = state.down_since

            self.check_state = CheckState(
                state="disabled",
                advertised=False,
                current_metric=None,
                last_result=result,
                down_since=since,
            )
            return

        # Already in the terminal "down" state (either fully withdrawn or
        # degraded with metric_down). No transition needed; just refresh the
        # last result.
        if state.state == "down":
            self.log.bind(event="debug").info(
                "Health check failure; service already in down state"
            )
            self.check_state = CheckState(
                state="down",
                advertised=state.advertised,
                current_metric=state.current_metric,
                last_result=result,
                down_since=state.down_since,
            )
            return

        # Service is "up", "falling", "rising", or "startup". Increment the
        # fall counter and check the threshold.
        fall = (state.fall or 0) + 1

        if fall >= self.check.fall:
            # Service has fallen. Either degrade (if metric_down is set) or
            # withdraw completely.
            if self.check.metric_down is not None:
                self.log.bind(event="announce").warning(
                    "Health check failure and service has fallen; "
                    "re-advertising routes with down metric ({metric})",
                    metric=self.check.metric_down,
                )
                self._degrade()
                self.check_state = CheckState(
                    state="down",
                    advertised=True,
                    current_metric=self.check.metric_down,
                    last_result=result,
                    down_since=datetime.now(),
                )
            else:
                self.log.bind(event="withdraw").warning(
                    "Health check failure and service has fallen; prefixes will be withdrawn"
                )
                self._withdraw()
                self.check_state = CheckState(
                    state="down",
                    advertised=False,
                    current_metric=None,
                    last_result=result,
                    down_since=datetime.now(),
                )
            return

        # The service does not meet minimum requirements to fall yet.
        # Preserve the current advertised/metric state.
        self.log.bind(event="info").info(
            "Health check unsuccessful but the service has not fallen yet",
        )
        self.check_state = CheckState(
            state="falling",
            advertised=state.advertised,
            current_metric=state.current_metric,
            last_result=result,
            up_since=state.up_since,
            fall=fall,
        )

    def _announce(self, restored: bool = False) -> None:
        """
        Announce the health check route at the normal (up) metric.

        Args:
            restored: True when this announce is returning the route from a
                degraded (metric_down) state. Adjusts the log/notification
                wording and forces re-emission even though the route is
                already advertised.
        """
        self.log.bind(event="debug").debug("Call to advertise route")

        # If already advertised at the normal metric, there is nothing to do.
        # (Note: when transitioning from a degraded state we *are* advertised,
        # but current_metric differs, so we must re-emit.)
        if (
            self.check_state.advertised
            and self.check_state.current_metric == self.check.metric
            and not restored
        ):
            self.log.bind(event="debug").debug(
                "Health check route is already advertised at the up metric; no action taken"
            )
            return

        self.log.bind(event="debug").debug(
            "Announcing route at up metric ({metric})",
            metric=self.check.metric,
        )
        self.announcer.announce(metric=self.check.metric)

        # Build the notification message
        if restored:
            preamble = (
                "Restoring routes to the normal metric as the service has recovered."
            )
            title = f"ExaCheck Event - Route Metric Restored - {self.check.name}"
        else:
            preamble = (
                "Announcing routes for the health check as the service is marked as up."
            )
            title = f"ExaCheck Event - Route Announcement - {self.check.name}"

        message = [
            preamble,
            f"The following prefixes will be advertised with the next hop address `{self.check.nexthop}`:",
        ]
        for prefix in self.check.prefixes:
            message.append(f"\n- `{prefix}`")

        self.notifications.notify(
            event="announce",
            check=self.check.name,
            log_context=self.log,
            title=title,
            message="\n\n".join(message),
        )

    def _degrade(self) -> None:
        """
        Re-advertise the health check route with the down metric (metric_down).

        Called instead of _withdraw() when the service has fallen and the check
        has a metric_down configured. The route remains advertised but at the
        less-preferred metric so upstream routers can fail over while still
        reaching the service if it is the only path.
        """
        assert self.check.metric_down is not None

        self.log.bind(event="debug").debug(
            "Re-advertising route at down metric ({metric})",
            metric=self.check.metric_down,
        )
        self.announcer.announce(metric=self.check.metric_down)

        message = [
            "Re-advertising routes with the down metric as the service has failed.",
            (
                f"The following prefixes will continue to be advertised with the "
                f"next hop address `{self.check.nexthop}` but with the degraded "
                f"metric `{self.check.metric_down}`:"
            ),
        ]
        for prefix in self.check.prefixes:
            message.append(f"\n- `{prefix}`")

        self.notifications.notify(
            event="announce",
            check=self.check.name,
            log_context=self.log,
            title=f"ExaCheck Event - Route Metric Degraded - {self.check.name}",
            message="\n\n".join(message),
        )

    def _withdraw(self) -> None:
        """
        Withdraw the health check route
        """
        # Log
        self.log.bind(event="debug").debug("Call to withdraw route advertisement")

        # Withdraw the route if advertised
        if not self.check_state.advertised:
            # Route not advertised, nothing to do
            self.log.bind(event="debug").debug(
                "Health check route is not advertised; no action taken"
            )
            return

        # Withdraw the route
        self.log.bind(event="debug").debug(
            "Health check route is advertised; withdrawing route"
        )
        self.announcer.withdraw(metric=self.check.metric)

        # Get the reason why the route is being withdrawn (disabled or down)
        if self.check_state.state == "disabled":
            reason = "the service has been disabled."
        else:
            reason = "the service has failed."

        # Create the message for notification
        message = [
            f"Withdrawing routes for the health check as {reason}.",
            f"The following prefixes with the next hop address `{self.check.nexthop}` will be withdrawn:",
        ]
        for prefix in self.check.prefixes:
            message.append(f"\n- `{prefix}`")

        # Send notification
        self.notifications.notify(
            event="withdraw",
            check=self.check.name,
            log_context=self.log,
            title=f"ExaCheck Event - Route Withdrawal - {self.check.name}",
            message="\n\n".join(message),
        )

    def _cleanup(self, sig: int, frame: object) -> None:
        """Signal handler for SIGINT/SIGTERM.

        Sets the termination flag + event and fires SIGALRM so any check in
        progress gets interrupted by the existing CheckExecutor timeout
        handler. The actual route withdrawal and exit run from the main
        loop, never from this signal handler.

        Idempotent: a second termination signal that arrives while the
        first one is still being handled (Ctrl-C on a foreground exacheck
        sends SIGINT to the whole process group *and* the master then
        sends SIGTERM via ``worker.terminate()``) must not raise SIGALRM
        a second time. Otherwise the new CheckTimeout fires inside
        whatever code is running while the first cleanup's exception is
        still propagating — typically Loguru's emit, which then prints a
        "Logging error in Loguru Handler" traceback.
        """
        if self._termination_requested:
            return
        self._termination_requested = True
        # Break any Sleeper.sleep() currently blocking on the event
        self._termination_event.set()
        # If we are inside executor.execute() the worker is in a syscall
        # that would otherwise wait for its full check timeout (up to 10s
        # by default). Fire SIGALRM to make the CheckExecutor's existing
        # timeout handler raise CheckTimeout, returning control to the
        # main loop near-immediately. Only do this if SIGALRM has been
        # bound to a handler — otherwise (e.g. in tests, or before run()
        # installed its baseline SIG_IGN) the default disposition would
        # terminate the process.
        if getsignal(SIGALRM) is not SIG_DFL:
            raise_signal(SIGALRM)

    def _shutdown(self) -> None:
        """Withdraw any advertised routes and exit the worker process.

        Runs from the main loop (not the signal handler) so logging and
        ``Announcer`` I/O happen in a normal execution context.
        """
        if self.check_state.advertised:
            self.announcer.withdraw(metric=self.check.metric, silent=True)
        # Drain any queued notifications from earlier _announce/_degrade/
        # _withdraw calls so they are not lost when the daemon thread dies
        # with the process. Bounded so a slow webhook cannot delay shutdown
        # past the master's 5 s kill timeout.
        self.notifications.shutdown(timeout=3)
        sys.exit(0)

    def _drain_pending_config(self) -> None:
        """Apply the most recent config updates pushed by the master.

        The queue carries two message types:

        * ``Check`` — replace the worker's check with this one and re-emit
          routes if applicable (see :meth:`_apply_new_config`).
        * ``NotificationsUpdate`` — rebuild the worker's ``Notifications``
          object so subsequent notifications go to the updated targets.

        The queue is fully drained (non-blocking) and only the latest of
        each type is applied; older queued updates of the same type are
        superseded. Notifications are applied before the check so that any
        notifications emitted by the check update go to the new targets.
        """
        if self.config_queue is None:
            return

        latest_check: Optional[Check] = None
        latest_notifications: Optional[NotificationsUpdate] = None
        try:
            while True:
                msg = self.config_queue.get_nowait()
                if isinstance(msg, NotificationsUpdate):
                    latest_notifications = msg
                elif isinstance(msg, Check):
                    latest_check = msg
                else:
                    self.log.bind(event="error").warning(
                        "Unknown config queue message type: {type}",
                        type=type(msg).__name__,
                    )
        except QueueEmpty:
            pass

        if latest_notifications is not None:
            self._apply_new_notifications(latest_notifications.configuration)
        if latest_check is not None:
            self._apply_new_config(latest_check)

    def _apply_new_notifications(
        self, configuration: Optional[list[NotificationSettings]]
    ) -> None:
        """Replace this worker's Notifications object with a fresh one.

        The old object is drained (best effort, bounded timeout) so any
        notifications already queued get sent via the old Apprise instance
        before it is dropped — this matters during reload because pending
        announce/withdraw notifications were targeted at the now-superseded
        URLs and would otherwise be lost.
        """
        self.log.bind(event="info").info(
            "Received notifications configuration update; rebuilding Notifications",
        )
        self.notifications.shutdown(timeout=3)
        self.notifications = Notifications(
            log_context=self.log,
            configuration=configuration,
        )

    def _apply_new_config(self, new_check: Check) -> None:
        """Apply a new Check in place.

        Replaces ``self.check`` and ``self.announcer`` and re-emits the route
        if currently advertised, choosing the appropriate metric for the
        current state. Rise/fall counters and up_since/down_since are
        preserved so the service does not have to re-rise from scratch.
        """
        self.log.bind(event="info").info(
            "Received in-place config update for check '{name}'",
            name=new_check.name,
        )
        state = self.check_state
        self.check = new_check
        self.announcer = Announcer(check=new_check, log_context=self.log)

        if not state.advertised:
            # Nothing on the wire; the next check iteration will use the new
            # configuration when emitting any future announcement.
            return

        # If the worker is currently degraded but the new config no longer
        # has a metric_down, the only correct behaviour is to withdraw — the
        # operator has explicitly removed the degraded-advertising policy.
        if state.state == "down" and new_check.metric_down is None:
            self.log.bind(event="withdraw").warning(
                "In-place update removed metric_down; withdrawing degraded routes",
            )
            self.announcer.withdraw()
            self.check_state = CheckState(
                state="down",
                advertised=False,
                current_metric=None,
                last_result=state.last_result,
                down_since=state.down_since,
            )
            return

        # Otherwise re-announce at the metric appropriate to the current state.
        if state.state == "down":
            target = new_check.metric_down
        else:
            target = new_check.metric

        self.announcer.announce(metric=target)
        self.check_state = CheckState(
            state=state.state,
            advertised=True,
            current_metric=target,
            last_result=state.last_result,
            up_since=state.up_since,
            down_since=state.down_since,
            rise=state.rise,
            fall=state.fall,
        )

    @property
    def _procname_status(self) -> str:
        """Generate the process name status string"""
        match self.check_state.state:
            case "rising":
                return f"rising ({self.check_state.rise}/{self.check.rise})"
            case "falling":
                return f"falling ({self.check_state.fall}/{self.check.fall})"
            case _:
                return self.check_state.state


def worker_main(
    check: Check,
    notifications: Notifications,
    config_queue: Optional[object] = None,
) -> None:
    """multiprocessing target — construct a Worker and run its loop.

    Kept as a module-level function so that ``__init__`` no longer has the
    side effect of running the worker, and so that tests can construct a
    ``Worker`` for inspection without spinning up the loop.
    """
    Worker(check, notifications, config_queue).run()
