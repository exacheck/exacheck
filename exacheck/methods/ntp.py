# -*- coding: utf-8 -*-

"""
ExaCheck - ExaBGP Health Checker

Check Method - NTP
"""

from __future__ import annotations

from datetime import datetime

from ntplib import NTPClient, NTPStats, leap_to_text, ref_id_to_text
from tabulate import tabulate

from ..checkresult import CheckResult
from ..settings.checkargs.ntpargs import NTPArgs
from ._remote import Remote


# pylint: disable=too-few-public-methods
class NTP(Remote):
    """
    Run a NTP health check
    """

    def check_one(self, addr: str) -> CheckResult:
        """
        Run the health check
        """
        # Set type for MyPy
        self.args: NTPArgs

        # Send the NTP request and get response
        try:
            response = self._get_ntp(addr=addr)
        except Exception as exc:  # pylint: disable=broad-except
            self.log.bind(event="debug").error(
                "NTP connection exception: {exc}",
                exc=f"{exc}",
            )
            # Return a failure as the check raised exception
            return CheckResult(
                success=False,
                message=f"NTP connection to {self.args.host}:{self.args.port} failed",
                output=f"Failed connection to IP {addr}:{self.args.port}",
                error=f"Exception raised: {exc}",
                exception=exc,
            )

        # Process the response into a check result and return
        return self._process_ntp_response(addr=addr, response=response)

    def _get_ntp(self, addr: str) -> NTPStats:
        """
        Get an NTP response from the specified address
        """
        # Create the NTP client object
        client = NTPClient()

        # Send the NTP request and get response
        self.log.bind(event="debug").debug(
            "Sending NTP request to {addr}:{port} using NTP v{version}",
            addr=addr,
            port=self.args.port,
            version=self.args.version,
        )
        response = client.request(
            host=addr,
            version=self.args.version,
            port=f"{self.args.port}",
            timeout=self.args.timeout,
        )
        self.log.bind(event="debug").debug(
            "NTP response received with offset: {offset}",
            offset=response.offset,
        )
        self.log.opt(lazy=True).bind(event="datadump").trace(
            "NTP data received:\n{result_table}",
            result_table=lambda: self._result_table(response),
        )

        # Return the NTP response
        return response

    def _process_ntp_response(self, addr: str, response: NTPStats) -> CheckResult:
        """
        Process the NTP response into a CheckResult object
        """
        self.log.bind(event="debug").debug(
            "Processing NTP response to validate against check parameters"
        )

        # Get the various statistics from response
        offset = response.offset
        reference = ref_id_to_text(response.ref_id)
        leap = leap_to_text(response.leap)
        version = response.version
        stratum = response.stratum

        # Create list of errors that may be returned
        errors: list[str] = []

        # Build output message
        output = (
            f"IP:{addr} Port:{self.args.port} Version:{version} Stratum:{stratum} Offset:{offset} "
            f"Reference:{reference} Leap Status:{leap}"
        )

        # Set success status to default to True; if failure is detected, this will be set to False
        success = True

        # Check if the offset is within the maximum offset value (+/-)
        if isinstance(self.args.max_offset, (int, float)):
            if abs(offset) > self.args.max_offset:
                # Offset is +/- over maximum offset
                success = False
                message = f"Offset {offset} exceeds maximum offset of {self.args.max_offset} compared to local time"
                self.log.bind(event="debug").error(message)
                errors.append(message)

        # Check if the stratum is within the maximum stratum value
        if isinstance(self.args.max_stratum, int):
            if stratum > self.args.max_stratum:
                # NTP server stratum is too high
                success = False
                message = f"Stratum {stratum} exceeds maximum stratum of {self.args.max_stratum}"
                self.log.bind(event="debug").error(message)
                errors.append(message)

        # Ensure the response version matches the requested version
        if self.args.version != version:
            success = False
            message = f"Response version {version} does not match requested version {self.args.version}"
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
            message = f"NTP check to {addr}:{self.args.port} successful"
        else:
            message = f"NTP check to {addr}:{self.args.port} failed"

        # Generate and return the check result
        return CheckResult(
            success=success,
            message=message,
            output=output,
            error=error,
        )

    @staticmethod
    def _result_table(result: NTPStats) -> str:
        """
        Generate a table of result information from the NTP response
        """
        # Set headers for the table
        headers = ["Name", "Value"]

        # Create data list
        data: list[list[str]] = []

        # Add the data to the data list
        data.append(["Offset", f"{result.offset}"])
        data.append(["Reference Clock", ref_id_to_text(result.ref_id)])
        data.append(["Stratum", f"{result.stratum}"])
        data.append(["Leap Status", leap_to_text(result.leap)])
        data.append(["Version", f"{result.version}"])
        data.append(["Precision", f"{result.precision}"])
        data.append(["TX Time", f"{result.tx_time}"])
        data.append(["RX Time", f"{result.recv_time}"])
        data.append(["TX Time Human", f"{datetime.fromtimestamp(result.tx_time)}"])
        data.append(["RX Time Human", f"{datetime.fromtimestamp(result.recv_time)}"])
        data.append(["Root Delay", f"{result.root_delay}"])

        # Create the table
        table = tabulate(data, headers=headers)

        # Return the table
        return table
