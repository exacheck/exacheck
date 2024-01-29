# -*- coding: utf-8 -*-

"""
ExaCheck - ExaBGP Health Checker

Store a single health check result
"""

from datetime import datetime
from pprint import pformat
from typing import Optional, Any

from pydantic import ConfigDict, BaseModel, Field, field_validator


class CheckResult(BaseModel):
    """
    Store the health check result and other information relating to the check
    """

    success: bool = Field(
        title="Check Result",
        description="The result of the health check",
    )

    message: Optional[str] = Field(
        title="Check Message",
        description="A message describing the result of the check",
    )

    output: str | None = Field(
        title="Check Output",
        description="Any output from the check",
        default=None,
    )

    error: str | None = Field(
        title="Check Error",
        description="If the check resulted in a handled exception or error, the error data",
        default=None,
    )

    exception: Any | None = Field(
        title="Check Exception",
        description="The exception that was raised during the check (if any)",
        default=None,
    )

    date: datetime = Field(
        title="Check Date",
        description="The date and time the check was performed",
        default=datetime.now(),
    )

    disabled: bool = Field(
        title="Check Disabled",
        description="If the check has been disabled by a disable file",
        default=False,
    )

    # Prevent unknown data
    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("exception")
    # pylint: disable=no-self-argument
    def validate_exception(cls, exception: Exception | None) -> Exception | None:
        """
        Validate that if an exception is provided that it really is an exception
        """
        # Skip if no exception is provided
        if exception is None:
            return None

        # Ensure the exception is really an exception
        if not isinstance(exception, Exception):
            raise ValueError(
                "The exception provided is not actually an instance of the Exception class"
            )

        # Return the exception value
        return exception

    @property
    def pretty(self) -> str:
        """
        Return a pretty printed version of the health check result
        """
        return pformat(self.model_dump(), indent=4, width=120)
