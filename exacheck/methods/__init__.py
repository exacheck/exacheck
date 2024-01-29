# -*- coding: utf-8 -*-

"""
ExaCheck - ExaBGP Health Checker

Import check methods
"""

from .dns import DNS
from .file import File
from .http import HTTP
from .icmp import ICMP
from .ntp import NTP
from .shell import Shell
from .tcp import TCP

# Create a Python type of the check methods
CheckMethods = DNS | File | HTTP | ICMP | NTP | Shell | TCP

# Create a list of check methods with their class
METHODS = {
    "dns": ("DNS", DNS),
    "file": ("File", File),
    "http": ("HTTP", HTTP),
    "icmp": ("ICMP", ICMP),
    "ntp": ("NTP", NTP),
    "shell": ("Shell", Shell),
    "tcp": ("TCP", TCP),
}
