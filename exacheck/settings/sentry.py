# -*- coding: utf-8 -*-

"""
ExaCheck - ExaBGP Health Checker

Store configuration for Sentry SDK
"""

from pydantic import Field, HttpUrl, NonNegativeFloat

from ._base import Base


class Sentry(Base):
    """
    Configuration for sentry SDK
    """

    dsn: HttpUrl = Field(
        title="DSN",
        description="The DSN to send to send Sentry logs to",
    )

    enabled: bool = Field(
        title="Enable",
        description="If Sentry should be sending events to the specified DSN",
        default=True,
    )

    sample_rate: NonNegativeFloat = Field(
        title="Sample Rate",
        description="The rate at which to sample events for Sentry",
        default=1.0,
        ge=0.0,
    )

    profiles_sample_rate: NonNegativeFloat = Field(
        title="Profile Sample Rate",
        description="If set, the Sentry profiling feature will be enabled at the specified sampling rate",
        default=0.0,
        ge=0.0,
    )

    attach_stacktrace: bool = Field(
        title="Attach Stacktrace",
        description="If Sentry should attach a stacktrace to all messages logged (not only exceptions)",
        default=False,
    )

    include_local_variables: bool = Field(
        title="Include Local Variables",
        description="If Sentry should capture and send local variables to send with events",
        default=True,
    )

    debug: bool = Field(
        title="Debug",
        description="Enable debugging mode for Sentry",
        default=False,
    )
