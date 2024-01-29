# -*- coding: utf-8 -*-

"""
ExaCheck - ExaBGP Health Checker

Worker process creation error
"""


class WorkerProcessError(Exception):
    """
    Exception raised when a worker process could not be created
    """

    def __init__(self, message: str = "Exception creating worker process"):
        """
        Set up the new WorkerProcessError object
        """
        self.message = message

    def __str__(self):
        return self.message
