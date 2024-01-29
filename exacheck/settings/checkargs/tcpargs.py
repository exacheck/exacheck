# -*- coding: utf-8 -*-

"""
ExaCheck - ExaBGP Health Checker

TCP health check arguments
"""

from typing import Literal

from pydantic import Field, field_validator, PositiveInt, PositiveFloat
from pydantic_core.core_schema import ValidationInfo

from ._remote import Remote


class TCPArgs(Remote):
    """
    Model for TCP check arguments
    """

    method: Literal["tcp"] = Field(
        title="TCO Check Method",
        description="Open a TCP connection to a host/port and ensure it is successful",
    )

    port: PositiveInt = Field(
        title="Port",
        description="The port to attempt connecting to",
        le=65535,
    )

    tcp_timeout: PositiveInt | PositiveFloat = Field(
        title="TCP Timeout",
        description="The timeout for the TCP connection",
        default=5,
    )

    @field_validator("tcp_timeout")
    # pylint: disable=no-self-argument
    def validate_tcp_timeout(
        cls, tcp_timeout: int | float, values: ValidationInfo
    ) -> int | float:
        """
        Ensure that the TCP timeout is a valid value
        """
        # Check if the TCP timeout is higher than the check timeout
        if tcp_timeout > values.data["timeout"]:
            raise ValueError(
                f"Invalid TCP timeout '{tcp_timeout}' defined for check: "
                f"It must be less than the check timeout of {values.data['timeout']} seconds"
            )

        # Return the TCP timeout
        return tcp_timeout
