# -*- coding: utf-8 -*-

"""
ExaCheck - ExaBGP Health Checker

ICMP health check arguments
"""

from typing import Literal, Optional

from pydantic import (
    Field,
    field_validator,
    PositiveInt,
    PositiveFloat,
    NonNegativeInt,
    NonNegativeFloat,
)
from pydantic_core.core_schema import ValidationInfo

from ._remote import Remote


class ICMPArgs(Remote):
    """
    Model for ICMP check arguments
    """

    method: Literal["icmp"] = Field(
        title="ICMP Check Method",
        description="Send ICMP ping packets and ensure the responses are within the configured thresholds",
    )

    count: PositiveInt = Field(
        title="Count",
        description="The number of ICMP packets to send",
        default=3,
    )

    interval: NonNegativeInt | NonNegativeFloat = Field(
        title="Interval",
        description="The interval in seconds between ICMP packets",
        default=0.25,
    )

    icmp_timeout: PositiveInt | PositiveFloat = Field(
        title="ICMP Timeout",
        description="The timeout for each ICMP packet in seconds",
        default=2,
    )

    privileged: bool = Field(
        title="Privileged Mode",
        description="Send ICMP packets in privileged mode (requires root)",
        default=False,
    )

    max_loss: NonNegativeInt = Field(
        title="Maximum Packets Lost",
        description="The maximum number of packets that can be lost before the check is marked as failed",
        default=0,
    )

    max_latency: Optional[PositiveInt | PositiveFloat] = Field(
        title="Maximum Latency",
        description="The highest maximum latency in milliseconds allowed before the check is marked as failed",
        default=None,
    )

    max_jitter: Optional[PositiveInt | PositiveFloat] = Field(
        title="Maximum Jitter",
        description="The maximum jitter in milliseconds allowed before the check is marked as failed",
        default=None,
    )

    @field_validator("count")
    # pylint: disable=no-self-argument
    def validate_count(cls, count: int, values: ValidationInfo) -> int | float:
        """
        Ensure that the count is a valid value

        The assumption is made that the interval will be 1 second; if the interval is higher
        it will be validated as a part of the interval validation
        """
        # Check that count would be below the check timeout
        if count > values.data["timeout"]:
            raise ValueError(
                "Invalid count defined for check: The count must be lower than the check timeout"
            )

        # Return the interval
        return count

    @field_validator("interval")
    # pylint: disable=no-self-argument
    def validate_interval(
        cls, interval: int | float, values: ValidationInfo
    ) -> int | float:
        """
        Ensure that the interval and count is a valid value
        """
        # Get the count
        count: int = values.data["count"] if "count" in values.data else 3

        # Check that count * interval would be below the check timeout
        if (count * interval) > values.data["timeout"]:
            raise ValueError(
                f"Invalid interval '{interval}' or count '{count}' defined for check: "
                f"The total time must be lower than the configured check timeout of {values.data['timeout']} seconds."
            )

        # Return the interval
        return interval

    @field_validator("icmp_timeout")
    # pylint: disable=no-self-argument
    def validate_icmp_timeout(
        cls, icmp_timeout: int | float, values: ValidationInfo
    ) -> int | float:
        """
        Ensure that the ICMP timeout is a valid value

        This is calculate by multiplying the count by the ICMP timeout and checking that the result
        is less than the check timeout
        """
        # Get the variables
        count: int = values.data["count"] if "count" in values.data else 3
        interval: int | float = (
            values.data["interval"] if "interval" in values.data else 1
        )

        # Get the maximum possible time that the check could run if all requests timed out
        maximum_runtime = (count * icmp_timeout) + (interval * (count - 1))

        # Check if the maximum run time is higher than the timeout
        if maximum_runtime > values.data["timeout"]:
            raise ValueError(
                f"Invalid ICMP timeout '{icmp_timeout}' defined for check: "
                f"It must be less than the check timeout of {values.data['timeout']} seconds. "
                "The configured timeouts would result in the check taking too long in a worst case scenario."
            )

        # Return the ICMP timeout
        return icmp_timeout

    @field_validator("max_loss")
    # pylint: disable=no-self-argument
    def validate_max_loss(cls, max_loss: int, values: ValidationInfo) -> int:
        """
        Validate the max loss value is less than the number of packets being sent
        """
        # Get the number of packets to send
        count: int = values.data["count"] if "count" in values.data else 3

        # Verify that the max loss is less than number of packets being sent
        if max_loss >= count:
            raise ValueError(
                f"Invalid max loss '{max_loss}' defined for check: "
                f"It must be less than the number of packets being sent ({count})"
            )

        # Return the max loss
        return max_loss

    @field_validator("max_latency")
    # pylint: disable=no-self-argument
    def validate_max_latency(
        cls, max_latency: int | float, values: ValidationInfo
    ) -> int | float:
        """
        Validate the maximum latency allowed is less than the ICMP timeout
        """
        # Get the ICMP timeout
        timeout: int | float = (
            values.data["icmp_timeout"] if "icmp_timeout" in values.data else 2
        )

        # Verify that the max latency is less than the ICMP timeout
        if max_latency >= timeout:
            raise ValueError(
                f"Invalid max latency '{max_latency}' defined for check: "
                f"It must be less than the ICMP timeout ({timeout})"
            )

        # Return the max latency
        return max_latency

    @field_validator("max_jitter")
    # pylint: disable=no-self-argument
    def validate_max_jitter(
        cls, max_jitter: int | float, values: ValidationInfo
    ) -> int | float:
        """
        If the maximum jitter value is set, require that at least two packets are sent
        """
        # Get the count
        count: int = values.data["count"]

        # Verify more than 1 packet is being sent
        if count == 1:
            raise ValueError(
                f"Invalid max jitter '{max_jitter}' defined for check: "
                f"2 or more packets must be sent to calculate jitter"
            )

        # Return the max jitter
        return max_jitter
