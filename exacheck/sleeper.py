# -*- coding: utf-8 -*-

"""
ExaCheck - ExaBGP Health Checker

Manage the sleep between task loop iterations
"""

from __future__ import annotations

from time import monotonic, sleep

import loguru


class Sleeper:
    """
    Manage sleep between task iterations (monitoring or health checks)
    """

    def __init__(self, interval: int | float, log_context: loguru.Logger):
        """
        Set up the new ExaCheck sleep object
        """

        # Set the logging context
        self.log = log_context.bind(subsystem="utility")

        # Set the sleep interval
        self._interval = interval

        # Set empty sleep time type
        self._sleep_time: int | float = 0

        # Log setup
        self.log.bind(event="debug").trace(
            "Created sleep object with interval {interval}", interval=self._interval
        )

        # Start the timer
        self._start = monotonic()
        self.log.bind(event="debug").trace(
            "Setting iteration start time to {start}", start=self._start
        )

    def finish(self) -> None:
        """
        Stop the timer for the current iteration and sleep
        """

        # Set the finish time
        finish = monotonic()
        self.log.bind(event="debug").trace(
            "Setting iteration finish time to {finish}", finish=finish
        )

        # Calculate and set the sleep time
        self._sleep_time = self._calculate(finish=finish)

    @property
    def sleep_time(self) -> int | float:
        """
        Return the expected sleep time
        """
        return self._sleep_time

    def sleep(self) -> None:
        """
        Sleep for the required sleep time
        """
        # Sleep for the required period
        self.log.bind(event="info").info(
            "Sleeping for {sleep_time:.5f} seconds", sleep_time=self._sleep_time
        )
        sleep(self._sleep_time)

        # Wake back up
        self.log.bind(event="info").debug("Waking back up after sleep")

    def _calculate(self, finish: int | float) -> int | float:
        """
        Calculate the sleep time
        """
        # Calculate the elapsed time
        elapsed = finish - self._start
        self.log.bind(event="debug").trace(
            "Calculated iteration took {elapsed:.5f} seconds", elapsed=elapsed
        )

        # If the iteration over-ran the interval, run the next iteration
        # immediately (no sleep) instead of forcing a fixed 1 second floor —
        # the configured interval is the contract.
        if elapsed >= self._interval:
            self.log.bind(event="info").warning(
                "Iteration took {elapsed:.5f}s which exceeds the configured interval of {interval}s; "
                "next iteration will run immediately",
                elapsed=elapsed,
                interval=self._interval,
            )
            return 0

        # Return the remaining time left in the interval
        remaining = self._interval - elapsed
        self.log.bind(event="debug").trace(
            "Calculated sleep interval for iteration: {remaining:.5f}",
            remaining=remaining,
        )
        return remaining
