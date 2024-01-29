# -*- coding: utf-8 -*-

"""
ExaCheck - ExaBGP Health Checker

Base logging configuration class
"""

from __future__ import annotations

from abc import ABC
from typing import Literal, Optional

from pydantic import ConfigDict, BaseModel, Field, PrivateAttr

from .._base import Base as BaseSettings


class Base(BaseSettings, ABC):
    """
    Log settings common to both file logging and syslog
    """

    # Create class to store the live logging configuration in a private attribute (_conf)
    class LiveConfiguration(BaseModel):
        """
        Store the live logger configuration
        """

        id: int | None = Field(
            title="Logger ID",
            description="The logger ID for this logging target",
            default=None,
        )
        model_config = ConfigDict(extra="forbid")

    level: Literal["error", "warning", "info", "success", "debug", "trace"] = Field(
        title="Log Level",
        description="The minimum log level to write logs for",
        default="info",
    )

    formatter: Optional[str] = Field(
        title="Custom Format String",
        description="The custom log format string to use",
        default=None,
    )

    events: list[
        Literal["announce", "datadump", "debug", "error", "info", "withdraw"]
    ] = Field(
        title="Log Events",
        description="The list of events that should be logged to this logging target",
        default=[
            "announce",
            "error",
            "info",
            "withdraw",
        ],
    )

    subsystems: list[
        Literal[
            "announcer",
            "configuration",
            "executor",
            "healthcheck",
            "logging",
            "master",
            "notification",
            "utility",
            "worker",
        ]
    ] = Field(
        title="Log Subsystem",
        description="The list of subsystems that should be logged to this logging target",
        default=[
            "announcer",
            "configuration",
            "executor",
            "healthcheck",
            "logging",
            "master",
            "notification",
            "utility",
            "worker",
        ],
    )

    checks: Optional[list[str]] = Field(
        title="Log Checks",
        description="The list of checks that should be logged to this logging target",
        default=None,
    )

    _conf: LiveConfiguration = PrivateAttr(default=LiveConfiguration())

    def set_logger_id(self, logger_id: int) -> None:
        """Set the logger ID for this logging target

        Args:
            logger_id (int): The logger ID
        """
        self._conf.id = logger_id

    def get_logger_id(self) -> int | None:
        """
        Get the logger ID for this logging target
        """
        return self._conf.id
