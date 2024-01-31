# -*- coding: utf-8 -*-

"""
ExaCheck - ExaBGP Health Checker

Main ExaCheck class
"""

from __future__ import annotations

from multiprocessing import Process
from pathlib import Path
from pprint import pformat
from time import sleep
from typing import Tuple, cast
from signal import signal, SIGTERM, SIGINT
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
from .worker import Worker
from .configuration import Configuration


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
                # Ensure that the job is still alive
                if job[1].is_alive():
                    # Worker is alive; log it
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

            # Check if live reloads are enabled
            if self.configuration.settings.exacheck.live_reload:
                # Start configuration file change test
                self.log.bind(event="debug").trace(
                    "Testing if the configuration needs to be reloaded"
                )

                # Check the modification date of the configuration file
                if self.configuration.is_modified():
                    # Log that the configuration file has been modified
                    self.log.bind(event="info").info(
                        "Configuration file has been modified; performing live configuration reload"
                    )
                    # Reload the configuration
                    self._reload_configuration()
                else:
                    # No changes to apply
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
            self.log.bind(event="datadump").trace(
                "Check '{check_name}' configuration:\n{check_configuration}",
                check_name=check.name,
                check_configuration=pformat(check.model_dump()),
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
        Create a single process/worker for a check
        """
        # Create the worker process
        self.log.bind(event="debug").trace(
            "Creating worker process for check {check_name}", check_name=check.name
        )
        try:
            worker = Process(
                target=Worker,
                args=(
                    check,
                    self.notifications,
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

        # Return the created process
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
                dsn=cast(
                    str, self.configuration.settings.sentry.dsn
                ),
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

        Args:
            sig (int): The signal that was received
            frame (object): The frame being executed when the signal was received
        """
        # Send notification
        self.notifications.notify(
            event="info",
            title="ExaCheck Process Terminated",
            message="The ExaCheck process has been terminated.",
        )

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

        # Check if the notification configuration is different
        if current.notifications != new.notifications:
            # Recreate the notification object
            self.log.bind(event="info").info(
                "Notification configuration has changed; recreating notifications object",
            )
            self.notifications = Notifications(
                log_context=self.log,
                configuration=new.notifications,
            )

        # Loop over all currently defined checks
        for check in current.checks:
            # Test if the check name is not defined anymore
            if not new.get_check_name(check.name):
                # Terminate the worker process
                self._terminate_worker(check)

        # Loop over all newly defined checks
        for check in new.checks:
            # Test if the check is newly defined
            if not current.get_check_name(check.name):
                # Create and start the worker process
                self._start_worker(check)

                # Send notification
                self.notifications.notify(
                    event="info",
                    title=f"ExaCheck Worker Started - {check.name}",
                    message=f"The ExaCheck worker process for the health check `{check.name}` has been started.",
                )

                # Move on to next check
                continue

            # Test if the check has changed
            if new.get_check_name(check.name) != current.get_check_name(check.name):
                # Restart the worker to apply new configuration
                self._restart_worker(check)

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
        self.log.bind(event="datadump").trace(
            "Check '{check_name}' configuration:\n{check_configuration}",
            check_name=check.name,
            check_configuration=pformat(check.model_dump()),
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
        """Stop a worker process"""
        # Logging
        self.log.bind(event="info").info(
            "Check worker for '{name}' is being stopped",
            name=check.name,
        )

        # Get the worker process associated with the check
        worker = [worker for worker in self.jobs if worker[0].name == check.name][0]

        # Terminate the worker process
        worker[1].terminate()

        # Remove the worker process from the list
        self.jobs.remove(worker)

        # Logging
        self.log.bind(event="info").info(
            "Check worker for '{name}' has been stopped",
            name=check.name,
        )
