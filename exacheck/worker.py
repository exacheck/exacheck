# -*- coding: utf-8 -*-

"""
ExaCheck - ExaBGP Health Checker

Health check work class - handles the tasks of running the health check
and announcing or withdrawing routes as needed.
"""

from __future__ import annotations

from datetime import datetime
from signal import signal, SIGTERM, SIGINT
import sys

from loguru import logger

from . import methods
from .announcer import Announcer
from .checkexecutor import CheckExecutor
from .checkresult import CheckResult
from .checkstate import CheckState
from .procname import ProcName
from .settings.check import Check
from .sleeper import Sleeper
from .notifications import Notifications


# pylint: disable=too-few-public-methods,too-many-instance-attributes
class Worker:
    """
    The ExaCheck worker process for a health check; the worker will call the checks and handle
    route advertisement/withdrawal as needed
    """

    def __init__(self, check: Check, notifications: Notifications):
        """
        Set up the new ExaCheck worker object
        """
        # Bind logging process name
        self.log = logger.bind(check_name=check.name, subsystem="worker")

        # Set the check data
        self.check: Check = check

        # Set the notifications object
        self.notifications = notifications

        # Create process name manager object
        self.procname = ProcName(
            base=f"ExaCheck Worker [{self.check.name}]",
            log_context=self.log,
        )
        # Set status to "starting"
        self.procname.update(message="Startup")

        # Create announcer
        self.announcer = Announcer(check=self.check, log_context=self.log)

        # Set the initial check state
        self.check_state = CheckState(
            state="startup",
            advertised=False,
        )

        # Set check method
        self.check_method = check.args.method

        # Setup done
        self.log.bind(event="info").info(
            "ExaCheck worker object created; beginning checks"
        )

        # Start the check loop
        self.run()

    def run(self) -> None:
        """
        Run the health check process loop
        """
        # Create the check executor
        executor = CheckExecutor(method=self.method, log_context=self.log)

        # Create signal handler to withdraw routes on SIGTERM/SIGINT
        signal(SIGINT, self.cleanup)
        signal(SIGTERM, self.cleanup)

        # Start infinite loop
        while True:
            # Log start of health check
            self.log.bind(event="debug").debug("Health check loop start")

            # Create the sleeper object and start timer
            sleeper = Sleeper(
                interval=self.check.interval,
                log_context=self.log,
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
                self.failure(result=result)

            else:
                # Perform the health check
                result = executor.execute()

            # Check the result
            if result.success:
                # Call the success handler
                self.success(result=result)
            else:
                # Call the failure handler
                self.failure(result=result)

            # Finish the sleep timer
            sleeper.finish()

            # Update process name
            self.procname.update(
                message=f"Sleeping for {sleeper.sleep_time:.3f} seconds",
                status=self._procname_status,
            )

            # Sleep for the remaining time
            sleeper.sleep()

    @property
    def method(self) -> methods.CheckMethods:
        """
        Generate and return the class for the type of health check requested
        """
        # Ensure the check method is available
        if self.check_method not in methods.METHODS:
            self.log.bind(event="error").critical(
                "No health check method '{method}' available",
                method=self.check_method,
            )
            raise NotImplementedError(
                f"Could not get check method: {self.check_method}"
            )

        # Look up the class for the check
        _, cls = methods.METHODS[self.check_method]

        # Set up and return the check
        return cls(
            log_context=self.log,
            args=self.check.args,
        )

    def success(self, result: CheckResult) -> None:
        """
        Called when the health check returns a successful status
        """
        # Get existing check state object
        state = self.check_state

        # Check if the route is currently advertised
        if state.advertised:
            # The route is already advertised, create new check state
            self.log.bind(event="debug").info(
                "Health check successful and prefixes are already advertised"
            )
            self.check_state = CheckState(
                state="up",
                advertised=True,
                last_result=result,
                up_since=state.up_since,
            )
            # Return
            return

        # Check if the service has risen
        if state.rise and (state.rise + 1) >= self.check.rise:
            # Service is now risen, call function to announce route
            self.log.bind(event="announce").success(
                "Health check successful and service has risen; prefixes will be advertised"
            )
            self.announce()
            # Create the new check state
            self.check_state = CheckState(
                state="up",
                advertised=True,
                last_result=result,
                up_since=datetime.now(),
            )
            # Return
            return

        # The service does not meet minimum requirements to rise yet
        self.log.bind(event="info").info(
            "Health check successful but service has not risen yet",
        )

        # If there is an existing rise value, add 1 otherwise set to 1
        if state.rise:
            rise = state.rise + 1
        else:
            rise = 1

        # Create the new check state
        self.check_state = CheckState(
            state="rising",
            advertised=False,
            last_result=result,
            down_since=state.down_since,
            rise=rise,
        )

    def failure(self, result: CheckResult) -> None:
        """
        Called when the health check returns a failed status
        """
        # Get existing check state object
        state = self.check_state

        # Check if the failure is due to the service being disabled
        if result.disabled:
            # Check if the route is currently advertised
            if state.advertised:
                # The state is advertised, withdraw the routes
                self.log.bind(event="withdraw").warning(
                    "Service has been disabled; prefixes will be withdrawn"
                )
                self.withdraw()
                # Set the "since" date to now
                since = datetime.now()
            else:
                # The route is not advertised, nothing to do
                since = state.down_since

            # Create the new check state
            self.check_state = CheckState(
                state="disabled",
                advertised=False,
                last_result=result,
                down_since=since,
            )

            # Finish
            return

        # Check if the route is currently advertised
        if not state.advertised:
            # The route is not advertised, create new check state
            self.log.bind(event="debug").info(
                "Health check failure; prefixes are not advertised"
            )
            self.check_state = CheckState(
                state="down",
                advertised=False,
                last_result=result,
                down_since=state.up_since,
            )

            # Return
            return

        # Check if the service is falling
        if state.fall and (state.fall + 1) >= self.check.fall:
            # Service should now be considered down
            self.log.bind(event="withdraw").warning(
                "Health check failure and service has fallen; prefixes will be withdrawn"
            )
            # Withdraw the route
            self.withdraw()
            # Create the new check state
            self.check_state = CheckState(
                state="down",
                advertised=False,
                last_result=result,
                down_since=datetime.now(),
            )
            # Return
            return

        # The service does not meet minimum requirements to fall yet
        self.log.bind(event="info").info(
            "Health check unsuccessful but the service has not fallen yet",
        )

        # If there is an existing fall value, add 1 otherwise set to 1
        if state.fall:
            fall = state.fall + 1
        else:
            fall = 1

        # Create the new check state
        self.check_state = CheckState(
            state="falling",
            advertised=True,
            last_result=result,
            up_since=state.up_since,
            fall=fall,
        )

    def announce(self) -> None:
        """
        Announce the health check route
        """
        # Log
        self.log.bind(event="debug").debug("Call to advertise route")

        # Advertise the route if not advertised yet
        if self.check_state.advertised:
            # Route advertised, nothing to do
            self.log.bind(event="debug").debug(
                "Health check route is already advertised; no action taken"
            )
        else:
            # Advertise the route
            self.log.bind(event="debug").debug(
                "Health check route is not advertised yet; announcing route"
            )
            self.announcer.announce(metric=self.check.metric)

            # Create the message for notification
            message = [
                "Announcing routes for the health check as the service is marked as up.",
                f"The following prefixes will be advertised with the next hop address `{self.check.nexthop}`:",
            ]
            for prefix in self.check.prefixes:
                message.append(f"\n- `{prefix}`")

            # Send notification
            self.notifications.notify(
                event="announce",
                check=self.check.name,
                log_context=self.log,
                title=f"ExaCheck Event - Route Announcement - {self.check.name}",
                message="\n\n".join(message),
            )

    def withdraw(self) -> None:
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

    def cleanup(self, sig: int, frame: object) -> None:
        """Handle clean up of the worker process when the process is terminated

        Args:
            sig (int): The signal that was received
            frame (object): The frame being executed when the signal was received
        """
        # Withdraw all routes if currently advertised
        if self.check_state.advertised:
            self.announcer.withdraw(metric=self.check.metric, silent=True)

        # Finish
        sys.exit(0)

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
