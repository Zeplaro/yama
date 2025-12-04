# encoding: utf8

import uuid
from functools import wraps

from maya import cmds
from . import utils, nodes


def mayaundo(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        chunk_id = uuid.uuid4()
        try:
            cmds.undoInfo(openChunk=True, chunkName=chunk_id)
            return func(*args, **kwargs)
        finally:
            cmds.undoInfo(closeChunk=True, chunkName=chunk_id)

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
        print(f"---- Calling {func.__name__}; -args: {args}; --kwargs: {kwargs}")
        result = func(*args, **kwargs)
        print(f"---- Result of {func.__name__} is : {result}; of type : {type(result).__name__}")
        return result

    return wrapper


def string_args(func):
    """
    Converts all args to string, and YamList to list (by using recursive_map), before passing them to the given func.
    Doing this allows to convert the args to str and still have the same behavior as the equivalent cmds function would
    with the same arguments.
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        args = tuple(utils.recursive_map(str, args, forcerecursiontypes=True))
        return func(*args, **kwargs)

    return wrapper


class Yammds:
    """
    Wraps a module functions to return yamified results (i.e. strings that are object names are converted to Yam objects).
    Usage:
        import yama
        cmds = Yammds(cmds)
        cmds.ls() # returns a list of Yam objects instead of strings
    """
    def __init__(self, module):
        self.__doc__ = getattr(module, '__doc__', self.__class__.__doc__)
        self.module = module

    def __getattr__(self, item):
        attr = getattr(self.module, item)
        return self._cook(attr) if callable(attr) else attr

    def __repr__(self):
        return f"<{self.__class__.__name__} wrapping {self.module!r}>"

    def _cook(self, func):
        """Wraps a function to yamify its results."""

        def recursive_yam(item):
            if isinstance(item, (list, tuple, set)):
                return type(item)(recursive_yam(x) for x in item)
            elif isinstance(item, str) and self.module.objExists(item):
                return nodes.yam(item)
            else:
                return item

        @wraps(func)
        def wrapper(*args, **kwargs):
            result = func(*args, **kwargs)
            return recursive_yam(result)

        return wrapper
