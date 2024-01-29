# -*- coding: utf-8 -*-

"""
ExaCheck - ExaBGP Health Checker

Store configuration for notification channels
"""

from typing import Optional, Literal

from pydantic import Field, AnyUrl, field_validator
from pydantic_core.core_schema import ValidationInfo

from ._base import Base


class Notifications(Base):
    name: str = Field(
        title="Notification Name",
        description="The name of the notification service",
        pattern=r"^[^\"']+$",
    )

    description: Optional[str] = Field(
        title="Check Description",
        description="An optional description for the notification service (not parsed)",
        default=None,
    )

    url: AnyUrl = Field(
        title="URL",
        description="The URL to send notifications to (with Apprise)",
    )

    checks: Optional[list[str]] = Field(
        title="Notify Checks",
        description="The list of checks that should have notifications sent to this target",
        default=None,
    )

    events: list[Literal["announce", "info", "error", "withdraw"]] = Field(
        title="Notify Events",
        description="The list of events that should result in notifications being sent to this target",
        default=[
            "announce",
            "error",
            "info",
            "withdraw",
        ],
    )

    general_events: bool = Field(
        title="General Events",
        description="Whether general events not associated with any check should be sent to this target",
        default=False,
    )

    @field_validator("url")
    def validate_url(  # NOSONAR pylint: disable=no-self-argument
        cls, url: AnyUrl, values: ValidationInfo
    ) -> AnyUrl:
        """
        Validate the notification URL
        """
        # Create the apprise object
        import apprise

        apobj = apprise.Apprise()

        # Try adding the notification target
        try:
            apobj.add(url)
        except Exception as exc:
            raise ValueError(f"Invalid notification target URL: {exc}")

        # Create a list to store all schema names for available notifications
        schemas = []

        # Loop over all schemas available from apprise and add to schemas
        details = apobj.details()
        schemas.extend(
            [
                scheme
                for schema in details["schemas"]
                for scheme in schema["details"]["tokens"]["schema"]["values"]
            ]
        )

        # Make sure the URL schema matches
        if url.scheme not in schemas:
            raise ValueError(
                f"Invalid notification target URL scheme (check https://github.com/caronc/apprise for supported schemes): {url.scheme}"
            )

        # Return the URL
        return url
