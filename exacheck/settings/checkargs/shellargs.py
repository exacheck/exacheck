# -*- coding: utf-8 -*-

"""
ExaCheck - ExaBGP Health Checker

Shell command health check arguments
"""

from typing import Literal, Optional

from pydantic import Field

from ._base import Base


class ShellArgs(Base):
    """
    Model for shell command check arguments
    """

    method: Literal["shell"] = Field(
        title="Shell Check Method",
        description="Run a script to determine if a service is healthy or not based on the exit code",
    )

    command: str = Field(
        title="Shell Command",
        description="The shell command to run for the health check",
    )

    environment: Optional[dict[str, str]] = Field(
        title="Environment Variables",
        description="Environment variables to set when running the command",
        default=None,
    )
