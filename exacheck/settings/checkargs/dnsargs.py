# -*- coding: utf-8 -*-

"""
ExaCheck - ExaBGP Health Checker

DNS health check arguments
"""

from typing import Literal, Optional, Pattern

from pydantic import Field, model_validator, field_validator, PositiveInt, PositiveFloat
from pydantic_core.core_schema import ValidationInfo

from ._remote import Remote


class DNSArgs(Remote):
    """
    Model for DNS check arguments
    """

    method: Literal["dns"] = Field(
        title="DNS Check Method",
        description="Send a query to a DNS server and optionally validate the response",
    )

    query: str = Field(
        title="Query Name",
        description="The name to query",
    )

    query_type: Literal[
        "a", "aaaa", "any", "cname", "mx", "ns", "ptr", "soa", "srv", "txt"
    ] = Field(
        title="Query Type",
        description="The type of DNS query to send",
        default="soa",
    )

    response: Optional[Pattern] = Field(
        title="Response Pattern",
        description="The regular expression to match in the answers received from the DNS server",
        default=None,
    )

    tcp: bool = Field(
        title="Use TCP",
        description="Send the DNS query using TCP rather than UDP",
        default=False,
    )

    port: PositiveInt = Field(
        title="Port",
        description="The port to send the DNS query to",
        default=53,
        le=65535,
    )

    dns_timeout: PositiveInt | PositiveFloat = Field(
        title="DNS Timeout",
        description="The timeout for the DNS request",
        default=5,
    )

    require_resolve: bool = Field(
        title="Require Resolve",
        description="Require the server to response with an answer and not a value such as NXDOMAIN or SRVFAIL",
        default=True,
    )

    @model_validator(mode="before")
    # pylint: disable=no-self-argument
    def set_protocol(cls, values: dict) -> dict:
        """
        Convert the protocol to lowercase
        """
        if "protocol" in values and isinstance(values["protocol"], str):
            values["protocol"] = values["protocol"].lower()
        return values

    @model_validator(mode="before")
    # pylint: disable=no-self-argument
    def set_query_type(cls, values: dict) -> dict:
        """
        Convert the query type to lowercase
        """
        if "query_type" in values and isinstance(values["query_type"], str):
            values["query_type"] = values["query_type"].lower()
        return values

    @field_validator("dns_timeout")
    # pylint: disable=no-self-argument
    def validate_dns_timeout(
        cls, dns_timeout: int | float, values: ValidationInfo
    ) -> int | float:
        """
        Ensure that the DNS timeout is a valid value
        """
        # Check if the DNS timeout is higher than the check timeout
        if dns_timeout > values.data["timeout"]:
            raise ValueError(
                f"Invalid DNS timeout '{dns_timeout}' defined for check: "
                f"It must be less than the check timeout of {values.data['timeout']} seconds"
            )

        # Return the DNS timeout
        return dns_timeout

    @field_validator("require_resolve")
    # pylint: disable=no-self-argument
    def validate_require_resolve(
        cls, require_resolve: bool, values: ValidationInfo
    ) -> bool:
        """
        Validate that require_resolve is set to true if there is a response pattern that needs to be matched
        for the check to be successful
        """
        # Check if a response pattern is defined
        if "response" in values.data and values.data["response"] is not None:
            # Check if require_resolve is false
            if not require_resolve:
                raise ValueError(
                    "Invalid require_resolve value defined for check: "
                    "It must be set to true if a response pattern is defined"
                )

        # Return the require_resolve value
        return require_resolve
