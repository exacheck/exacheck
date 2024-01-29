# -*- coding: utf-8 -*-

"""
ExaCheck - ExaBGP Health Checker

Base settings model
"""

from abc import ABC
from pprint import pformat

from pydantic import ConfigDict, BaseModel


class Base(ABC, BaseModel):
    """
    Base settings model; all settings inherit from this
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    @property
    def pretty(self) -> str:
        """
        Return a pretty printed version of the settings
        """
        return pformat(self.model_dump(), indent=4, width=120)
