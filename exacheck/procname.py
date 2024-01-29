# -*- coding: utf-8 -*-

"""
ExaCheck - ExaBGP Health Checker

Manage the master and worker process names
"""

from __future__ import annotations

from typing import Optional

import loguru
from setproctitle import setproctitle


class ProcName:
    """
    Manage the master and worker process names
    """

    def __init__(self, base: str, log_context: loguru.Logger):
        """
        Set up the new ExaCheck sleep object
        """

        # Set the logging context
        self.log = log_context.bind(subsystem="utility")

        # Set the base process name that will be used
        self._base = base

        # Set empty process name string
        self._name = ""

        # Log setup
        self.log.bind(event="debug").info(
            "Created process name manager object with base name '{base}'", base=base
        )

    def update(self, message: str, status: Optional[str] = None) -> None:
        """
        Update the process name with the new message and optionally status
        """
        # Logging
        if status is None:
            self.log.bind(event="debug").trace(
                "Call to set new process name: '{message}'", message=message
            )
        else:
            self.log.bind(event="debug").trace(
                "Call to set new process name with status: '{message} [{status}]'",
                message=message,
                status=status,
            )

        # Combine the base process name with the new process name
        if status is None:
            procname = f"{self._base}: {message}"
        else:
            procname = f"{self._base}: {message} [{status}]"

        # Set the process name
        try:
            setproctitle(procname)
        # pylint: disable=broad-except
        except Exception as exc:
            self.log.bind(event="error").warning(
                "Exception while changing process name: {exception}", exception=exc
            )
        else:
            self.log.bind(event="debug").debug(
                "Set new process name: '{procname}'", procname=procname
            )
