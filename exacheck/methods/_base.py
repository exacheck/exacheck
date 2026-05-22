# -*- coding: utf-8 -*-

"""
ExaCheck - ExaBGP Health Checker

Base Check Method
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ClassVar

import loguru

from ..settings.checkargs._base import Base as ArgsBase
from ..checkresult import CheckResult


# pylint: disable=too-few-public-methods
class Base(ABC):
    """
    The base health check class.

    Concrete subclasses self-register by declaring ``method_name`` and
    ``args_model`` class variables. Abstract intermediates (e.g. ``Remote``)
    inherit ``method_name = ""`` from this class and so are skipped.
    """

    method_name: ClassVar[str] = ""
    args_model: ClassVar[type[ArgsBase]]

    _registry: ClassVar[dict[str, type["Base"]]] = {}

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        # Only register classes that explicitly declare their own method_name —
        # an inherited value (the empty default on Base) means the subclass is
        # an abstract intermediate.
        if "method_name" not in cls.__dict__ or not cls.method_name:
            return
        if cls.method_name in Base._registry:
            raise RuntimeError(
                f"Duplicate check method registration for {cls.method_name!r}: "
                f"existing={Base._registry[cls.method_name].__qualname__} "
                f"new={cls.__qualname__}"
            )
        Base._registry[cls.method_name] = cls

    def __init__(
        self,
        log_context: loguru.Logger,
        args: ArgsBase,
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
        self.log.opt(lazy=True).bind(event="datadump").trace(
            "Health check result:\n{result}",
            result=lambda: result.pretty,
        )
