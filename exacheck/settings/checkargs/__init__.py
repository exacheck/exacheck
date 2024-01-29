# -*- coding: utf-8 -*-

"""
ExaCheck - ExaBGP Health Checker

Import check argument types
"""

# flake8: noqa

from .dnsargs import DNSArgs
from .fileargs import FileArgs
from .httpargs import HTTPArgs
from .icmpargs import ICMPArgs
from .ntpargs import NTPArgs
from .shellargs import ShellArgs
from .tcpargs import TCPArgs

# Create a Python type of the check args
CheckArgs = DNSArgs | FileArgs | HTTPArgs | ICMPArgs | NTPArgs | ShellArgs | TCPArgs

# Create a Python type of the check args that support remote checks
CheckArgsRemote = DNSArgs | HTTPArgs | ICMPArgs | NTPArgs | TCPArgs
