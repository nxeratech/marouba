from __future__ import absolute_import, print_function

import importlib


def create_instance(c_instance):
    try:
        from . import manager

        module = importlib.reload(manager)
        return module.Manager(c_instance)
    except Exception as error:
        raise RuntimeError("MaroubaAbleton failed to import Manager: %s" % error)
