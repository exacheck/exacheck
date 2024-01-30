# -*- coding: utf-8 -*-

"""
ExaCheck - ExaBGP Health Checker

Store configuration for the ExaCheck application.
"""

from typing import Optional, Annotated, Union

from pydantic import (
    Field,
    model_validator,
    field_validator,
    FilePath,
)
from pydantic_core.core_schema import ValidationInfo

from ._base import Base
from .check import Check
from .loggers import LogFile, Syslog
from .sentry import Sentry
from .notifications import Notifications
from .exacheck import ExaCheck


# Set the available log types to allow the log type to be discriminated
LogMethods = Annotated[Union[LogFile, Syslog], Field(discriminator="method")]


class Settings(Base):
    """
    Define and store the parsed configuration for ExaCheck
    """

    # File path set to optional as it is defined by the CLI
    file: Optional[FilePath] = Field(
        title="Configuration File",
        description="The path to the configuration file that was loaded",
        default=None,
    )

    exacheck: ExaCheck = Field(
        title="ExaCheck Configuration",
        description="ExaCheck internal options",
        default=ExaCheck(),
    )

    checks: list[Check] = Field(
        title="Checks",
        description="The list of health checks to perform",
    )

    logging: Optional[list[LogMethods]] = Field(
        title="Logging Configuration",
        description="The logging configuration for ExaCheck",
        default=None,
    )

    notifications: Optional[list[Notifications]] = Field(
        title="Notifications",
        description="The list of services to send notifications to for check events",
        default=None,
    )

    sentry: Optional[Sentry] = Field(
        title="Sentry Configuration",
        description="The Sentry SDK configuration for error reporting/profiling",
        default=None,
    )

    @model_validator(mode="before")
    # pylint: disable=no-self-argument
    def validate_logfiles_unique(cls, values: dict) -> dict:
        """
        If any file based loggers are defined, ensure the file names are unique
        """
        # Skip if no logging defined
        if "logging" not in values or values["logging"] is None:
            return values

        # Get a list of all log file paths from file loggers
        paths = [
            f"{logger.destination}"
            for logger in values["logging"]
            if isinstance(logger, LogFile)
        ]

        # Create set of unique paths for searching duplicates
        unique_paths = set()

        # Search for duplicates
        duplicates = [path for path in paths if path in unique_paths or unique_paths.add(path)]  # type: ignore

        # Raise error if duplicates found
        if duplicates:
            raise ValueError(
                f"Log files must be unique. Duplicate log file paths found: {', '.join(duplicates)}"
            )

        # Return the validated values
        return values

    @field_validator("logging")
    # pylint: disable=no-self-argument
    def validate_log_filter_names(
        cls, logging: list[LogFile | Syslog], values: ValidationInfo
    ) -> list[LogFile | Syslog]:
        """
        If any check name log filters are defined, ensure the check name actually exists
        """
        # Create a list of all check names
        check_names: list[str] = [check.name for check in values.data["checks"]]

        # Loop through each logger
        for logger in logging:
            # Skip if no check filters defined
            if not logger.checks:
                continue

            # Check if undefined check names have been set
            if undefined := [
                check_name
                for check_name in logger.checks
                if check_name not in check_names
            ]:
                if logger.method == "file":
                    raise ValueError(
                        f"Log to file {logger.destination} has undefined check name(s) configured: "
                        f"{', '.join(undefined)}"
                    )
                raise ValueError(
                    f"Log to syslog server {logger.destination} has undefined check name(s) configured: "
                    f"{', '.join(undefined)}"
                )

        # Return the validated data
        return logging

    def get_check_name(self, name: str) -> Check | None:
        """Retrieve a check object by name"""
        # Loop through each check searching for the matching name
        for check in self.checks:
            if check.name == name:
                return check
