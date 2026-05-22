# -*- coding: utf-8 -*-

"""
ExaCheck - ExaBGP Health Checker

Store configuration for notification channels
"""

from typing import Optional, Literal

from pydantic import Field, AnyUrl, field_validator

from ._base import Base


# Cache of supported Apprise URL schemes. apprise.Apprise().details() walks
# the full plugin catalogue and is expensive, so resolve it once on first
# call instead of once per validated notification URL.
_APPRISE_SCHEMAS: Optional[list[str]] = None


def _apprise_schemas() -> list[str]:
    """Return the cached set of Apprise URL schemes supported by this install."""
    # pylint: disable=global-statement
    global _APPRISE_SCHEMAS
    if _APPRISE_SCHEMAS is None:
        import apprise  # pylint: disable=import-outside-toplevel

        details = apprise.Apprise().details()
        _APPRISE_SCHEMAS = [
            scheme
            for schema in details["schemas"]
            for scheme in schema["details"]["tokens"]["schema"]["values"]
        ]
    return _APPRISE_SCHEMAS


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
    def validate_url(cls, url: AnyUrl) -> AnyUrl:  # pylint: disable=no-self-argument
        """
        Validate the notification URL
        """
        # Try registering the target with a throwaway Apprise instance to
        # catch any plugin-side validation errors that surface as exceptions.
        import apprise  # pylint: disable=import-outside-toplevel

        try:
            apprise.Apprise().add(str(url))
        except Exception as exc:
            raise ValueError(f"Invalid notification target URL: {exc}")

        # Make sure the URL scheme is one Apprise actually supports.
        if url.scheme not in _apprise_schemas():
            raise ValueError(
                f"Invalid notification target URL scheme (check "
                f"https://github.com/caronc/apprise for supported schemes): "
                f"{url.scheme}"
            )

        return url
