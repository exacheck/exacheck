# -*- coding: utf-8 -*-

"""
ExaCheck - ExaBGP Health Checker

Set up/configure logging to STDERR, files and/or syslog
"""

from __future__ import annotations

import logging
import logging.handlers
from pathlib import PosixPath
from sys import stderr
from typing import Callable
from socket import SOCK_STREAM, SOCK_DGRAM, gethostname

import loguru
from loguru._defaults import (
    LOGURU_DEBUG_NO,
    LOGURU_ERROR_NO,
    LOGURU_INFO_NO,
    LOGURU_SUCCESS_NO,
    LOGURU_TRACE_NO,
    LOGURU_WARNING_NO,
)

from .settings.loggers import LogFile, Syslog


class LogManager:
    """
    Set up/configure logging to STDERR, a file and/or syslog
    """

    def __init__(self, verbosity: int):
        """
        Create the new log object
        """
        # Set up the default STDERR log
        self.setup_stderr(verbosity=verbosity)

        # Create a logging context for self
        self.log = loguru.logger.bind(
            check_name="MASTER",
            subsystem="logging",
        )

        # Log the creation of the log manager
        self.log.bind(event="debug").debug("New LogManager object created")

        # Log creation of STDERR logger
        self.log.bind(event="debug").debug(
            "STDERR logger created at level {level}",
            level=self._stderr_level,
        )
        self.log.bind(event="datadump").trace(
            "STDERR log format string:\n{log_format}",
            log_format=self._stderr_log_format,
        )

    def setup_stderr(self, verbosity: int) -> None:
        """
        Setup logging to STDERR
        """

        # Define the available log levels for verbosity flags
        levels = {
            0: LOGURU_ERROR_NO,
            1: LOGURU_WARNING_NO,
            2: LOGURU_SUCCESS_NO,
            3: LOGURU_INFO_NO,
            4: LOGURU_DEBUG_NO,
            5: LOGURU_TRACE_NO,
        }

        # Fix typing for loguru levels
        assert isinstance(LOGURU_ERROR_NO, int)
        assert isinstance(LOGURU_WARNING_NO, int)
        assert isinstance(LOGURU_SUCCESS_NO, int)
        assert isinstance(LOGURU_INFO_NO, int)
        assert isinstance(LOGURU_DEBUG_NO, int)
        assert isinstance(LOGURU_TRACE_NO, int)

        # Get log level to set; if debug is disabled, limit to info level to prevent log spam
        self._stderr_level: int = (  # type: ignore
            levels.get(verbosity, LOGURU_TRACE_NO) if __debug__ else LOGURU_INFO_NO
        )
        # Set type for MyPy
        assert isinstance(self._stderr_level, int)

        # Create the common log format for STDERR messages
        log_format: list[str] = [
            "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green>",
            "<level>{level: <8}</level>",
            "<light-blue>PID {process: <8}</light-blue>",
            "<cyan>{extra[check_name]}</cyan>",
            "<green>{extra[subsystem]}/{extra[event]}</green>",
            "<level>{message}</level>",
        ]

        # If the log level is less than LOGURU_INFO_NO, add the function name, line number and file name to the log
        # format. If LOGURU_DEBUG_NO or less the full file path will be used
        if self._stderr_level < LOGURU_INFO_NO:
            if self._stderr_level < LOGURU_DEBUG_NO:
                log_format.insert(
                    3, "<magenta>{file.path}:{line} {function}()</magenta>"
                )
            else:
                log_format.insert(3, "<magenta>{file}:{line} {function}()</magenta>")

        # Combine the log format strings
        self._stderr_log_format = " | ".join(log_format)

        # Remove the default logger
        loguru.logger.remove()

        # Add the new logger set at the correct log level and with correct format
        loguru.logger.add(
            stderr, format=self._stderr_log_format, level=self._stderr_level
        )

    def setup(self, loggers: list[LogFile | Syslog]) -> None:
        """
        Configure the list of log files/syslog destinations
        """
        # Log start of setup
        self.log.bind(event="debug").debug("Setting up file/syslog loggers")

        # Loop through the list of loggers
        for config in loggers:
            # Set up the required logger
            self._setup_logger(config=config)

    def _setup_logger(self, config: LogFile | Syslog) -> None:
        """
        Create a single logger for a log file or syslog destination
        """
        # Log setup of the individual logger
        self.log.bind(event="debug").debug(
            "Creating {log_type} logger", log_type=config.method
        )
        self.log.bind(event="datadump").trace(
            "Logger config:\n{config}",
            config=config.pretty,
        )

        # Generate the log format
        log_format = self.log_format(config=config)
        self.log.bind(event="datadump").trace(
            "Generated log format:\n{log_format}", log_format=log_format
        )

        # Create a filter for the log
        log_filter = self.log_filter(config=config)

        # Uppercase the log level
        level = config.level.upper()

        # If the logger is a syslog destination, set the destination and create the log handler first
        if isinstance(config, Syslog):
            # First check if logging to the local syslog socket
            if config.destination == "/dev/log" or isinstance(
                config.destination, PosixPath
            ):
                # Create the log handler
                handler = logging.handlers.SysLogHandler(
                    address=f"{config.destination}"
                )
            else:
                # Set the protocol to use
                if config.protocol == "tcp":
                    protocol = SOCK_STREAM
                else:
                    protocol = SOCK_DGRAM

                # Create the log handler
                handler = logging.handlers.SysLogHandler(
                    address=(config.destination, config.port),
                    socktype=protocol,
                )

            # Add the new logger
            logger_id = loguru.logger.add(
                handler,
                format=log_format,
                level=level,
                filter=log_filter,
            )

        # Logging is to a file, set compression type and create logger
        else:
            # Set compression if enabled
            compression = config.compression_format if config.compress else None

            # Add the new logger
            logger_id = loguru.logger.add(
                config.destination,
                format=log_format,
                level=level,
                rotation=config.size,
                compression=compression,
                enqueue=True,
                filter=log_filter,
                retention=config.count,
            )

        # Set the logger ID for the config
        config.set_logger_id(logger_id)

    @staticmethod
    def log_format(config: LogFile | Syslog) -> str:
        """
        Generate the log format string for the supplied log configuration
        """
        # Return the user defined format if set
        if config.formatter:
            return config.formatter

        # Create a list of fields to include in the log format
        fields: list[tuple[str, str]] = []

        # When using file logging, the date/time is formatted uniquely depending on structured logging
        if isinstance(config, LogFile):
            if config.structured:
                fields.append(("date", "{time:YYYY-MM-DD}"))
                fields.append(("time", "{time:HH:mm:ss.SSS}"))
            else:
                fields.append(("time", "{time:YYYY-MM-DD HH:mm:ss.SSS}"))

        # Check if logging with syslog
        if isinstance(config, Syslog):

            # If using structured logging or logging to a remote server, include a time field
            if config.structured or isinstance(config.destination, str):
                fields.append(("time", "{time:YYYY-MM-DD HH:mm:ss.SSS}"))

            # If logging to a remote server, include the hostname
            if isinstance(config.destination, str):
                fields.append(("hostname", f"{gethostname()}"))

        # Define the log level field
        if config.structured:
            fields.append(("level", "{level}"))
        else:
            fields.append(("level", "{level: <8}"))

        # Add the process ID and check name
        fields.append(("pid", "{process}"))
        fields.append(("check_name", "{extra[check_name]}"))

        # If using structured logging the file path, line number and function is split
        if config.structured:
            fields.append(("file", "{file.path}"))
            fields.append(("line", "{line}"))
            fields.append(("function", "{function}"))
        else:
            # If not using structured logging and the log level is debugging/trace, log the file and line number
            if config.level in ["debug", "trace"]:
                fields.append(("file", "{file.path}:{line}"))
                fields.append(("function", "{function}"))

        # Append the event
        fields.append(("event", "{extra[event]}"))

        # Append the subsystem
        fields.append(("subsystem", "{extra[subsystem]}"))

        # Append the log message
        fields.append(("message", "{message}"))

        # Create the log format string from the fields provided; depending on if structured formatting is used or not
        if config.structured:
            log_format = " ".join([f'"{field[0]}"="{field[1]}"' for field in fields])
        else:
            log_format = " | ".join([field[1] for field in fields])

        # Return the log format
        return log_format

    @staticmethod
    def log_filter(config: LogFile | Syslog) -> Callable:
        """
        Generate a filter for the supplied log configuration
        """

        # Create set of events, subsystems and check names to log
        events = set(config.events)
        subsystems = set(config.subsystems)
        if config.checks:
            checks = set(config.checks)
        else:
            checks = set()

        # If the log is structured or to syslog, data dumping is not permitted
        if config.structured or isinstance(config, Syslog):
            if "datadump" in events:
                events.remove("datadump")

        # Define the filter function
        def _filter(record: loguru.Record) -> bool:
            """
            Create a filter for log records based on the supplied configuration
            """
            # If filter by check name is set, ensure the record check name is in the allow list
            if checks and record["extra"]["check_name"] not in checks:
                return False

            # Ensure the record event is in the allow list
            if (
                record["extra"]["event"] not in events
                or record["extra"]["subsystem"] not in subsystems
            ):
                return False

            # If not matched by previous checks, log the message
            return True

        # Return the filter function
        return _filter
