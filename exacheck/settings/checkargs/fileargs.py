# -*- coding: utf-8 -*-

"""
ExaCheck - ExaBGP Health Checker

File health check arguments
"""

from os import W_OK, access
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator

from ._base import Base


class FileArgs(Base):
    """
    Model for file check arguments
    """

    method: Literal["file"] = Field(
        title="File Check Method",
        description="Test if a file exists or doesn't exist",
    )

    path: Path = Field(
        title="File Path",
        description="The path to the file that should be checked",
    )

    exists: bool = Field(
        title="File Exists",
        description="If set to false the check will fail if the file exists",
        default=True,
    )

    @field_validator("path")
    # pylint: disable=no-self-argument
    def validate_path(cls, path: Path) -> Path:
        """Validate that the file parent directory can be read

        Args:
            path (Path): The path to the file

        Returns:
            Path: The original path
        """
        # Try to access the parent directory
        if not access(path.parent, W_OK):
            raise ValueError(
                f"File path '{path}' parent directory '{path.parent}' is not readable; the health check cannot work"
            )

        # Return the path
        return path
