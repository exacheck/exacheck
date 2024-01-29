# -*- coding: utf-8 -*-

"""
ExaCheck - ExaBGP Health Checker

Store configuration for logging to a file and/or syslog
"""

from __future__ import annotations

from os import W_OK, access
from pathlib import Path
from typing import Literal, Union

from pydantic import Field, FilePath, NewPath, field_validator, PositiveInt

from ._base import Base


class LogFile(Base):
    """
    Define and store parsed configuration for file based logging
    """

    method: Literal["file"] = Field(
        title="Log Method",
        description="Enable file based logging",
    )

    structured: bool = Field(
        title="Structured Logging",
        description="Use structured logging format",
        default=False,
    )

    destination: Union[NewPath, FilePath] = Field(
        title="Destination File",
        description="The path to the log file to write to",
        default=Path("/tmp/exacheck.log"),
    )

    size: str = Field(
        title="Log File Size",
        description="The maximum size of the log before it is rotated or overwritten",
        default="10MB",
        pattern=r"(?i)^\d+((k|m|g|t)b|b)?$",
    )

    count: PositiveInt = Field(
        title="Log Count",
        description="The number of log file rotations to keep",
        default=5,
    )

    compress: bool = Field(
        title="Compress Logs",
        description="Enable compression for the rotated logs using compression_format",
        default=True,
    )

    compression_format: Literal[
        "gz", "bz2", "xz", "lzma", "tar", "tar.gz", "tar.bz2", "tar.xz", "zip"
    ] = Field(
        title="Compression Format",
        description="If compress is enabled, the log compression format to use for rotated logs",
        default="gz",
    )

    @field_validator("destination")
    # pylint: disable=no-self-argument
    def validate_writeable(cls, destination: FilePath) -> FilePath:
        """Validate that the path to the log file/log file itself is writeable.

        Args:
            path (Path): The path to the log file

        Returns:
            Path: The original path
        """
        # Check if the log file exists already
        if destination.exists():
            # The log exists, check the log file is writable
            if not access(destination, W_OK):
                raise ValueError(
                    f"Log file '{destination}' is not writable; logs cannot be written"
                )

        # Log does not exist, check if the parent path is writable
        if not access(destination.parent, W_OK):
            raise ValueError(
                f"Log file '{destination}' parent directory '{destination.parent}' is not writable; "
                "logs cannot be written"
            )

        # Return the file path
        return destination
