# -*- coding: utf-8 -*-

"""
ExaCheck - ExaBGP Health Checker

Store internal configuration for ExaCheck
"""

from pydantic import (
    Field,
    PositiveInt,
    PositiveFloat,
)

from ._base import Base


class ExaCheck(Base):
    """
    Configuration for ExaCheck
    """

    live_reload: bool = Field(
        title="Live Reload",
        description="Automatically reload the configuration on any changes",
        default=False,
    )

    monitoring_interval: PositiveInt | PositiveFloat = Field(
        title="Monitoring Interval",
        description=(
            "The interval in seconds between checking the health of each check process/thread and looking for changes "
            "to the configuration file"
        ),
        default=30,
    )
