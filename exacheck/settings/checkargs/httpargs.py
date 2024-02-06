# -*- coding: utf-8 -*-

"""
ExaCheck - ExaBGP Health Checker

HTTP health check arguments
"""

import re
from typing import Literal, Optional, Pattern
from urllib.parse import urlparse

from pydantic import (
    AnyHttpUrl,
    Field,
    model_validator,
    field_validator,
    PositiveInt,
    PositiveFloat,
)
from pydantic_core.core_schema import ValidationInfo

from ...__version__ import __version__
from ._remote import Remote


class HTTPArgs(Remote):
    """
    Model for HTTP check arguments
    """

    method: Literal["http"] = Field(
        title="HTTP Check Method",
        description="Send a HTTP or HTTPS request to a web server and optionally perform various validation",
    )

    host: Optional[str] = Field(  # type: ignore
        title="Hostname/IP Address",
        description="The hostname or IP address the health check will be performed against",
        default=None,
    )

    url: AnyHttpUrl = Field(
        title="URL",
        description="The HTTP/HTTPS URL to check",
    )

    response: Optional[Pattern] = Field(
        title="Response Pattern",
        description="The regular expression to match in the response body of the HTTP request",
        default=None,
    )

    expected_status: Optional[list[PositiveInt]] = Field(
        title="Expected Status Code",
        description="One or more HTTP status codes that indicate a successful response",
        default=None,
    )

    require_status: bool = Field(
        title="Require 2xx Status Code",
        description="Require a 2xx HTTP status code to indicate a successful response",
        default=True,
    )

    http_timeout: PositiveInt | PositiveFloat = Field(
        title="HTTP Timeout",
        description="The timeout for the HTTP request",
        default=5,
    )

    user_agent: str = Field(
        title="User Agent",
        description="The user agent to send with the HTTP request",
        default=f"ExaCheck HTTP Health Check [v{__version__}]",
    )

    headers: Optional[dict[str, str | int | float]] = Field(
        title="Headers",
        description="Any additional HTTP headers to send with the HTTP request",
        default=None,
    )

    verify_ssl: bool = Field(
        title="Verify SSL",
        description="If making a request to an HTTPS URL, verify the SSL certificate",
        default=False,
    )

    request_method: Literal["GET", "POST", "PUT", "DELETE", "HEAD", "OPTIONS"] = Field(
        title="Request Method",
        description="The method for the HTTP request",
        default="GET",
    )

    data: Optional[dict[str, str]] = Field(
        title="Request Data",
        description="The request data to send for POST requests",
        default=None,
    )

    @field_validator("http_timeout")
    # pylint: disable=no-self-argument
    def validate_http_timeout(
        cls, http_timeout: int | float, values: ValidationInfo
    ) -> int | float:
        """
        Ensure that the HTTP timeout is a valid value
        """
        # Check if the HTTP timeout is higher than the check timeout
        if http_timeout > values.data["timeout"]:
            raise ValueError(
                f"Invalid HTTP timeout '{http_timeout}' defined for check: "
                f"It must be less than the check timeout of {values.data['timeout']} seconds"
            )

        # Return the HTTP timeout
        return http_timeout

    @field_validator("headers")
    # pylint: disable=no-self-argument
    def validate_header_names(cls, headers: dict[str, str]) -> dict[str, str]:
        """
        Ensure that the header names are valid
        """
        # Make regex to match the valid header name characters
        valid_header_name = re.compile(r"^([\w+\-\=]+)$")

        # Loop over each header and ensure that the header name is valid
        for header_name in headers:
            if not valid_header_name.match(header_name):
                raise ValueError(
                    f"Invalid header name '{header_name}' defined for check: "
                    "Header names must only contain alphanumeric characters and dashes"
                )

        # Return the validated headers
        return headers

    @model_validator(mode="before")
    # pylint: disable=no-self-argument
    def set_require_status(cls, values: dict) -> dict:
        """
        If expected_status has a value set require_status must be set to false as the expected status code
        may not be a 2xx code.
        """
        # Test if require_status was set to true specifically
        if "require_status" in values and values["require_status"] is True:
            raise ValueError(
                "The require_status value cannot be set to true when using expected_status"
            )

        # Test if the expected_status value is provided
        if "expected_status" in values and values["expected_status"] is not None:
            # Set require_status false
            values["require_status"] = False

        # Return the new dict
        return values

    @model_validator(mode="before")
    # pylint: disable=no-self-argument
    def set_host(cls, values: dict) -> dict:
        """
        If no "host" value is provided, set it to the hostname of the URL
        """
        # Only proceed if the URL is provided
        if "url" not in values or values["url"] is None:
            return values

        # Skip if a host value was provided
        if "host" in values and values["host"] is not None:
            return values

        # Attempt to parse the URL
        try:
            url = urlparse(values["url"])
        except ValueError:
            raise ValueError(
                f"Could not parse the supplied URL '{values['url']}' to retrieve hostname; "
                "specify the host parameter manually"
            )

        # Set the host for the URL
        values["host"] = url.hostname

        # Return the values
        return values

    @model_validator(mode="before")
    # pylint: disable=no-self-argument
    def set_request_method_case(cls, values: dict) -> dict:
        """
        Set the HTTP method to uppercase
        """
        # Check if a HTTP method was defined by the user
        if "request_method" not in values or values["request_method"] is None:
            # Nothing to do
            return values

        # Set the HTTP method to uppercase
        values["request_method"] = values["request_method"].upper()

        # Return the values
        return values

    @field_validator("data")
    def validate_data(
        cls, data: dict[str, str], values: ValidationInfo
    ) -> dict[str, str]:
        """
        Validate the HTTP request type supports supplying data
        """
        # Make sure the HTTP method is POST
        if values.data["request_method"] != "POST":
            raise ValueError(
                f"Cannot supply data for HTTP request method {values.data['request_method']}"
            )

        # Return the post data
        return data
