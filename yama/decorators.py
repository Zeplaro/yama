# encoding: utf8

from functools import wraps
from maya import cmds


def mayaundo(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        cmds.undoInfo(openChunk=True)
        result = func(*args, **kwargs)
        cmds.undoInfo(closeChunk=True)
        return result
    return wrapper


def keepsel(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        sel = cmds.ls(sl=True, fl=True)
        result = func(*args, **kwargs)
        cmds.select(sel)
        return result
    return wrapper


def verbose(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        print("---- Calling '{}' -args: '{}' --kwargs: '{}'".format(func.__name__, args, kwargs))
        return func(*args, **kwargs)
    return wrapper
