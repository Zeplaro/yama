# encoding: utf8

from functools import wraps
from maya import cmds


def mayaundo(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            cmds.undoInfo(openChunk=True)
            result = func(*args, **kwargs)
        finally:
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
        print("---- Calling {}; -args: {}; --kwargs: {}".format(func.__name__, args, kwargs))
        result = func(*args, **kwargs)
        print("---- Result of {} is : {}; of type : {}".format(func.__name__, result, type(result).__name__))
        return result
    return wrapper


def condition_debugger(condition):
    def decorator(func):
        def wrapper(*args, **kwargs):
            print("#$@&%*!    Function: '{}'; args={}, kwargs={}    #$@&%*!".format(func.__name__, args, kwargs))

            if eval(condition):
                raise RuntimeError("Condition met before: '{}'; Condition: '{}'".format(func.__name__, condition))

            result = func(*args, **kwargs)

            if eval(condition):
                raise RuntimeError("Condition met after: '{}'; Condition: '{}'".format(func.__name__, condition))

            return result
        return wrapper
    return decorator
