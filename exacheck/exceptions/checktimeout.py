# -*- coding: utf-8 -*-

"""
ExaCheck - ExaBGP Health Checker

Check timeout exception
"""


class CheckTimeout(Exception):
    """
    Exception raised when a check times out
    """

    def __init__(self, message: str = "The check timed out"):
        """
        Set up the new CheckTimeout object
        """
        self.message = message

    def __str__(self):
        return self.message
