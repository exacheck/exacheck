# -*- coding: utf-8 -*-

"""
ExaCheck - ExaBGP Health Checker

Run the requested health check and return the result
"""

from __future__ import annotations

import signal

import loguru

from .checkresult import CheckResult
from .exceptions.checktimeout import CheckTimeout
from .exceptions.dnsresolutionerror import DNSResolutionError
from .methods import CheckMethods


# pylint: disable=too-few-public-methods
class CheckExecutor:
    """
    The ExaCheck executor that will run a supplied health check and process the result in to a CheckResult
    """

    def __init__(self, method: CheckMethods, log_context: loguru.Logger):
        """Create the health check executor object

        Args:
            method (CheckMethods): The list of available health check methods that are supported
            log_context (loguru.Logger): The loguru logging context
        """
        # Set the logging context
        self.log = log_context.bind(subsystem="executor")

        # Set the check method
        self.method = method

        # Log completion of setup
        self.log.bind(event="debug").info("Check executor setup")

    def execute(self) -> CheckResult:
        """Perform a health check and retrieve the result

        Returns:
            CheckResult: The CheckResult object for this health check execution.
        """
        # Log the check starting
        self.log.bind(event="info").debug("Executing health check")

        # Execute the health check to get result
        result = self._execute()

        # Log the raw check result
        self.log.bind(event="datadump").trace(
            "Raw check result:\n{result}",
            result=result.pretty,
        )

        # Log the status of the check
        if result.success:
            self.log.bind(event="info").success(
                "Health check succeeded; service is healthy"
            )
        else:
            self.log.bind(event="info").error(
                "Health check failed; service is unhealthy"
            )

        # Return the result
        return result

    def _execute(self) -> CheckResult:
        """
        Execute the health check
        """
        # Log setup of timeout handler for health check
        self.log.bind(event="debug").debug(
            "Registering timeout handler with timeout of {timeout} seconds",
            timeout=self.method.args.timeout,
        )

        # Define the timeout handler
        def timeout_handler(signum, frame):
            """
            Raise a CheckTimeout exception if the check takes too long
            """
            raise CheckTimeout(
                f"The check timed out after {self.method.args.timeout} seconds"
            )

        # Register the timeout alarm handler
        signal.signal(signal.SIGALRM, timeout_handler)

        # Set the alarm to trigger the handler after the timeout
        self.log.bind(event="debug").trace(
            "Check timeout handler registered, setting alarm for {timeout} seconds",
            timeout=self.method.args.timeout,
        )
        signal.alarm(self.method.args.timeout)

        # Run the health check
        try:
            result = self._run_check()
        except CheckTimeout as exc:
            # Catch a timeout exception if the check takes too long to run
            result = CheckResult(
                success=False,
                message=f"{exc}",
            )
            self.log.bind(event="error").error(
                "Health check execution timed out after {timeout} seconds",
                timeout=self.method.args.timeout,
            )

        # Disable timeout signal since the check finished
        signal.alarm(0)
        self.log.bind(event="debug").trace(
            "Health check result generated, disabling timeout handler",
        )

        # Return the result
        return result

    def _run_check(self) -> CheckResult:
        """
        Call the health check method for the check and return the result
        """
        # Attempt to run the health check
        try:
            result = self.method.check()
        except DNSResolutionError as exc:
            result = CheckResult(
                success=False,
                message="Could not resolve hostname into an IP address",
                error="Hostname could not be resolved to an IP address of the appropriate address family.",
                exception=exc,
            )
            self.log.bind(event="debug").error(
                "DNS resolution error while running health check: {exc}",
                exc=f"{exc}",
            )
        except Exception as exc:  # pylint: disable=broad-except
            # The check raised an unhandled exception, generate a CheckResult with exception message
            result = CheckResult(
                success=False,
                message="Unexpected exception while running health check",
                error=f"Exception was raised: {exc}",
                exception=exc,
            )
            self.log.bind(event="error").error(
                "Unhandled exception while running health check: {exc}",
                exc=f"{exc}",
            )

        # Return the result
        return result
