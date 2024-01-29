# -*- coding: utf-8 -*-

"""
ExaCheck - ExaBGP Health Checker

Base check model for any checks that connect to a remote host
"""

from abc import ABC
from ipaddress import IPv4Address, IPv6Address, ip_address
from typing import Literal

from pydantic import Field, field_validator
from pydantic_core.core_schema import ValidationInfo

from ._base import Base


class Remote(Base, ABC):
    """
    Base model for remote checks which accept a hostname and address family
    """

    host: str = Field(
        title="Hostname/IP Address",
        description="The hostname or IP address the health check will be performed against",
    )

    address_family: Literal["ipv4", "ipv6"] | None = Field(
        title="Address Family",
        description="If checking a hostname, force the check to the specified address family",
        default=None,
    )

    all_valid: bool = Field(
        title="All IP Addresses Valid",
        description=(
            "If checking a hostname, require all IP addresses from the DNS response to pass the health check. "
            "If False, any single IP address that returns a successful check will return the service as healthy."
        ),
        default=False,
    )

    @field_validator("address_family")
    def validate_address_family(  # NOSONAR pylint: disable=no-self-argument
        cls, address_family: Literal["ipv4", "ipv6"], values: ValidationInfo
    ) -> str:
        """
        Validate the address family
        """
        # Try casting the host into an IP address
        try:
            host = ip_address(values.data["host"])
        # pylint: disable=broad-except
        except Exception:
            # The host is not an IP address; nothing to check
            return address_family

        # If the host is an IP address, check that the address family matches
        if isinstance(host, IPv4Address) and address_family == "ipv6":
            raise ValueError("Address family must be IPv4 when querying an IPv4 host")
        if isinstance(host, IPv6Address) and address_family == "ipv4":
            raise ValueError("Address family must be IPv6 when querying an IPv6 host")

        # Return the address family
        return address_family
