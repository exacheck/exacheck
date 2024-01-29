# -*- coding: utf-8 -*-

"""
ExaCheck - ExaBGP Health Checker

Store configuration for logging to a file and/or syslog
"""

from __future__ import annotations

import re
import os
import stat
from pathlib import Path
from ipaddress import ip_address
from typing import Literal

from pydantic import Field, field_validator, PositiveInt, FilePath

from ._base import Base


class Syslog(Base):
    """
    Define and store parsed configuration for syslog based logging
    """

    method: Literal["syslog"] = Field(
        title="Log Method",
        description="Enable logging to a syslog server hostname, IP address or socket",
    )

    structured: bool = Field(
        title="Structured Logging",
        description="Use structured logging format",
        default=True,
    )

    destination: Literal["/dev/log"] | FilePath | str = Field(
        title="Syslog Destination",
        description="The destination IP address or hostname to send messages to",
        default="/dev/log",
    )

    port: PositiveInt = Field(
        title="Syslog Port",
        description="The port to send syslog messages to",
        default=514,
        le=65535,
    )

    protocol: Literal["tcp", "udp"] = Field(
        title="Syslog Protocol",
        description="The protocol to send syslog messages with",
        default="udp",
    )

    @field_validator("destination")
    # pylint: disable=no-self-argument
    def validate_destination(
        cls, destination: Literal["/dev/log"] | str
    ) -> Literal["/dev/log"] | str:
        """
        Perform very basic validation for the destination address to send syslog messages
        """
        # Skip validation for "/dev/log"
        if destination == "/dev/log":
            return destination

        # Check if destination is an IPv4 or IPv6 address
        try:
            ip_address(destination)
        except ValueError:
            # Test if it is a path to a socket
            if os.path.exists(destination):
                # Path exists, make sure it is a socket
                mode = os.stat(destination).st_mode
                if not stat.S_ISSOCK(mode):
                    raise ValueError(
                        f"Logging destination {destination} is not a socket"
                    )

                # Convert the destination into a file path
                destination = Path(destination).resolve()
                assert isinstance(destination, Path)

                # Make sure the socket is writable
                if not os.access(destination, os.W_OK):
                    raise ValueError(
                        f"Destination logging socket {destination} is not writable"
                    )

            # Test if it is a hostname
            else:
                host_regex = re.compile(
                    r"^[a-zA-Z0-9][a-zA-Z0-9\-]{0,61}[a-zA-Z0-9](\.[a-zA-Z0-9][a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])*$"
                )
                if not host_regex.match(destination):
                    raise ValueError(  # pylint: disable=raise-missing-from
                        f"Invalid destination address '{destination}' for syslog messages"
                    )

        # Return as it seems to be valid enough to use
        return destination
