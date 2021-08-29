# encoding: utf8


from functools import wraps
from maya import cmds


def maya_undo(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        cmds.undoInfo(openChunk=True)
        result = func(*args, **kwargs)
        cmds.undoInfo(cloasChunck=True)
        return result
    return wrapper


def keep_sel(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        sel = cmds.ls(sl=True, fl=True)
        result = func(*args, **kwargs)
        cmds.select(sel)
        return result
    return wrapper
