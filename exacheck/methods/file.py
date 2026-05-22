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

    method_name = "file"
    args_model = FileArgs
    args: FileArgs  # pyre-ignore[13]: narrows the parent's args type; init happens in Base

    def check(self) -> CheckResult:  # NOSONAR
        """
        Run the health check
        """

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

        ok = exists == self.args.exists
        state = "exists" if exists else "does not exist"
        return CheckResult(
            success=ok,
            message=f"File {self.args.path} {state}",
            error=(
                None
                if ok
                else f"The file {self.args.path} must {'' if self.args.exists else 'not '}exist"
            ),
        )
