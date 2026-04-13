# encoding: utf8
import inspect
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
    signature = inspect.signature(func)

    @wraps(func)
    def wrapper(*args, **kwargs):
        bound_args = signature.bind(*args, **kwargs)
        bound_args.apply_defaults()
        arg_strings = [f"{name}={repr(value)}" for name, value in bound_args.arguments.items()]
        print(f"---- Calling {func.__module__}.{func.__qualname__} with arguments:\n-------- {', '.join(arg_strings)}")
        result = func(*args, **kwargs)
        print(f"---- Result of {func.__name__} is :\n-------- {repr(result)}")
        return result

    return wrapper


def stringify_args(str_kwargs: list | tuple = (), /):
    """
    Converts all args to string, and YamList to list (by using recursive_map), before passing them to the given func.
    Doing this allows to convert the args to str and still have the same behavior as the equivalent cmds function would
    with the same arguments.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            new_args = tuple(utils.recursive_map(str, args, forcerecursiontypes=True))
            new_values = utils.recursive_map(str, (kwargs[key] for key in str_kwargs if key in kwargs))
            new_kwargs = kwargs | dict(((key, value) for key, value in zip(str_kwargs, new_values) if key in kwargs))
            return func(*new_args, **new_kwargs)
        return wrapper

    if callable(str_kwargs):
        _func, str_kwargs = str_kwargs, ()
        return decorator(_func)

    return decorator


def yammds(wrapped_module, /):
    """
    Wraps a module functions to return yamified results (i.e. strings that are object names are converted to Yam objects).
    Usage:
        import yama
        ymds = yammds(cmds)
        ymds.ls() # returns a list of Yam objects instead of strings
    """

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
