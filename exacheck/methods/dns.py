# -*- coding: utf-8 -*-

"""
ExaCheck - ExaBGP Health Checker

Check Method - DNS
"""

from re import Pattern

import dns.exception as dns_exceptions
from dns import rdatatype, resolver
from dns.rrset import RRset

from ..checkresult import CheckResult
from ..settings.checkargs.dnsargs import DNSArgs
from ._remote import Remote


# pylint: disable=too-few-public-methods,too-many-instance-attributes
class DNS(Remote):
    """
    Run a DNS health check
    """

    def check_one(self, addr: str) -> CheckResult:  # NOSONAR
        """
        Run the health check
        """
        # Set type for MyPy
        self.args: DNSArgs

        # Send request to the DNS server
        try:
            response = self._get_dns(addr=addr)
        except dns_exceptions.Timeout:
            # The query timed out; return failed check result
            return CheckResult(
                success=False,
                message=f"DNS request to {self.args.host}:{self.args.port} timed out",
                output=f"Connection was initiated to IP {addr}:{self.args.port}",
                error="DNS query timed out",
            )
        except dns_exceptions.DNSException as exc:
            # Handle the exception that was received
            return self._handle_dns_exception(addr=addr, exc=exc)

        # Process the response into a CheckResult
        return self._process_dns_response(addr=addr, response=response)

    def _process_dns_response(
        self, addr: str, response: resolver.Answer
    ) -> CheckResult:
        """
        Process a DNS response to ensure it is valid
        """
        self.log.bind(event="debug").debug(
            "Processing DNS response to validate against check parameters"
        )

        # Ensure there is an rrset if required
        if not response.rrset and self.args.require_resolve:
            return CheckResult(
                success=False,
                message=f"DNS query to {self.args.host}:{self.args.port} returned no answers",
                output=f"The query response from IP address {addr} returned no answer for the requested name",
            )

        # If there is no pattern to match, return a successful check result
        if not self.args.response:
            return CheckResult(
                success=True,
                message=f"DNS query to {self.args.host}:{self.args.port} returned a response",
                output=f"The query response from IP address {addr} returned a response for the requested name",
            )

        # Search for the response pattern in response and return
        return self._search_response_pattern(addr=addr, response=response)

    def _search_response_pattern(
        self, addr: str, response: resolver.Answer
    ) -> CheckResult:
        """
        Search for a pattern in the DNS response
        """
        # Set type for MyPy
        assert isinstance(response.rrset, RRset)
        assert isinstance(self.args.response, Pattern)

        # Loop over each answer in the response and look for the response pattern
        self.log.bind(event="debug").debug(
            "Searching DNS response for a match to response pattern"
        )
        for answer in [answer.to_text()[:-1] for answer in response.rrset]:
            # Test if the answer matches
            if self.args.response.match(answer):
                # Match found
                return CheckResult(
                    success=True,
                    message=f"DNS query to {self.args.host}:{self.args.port} returned a validated response",
                    output=(
                        f"The query response from IP address {addr} returned a response with content matching "
                        f"response pattern: {answer}"
                    ),
                )

        # No match found, check failed
        return CheckResult(
            success=False,
            message=f"DNS query to {self.args.host}:{self.args.port} returned a response without matches",
            output=(
                f"The query response from IP address {addr} returned a response but no matches were found for the "
                f"pattern {self.args.response}"
            ),
        )

    def _handle_dns_exception(  # NOSONAR
        self, addr: str, exc: dns_exceptions.DNSException
    ) -> CheckResult:
        """
        Handle a DNS exception
        """
        # Log the exception at a low level; it could mean nothing at all without further checking
        self.log.bind(event="debug").debug(
            "DNS exception while sending {query_type} query to {host}:{port} with IP {addr} for name {query}",
            query_type=self.args.query_type,
            host=self.args.host,
            port=self.args.port,
            addr=addr,
            query=self.args.query,
        )
        self.log.bind(event="debug").trace(
            "DNS exception:\n{exc}",
            exc=exc,
        )

        # Check the type of exception
        match type(exc):
            # NXDOMAIN and NoAnswer indicate that a response was received; check if a response is required
            # and if it needs to be validated
            case resolver.NXDOMAIN | resolver.NoAnswer:
                # Test if the response should be validated
                if self.args.require_resolve or self.args.response:
                    return CheckResult(
                        success=False,
                        message=f"DNS query to {self.args.host}:{self.args.port} returned no answer",
                        output=f"The query response from IP address {addr} returned no answer for the requested name",
                        error=f"{exc}",
                        exception=exc,
                    )

            # YXDOMAIN and NoNameservers indicate that a response was received but it is invalid
            case resolver.YXDOMAIN | resolver.NoNameservers:
                # Test if the response should be validated
                if self.args.require_resolve or self.args.response:
                    return CheckResult(
                        success=False,
                        message=f"DNS query to {self.args.host}:{self.args.port} returned an invalid response",
                        output=f"The query response from IP address {addr} returned an invalid response",
                        error=exc.msg,
                        exception=exc,
                    )

            # LifetimeTimeout indicates the query timed out
            case resolver.LifetimeTimeout:
                return CheckResult(
                    success=False,
                    message=f"DNS query to {self.args.host}:{self.args.port} timed out",
                    output=f"No query response was received from IP address {addr}",
                    error=f"{exc}",
                    exception=exc,
                )

            # Catch other exceptions
            case _:
                return CheckResult(
                    success=False,
                    message=f"DNS query to {self.args.host}:{self.args.port} returned an exception",
                    output=f"The DNS query to IP address {addr} returned an unhandled exception",
                    error=f"{exc}",
                    exception=exc,
                )

        # If reaching this point the exception was not fatal; return the check result
        return CheckResult(
            success=True,
            message=f"DNS query to {self.args.host}:{self.args.port} succeeded",
            output=f"The query response from IP address {addr} an answer which did not require validation",
            error=f"{exc}",
            exception=exc,
        )

    def _create_client(self, addr: str) -> resolver.Resolver:
        """
        Create a DNS resolver object
        """
        # Create the resolver object
        client = resolver.Resolver(configure=False)

        # Set the timeout for the query
        client.timeout = self.args.timeout
        client.lifetime = self.args.timeout

        # Set the name server that will be queried
        client.nameservers = [addr]

        # Set the port to query
        client.port = self.args.port

        return client

    def _get_dns(self, addr: str) -> resolver.Answer:
        """
        Send a DNS query to the specified host
        """
        # Create the resolver object
        client = self._create_client(addr=addr)

        # Log query about to happen
        self.log.bind(event="debug").debug(
            "Sending {query_type} query to {addr}:{port} for name {query}",
            query_type=self.args.query_type,
            addr=addr,
            port=self.args.port,
            query=self.args.query,
        )

        # Send the DNS query
        result = client.resolve(
            qname=self.args.query,
            rdtype=rdatatype.from_text(self.args.query_type),
            tcp=self.args.tcp,
            raise_on_no_answer=True,
        )
        self.log.bind(event="debug").debug(
            "DNS response received from {addr}:{port}",
            addr=addr,
            port=self.args.port,
        )

        # Dump response if available
        if result.rrset:
            self.log.bind(event="datadump").trace(
                "Raw DNS response:\n{response}",
                response=f"{result.rrset.to_text()}",
            )
        else:
            self.log.bind(event="debug").debug(
                "Empty DNS response received from {addr}:{port}"
            )

        # Return the answer
        return result
