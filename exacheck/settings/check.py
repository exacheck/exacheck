# -*- coding: utf-8 -*-

"""
ExaCheck - ExaBGP Health Checker

Store configuration for an individual health check
"""

import re

from ipaddress import (
    IPv4Address,
    IPv4Network,
    IPv6Address,
    IPv6Network,
)
from pathlib import Path
from typing import Literal, Optional

from pydantic import (
    Field,
    model_validator,
    field_validator,
    IPvAnyNetwork,
    IPvAnyAddress,
    PositiveInt,
    PositiveFloat,
    NonNegativeInt,
)
from pydantic_core.core_schema import ValidationInfo
from typing_extensions import Annotated

from ._base import Base
from .checkargs.dnsargs import DNSArgs
from .checkargs.fileargs import FileArgs
from .checkargs.httpargs import HTTPArgs
from .checkargs.icmpargs import ICMPArgs
from .checkargs.ntpargs import NTPArgs
from .checkargs.shellargs import ShellArgs
from .checkargs.tcpargs import TCPArgs


class Check(Base):
    """
    The common base check method
    """

    name: str = Field(
        title="Check Name",
        description="The name of the check",
        pattern=r"^[^\"']+$",
    )

    description: Optional[str] = Field(
        title="Check Description",
        description="An optional description for the health check (not parsed)",
        default=None,
    )

    args: DNSArgs | FileArgs | HTTPArgs | ICMPArgs | NTPArgs | ShellArgs | TCPArgs = (
        Field(
            title="Check Arguments",
            description="The arguments for the health check check",
            discriminator="method",
        )
    )

    path_id: Optional[
        Annotated[NonNegativeInt, Field(le=4294967295, strict=True)] | IPv4Address
    ] = Field(
        title="Path ID",
        description="The path ID to announce with the route",
        default=None,
    )

    prefixes: list[IPvAnyNetwork] = Field(
        title="Prefixes",
        description="The list of IP addresses or prefixes that will be advertised",
    )

    nexthop: IPvAnyAddress | Literal["self"] = Field(
        title="Next Hop",
        description="The next-hop address for the prefix that will be advertised",
    )

    metric: Optional[NonNegativeInt] = Field(
        title="Metric",
        description="The metric to advertise with the route",
        le=4294967295,
        default=None,
    )

    metric_down: Optional[NonNegativeInt] = Field(
        title="Down Metric",
        description="If the health check fails, continue to announce the route but with this metric",
        le=4294967295,
        default=None,
    )

    local_preference: Optional[NonNegativeInt] = Field(
        title="Local Preference",
        description="The local preference to announce with the route",
        le=4294967295,
        default=None,
    )

    disable: Optional[Path] = Field(
        title="Disable File",
        description="If the file exists, the route will be withdrawn and the check will be disabled",
        default=None,
    )

    neighbors: Optional[list[IPvAnyAddress]] = Field(
        title="Neighbors",
        description="Filter the route to only be announced to the specified neighbors",
        default=None,
    )

    communities: Optional[list[str]] = Field(
        title="BGP Communities",
        description="Announce the route with the specified BGP communities",
        default=None,
    )

    as_path: Optional[
        Annotated[PositiveInt, Field(le=4294967294, strict=True)] | str
    ] = Field(
        title="AS Path",
        description="Announce the route with the specified AS path",
        default=None,
    )

    interval: PositiveInt | PositiveFloat = Field(
        title="Check Interval",
        description="The interval in seconds between checks",
        default=15,
    )

    rise: NonNegativeInt = Field(
        title="Rise",
        description="The number of consecutive successful checks required to mark the check as healthy",
        default=3,
    )

    fall: NonNegativeInt = Field(
        title="Fall",
        description="The number of consecutive failed checks required to mark the check as failed",
        default=3,
    )

    @model_validator(mode="before")
    # pylint: disable=no-self-argument
    def set_prefixes_list(cls, values: dict) -> dict:
        """
        Set the list of prefixes to advertise to a list if it is not already
        """
        # Ensure that the prefixes are defined
        if "prefixes" not in values or values["prefixes"] is None:
            raise ValueError(
                f"One or more prefixes to advertise must be defined for check {values['name']}"
            )

        # Ensure that the prefixes are a list
        if not isinstance(values["prefixes"], list):
            # Create list of prefixes
            prefixes: list[str] = [values["prefixes"]]
            # Set the prefixes to the list generated
            values["prefixes"] = prefixes

        # Return the correctly set values
        return values

    @model_validator(mode="before")
    # pylint: disable=no-self-argument
    def set_path_id(cls, values: dict) -> dict:
        """
        If the path ID attribute is defined and it is a string, convert to an IPv4Address object
        """
        # Skip processing if not defined
        if "path_id" not in values or values["path_id"] is None:
            return values

        # Check if the path ID is a string
        if isinstance(values["path_id"], str):
            try:
                values["path_id"] = IPv4Address(values["path_id"])
            except Exception as exc:
                raise ValueError(
                    f"Invalid path ID '{values['path_id']}' for check {values['name']} defined: "
                    "It must be an integer in the range 0-4294967295 or an IPv4 address"
                ) from exc

        # Return the path ID
        return values

    @model_validator(mode="before")
    # pylint: disable=no-self-argument
    def validate_communities_string(cls, values: dict) -> dict:
        """
        If the communities attribute is set, ensure that it is a string or list of strings
        """
        # Skip processing if not defined
        if "communities" not in values or values["communities"] is None:
            return values

        # Check if the communities is not a list; if not then convert to a list
        if not isinstance(values["communities"], list):
            # Convert to a list
            values["communities"] = [values["communities"]]

        # Loop over each community
        for community in values["communities"]:
            # Raise error if the community is not a string
            if not isinstance(community, str):
                raise ValueError(
                    f"BGP community {community} for check {values['name']} must be a string; current type is "
                    f"{type(community).__name__}"
                )

        # Return the AS path
        return values

    @model_validator(mode="before")
    # pylint: disable=no-self-argument
    def set_as_path(cls, values: dict) -> dict:
        """
        If the AS path attribute is set, convert to a string as it may be an integer
        """
        # Skip processing if not defined
        if "as_path" not in values or values["as_path"] is None:
            return values

        # Check if the AS path is an integer
        if isinstance(values["as_path"], int):
            # Convert to a string
            values["as_path"] = f"{values['as_path']}"

        # Return the AS path
        return values

    @field_validator("as_path")
    # pylint: disable=no-self-argument
    def validate_as_path(cls, as_path: str, values: ValidationInfo) -> str:
        """
        Validate the AS path attribute
        """
        # Loop over each AS in the list
        for asn in as_path.split():
            # Convert the ASN to an integer
            asn_int = int(asn)
            # Make sure the AS is within range
            if asn_int < 1 or asn_int > 4294967295:
                raise ValueError(
                    f"Invalid AS number '{asn}' defined in the AS path for check {values.data['name']}: "
                    "It must be an integer in the range 1-4294967295"
                )

        # Return the AS path
        return as_path

    @field_validator("communities")
    # pylint: disable=no-self-argument
    def validate_communities(cls, communities: list[str]) -> list[str]:
        """
        Validate BGP communities
        """
        # Create community regex
        community_regex = re.compile(
            r"^(\d+:\d+(:\d+)?|no-export|no-advertise|no-export-subconfed|internet|local-as)$"
        )

        # Loop over each community
        for community in communities:
            # Validate the community matches pattern
            if not community_regex.match(community):
                raise ValueError(f"BGP community {community} is not valid")

        # Return the communities
        return communities

    @field_validator("nexthop")
    # pylint: disable=no-self-argument
    def validate_nexthop(
        cls,
        nexthop: IPv4Address | IPv6Address | Literal["self"],
        values: ValidationInfo,
    ) -> IPv4Address | IPv6Address | Literal["self"]:
        """
        Validate the next hop attribute matches the prefix address families
        """
        # Check if the next hop attribute is self
        if nexthop == "self":
            # Return without further validation as the prefixes cannot be validated
            return nexthop

        # Check if the next hop is IPv4 and any prefixes are not IPv4
        if isinstance(nexthop, IPv4Address) and not all(
            isinstance(prefix, IPv4Network) for prefix in values.data["prefixes"]
        ):
            raise ValueError(
                f"Next hop address '{nexthop}' defined for check {values.data['name']} must match the address family "
                "of the prefixes that are to be advertised (the prefixes must be IPv4 only if the next hop is IPv4)"
            )

        # Check if the next hop is IPv6 and any prefixes are not IPv6
        if isinstance(nexthop, IPv6Address) and not all(
            isinstance(prefix, IPv6Network) for prefix in values.data["prefixes"]
        ):
            raise ValueError(
                f"Next hop address '{nexthop}' defined for check {values.data['name']} must match the address family "
                "of the prefixes that are to be advertised (the prefixes must be IPv6 only if the next hop is IPv6)"
            )

        # Return the next hop
        return nexthop
