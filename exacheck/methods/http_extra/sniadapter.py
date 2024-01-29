# -*- coding: utf-8 -*-

"""
ExaCheck - ExaBGP Health Checker

HTTPS adapter for use with requests to allow SNI to work
"""

from requests.adapters import HTTPAdapter


class SNIAdapter(HTTPAdapter):
    """
    A HTTPS Adapter for Python Requests that sets the hostname for certificate
    verification based on the Host header.

    This allows requesting the IP address directly via HTTPS without getting
    a "hostname doesn't match" exception.

    Example usage:

        >>> s = requests.Session()
        >>> s.mount('https://', SNIAdapter())
        >>> s.get("https://192.0.2.1", headers={"Host": "example.org"})

    """

    def send(self, request, **kwargs):  # pylint: disable=arguments-differ
        # HTTP headers are case-insensitive (RFC 7230)
        host_header = None
        for header in request.headers:
            if header.lower() == "host":
                host_header = request.headers[header]
                break

        connection_pool_kwargs = self.poolmanager.connection_pool_kw

        if host_header:
            connection_pool_kwargs["assert_hostname"] = host_header
            connection_pool_kwargs["server_hostname"] = host_header
        elif "assert_hostname" in connection_pool_kwargs:
            # an assert_hostname from a previous request may have been left
            connection_pool_kwargs.pop("assert_hostname", None)
            connection_pool_kwargs.pop("server_hostname", None)

        return super(SNIAdapter, self).send(request, **kwargs)
