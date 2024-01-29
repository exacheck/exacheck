# -*- coding: utf-8 -*-

"""
ExaCheck - ExaBGP Health Checker

Check Method - Shell Command
"""

from __future__ import annotations

import subprocess
from typing import Tuple

from ..checkresult import CheckResult
from ..settings.checkargs.shellargs import ShellArgs
from ._base import Base


# pylint: disable=too-few-public-methods
class Shell(Base):
    """
    Run a shell command health check
    """

    @staticmethod
    def _to_str(
        stdout: bytes | None, stderr: bytes | None
    ) -> Tuple[str | None, str | None]:
        """
        Convert stdout and stderr to strings if defined
        """
        # If there is stdout convert to string
        stdout_str: str | None = bytes.decode(stdout, "utf-8") if stdout else None

        # If there is stderr convert to string
        stderr_str: str | None = bytes.decode(stderr, "utf-8") if stderr else None

        return stdout_str, stderr_str

    def check(self) -> CheckResult:  # NOSONAR
        """
        Run the health check
        """
        # Set type for MyPy
        self.args: ShellArgs

        # Execute the command
        try:
            result = subprocess.run(  # nosemgrep:python.lang.security.audit.subprocess-shell-true.subprocess-shell-true
                self.args.command,
                check=True,
                shell=True,
                env=self.args.environment,
            )
        except subprocess.CalledProcessError as error:
            # Convert stdout/stderr to strings if defined
            stdout, stderr = self._to_str(error.stdout, error.stderr)
            # Return the health check result
            return CheckResult(
                success=False,
                message=f"Command returned non-zero exit code: {error.returncode}",
                output=stdout,
                error=stderr,
            )
        except Exception as exc:  # pylint: disable=broad-except
            return CheckResult(
                success=False,
                message="Shell command failed to execute",
                error=f"Exception raised: {exc}",
                exception=exc,
            )

        # Convert stdout/stderr to strings if defined
        stdout, stderr = self._to_str(result.stdout, result.stderr)

        # Return the result
        return CheckResult(
            success=True,
            message="Shell command executed successfully",
            output=stdout,
            error=stderr,
        )
