# -*- coding: utf-8 -*-

"""
ExaCheck - ExaBGP Health Checker

Test to ensure that the configuration is loaded and validated correctly
"""

from pathlib import Path

from pydantic import ValidationError

from exacheck.exacheck import ExaCheck
from exacheck.settings.settings import Settings
from exacheck.settings.check import Check


def test_valid_minimal():
    """
    Test a minimal valid configuration
    """
    config = Settings(
        checks=[
            Check(
                name="test",
                prefixes=["192.0.2.1/32"],
                nexthop="192.0.2.1",
                args={
                    "method": "tcp",
                    "host": "192.0.2.1",
                    "port": 80,
                },
            ),
        ],
    )
    assert isinstance(config, Settings)


def test_invalid_address_family():
    """
    Test a minimal invalid configuration

    IPv4 prefixes are being advertised to an IPv6 next hop address
    """
    try:
        Settings(
            checks=[
                Check(
                    name="test",
                    prefixes=["192.0.2.1/32"],
                    nexthop="2001:db8::",
                    args={
                        "method": "tcp",
                        "host": "192.0.2.1",
                        "port": 80,
                    },
                ),
            ],
        )
    except ValidationError:
        pass
    else:
        assert False


def test_from_file():
    """
    Test loading configuration from a file
    """
    # Get test file path
    directory = Path(__file__).parent

    # Create path to configuration file to load from
    configuration = directory / "configuration" / "valid_minimal.yaml"

    # Create the ExaCheck object
    exacheck = ExaCheck(
        file=configuration,
        verbosity=0,
        dry_run=True,
    )

    # Make sure the object is of the correct type
    assert isinstance(exacheck, ExaCheck)
