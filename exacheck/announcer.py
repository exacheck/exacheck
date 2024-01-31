# -*- coding: utf-8 -*-

"""
ExaCheck - ExaBGP Health Checker

Manage the announcement and withdrawal of routes to ExaBGP
"""

from __future__ import annotations

import re
from sys import stdout
from pprint import pformat
from typing import Literal

import loguru

from .settings.check import Check


class Announcer:
    """
    Announce and withdraw routes from ExaBGP
    """

    def __init__(self, check: Check, log_context: loguru.Logger):
        """Set up the new ExaCheck announcer object

        Args:
            check (Check): The health check configuration object
            log_context (loguru.Logger): The loguru logging context
        """

        # Set the logging context
        self.log = log_context.bind(subsystem="announcer")

        # Build the list of routes to manage
        self.routes = self.generate_routes(check=check)

        # Log completion of setup
        self.log.bind(event="debug").info("New route announcer object setup")

    def announce(self, metric: int | None = None) -> None:
        """Announce a route to ExaBGP

        Args:
            metric (int | None, optional): The metric for the route. Defaults to None.
        """
        # Log the route advertisement event
        self.log.bind(event="info").info("Advertising routes")

        # Advertise the routes
        self.send_command(command="announce", metric=metric)

    def withdraw(self, metric: int | None = None, silent: bool = False) -> None:
        """Withdraw a route from ExaBGP

        Args:
            metric (int | None, optional): The metric for the route. Defaults to None.
        """
        # Log the route withdraw event
        if not silent:
            self.log.bind(event="info").info("Withdrawing routes")

        # Withdraw the routes
        self.send_command(command="withdraw", metric=metric, silent=silent)

    def send_command(
        self,
        command: Literal["announce", "withdraw"],
        metric: int | None = None,
        silent: bool = False,
    ) -> None:
        """Send the announce or withdraw command to ExaBGP

        The command is sent to ExaBGP via stdout.

        Args:
            command (Literal["announce","withdraw]): If the route needs to be withdrawn or announced/advertised.
            metric (int | None, optional): The metric for the route. Defaults to None.
        """
        # Test if a metric was defined; if set, create the metric string
        if metric:
            med = f"med {metric}"
        else:
            # No metric defined, just set to empty variable
            med = None

        # Loop over each route
        for route in self.routes:
            # Format the route with command and MED/metric
            route_string = route.format(command=command, metric=med)

            # Log the command being sent
            if not silent:
                self.log.bind(event="datadump").trace(
                    "Sending command to ExaBGP:\n{route}",
                    route=route_string,
                )

            # Send the command to ExaBGP
            try:
                print(route_string)
                stdout.flush()
            except Exception as exc:
                # Log the error sending the command
                if not silent:
                    self.log.bind(event="error").error(
                        "Error sending command to ExaBGP: {exc}",
                        exc=exc,
                    )

    def generate_routes(self, check: Check) -> list[str]:
        """Generate the route commands used by ExaBGP to announce/withdraw routes

        Args:
            check (Check): The health check configuration object.

        Returns:
            list[str]: The list of formatted routes as strings ready for ExaBGP.
        """
        # Send log about generation
        self.log.bind(event="info").debug("Generating route(s) to announce/withdraw")

        # Create empty list to store the route to use as a template
        route_template: list[str] = []

        # Check if there are neighbors
        if check.neighbors:
            # Create a list of neighbors
            neighbors = [f"neighbor {neighbor}" for neighbor in check.neighbors]
            # Add the neighbors to route
            route_template.append(", ".join(neighbors))

        # Add the announce/withdraw command which will be formatted when actually announcing/withdrawing
        route_template.append("{{command}}")

        # Add the route prefix
        route_template.append("route {prefix}")

        # Add the next hop
        route_template.append(f"next-hop {check.nexthop}")

        # Add the metric placeholder if required
        if check.metric or check.metric_down:
            route_template.append("{{metric}}")

        # Add the local preference if defined
        if check.local_preference:
            route_template.append(f"local-preference {check.local_preference}")

        # Add BGP communities if defined
        if check.communities:
            route_template.append(self._generate_communities(check.communities))

        # Add the AS path if defined
        if check.as_path:
            route_template.append(f"as-path {check.as_path}")

        # Add the path ID if required
        if check.path_id:
            route_template.append(f"path-information {check.path_id}")

        # Join route template
        route_template_string = " ".join(route_template)

        # Log the generated route template
        self.log.bind(event="info").debug(
            "Generated route template: {route_template_string}",
            route_template_string=route_template_string,
        )

        # Create empty list to store the routes
        routes: list[str] = []

        # Loop over each prefix defined in the check
        for prefix in check.prefixes:
            # Apply prefix to route template and append to routes
            routes.append(route_template_string.format(prefix=prefix))

        # Log the completed routes
        self.log.bind(event="datadump").trace(
            "Generated routes from template:\n{routes}",
            routes=pformat(routes, indent=4, width=120),
        )

        # Return routes
        return routes

    def _generate_communities(self, communities: list[str]) -> str:
        """Generate a list of communities to insert into the route string to advertise

        This is required as the community type needs to be determined (to see if it is a large or extended community).

        Args:
            communities (list[str]): The list of BGP communities to insert into the route string

        Returns:
            str: The formatted communities as a single string.
        """
        # Log community generation
        self.log.bind(event="debug").debug(
            "Generating communities to insert into route"
        )
        self.log.bind(event="datadump").trace(
            "Raw communities:\n{communities}",
            communities=pformat(communities, indent=4, width=120),
        )

        # Create community regex patterns
        standard_pattern = re.compile(r"^\d{1,10}:\d{1,10}$")
        large_pattern = re.compile(r"^\d{1,10}:\d{1,10}:\d{1,10}$")

        # Create empty list to store each form of communities
        standard: list[str] = []
        large: list[str] = []
        extended: list[str] = []

        # Loop over each community provided
        for community in communities:
            # Check if the community is a standard community
            if standard_pattern.match(community):
                # Add the community to the standard list
                standard.append(community)
                continue

            # Check if the community is a large community
            if large_pattern.match(community):
                # Add the community to the large list
                large.append(community)
                continue

            # Make the assumption the community is extended if reaching this point
            extended.append(community)

        # Create list to store the communities after formatting
        community_string: list[str] = []

        # Check if there are any standard communities
        if standard:
            # Add the standard communities to the route
            community_string.append(f"community [{' '.join(standard)}]")

        # Check if there are any standard communities
        if large:
            # Add the standard communities to the route
            community_string.append(f"large-community [{' '.join(large)}]")

        # Check if there are any standard communities
        if extended:
            # Add the standard communities to the route
            community_string.append(f"extended-community [{' '.join(extended)}]")

        # Return the communities joined together
        communities_joined = " ".join(community_string)
        self.log.bind(event="datadump").trace(
            "Generated communities string:\n{community_string}",
            community_string=communities_joined,
        )
        return communities_joined
