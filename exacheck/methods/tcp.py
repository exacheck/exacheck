# -*- coding: utf-8 -*-

"""
ExaCheck - ExaBGP Health Checker

Check Method - TCP Connection
"""

from __future__ import annotations

import socket
from ipaddress import ip_address, IPv4Address

from ..checkresult import CheckResult
from ..settings.checkargs.tcpargs import TCPArgs
from ._remote import Remote


# pylint: disable=too-few-public-methods
class TCP(Remote):
    """
    Run a health check to a TCP port to ensure it is listening
    """

    def check_one(self, addr: str) -> CheckResult:
        """
        Run a TCP health check to the supplied IP address
        """
        # Set type for MyPy
        self.args: TCPArgs

        # Create IP address object
        ipaddr = ip_address(addr)

        # Set the address family type
        family = socket.AF_INET if isinstance(ipaddr, IPv4Address) else socket.AF_INET6

        # Run the health check and check if successful
        if self._test_socket(addr=addr, family=family):
            # Return success
            return CheckResult(
                success=True,
                message=f"TCP connection to {self.args.host}:{self.args.port} succeeded",
                output=f"Connection was initiated to IP {addr}:{self.args.port}",
            )

        # Failure opening the connection
        return CheckResult(
            success=False,
            message=f"TCP connection to {self.args.host}:{self.args.port} failed",
            output=f"Connection was initiated to IP {addr}:{self.args.port}",
        )

    def _test_socket(self, addr: str, family) -> bool:
        """
        Attempt making a TCP connection to the IP address/port and return true/false
        """

        # Set up the socket
        self.log.bind(event="debug").debug(
            "Opening socket to {addr}:{port}",
            addr=addr,
            port=self.args.port,
        )
        sock = socket.socket(family=family, type=socket.SOCK_STREAM)
        sock.settimeout(self.args.tcp_timeout)

        # Open connection
        self.log.bind(event="debug").debug(
            "Testing connection to {addr}:{port}",
            addr=addr,
            port=self.args.port,
        )
        try:
            result = sock.connect_ex((addr, self.args.port))
        except Exception as exc:  # pylint: disable=broad-except
            # Log failure
            self.log.bind(event="debug").debug(
                "Error connecting to {addr}:{port}: {error}",
                addr=addr,
                port=self.args.port,
                error=f"{exc}",
                exception=exc,
            )

            # Shut down/close socket
            try:
                sock.shutdown(socket.SHUT_RDWR)
                sock.close()
            except Exception:  # pylint: disable=broad-except
                pass

            # Return failed result
            return False

        # Shut down/close socket
        try:
            self.log.bind(event="debug").debug(
                "Shutting down socket to {addr}:{port}",
                addr=addr,
                port=self.args.port,
            )
            sock.shutdown(socket.SHUT_RDWR)
            sock.close()
        except Exception:  # pylint: disable=broad-except
            pass

        # Return the result as a bool
        self.log.bind(event="debug").debug(
            "Connection to {addr}:{port} returned code: {result}",
            addr=addr,
            port=self.args.port,
            result=result,
        )
        return result == 0
