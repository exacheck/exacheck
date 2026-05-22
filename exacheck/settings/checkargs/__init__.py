# -*- coding: utf-8 -*-

"""
ExaCheck - ExaBGP Health Checker

Check argument models.

Each method's args model lives in its own submodule and is imported by the
matching method class in ``exacheck.methods``. There is no need for this
package's __init__.py to enumerate them — the method registry in
``exacheck.methods`` is the single source of truth for which arg models exist.
"""
