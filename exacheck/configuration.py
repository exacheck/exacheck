# -*- coding: utf-8 -*-

"""
ExaCheck - ExaBGP Health Checker

Load and manage the configuration for ExaCheck
"""

from __future__ import annotations

from hashlib import sha256
from json import loads as json_loads
from pathlib import Path
from pprint import pformat
from typing import Any, Callable, Optional
import sys

import loguru
from pydantic import ValidationError
from yaml import safe_load as yaml_safe_load

from .settings.settings import Settings


# Map a (lower-cased) file extension to the function that parses its
# contents into a Python dict. Adding another supported format is one
# line — no branching logic elsewhere.
_CONFIG_PARSERS: dict[str, Callable[[str], Any]] = {
    ".yaml": yaml_safe_load,
    ".yml": yaml_safe_load,
    ".json": json_loads,
}


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
            # Read the configuration file into a dict. _load_file validates
            # the extension (and raises SystemExit on an unsupported one)
            # so the suffix check lives in exactly one place.
            configuration = self._load_file(file=file)

            # Record the content hash so polling can detect real changes
            # (insensitive to mtime touches that don't alter the bytes).
            self.content_hash = self._hash_file(file)

        # Parse the configuration into a Settings object. At this point
        # ``configuration`` is non-None — either the user passed it in or
        # _load_file produced it above.
        assert configuration is not None
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
        self.log.opt(lazy=True).bind(event="datadump").trace(
            "Loaded settings from configuration:\n{settings}",
            settings=lambda: self.settings.pretty,
        )

    def _load_file(self, file: Path) -> dict:
        """
        Read configuration from the supplied YAML or JSON file into a dict.

        The file extension determines the parser (see ``_CONFIG_PARSERS``).
        Matching is case-insensitive so ``foo.YAML`` works the same as
        ``foo.yaml``.
        """
        suffix = file.suffix.lower()
        parser = _CONFIG_PARSERS.get(suffix)
        if parser is None:
            self.log.bind(event="error").critical(
                "Configuration file '{file}' must have one of these extensions: {exts}",
                file=file,
                exts=", ".join(sorted(_CONFIG_PARSERS)),
            )
            raise SystemExit(1)

        self.log.bind(event="info").debug(
            "Loading {fmt} configuration data from file '{file}'",
            fmt=suffix[1:].upper(),
            file=file,
        )

        configuration = parser(file.read_text(encoding="utf-8"))

        self.log.opt(lazy=True).bind(event="datadump").trace(
            "Read {file_type} data:\n{file_content}",
            file_type=lambda: suffix[1:].upper(),
            file_content=lambda: pformat(configuration, indent=4, width=120),
        )

        return configuration

    @staticmethod
    def _hash_file(file: Path) -> str:
        """Compute a content hash of the configuration file"""
        return sha256(file.read_bytes()).hexdigest()

    def is_modified(self) -> bool:
        """Check if the configuration file's contents have changed"""
        # Configuration can only be modified if it is from a configuration file
        if not self.settings.file:
            return False

        self.log.bind(event="debug").trace(
            "Testing if configuration file has been modified",
        )

        current_hash = self._hash_file(self.settings.file)
        if current_hash != self.content_hash:
            self.log.bind(event="info").info(
                "Configuration file has been modified",
            )
            return True

        self.log.bind(event="debug").trace(
            "Configuration file has not been modified",
        )
        return False

    def reload(self) -> bool:
        """Reload the configuration file.

        Returns True if the file parsed and validated successfully and the new
        settings were applied. Returns False on any failure; the previous
        settings remain in use. In both cases ``self.content_hash`` is updated
        to the current file contents so that ``is_modified`` does not retry
        the same bytes again — a fix only retriggers when the contents
        actually change.
        """
        # Hash the current file contents first so that even on failure we
        # avoid hot-looping on the same broken bytes. reload() is only called
        # for file-backed configs, so file is guaranteed non-None here.
        config_file = self.settings.file
        assert config_file is not None
        new_hash = self._hash_file(config_file)

        try:
            configuration = self._load_file(file=config_file)
        except Exception as exc:
            self.log.bind(event="error").error(
                "Configuration file has been modified but could not be parsed: {exc}",
                exc=exc,
            )
            self.content_hash = new_hash
            return False

        try:
            settings = Settings(**configuration, file=self.settings.file)
        except ValidationError as exc:
            self.log.bind(event="error").error(
                "Configuration file is invalid: {exc}",
                exc=exc,
            )
            self.content_hash = new_hash
            return False
        except Exception as exc:
            self.log.bind(event="error").error(
                "Exception loading configuration file: {exc}",
                exc=exc,
            )
            self.content_hash = new_hash
            return False

        # Success — adopt the new settings and remember the hash
        self.settings = settings
        self.content_hash = new_hash

        self.log.bind(event="info").info(
            "The configuration has been reloaded successfully",
        )
        return True
