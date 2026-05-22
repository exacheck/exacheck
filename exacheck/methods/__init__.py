# -*- coding: utf-8 -*-

"""
ExaCheck - ExaBGP Health Checker

Health check method registry.

Concrete method classes self-register on import via ``Base.__init_subclass__``.
All non-private submodules of this package are imported automatically here so
that registration fires without the package's __init__.py having to enumerate
each method by hand — adding a new method is just a matter of dropping a new
file into this directory.
"""

from __future__ import annotations

import importlib
import pkgutil

from ._base import Base

# Import every non-private submodule so each concrete class registers itself.
for _info in pkgutil.iter_modules(__path__):
    if not _info.name.startswith("_"):
        importlib.import_module(f"{__name__}.{_info.name}")
del _info, importlib, pkgutil


def get(method: str) -> type[Base]:
    """Return the check method class registered for ``method``.

    Raises:
        KeyError: if no method with that name has been registered.
    """
    return Base._registry[method]  # pylint: disable=protected-access


def names() -> list[str]:
    """Return the sorted list of registered method names."""
    return sorted(Base._registry)  # pylint: disable=protected-access
