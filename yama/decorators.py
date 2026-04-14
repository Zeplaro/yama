# encoding: utf8

import inspect
import uuid
from functools import wraps, update_wrapper

from maya import cmds
import maya.api.OpenMaya as om


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
        sl = om.MGlobal.getActiveSelectionList()
        try:
            result = func(*args, **kwargs)
        finally:
            om.MGlobal.setActiveSelectionList(sl)
        return result

    return wrapper


def verbose(func):
    signature = inspect.signature(func)

    @wraps(func)
    def wrapper(*args, **kwargs):
        bound_args = signature.bind(*args, **kwargs)
        bound_args.apply_defaults()
        arg_strings = [f"{name}={repr(value)}" for name, value in bound_args.arguments.items()]
        print(
            f"---- Calling {func.__module__}.{func.__qualname__} with arguments:\n-------- {', '.join(arg_strings)}"
        )
        result = func(*args, **kwargs)
        print(f"---- Result of {func.__name__} is :\n-------- {repr(result)}")
        return result

    return wrapper


class stringify_args:
    """
    Converts all args to string, and YamList to list (by using recursive_map), before passing them to the given func.
    Doing this allows to convert the args to str and still have the same behavior as the equivalent cmds function would
    with the same arguments.
    Option to give a list of kwarg keys whose values will also be converted to str.
    """

    def __init__(self, func, /, *args):
        if callable(func):
            self.func = func
            self.str_kwargs = ()
            update_wrapper(self, func)
        else:
            self.func = None
            if not isinstance(func, (tuple, list, set)) and not args:
                self.str_kwargs = func
            else:
                self.str_kwargs = (func, *args)

    def __repr__(self):
        return repr(self.func) if self.func is not None else super().__repr__()

    def __call__(self, *args, **kwargs):
        if self.func is None:
            if not args:
                raise RuntimeError(
                    "stringifyargs initialized with string kwargs now called with no args."
                )
            if not callable(func := args[0]):
                raise ValueError(
                    "stringifyargs initialized with string kwargs now called with a none callable first arg."
                )
            self.func = func
            update_wrapper(self, self.func)
            return self

        return self.getWrapper()(*args, **kwargs)

    def __get__(self, instance, owner=None):
        if instance is None:
            return self
        return self.getWrapper(instance)

    def getWrapper(self, instance=None):
        from . import utils

        @wraps(self.func)
        def wrapper(*args, **kwargs):
            str_args = utils.recursive_map(str, args, forcerecursiontypes=True)
            str_kwarg_keys = [x for x in self.str_kwargs if x in kwargs]
            str_kwarg_values = utils.recursive_map(
                str, (kwargs[key] for key in str_kwarg_keys), forcerecursiontypes=True
            )
            new_kwargs = kwargs | dict(zip(str_kwarg_keys, str_kwarg_values))

            if instance is not None:
                str_args = instance, *str_args
            return self.func(*str_args, **new_kwargs)

        return wrapper


def yammds(wrapped_module, /):
    """
    Wraps a module functions to return yamified results (i.e. strings that are object names are converted to Yam objects).
    Usage:
        import yama
        ymds = yammds(cmds)
        ymds.ls() # returns a list of Yam objects instead of strings
    """
    from . import nodes

    def cook(func):
        """Wraps a function to yamify its results."""

        def recursive_yam(item):
            if isinstance(item, (list, tuple, set)):
                return type(item)(recursive_yam(x) for x in item)
            elif isinstance(item, str) and wrapped_module.objExists(item):
                return nodes.yam(item)
            else:
                return item

        @wraps(func)
        def wrapper(*args, **kwargs):
            result = func(*args, **kwargs)
            return recursive_yam(result)

        return wrapper

    class ModuleWrapper:
        """Wraps a module to yamify its callable attributes' results."""

        module = wrapped_module
        __doc__ = wrapped_module.__doc__

        def __getattr__(self, item):
            attr = getattr(wrapped_module, item)
            return cook(attr) if callable(attr) else attr

    return ModuleWrapper()


def return_yam(func=None, /, *, passNone=False):
    from . import nodes

    if func is not None and not callable(func):
        raise TypeError(f"Given func: {func} should be a callable not a {type(func).__name__}.")

    def decorator(func_):
        @wraps(func_)
        def wrapper(*args, **kwargs):
            result = func_(*args, **kwargs)
            if passNone and result is None:
                return None
            return nodes.yam(result)

        return wrapper

    if func is None:
        return decorator
    return decorator(func)


def return_yams(func):
    from . import nodes

    @wraps(func)
    def wrapper(*args, **kwargs):
        return nodes.yams(func(*args, **kwargs))

    return wrapper
