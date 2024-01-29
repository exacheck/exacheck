# -*- coding: utf-8 -*-

"""
ExaCheck - ExaBGP Health Checker

Base Check Method
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import loguru

from ..settings.checkargs import CheckArgs
from ..checkresult import CheckResult


# pylint: disable=too-few-public-methods
class Base(ABC):
    """
    The base health check class
    """

    def __init__(
        self,
        log_context: loguru.Logger,
        args: CheckArgs,
    ):
        """
        Initialize the class
        """
        # Define log context
        self.log = log_context.bind(subsystem="healthcheck")

        # Define check args
        self.args = args

        # Complete setup
        self.log.bind(event="debug").info("Health check setup complete")

    @abstractmethod
    def check(self) -> CheckResult:
        """Function that is called each healthcheck interval.

        Your health check must return a "CheckResult" object with the results of the health check.
        Any exceptions should be handled in this function with a textual representation of the exception stored
        in the CheckResult object.

        Returns:
            CheckResult: The results of the health check
        """

    def _log_result(self, result: CheckResult) -> None:
        """
        Log a check result
        """
        # Log the data
        self.log.bind(event="debug").debug(
            "Health check returned {status}",
            status="success" if result.success else "failure",
        )
        self.log.bind(event="datadump").trace(
            "Health check result:\n{result}",
            result=result.pretty,
        )
