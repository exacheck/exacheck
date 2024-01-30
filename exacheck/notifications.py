# -*- coding: utf-8 -*-

"""
ExaCheck - ExaBGP Health Checker

Configure and manage notifications/alerting with Apprise
"""

from __future__ import annotations
from typing import Optional

import apprise
import loguru

from .settings.notifications import Notifications as NotificationSettings


class Notifications:
    """
    Set up Apprise notifications and manage the sending of notifications
    """

    def __init__(
        self,
        log_context: loguru.Logger,
        configuration: Optional[list[NotificationSettings]] = None,
    ):
        """
        Set up Apprise
        """

        # Set the logging context
        self.log = log_context.bind(subsystem="notification")

        # Set an empty check name
        self._check = None

        # Check if there is no configuration
        if not configuration:
            # Set noop flag and shortcut setup
            self.noop = True

            # Log shortcut
            self.log.bind(event="debug").debug(
                "No notification configuration defined; skipping setup"
            )

            # Return early
            return

        # Unset noop flag
        self.noop = False

        # Log setup
        self.log.bind(event="debug").debug("Setting up Apprise notification handlers")

        # Perform setup
        self._setup(configuration=configuration)

        # Create the list of notification types/levels for themes
        self._types = (
            ("announce", apprise.NotifyType.SUCCESS),
            ("withdraw", apprise.NotifyType.WARNING),
            ("error", apprise.NotifyType.FAILURE),
            ("info", apprise.NotifyType.INFO),
        )

    def _setup(self, configuration: list[NotificationSettings]):
        """
        Set up Apprise
        """

        # Create the Apprise asset
        asset = apprise.AppriseAsset(
            app_id="ExaCheck",
            app_desc="ExaCheck - ExaBGP Health Checker",
            app_url="https://exacheck.net"
        )

        # Create Apprise object
        self.apprise = apprise.Apprise(
            asset=asset,
        )

        # Loop over each notification target defined in the configuration file
        for target in configuration:
            # Log setup
            self.log.bind(event="debug").debug(
                "Configuring notification target {name}",
                name=target.name,
            )
            self.log.bind(event="debug").trace(
                "Notification URL: {url}",
                url=target.url,
            )
            self.log.bind(event="debug").trace(
                "Notification target is configured for the following events: {events}",
                events=", ".join(target.events),
            )

            # Check if the target has a list of checks to notify on
            if target.checks:
                # Log there is filtering
                self.log.bind(event="debug").trace(
                    "Notification target will be filtered to the following checks: {checks}",
                    checks=", ".join(target.checks),
                )

                # Create the list of tags for filtering to work
                tags = [
                    f"{check}-{event}"
                    for event in target.events
                    for check in target.checks
                ]

            else:
                # Log there is no filtering
                self.log.bind(event="debug").trace(
                    "Notification target will be used for all checks as no filter is defined",
                )

                # There is no filtering for checks, use the special check name "_all_"
                tags = [f"_all_-{event}" for event in target.events]

            # Check if general events should be logged
            if target.general_events:
                tags = tags + [f"_general_-{event}" for event in target.events]

            # Log tags
            self.log.bind(event="debug").trace(
                "Notification tags: {tags}",
                tags=", ".join(tags),
            )

            # Create the target URL with the tags
            try:
                self.apprise.add(f"{target.url}", tag=tags)
            except Exception as exc:
                self.log.bind(event="error").error(
                    "Failed to configure notification target {name} with URL {url}; skipping: {error}",
                    name=target.name,
                    url=target.url,
                    error=exc,
                )

    def notify(
        self,
        event: str,
        message: str,
        title: str = "ExaCheck Event",
        check: Optional[str] = None,
        log_context: Optional[loguru.Logger] = None,
    ):
        """
        Send a notification to the relevant targets

        Args:
            event (str): The event type
            title (str): The optional title for the notification
            message (str): The message to send
        """
        # If there is a log context, bind it
        if log_context:
            log = log_context.bind(subsystem="notification")
        else:
            log = self.log

        # If there is no notification configuration, return early
        if self.noop:
            if check:
                log.bind(event="debug").trace(
                    "Notification from check {check} of type {event} will be ignored as there is no notifications configured",
                    check=check,
                    event=event,
                )
            else:
                log.bind(event="debug").trace(
                    "General notification of type {event} will be ignored as there is no notifications configured",
                    event=event,
                )
            return

        # Log the fact that a notification needs to be sent
        if check:
            log.bind(event="debug").debug(
                "Notification from check {check} of type {event} will be sent to available notification channels",
                check=check,
                event=event,
            )
        else:
            log.bind(event="debug").debug(
                "General notification of type {event} will be sent to available notification channels",
                event=event,
            )

        # Log the content
        log.bind(event="datadump").trace(
            "Notification title: {title}",
            title=title,
        )
        log.bind(event="datadump").trace(
            "Notification message: {message}",
            message=message,
        )

        # Create the tags for the notification
        if check:
            tags = [f"{check}-{event}", f"_all_-{event}"]
        else:
            tags = [f"_general_-{event}"]

        # Get the notification type
        notification_type = [
            notify_type
            for notify_event, notify_type in self._types
            if notify_event == event
        ][0]

        # Send the notification
        log.bind(event="debug").debug(
            "Sending the notification with tags {tags}",
            tags=", ".join(tags),
        )

        try:
            self.apprise.notify(
                title=title,
                body=message,
                tag=tags,
                notify_type=notification_type,
                body_format=apprise.NotifyFormat.MARKDOWN,
            )
        except Exception as exc:
            log.bind(event="error").error(
                "Failed to send notification: {error}",
                error=exc,
            )
        else:
            log.bind(event="debug").debug(
                "Notification sent",
            )
