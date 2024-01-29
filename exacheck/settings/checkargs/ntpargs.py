# -*- coding: utf-8 -*-

"""
ExaCheck - ExaBGP Health Checker

NTP health check arguments
"""

from typing import Literal, Optional

from pydantic import Field, field_validator, PositiveInt, PositiveFloat, NonNegativeInt
from pydantic_core.core_schema import ValidationInfo

from ._remote import Remote


class NTPArgs(Remote):
    """
    Model for NTP check arguments
    """

    method: Literal["ntp"] = Field(
        title="NTP Check Method",
        description="Send a NTP query to a NTP server and validate the response is within the configured thresholds",
    )

    port: PositiveInt = Field(
        title="Port",
        description="The port to send the NTP query to",
        default=123,
        le=65535,
    )

    version: Literal[2, 3] = Field(
        title="NTP Version",
        description="The NTP version to use for the NTP request",
        default=3,
    )

    ntp_timeout: PositiveInt | PositiveFloat = Field(
        title="NTP Timeout",
        description="The timeout for the NTP request",
        default=5,
    )

    max_offset: Optional[PositiveInt | PositiveFloat] = Field(
        title="Maximum NTP Offset",
        description="The maximum offset +/- allowable in seconds before the server is marked as unhealthy",
        default=None,
    )

    max_stratum: Optional[NonNegativeInt] = Field(
        title="Maximum NTP Stratum",
        description="The maximum stratum value before the server is marked as unhealthy",
        default=None,
        le=15,
    )

    @field_validator("ntp_timeout")
    # pylint: disable=no-self-argument
    def validate_ntp_timeout(
        cls, ntp_timeout: int | float, values: ValidationInfo
    ) -> int | float:
        """
        Ensure that the NTP timeout is a valid value
        """
        # Check if the NTP timeout is higher than the check timeout
        if ntp_timeout > values.data["timeout"]:
            raise ValueError(
                f"Invalid NTP timeout '{ntp_timeout}' defined for check: "
                f"It must be less than the check timeout of {values.data['timeout']} seconds"
            )

        # Return the NTP timeout
        return ntp_timeout
