# -*- coding: utf-8 -*-

"""
ExaCheck - ExaBGP Health Checker

Load and manage the configuration for ExaCheck
"""

from __future__ import annotations

from pathlib import Path
from pprint import pformat
from typing import Optional
import sys

import ujson
import loguru
from pydantic import ValidationError
from yaml import safe_load as yaml_safe_load

from .settings.settings import Settings


class Configuration:
    """
    ExaCheck configuration handler
    """

    def __init__(
        self,
        log_context: loguru.Logger,
        file: Optional[Path] = None,
        configuration: Optional[dict] = None,
    ):
        # Set the logging context
        self.log = log_context.bind(subsystem="configuration")

        # Ensure that either a file or configuration dict is provided
        if not file and not configuration:
            self.log.bind(event="error").critical(
                "No configuration file or configuration dict provided"
            )
            raise SystemExit(1)

        # Check if a file name was provided
        if file:
            # Ensure the file name is yaml or json
            if file.suffix not in (".yaml", ".yml", ".json"):
                self.log.bind(event="error").critical(
                    "Configuration file '{file}' must have a '.json' or '.yaml' extension",
                    file=file,
                )
                raise SystemExit(1)

            # Read the configuration file into a dict
            configuration = self._load_file(file=file)

            # Set the modification time for the file
            self.mtime = file.stat().st_mtime

        # Parse the configuration into a Settings object
        try:
            self.settings = Settings(**configuration, file=file)
        except ValidationError as exc:
            # Invalid configuration
            self.log.bind(event="error").critical(
                "The configuration could not be parsed due to validation errors."
            )
            for error in exc.errors():
                self.log.bind(event="error").error(
                    "{location}: {error}",
                    location=error["loc"],
                    error=error["msg"],
                )
            self.log.bind(event="datadump").error(
                "Pydantic reported the following errors:\n{errors}",
                errors=pformat(exc.errors()),
            )
            # Exit
            sys.exit(2)

        except Exception as exc:
            # An unexpected exception occurred; raise SystemExit exception to exit
            raise SystemExit(99) from exc

        # Return loaded settings
        self.log.bind(event="info").info("Configuration file loaded successfully")
        self.log.bind(event="datadump").trace(
            "Loaded settings from configuration:\n{settings}",
            settings=self.settings.pretty,
        )

    def _load_file(self, file: Path) -> dict:
        """
        Read configuration from the supplied JSON or YAML file into a dict
        """
        # Logging
        self.log.bind(event="info").debug(
            "Loading configuration data from file '{file}'",
            file=file,
        )

        # Check the file type
        match file.suffix:
            case file.suffix if file.suffix in (".yaml", ".yml"):
                configuration = yaml_safe_load(file.read_text(encoding="utf-8"))
            case ".json":
                configuration = ujson.loads(file.read_text(encoding="utf-8"))
            case _:
                self.log.bind(event="error").critical(
                    "Configuration file '{file}' does not have a valid extension",
                    file=file,
                )
                raise SystemExit(1)

        # Dump the configuration dict
        self.log.bind(event="datadump").trace(
            "Read {file_type} data:\n{file_content}",
            file_type=file.suffix[1:].upper(),
            file_content=pformat(configuration, indent=4, width=120),
        )

        # Return the configuration dict
        return configuration

    def is_modified(self) -> bool:
        """Check if the configuration file has been modified"""
        # Configuration can only be modified if it is from a configuration file
        if not self.settings.file:
            return False

        # Logging
        self.log.bind(event="debug").trace(
            "Testing if configuration file has been modified",
        )

        # Get the current modification time of the configuration file
        mtime = self.settings.file.stat().st_mtime

        # Compare the modification times
        if mtime != self.mtime:
            # Logging
            self.log.bind(event="info").info(
                "Configuration file has been modified",
            )

            # Return True
            return True

        # Configuration not modified
        self.log.bind(event="debug").trace(
            "Configuration file has not been modified",
        )
        return False

    def reload(self) -> bool:
        """Reload the configuration file"""
        # Configuration file appears to have been modified, attempt to parse it into a dict
        try:
            configuration = self._load_file(file=self.settings.file)
        except Exception as exc:
            # Log failure
            self.log.bind(event="error").error(
                "Configuration file has been modified but could not be parsed: {exc}",
                exc=exc,
            )
            # Update the modification time
            self.mtime = self.settings.file.stat().st_mtime
            # Return False to indicate that the configuration was not reloaded
            return False

        # Configuration file was modified and parsed successfully, attempt to load it
        try:
            settings = Settings(**configuration, file=self.settings.file)
        except ValidationError as exc:
            # Log failure
            self.log.bind(event="error").error(
                "Configuration file is invalid: {exc}",
                exc=exc,
            )
            # Update the modification time
            self.mtime = self.settings.file.stat().st_mtime
            # Return False to indicate that the configuration was not reloaded
            return False
        except Exception as exc:
            # Log failure
            self.log.bind(event="error").error(
                "Exception loading configuration file: {exc}",
                exc=exc,
            )
            # Update the modification time
            self.mtime = self.settings.file.stat().st_mtime
            # Return False to indicate that the configuration was not reloaded
            return False

        # Update the modification time
        self.mtime = self.settings.file.stat().st_mtime

        # Configuration file was loaded successfully, update the settings
        self.settings = settings

        # Log success
        self.log.bind(event="info").info(
            "The configuration has been reloaded successfully",
        )

        # Return True to indicate that the configuration was reloaded
        return True
