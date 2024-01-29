# -*- coding: utf-8 -*-

"""
ExaCheck - ExaBGP Health Checker

DNS resolution error; host name could not be resolved
"""


class DNSResolutionError(Exception):
    """
    Exception raised when a hostname could not be resolved to an IP address
    """

    def __init__(self, message: str):
        """
        Set up the new DNSResolutionError object
        """
        self.message = message

    def __str__(self):
        return self.message
