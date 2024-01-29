# -*- coding: utf-8 -*-

"""
ExaCheck - ExaBGP Health Checker

Check Method - File Path
"""


from os import R_OK, access

from ..checkresult import CheckResult
from ..settings.checkargs.fileargs import FileArgs
from ._base import Base


# pylint: disable=too-few-public-methods
class File(Base):
    """
    Run a file path health check
    """

    def check(self) -> CheckResult:  # NOSONAR
        """
        Run the health check
        """
        # Set type for MyPy
        self.args: FileArgs

        # Ensure path can be read
        if not access(self.args.path.parent, R_OK):
            return CheckResult(
                success=False,
                message=(
                    f"File path '{self.args.path}' parent directory '{self.args.path.parent}' is not readable; "
                    "the check will always fail"
                ),
            )

        # Check if the file exists
        try:
            exists = self.args.path.exists()
        except Exception as exc:  # pylint: disable=broad-except
            return CheckResult(
                success=False,
                message=f"Failed to check file '{self.args.path}'",
                error=f"Failed to check file '{self.args.path}': {exc}",
                exception=exc,
            )

        if exists:
            # File exists; check if it should
            if self.args.exists:
                # File should be existing and it does, return the check result
                return CheckResult(
                    success=True,
                    message=f"File {self.args.path} exists",
                )

            # File should not be existing and it does, return
            return CheckResult(
                success=False,
                message=f"File {self.args.path} exists",
                error=f"The file {self.args.path} must not exist",
            )

        # File does not exist, check if it should
        if self.args.exists:
            # File should be existing and it doesn't, return
            return CheckResult(
                success=False,
                message=f"File {self.args.path} does not exist",
                error=f"The file {self.args.path} must exist",
            )

        # File should not be existing and it does, return
        return CheckResult(
            success=True,
            message=f"File {self.args.path} does not exist",
        )
