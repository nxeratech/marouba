from __future__ import absolute_import, print_function

try:
    from .manager import Manager
except Exception:
    Manager = None


def create_instance(c_instance):
    if Manager is None:
        raise RuntimeError("MaroubaAbleton failed to import Manager")
    return Manager(c_instance)
