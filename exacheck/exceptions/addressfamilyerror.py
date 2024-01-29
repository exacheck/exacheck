# -*- coding: utf-8 -*-

"""
ExaCheck - ExaBGP Health Checker

Address family error; the IP address family does not match the requested address family
"""


class AddressFamilyError(Exception):
    """
    Exception raised when a hostname is resolved to an IP address that does not match the requested address family
    """

    def __init__(self, message: str):
        """
        Set up the new AddressFamilyError object
        """
        self.message = message

    def __str__(self):
        return self.message
