# -*- coding: utf-8 -*-

"""
ExaCheck - ExaBGP Health Checker

Check Method - ICMP
"""

from __future__ import annotations

from icmplib import SocketPermissionError, TimeoutExceeded, ping, Host

from ..checkresult import CheckResult
from ..settings.checkargs.icmpargs import ICMPArgs
from ._remote import Remote


# pylint: disable=too-few-public-methods
class ICMP(Remote):
    """
    Run a ICMP health check
    """

    def check_one(self, addr: str) -> CheckResult:
        """
        Run the ICMP health check
        """
        # Set type for MyPy
        self.args: ICMPArgs

        # Send the ping/ICMP request and get response
        try:
            response = self._ping(addr=addr)
        except SocketPermissionError as exc:
            # If a SocketPermissionError is raised, then the user does not have sufficient permissions; the check
            # will fail for all addresses so return a failure immediately
            self.log.bind(event="error").error(
                (
                    "Ping to host {host} failed due to insufficient permissions. "
                    "The service is marked as failed due to this error. The ping request was sent to IP {addr}."
                ),
                host=self.args.host,
                addr=addr,
            )
            return CheckResult(
                success=False,
                message="Failed to create socket; insufficient permissions",
                output=f"Ping request destined to '{self.args.host}' failed due to insufficient permissions",
                error=f"Exception raised: {exc}",
                exception=exc,
            )
        except TimeoutExceeded as exc:
            # If there was a timeout exceeded exception the check can't have further processing performed
            self.log.bind(event="error").warning(
                (
                    "Ping to {host} using IP {addr} raised timeout; returning failure for check as all "
                    "results must be valid"
                ),
                host=self.args.host,
                addr=addr,
            )
            return CheckResult(
                success=False,
                message=f"Timeout exceeded pinging host {self.args.host}",
                output=f"Ping was sent to IP {addr}",
                error=f"{exc}",
            )

        # Process the response into a check result and return
        return self._process_icmp_response(response=response)

    def _ping(self, addr: str) -> Host:
        """
        Ping an IP address and retrieve the result
        """
        # Attempt to ping the provided IP address
        self.log.bind(event="debug").debug(
            "Sending {count} ping requests to {addr} using {privileged} mode",
            count=self.args.count,
            addr=addr,
            privileged="privileged" if self.args.privileged else "unprivileged",
        )
        result = ping(
            address=addr,
            count=self.args.count,
            interval=self.args.interval,  # type: ignore
            timeout=self.args.timeout,
            privileged=self.args.privileged,
        )

        # Log the result
        self.log.bind(event="debug").debug(
            "Ping response indicates that {addr} is {reachable}",
            addr=addr,
            reachable="reachable" if result.is_alive else "unreachable",
        )
        self.log.bind(event="datadump").trace(
            "Raw ping result:\n{response}",
            response=f"{result}",
        )

        # Return the result
        return result

    def _process_icmp_response(self, response: Host) -> CheckResult:
        """
        Process the results of an ICMP test to ensure the values are within the expected parameters
        """
        self.log.bind(event="debug").debug(
            "Processing ICMP response to validate against check parameters",
        )

        # Ensure that at least one response is received
        if response.packets_received == 0:
            # Create log of failure
            self.log.bind(event="info").warning(
                "Ping request to {host} with IP {addr} failed; no packets received",
                host=self.args.host,
                addr=response.address,
            )

            # Build result
            result = CheckResult(
                success=False,
                message=f"No ICMP response from {self.args.host} with IP {response.address}",
            )

            # Return response early
            self.log.bind(event="debug").debug(
                "Returning CheckResult with failure due to missing ICMP response"
            )
            self.log.bind(event="datadump").trace(
                "Raw check result:\n{result}",
                result=result.pretty,
            )
            return result

        # Build output message
        output = (
            f"Packets:{self.args.count} Received:{response.packets_received} "
            f"Loss:{response.packet_loss} Interval:{self.args.interval} Min:{response.min_rtt}ms "
            f"Max:{response.max_rtt}ms Avg:{response.avg_rtt}ms"
        )

        # Create list of errors that may be returned
        errors: list[str] = []

        # Set default success status to True
        success = True

        # Check if the number of packets lost is within the allowed range
        if (
            lost := response.packets_sent - response.packets_received
            > self.args.max_loss
        ):
            success = False
            message = (
                f"Packets lost ({lost}) exceeds maximum limit of {self.args.max_loss}"
            )
            self.log.bind(event="debug").error(message)
            errors.append(message)

        # Check if the latency (if set) is within the allowed range
        if self.args.max_latency and response.max_rtt > self.args.max_latency:
            success = False
            message = f"Maximum latency ({response.max_rtt}ms) exceeds maximum limit of {self.args.max_latency}ms"
            self.log.bind(event="debug").error(message)
            errors.append(message)

        # Check if the jitter (if set) is within the allowed range
        if (
            self.args.max_jitter
            and response.packets_received > 1
            and response.jitter > self.args.max_jitter
        ):
            success = False
            message = f"Maximum jitter ({response.max_rtt}ms) exceeds limit of {self.args.max_jitter}ms"
            self.log.bind(event="debug").error(message)
            errors.append(message)

        # If there were errors, build the error string
        error: str | None
        if errors:
            error = ", ".join(errors)
        else:
            error = None

        # Build message
        if success:
            message = f"ICMP test to {response.address} successful"
        else:
            message = f"ICMP test to {response.address} failed"

        # Create the check result object and return
        return CheckResult(
            success=success,
            message=message,
            output=output,
            error=error,
        )
