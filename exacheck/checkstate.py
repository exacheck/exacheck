# -*- coding: utf-8 -*-

"""
ExaCheck - ExaBGP Health Checker

Store the current state of a health check instance
"""

from datetime import datetime
from pprint import pformat
from typing import Literal, Optional

from pydantic import ConfigDict, BaseModel, Field, PositiveInt

from .checkresult import CheckResult


class CheckState(BaseModel):
    """
    Store the current state information for a health check
    """

    state: Literal["up", "down", "rising", "falling", "disabled", "startup"] = Field(
        title="Check State",
        description="The current state of the health check",
    )

    advertised: bool = Field(
        title="Advertised",
        description="Whether the prefixes are currently being advertised",
    )

    last_result: Optional[CheckResult] = Field(
        title="Last Check Result",
        description="The CheckResult object from the last health check",
        default=None,
    )

    down_since: Optional[datetime] = Field(
        title="Down Since",
        description="The time the health check entered the down state",
        default=None,
    )

    up_since: Optional[datetime] = Field(
        title="Up Since",
        description="The time the health check entered the up state",
        default=None,
    )

    rise: Optional[PositiveInt] = Field(
        title="Rise Count",
        description="If the service is not in an 'up' state, the number of consecutive successful health checks",
        default=None,
    )

    fall: Optional[PositiveInt] = Field(
        title="Fall Count",
        description="If the service is not in a 'down' state, the number of consecutive failed health checks",
        default=None,
    )
    model_config = ConfigDict(extra="forbid", frozen=True)

    @property
    def pretty(self) -> str:
        """
        Return a pretty printed version of the current health check state
        """
        return pformat(self.model_dump(), indent=4, width=120)
