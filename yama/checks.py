# encoding: utf8

"""
Contains all the custom exceptions and warning classes and methods
"""

from maya import cmds


class ObjExistsError(Exception):
    pass


def objExists(obj, raiseError=False, verbose=False):
    if cmds.objExists(obj):
        return True
    elif raiseError == 'raise':
        raise ObjExistsError("'{}' does not exist in the current scene".format(obj))
    elif verbose == 'warning':
        cmds.warning("'{}' does not exist in the current scene".format(obj))
    else:
        return False
