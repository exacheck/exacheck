# -*- coding: utf-8 -*-

"""
ExaCheck - ExaBGP Health Checker

Base check arguments - common to all check types
"""

from abc import ABC
from pprint import pformat

from pydantic import ConfigDict, BaseModel, Field, PositiveInt


class Base(ABC, BaseModel):
    """
    Base model for check arguments
    """

    timeout: PositiveInt = Field(
        title="General Check Timeout",
        description="The total timeout in seconds for the check to execute",
        default=10,
    )
    model_config = ConfigDict(extra="forbid", frozen=True, title="Check Arguments")

    @property
    def pretty(self) -> str:
        """
        Return a pretty printed version of the settings
        """
        return pformat(self.model_dump(), indent=4, width=120)
