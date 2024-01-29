# -*- coding: utf-8 -*-

"""
ExaCheck - ExaBGP Health Checker

Base Check Method for remote checks
"""

from __future__ import annotations

import socket
from abc import ABC, abstractmethod
from enum import Enum
from pprint import pformat
from typing import Literal
from ipaddress import ip_address, IPv4Address

from ..settings.checkargs import CheckArgsRemote
from ..exceptions.dnsresolutionerror import DNSResolutionError
from ..exceptions.addressfamilyerror import AddressFamilyError
from ..checkresult import CheckResult
from ._base import Base


class Remote(Base, ABC):
    """
    The remote base health check class
    """

    class AddressFamilies(Enum):
        """
        Create enum for lookups of address families from the string IPv4/IPv6 to a socket object
        """

        IPV4 = socket.AF_INET
        IPV6 = socket.AF_INET6
        UNSPECIFIED = socket.AF_UNSPEC

        @classmethod
        def _missing_(cls, value):
            """
            Capitalize the value provided if missing from enum and try to match it to a member
            """
            # First check there was even a value provided; if not, return the default value of unspecified
            if not value:
                return cls.UNSPECIFIED

            # Set type for MyPy to string
            assert isinstance(value, str)

            # Search through enum
            for member in cls:
                if member.name == value.upper():
                    return member

            # Return the default value of unspecified if not defined
            return cls.UNSPECIFIED

    def __init__(self, *args, **kwargs):
        """
        Add address family definition to init; used to resolve the host to an IP address
        """
        # Call the parent init
        super().__init__(*args, **kwargs)

        # Define the address family to use for DNS resolution
        self.address_family = self.AddressFamilies(self.args.address_family).value  # type: ignore

    def check(self) -> CheckResult:
        """
        Loop over each IP address and perform the health check
        """
        # Inform MyPy that the check args are for a remote check
        self.args: CheckArgsRemote
        assert isinstance(self.args.host, str)

        # Resolve the host into a list of IP addresses
        ips = self.resolve(
            host=self.args.host,
        )

        # Loop over each IP address
        for addr in ips:
            # Run the individual health check and return if a check result was retrieved
            if (result := self._check(addr=addr)) is not None:
                return result

        # If all health checks were required to be valid, return a success result
        if self.args.all_valid:
            self.log.bind(event="info").success(
                "Health check for {host} using all resolved IP address was successful; tested IP addresses: {ips}",
                host=self.args.host,
                ips=", ".join(ips),
            )
            # Return a generated check result
            return CheckResult(
                success=True,
                message="Health check for all resolved IP addresses successful",
                output=f"Tested IP addresses: {', '.join(ips)}",
            )

        # If reaching this point generate and return failed check result
        self.log.bind(event="error").warning(
            "Health check for {host} failed for one or more IP addresses; tested IP addresses: {ips}",
            host=self.args.host,
            ips=", ".join(ips),
        )
        return CheckResult(
            success=False,
            message="Health check for one or more IP addresses failed",
            output=f"Tested IP addresses: {', '.join(ips)}",
        )

    def _check(self, addr: str) -> CheckResult | None:
        """
        Perform the health check to a single address
        """
        # Log the check start
        self.log.bind(event="debug").debug(
            "Health check started for host {host} using IP address {addr}",
            host=self.args.host,
            addr=addr,
        )

        # Run the health check
        try:
            result = self.check_one(addr=addr)
        except Exception as exc:  # pylint: disable=broad-except
            self.log.bind(event="debug").error(
                "Health check raised unhandled exception: {exc}",
                exc=f"{exc}",
            )
            result = CheckResult(
                success=False,
                message="Check raised unhandled exception",
                error=f"Unhandled exception raised for IP address {addr}: {exc}",
                exception=exc,
            )

        # Log the result
        self._log_result(result=result)

        # If all health checks must be successful and a failure was returned, return the failed check result
        if self.args.all_valid and result.success is False:
            self.log.bind(event="error").warning(
                "Health check for {host} using IP address {addr} failed; skipping subsequent IPs if any",
                host=self.args.host,
                addr=addr,
            )
            return result

        # If only a single health check needs to be successful, return the successful result
        if not self.args.all_valid and result.success is True:
            self.log.bind(event="info").success(
                "Health check for {host} using IP address {addr} successful; skipping subsequent IPs if any",
                host=self.args.host,
                addr=addr,
            )
            return result

        # If the check was successful, log but continue on to next health check
        if result.success:
            self.log.bind(event="info").success(
                (
                    "Health check for {host} using IP address {addr} successful; proceeding with subsequent "
                    "IPs if any"
                ),
                host=self.args.host,
                addr=addr,
            )
        else:
            # The health check failed, log and continue on to next IP address if defined
            self.log.bind(event="error").warning(
                (
                    "Health check for {host} using IP address {addr} failed; health check will proceed with "
                    "subsequent IPs if any"
                ),
                host=self.args.host,
                addr=addr,
            )

        # Return empty result
        return None

    @abstractmethod
    def check_one(self, addr: str) -> CheckResult:
        """
        Function that is called to health check each individual IP address
        """

    def _dns_resolver(
        self, host: str, family: Literal["ipv4", "ipv6", None] = None
    ) -> list[str]:
        """Perform the requested DNS resolution. This class is called by the resolver() method and should not be used
        directly.

        Args:
            host (str): The host name or IP address.
            family (Literal["ipv4", "ipv6", None], optional): Force to the specified address family. Defaults to None.
            one (bool, optional): Only return a single IP address even if multiple IPs are available. Defaults to False.

        Raises:
            DNSResolutionError: Exception raised if the host cannot be resolved to an IP address.
            AddressFamilyError: Exception raised if the host resolves to an IP address of the wrong address family.

        Returns:
            list[str]: The list of IP address(es) of the specified address family.
        """

        # Check if there is an address family defined
        if family:
            # Address family is defined, lookup from enum
            address_family = self.AddressFamilies(family).value
        else:
            # Address family is not defined, get from init
            address_family = self.address_family

        # Set the address family type to pass to getaddrinfo
        self.log.bind(event="debug").debug(
            "Attempting to resolve host '{host}' to an IP address",
            host=host,
        )

        # Attempt the DNS resolution
        try:
            addrinfo = socket.getaddrinfo(host=host, port=0, family=address_family)
        except socket.gaierror as exc:
            # Get the type of exception based on error number
            match exc.errno:
                case "-9":
                    # No IP address of the provided address family could be found
                    message = f"Could not resolve an {family} family IP address for hostname '{host}'"
                    self.log.bind(event="error").warning(message)
                    raise AddressFamilyError(message) from exc
                case "-2":
                    message = f"Could not resolve host '{host}'; check if it exists"
                case _:
                    message = f"Could not resolve host '{host}' to an IP address: {exc}"

            # Log the failure
            self.log.bind(event="error").warning(message)

            # Raise the DNS resolution error
            raise DNSResolutionError(message=message) from exc

        # Retrieve the list of IP addresses from the addrinfo as a set to remove duplicates
        addresses = set(ip for ip in [ip[4][0] for ip in addrinfo])

        # Log the DNS resolution information
        self.log.bind(event="datadump").trace(
            "Hostname '{host}' resolved to the following IP addresses:\n{addresses}",
            host=host,
            addresses=pformat(addresses, indent=4, width=120),
        )

        # Return the resolved addresses as a list
        return list(addresses)

    def resolve(  # NOSONAR
        self, host: str, family: Literal["ipv4", "ipv6", None] = None, one: bool = False
    ) -> list[str] | str:
        """Resolve the supplied hostname into one or more IP addresses. If required, the address family may be defined
        to only return addresses of that family.

        If called with an IP address as the host argument, the IP address will be verified to be of the correct address
        family.

        Hostnames that resolve to multiple IP addresses will return a list of IP addresses unless the one argument is
        set to True, in which case only the first IP address will be returned.

        Args:
            host (str): The host name or IP address.
            family (Literal["ipv4", "ipv6", None], optional): Force to the specified address family. Defaults to None.
            one (bool, optional): Only return a single IP address even if multiple IPs are available. Defaults to False.

        Raises:
            DNSResolutionError: Exception raised if the host cannot be resolved to an IP address.
            AddressFamilyError: Exception raised if the host resolves to an IP address of the wrong address family.

        Returns:
            list[str] | str: The list of IP addresses or a single IP address.
        """
        # Perform the DNS resolution
        addresses = self._dns_resolver(host=host, family=family)

        # If a list of IP addresses is requested, return the list
        if not one:
            return addresses

        # Log that a single IP was requested
        self.log.bind(event="debug").debug(
            "Single IP address from DNS resolution requested; filtering IPs"
        )

        # If a single IP address was returned, pop and return
        if len(addresses) == 1:
            return addresses.pop()

        # Test if an address family was defined; if one was then pop the first address
        if family or hasattr(self.args, "address_family"):
            address = addresses.pop()
            self.log.bind(event="info").warning(
                "Hostname '{host}' resolved to more than one IP; only the IP '{address}' will be used",
                host=host,
                address=address,
            )
            return address

        # No address family defined; return the first IPv4 address if available
        for ipaddr in addresses:
            if isinstance(ip_address(ipaddr), IPv4Address):
                self.log.bind(event="info").warning(
                    "Hostname '{host}' resolved to more than one IP; only the first IPv4 IP '{address}' will be used",
                    host=host,
                    address=ipaddr,
                )
                return ipaddr

        # Return first IPv6 address
        address = addresses.pop()
        self.log.bind(event="info").warning(
            "Hostname '{host}' resolved to more than one IP; only the first IPv6 IP '{address}' will be used",
            host=host,
            address=address,
        )
        return address
