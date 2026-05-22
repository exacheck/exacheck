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

    # Concrete subclasses narrow this to ``Literal["dns"]`` etc.; declaring it
    # here means consumers can read ``args.method`` without needing the static
    # type to be the dynamically-built discriminated union.
    method: str = Field(
        title="Check Method",
        description="The check method type identifier",
    )
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
