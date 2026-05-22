# -*- coding: utf-8 -*-

"""
ExaCheck - ExaBGP Health Checker

Main ExaCheck class
"""

from __future__ import annotations

from multiprocessing import Process, Queue
from pathlib import Path
from pprint import pformat
from time import sleep
from typing import Tuple
from signal import signal, SIGTERM, SIGINT, SIGHUP
import sys
import importlib.metadata

from loguru import logger

from .exceptions.workerprocesserror import WorkerProcessError
from .logmanager import LogManager
from .procname import ProcName
from .settings.check import Check
from .settings.sentry import Sentry
from .notifications import Notifications
from .sleeper import Sleeper
from .worker import NotificationsUpdate, worker_main
from .configuration import Configuration


# Check fields whose change requires a full worker restart (a new CheckExecutor
# or different cadence/threshold/disable behaviour cannot be applied to a
# running worker mid-loop without subtle races).
_OPERATIONAL_FIELDS: Tuple[str, ...] = (
    "args",
    "interval",
    "rise",
    "fall",
    "disable",
)

# Check fields whose change can be applied in place: just push the new Check
# to the worker, which rebuilds its Announcer and re-emits the route. Rise/
# fall counters and current state are preserved, so no BGP churn or false
# re-rise period.
_ROUTE_FIELDS: Tuple[str, ...] = (
    "prefixes",
    "nexthop",
    "metric",
    "metric_down",
    "communities",
    "as_path",
    "local_preference",
    "path_id",
    "neighbors",
)


# pylint: disable=too-few-public-methods
class ExaCheck:
    """
    ExaCheck main class
    """

    def __init__(
        self,
        file: Path,
        verbosity: int = 0,
        dry_run: bool = False,
    ):
        """
        Set up the new ExaCheck object
        """
        # Create STDERR logger/Log object
        self.logmanager = LogManager(verbosity=verbosity)

        # Set logging context
        self.log = logger.bind(
            check_name="MASTER",
        )

        # Set logging context to set subsystem to master
        self.log = logger.bind(
            check_name="MASTER",
            subsystem="master",
        )

        # Log setup of object
        self.log.bind(event="info").info(
            "Creating new ExaCheck object with configuration file '{file}'", file=file
        )

        # Load configuration
        self.configuration = Configuration(
            log_context=self.log,
            file=file,
        )

        # Check if dry run
        if dry_run:
            # Log configuration is valid
            self.log.bind(event="info").info(
                "Configuration test only; configuration is valid"
            )
            return

        # If Sentry is to be enabled, try to import the Sentry SDK module and enable it
        if (
            self.configuration.settings.sentry
            and self.configuration.settings.sentry.enabled  # pylint: disable=no-member
        ):
            self._sentry_setup()

        # Configure additional logging if required
        if self.configuration.settings.logging:
            self.logmanager.setup(
                loggers=self.configuration.settings.logging,
            )

        # Configure notifications
        self.notifications = Notifications(
            log_context=self.log,
            configuration=self.configuration.settings.notifications,
        )

        # Per-worker config queues keyed by check name. The master pushes a
        # new Check onto the queue for an in-place worker update.
        self._config_queues: dict[str, Queue] = {}

        # Set by the SIGHUP handler; read by the monitoring loop to trigger a
        # reload outside of the mtime/content poll.
        self._reload_requested = False

        # Log finish of setup
        self.log.bind(event="debug").info("ExaCheck object setup complete")

    def run(self) -> None:
        """
        Run ExaCheck
        """
        # Create process name manager
        self.procname = ProcName(  # pylint: disable=attribute-defined-outside-init
            base=f"ExaCheck Master Process [{self.configuration.settings.file}]",
            log_context=self.log,
        )

        # Set process name
        self.procname.update(message="Starting workers")

        # Create jobs
        self.jobs = self._start_processes()

        # Notify that ExaCheck is started
        self.notifications.notify(
            event="info",
            title="ExaCheck Startup",
            message="The ExaCheck process has now been started.",
        )

        # Create signal handler to handle process termination and notification
        signal(SIGINT, self.cleanup)
        signal(SIGTERM, self.cleanup)
        signal(SIGHUP, self._handle_sighup)

        # Run loop of doing nothing for now
        self.log.bind(event="info").info(
            "ExaCheck now running; entering monitoring loop"
        )

        # Set new process title
        self.procname.update(message="Sleeping")

        # Perform initial sleep
        self.log.bind(event="debug").debug(
            "Sleeping for {interval} seconds before monitoring loop starts",
            interval=self.configuration.settings.exacheck.monitoring_interval,
        )
        sleep(self.configuration.settings.exacheck.monitoring_interval)

        # Run infinite loop
        while True:
            # Log start of monitoring loop
            self.log.bind(event="info").info("Monitoring loop starting")

            # Create sleep object
            sleeper = Sleeper(
                interval=self.configuration.settings.exacheck.monitoring_interval,
                log_context=self.log,
            )

            # Set new process title
            self.procname.update(message="Monitoring loop start")

            # Loop over each job defined in configuration
            self.log.bind(event="debug").debug(
                "Looping over each worker to ensure it is alive"
            )
            for job in self.jobs:
                # is_alive() also reaps the child if it has exited (it calls
                # _popen.poll internally), so it is sufficient on its own.
                if job[1].is_alive():
                    self.log.bind(event="debug").trace(
                        "Worker '{job_name}' is alive", job_name=job[0].name
                    )

                else:
                    # Worker is not alive; respawn it
                    self.log.bind(event="error").critical(
                        "Worker '{job_name}' is not alive; it will be respawned",
                        job_name=job[0].name,
                    )

                    # Create the new worker process
                    worker = self._create_process(check=job[0])

                    # Start the new worker
                    worker.start()
                    self.log.bind(event="info").info(
                        "Worker '{job_name}' respawned", job_name=job[0].name
                    )

                    # Replace the job with the new one
                    self.jobs[self.jobs.index(job)] = (job[0], worker)

                    # Send notification
                    self.notifications.notify(
                        event="error",
                        title=f"ExaCheck Worker Failure - {job[0].name}",
                        message=f"The ExaCheck worker process for the health check `{job[0].name}` failed and has now been respawned.",
                    )

            # Determine whether to reload: either SIGHUP forced it, or live
            # reload is enabled and the file contents have changed.
            if self._reload_requested:
                self._reload_requested = False
                self.log.bind(event="info").info(
                    "Reload requested by signal; performing configuration reload"
                )
                self._reload_configuration()
            elif self.configuration.settings.exacheck.live_reload:
                self.log.bind(event="debug").trace(
                    "Testing if the configuration needs to be reloaded"
                )
                if self.configuration.is_modified():
                    self.log.bind(event="info").info(
                        "Configuration file has been modified; performing live configuration reload"
                    )
                    self._reload_configuration()
                else:
                    self.log.bind(event="debug").trace(
                        "No configuration changes to apply"
                    )
            else:
                self.log.bind(event="debug").trace(
                    "Live configuration reload disabled; not checking for modifications"
                )

            # Finish the sleep timer
            sleeper.finish()

            # Set new process name
            self.procname.update(
                message=f"Sleeping for {sleeper.sleep_time:.3f} seconds"
            )

            # Sleep for the remaining time
            self.log.bind(event="info").debug(
                "Monitoring loop finished; sleeping for {sleep_time:.3f} seconds until next loop",
                sleep_time=sleeper.sleep_time,
            )
            sleeper.sleep()

    def _start_processes(self) -> list[Tuple[Check, Process]]:
        """
        Run ExaCheck using process based health checks
        """
        # Create a list of check processes
        workers: list[Tuple[Check, Process]] = []

        # Start the processes for each check
        for (
            check
        ) in self.configuration.settings.checks:  # pylint: disable=not-an-iterable
            # Log setup
            self.log.bind(event="info").debug(
                "Creating process for check '{check_name}'", check_name=check.name
            )
            self.log.opt(lazy=True).bind(event="datadump").trace(
                "Check '{check_name}' configuration:\n{check_configuration}",
                check_name=lambda: check.name,
                check_configuration=lambda: pformat(check.model_dump()),
            )

            # Create the process
            worker = self._create_process(check=check)

            # Store the process in the list
            workers.append((check, worker))

        # Loop over each process and start it
        self.log.bind(event="info").info("Starting worker processes")
        for check, worker in workers:
            self.log.bind(event="debug").debug(
                "Starting worker process for '{check_name}'",
                check_name=check.name,
            )
            worker.start()
            self.log.bind(event="info").debug(
                "Worker process for '{check_name}' started",
                check_name=check.name,
            )

        # Return the list of processes
        return workers

    def _create_process(self, check: Check) -> Process:
        """
        Create a single process/worker for a check.

        Also creates a per-worker config queue used by ``_reload_configuration``
        to push in-place updates without restarting the process.
        """
        self.log.bind(event="debug").trace(
            "Creating worker process for check {check_name}", check_name=check.name
        )
        config_queue: Queue = Queue()
        try:
            worker = Process(
                target=worker_main,
                args=(
                    check,
                    self.notifications,
                    config_queue,
                ),
                daemon=True,
                name=check.name,
            )
        except Exception as exc:  # pylint: disable=broad-except
            self.log.bind(event="error").exception(
                "Exception creating process for check {check_name}:\n{exc}",
                check_name=check.name,
                exc=exc,
            )
            raise WorkerProcessError from exc

        # Register the queue so the master can push in-place updates later
        self._config_queues[check.name] = config_queue

        self.log.bind(event="debug").debug(
            "Worker process for check {check_name} created",
            check_name=check.name,
        )
        return worker

    def _sentry_setup(self):
        """
        Set up Sentry error reporting
        """
        # Set type for MyPy
        assert isinstance(self.configuration.settings.sentry, Sentry)
        try:
            import sentry_sdk  # pylint: disable=import-outside-toplevel

            sentry_sdk.init(
                dsn=str(self.configuration.settings.sentry.dsn),
                release=f"exacheck@{importlib.metadata.version('exacheck')}",
                attach_stacktrace=self.configuration.settings.sentry.attach_stacktrace,
                include_local_variables=self.configuration.settings.sentry.include_local_variables,
                debug=self.configuration.settings.sentry.debug,
                traces_sample_rate=self.configuration.settings.sentry.sample_rate,
                profiles_sample_rate=self.configuration.settings.sentry.profiles_sample_rate,
            )
        except ImportError:
            self.log.bind(event="error").error(
                "Sentry SDK not installed; not enabling Sentry reporting"
            )
        except Exception as exc:  # pylint: disable=broad-except
            self.log.bind(event="error").error(
                "Exception enabling Sentry SDK; skipping: {exc}",
                exc=f"{exc}",
            )
        else:
            self.log.bind(event="debug").debug(
                "Enabled Sentry SDK for error reporting to '{dsn}'",
                dsn=self.configuration.settings.sentry.dsn,  # pylint: disable=no-member
            )

    def cleanup(self, sig: int, frame: object) -> None:
        """Handle clean up of the master process when the process is terminated

        Terminates every worker process and waits for it to exit so the child
        is reaped and does not linger as a zombie after the master exits.

        Args:
            sig (int): The signal that was received
            frame (object): The frame being executed when the signal was received
        """
        # Guard against re-entry if a second termination signal arrives while
        # we are already shutting down
        if getattr(self, "_shutting_down", False):
            return
        self._shutting_down = True

        self.log.bind(event="info").info(
            "Received termination signal {sig}; shutting down workers",
            sig=sig,
        )

        # Send notification
        self.notifications.notify(
            event="info",
            title="ExaCheck Process Terminated",
            message="The ExaCheck process has been terminated.",
        )

        # Signal every worker to exit. Each worker's own SIGTERM handler will
        # withdraw any advertised routes before it exits.
        for check, worker in self.jobs:
            if worker.is_alive():
                self.log.bind(event="debug").debug(
                    "Sending SIGTERM to worker for check '{name}'",
                    name=check.name,
                )
                worker.terminate()

        # Wait for each worker to exit so it is reaped. Escalate to SIGKILL
        # if a worker fails to exit within the timeout.
        for check, worker in self.jobs:
            worker.join(timeout=5)
            if worker.is_alive():
                self.log.bind(event="error").warning(
                    "Worker for check '{name}' did not exit after SIGTERM; killing",
                    name=check.name,
                )
                worker.kill()
                worker.join(timeout=2)
            try:
                worker.close()
            except ValueError:
                # Process is still alive (kill+join failed); nothing more we can do
                pass

        # Drain queued notifications before exiting so the final "Process
        # Terminated" notification (and anything queued just before) has a
        # chance to be delivered.
        self.notifications.shutdown(timeout=5)

        # Exit
        sys.exit(0)

    def _reload_configuration(self) -> None:
        """Perform a reload of the configuration file"""
        # Make a copy of the current configuration object
        current = self.configuration.settings

        # Reload the configuration
        if not self.configuration.reload():
            # Log failure
            self.log.bind(event="error").error(
                "Failed to reload configuration file; skipping reload until next change",
            )
            return

        # Get the new configuration object
        new = self.configuration.settings

        # Warn about top-level settings that the master only reads at startup.
        # Applying them properly requires a full ExaCheck restart.
        ignored: list[str] = []
        if current.exacheck != new.exacheck:
            ignored.append(
                "`exacheck` (monitoring_interval, live_reload) — read once at startup"
            )
        if current.logging != new.logging:
            ignored.append("`logging` — log sinks are configured once at startup")
        if current.sentry != new.sentry:
            ignored.append("`sentry` — initialised once at startup")
        if ignored:
            self.log.bind(event="error").warning(
                "The following configuration changes require an ExaCheck restart "
                "and will not take effect on this reload:\n - {fields}",
                fields="\n - ".join(ignored),
            )

        # Notifications can be recreated in-place. Drain the old one's queue
        # first so anything pending is flushed before its thread is dropped.
        if current.notifications != new.notifications:
            self.log.bind(event="info").info(
                "Notification configuration has changed; recreating notifications object",
            )
            self.notifications.shutdown(timeout=5)
            self.notifications = Notifications(
                log_context=self.log,
                configuration=new.notifications,
            )
            # Forked workers hold a copy of the pre-reload Notifications and
            # would otherwise keep sending to the old Apprise targets. Push
            # the new config down each worker's existing config queue so
            # they rebuild their own Notifications on the next iteration.
            update = NotificationsUpdate(configuration=new.notifications)
            for queue in self._config_queues.values():
                queue.put(update)

        # Stop workers whose check is no longer in the new config.
        for check in current.checks:
            if not new.get_check_name(check.name):
                self._terminate_worker(check)

        # Start, update, or restart workers for the new check list.
        for check in new.checks:
            old_check = current.get_check_name(check.name)

            # New check — start a fresh worker
            if old_check is None:
                self._start_worker(check)
                self.notifications.notify(
                    event="info",
                    title=f"ExaCheck Worker Started - {check.name}",
                    message=(
                        f"The ExaCheck worker process for the health check "
                        f"`{check.name}` has been started."
                    ),
                )
                continue

            # Existing check — classify what kind of change happened
            op_changed, route_changed = self._classify_check_change(old_check, check)
            if op_changed:
                # Behaviour/cadence change: full restart preserves correctness.
                self._restart_worker(check)
            elif route_changed:
                # Route-attribute change only: hot-update without losing
                # rise/fall counters or causing a withdraw/re-announce cycle
                # at startup-rise speed.
                self._update_worker_routes(check)
            else:
                # Only cosmetic fields (e.g. description) changed — nothing
                # to do, but keep the master's view of the Check in sync.
                self.log.bind(event="debug").info(
                    "Check '{name}' has only cosmetic changes; no worker action",
                    name=check.name,
                )
                for index, (existing, process) in enumerate(self.jobs):
                    if existing.name == check.name:
                        self.jobs[index] = (check, process)
                        break

    def _restart_worker(self, check: Check) -> None:
        """Restart a worker process"""
        # Log that the check will be restarted
        self.log.bind(event="info").info(
            "Check worker for '{name}' will be restarted",
            name=check.name,
        )

        # Stop the worker process
        self._stop_worker(check)

        # Create the new worker and start process
        self._start_worker(check)

        # Send notification
        self.notifications.notify(
            event="info",
            title=f"ExaCheck Worker Restarted - {check.name}",
            message=f"The ExaCheck worker process for the health check `{check.name}` has been restarted.",
        )

    def _start_worker(self, check: Check) -> None:
        """Create and start a worker process"""
        # Log the startup
        self.log.bind(event="info").info(
            "Creating and starting worker process for '{check_name}'",
            check_name=check.name,
        )

        # Dump the configuration
        self.log.opt(lazy=True).bind(event="datadump").trace(
            "Check '{check_name}' configuration:\n{check_configuration}",
            check_name=lambda: check.name,
            check_configuration=lambda: pformat(check.model_dump()),
        )

        # Create the new worker process
        worker = self._create_process(check=check)

        # Start worker
        worker.start()

        # Logging
        self.log.bind(event="info").debug(
            "Worker process for '{check_name}' started",
            check_name=check.name,
        )

        # Add to the jobs list
        self.jobs.append((check, worker))

    def _terminate_worker(self, check: Check) -> None:
        """Terminate a worker process"""

        # Log that the check is no longer configured
        self.log.bind(event="info").info(
            "Check worker for '{name}' will be terminated and routes withdrawn",
            name=check.name,
        )

        # Stop the worker
        self._stop_worker(check)

        # Send notification
        self.notifications.notify(
            event="info",
            title=f"ExaCheck Worker Removed - {check.name}",
            message=f"The ExaCheck worker process for the health check `{check.name}` has been removed as it is no longer configured.",
        )

    def _stop_worker(self, check: Check) -> None:
        """Stop a worker process

        Terminates the worker and waits for it to exit so the process is
        reaped (no zombies). Escalates to SIGKILL if the worker hangs.
        """
        # Logging
        self.log.bind(event="info").info(
            "Check worker for '{name}' is being stopped",
            name=check.name,
        )

        # Get the worker process associated with the check
        worker = next(
            (w for w in self.jobs if w[0].name == check.name),
            None,
        )
        if worker is None:
            self.log.bind(event="error").error(
                "No worker found for check '{name}'; nothing to stop",
                name=check.name,
            )
            return
        process = worker[1]

        # Terminate and wait for the worker to exit so it is reaped
        process.terminate()
        process.join(timeout=5)
        if process.is_alive():
            self.log.bind(event="error").warning(
                "Worker for check '{name}' did not exit after SIGTERM; killing",
                name=check.name,
            )
            process.kill()
            process.join(timeout=2)
        try:
            process.close()
        except ValueError:
            pass

        # Remove the worker process from the list and forget its config queue
        self.jobs.remove(worker)
        self._config_queues.pop(check.name, None)

        # Logging
        self.log.bind(event="info").info(
            "Check worker for '{name}' has been stopped",
            name=check.name,
        )

    def _handle_sighup(self, sig: int, frame: object) -> None:
        """Set the reload flag in response to SIGHUP.

        The actual reload is performed by the monitoring loop; the signal
        handler only sets a flag to keep its execution path minimal.
        """
        self._reload_requested = True

    @staticmethod
    def _classify_check_change(old: Check, new: Check) -> Tuple[bool, bool]:
        """Classify how a check has changed.

        Returns ``(operational_changed, route_changed)``. Fields not in either
        bucket (currently just ``description``) are considered cosmetic.
        """
        op = any(getattr(old, f) != getattr(new, f) for f in _OPERATIONAL_FIELDS)
        rt = any(getattr(old, f) != getattr(new, f) for f in _ROUTE_FIELDS)
        return op, rt

    def _update_worker_routes(self, check: Check) -> None:
        """Push a new Check to a running worker for in-place re-announce.

        The worker drains the queue at the top of each iteration, swaps in
        the new Check, rebuilds its Announcer, and re-emits the route — all
        without losing the current rise/fall counters or up_since/down_since
        timestamps.
        """
        queue = self._config_queues.get(check.name)
        if queue is None:
            self.log.bind(event="error").warning(
                "No config queue for check '{name}'; cannot push in-place update",
                name=check.name,
            )
            return

        self.log.bind(event="info").info(
            "Pushing in-place route update to worker for check '{name}'",
            name=check.name,
        )
        # Replace the Check on the corresponding job tuple so the master's
        # view stays in sync with the worker's.
        for index, (existing, process) in enumerate(self.jobs):
            if existing.name == check.name:
                self.jobs[index] = (check, process)
                break
        queue.put(check)

        # Notification (uses the existing "info" event)
        self.notifications.notify(
            event="info",
            title=f"ExaCheck Worker Route Update - {check.name}",
            message=(
                f"Route attributes for the health check `{check.name}` have "
                "been updated in place without restarting the worker."
            ),
        )
