# -*- coding: utf-8 -*-

"""
ExaCheck - ExaBGP Health Checker

Check Method - HTTP
"""

import warnings
from pprint import pformat
from ipaddress import ip_address, IPv6Address

import requests

from ..checkresult import CheckResult
from ..settings.checkargs.httpargs import HTTPArgs
from .http_extra import SNIAdapter
from ._remote import Remote


class HTTP(Remote):
    """
    Run a HTTP health check
    """

    def check_one(self, addr: str) -> CheckResult:
        """
        Run the HTTP health check
        """
        # Set type for MyPy
        self.args: HTTPArgs

        # Create the HTTP/S client session
        session = self._create_session()

        # Send the HTTP request and get response
        try:
            response = self._request(session=session, addr=addr)
        except Exception as exc:
            return CheckResult(success=False, message=f"HTTP request failed: {exc}")

        # Perform validation on the response and get the check result object
        result = self._validate(response=response)

        # Return the check result
        return result

    def _validate(self, response: requests.Response) -> CheckResult:
        """
        Validate the HTTP response received
        """
        # Check if a specific response code is required; if so validate it matches
        if (
            self.args.expected_status
            and response.status_code not in self.args.expected_status
        ):
            return CheckResult(
                success=False,
                message=f"HTTP status code {response.status_code} does not match expected status code(s)",
                error=(
                    f"{response.status_code} not listed in the status codes: "
                    f"{', '.join(map(str, self.args.expected_status))}"
                ),
            )

        # Check if a successful response code is required; if so validate it matches
        if (
            self.args.require_status
            and response.status_code != requests.codes.ok  # pylint: disable=no-member
        ):
            return CheckResult(
                success=False,
                message=f"HTTP status code {response.status_code} does not match expected status code(s)",
                error=f"{response.status_code} could not be confirmed as a valid status code",
            )

        # Check if a response pattern is required; if so validate it matches
        if self.args.response and not self.args.response.search(response.text):
            return CheckResult(
                success=False,
                message="Response pattern not found in response body",
                error=f"The response pattern {self.args.response.pattern!r} did not match the response body",
            )

        # Return a valid check result
        return CheckResult(
            success=True,
            message="HTTP response was valid and passed all checks",
            output=f"HTTP response received in {response.elapsed.total_seconds():.3f} seconds",
        )

    def _request(self, session: requests.Session, addr: str) -> requests.Response:
        """
        Send the HTTP request and return the response
        """
        # Get the URL to make request to
        url = self._create_url(addr=addr)

        # Disable SSL warning if not verifying certificate
        if self.args.url.scheme == "https" and not self.args.verify_ssl:
            warnings.filterwarnings("ignore", message="Unverified HTTPS request")

        # Send the request of the specified type
        response = getattr(session, self.args.request_method.lower())(
            url=url,
            timeout=self.args.http_timeout,
            params=self.args.url.query,
            data=self.args.data,
        )

        # Return the response
        return response

    def _create_session(self) -> requests.Session:
        """
        Create the HTTP/S client session
        """
        # Create the client session
        session = requests.Session()

        # Create the headers for the request
        headers = self._create_headers()

        # Check if the URL is HTTPS and if the request is to a hostname
        if self.args.url.scheme == "https" and "Host" in headers:
            # Mount the SNI adapter for SNI support
            session.mount("https://", SNIAdapter())

        # Set the headers from "headers"
        session.headers.update(headers)

        # Set basic auth credentials if required
        if self.args.url.username and self.args.url.password:
            session.auth = (self.args.url.username, self.args.url.password)

        # Set the SSL verification option if required
        session.verify = self.args.verify_ssl

        return session

    def _create_headers(self) -> dict[str, str]:
        """
        Create the HTTP headers to use for the HTTP request
        """
        self.log.bind(event="debug").debug("Creating HTTP headers")

        # Create headers dict
        headers: dict[str, str] = {}

        # Set user agent header
        headers["User-Agent"] = self.args.user_agent

        # If the address to check is not an IP address set the host header
        if self.args.url.host and not self._is_ip(self.args.url.host):
            # Host isn't an IP; set host header
            headers["Host"] = self.args.url.host

        # Add any extra headers if required
        # As the values may be an integer/float, coerce them into a string
        if self.args.headers:
            for k, val in self.args.headers.items():
                headers[k] = f"{val}"

        # Log the headers that will be used
        self.log.bind(event="datadump").trace(
            "HTTP headers created for client:\n{headers}",
            headers=pformat(headers, indent=4, width=120),
        )

        # Return the headers
        return headers

    def _create_url(self, addr: str) -> str:
        """
        Build the URL that the HTTP health check should be made to
        """
        self.log.bind(event="debug").debug("Creating HTTP URL")

        # Create URL template
        template = "{scheme}://{host}{port}{path}"

        # Set port if defined
        if self.args.url.port:
            port = f":{self.args.url.port}"
        else:
            port = ""

        # Set path if defined
        if self.args.url.path:
            path = self.args.url.path
        else:
            path = "/"

        # If the IP address to test is an IPv6 IP, enclose it with square brackets
        if isinstance(ip_address(addr), IPv6Address):
            addr = f"[{addr}]"

        # Generate the URL
        url = template.format(
            scheme=self.args.url.scheme,
            host=addr,
            port=port,
            path=path,
        )

        # Log the URL that will be used
        self.log.bind(event="debug").debug("HTTP URL created: {url}", url=url)

        # Return the URL
        return url

    # Check if the supplied value is an IP address
    @staticmethod
    def _is_ip(value: str) -> bool:
        """
        Check if the supplied value is an IP address
        """
        try:
            ip_address(value)
            return True
        except ValueError:
            return False
