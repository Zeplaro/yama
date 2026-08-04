# encoding: utf8

import inspect
import uuid
from functools import wraps, update_wrapper
from collections.abc import Callable

import maya.api.OpenMaya as om
from maya import cmds, mel


def mayaundo(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        chunk_name = f"{func.__module__}.{func.__qualname__} undoChunk: {uuid.uuid4()}"
        try:
            cmds.undoInfo(openChunk=True, chunkName=chunk_name)
            return func(*args, **kwargs)
        finally:
            cmds.undoInfo(closeChunk=True, chunkName=chunk_name)

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
            f"---- Calling {func.__module__}.{func.__qualname__} with arguments:\n--------"
            f" {', '.join(arg_strings)}"
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
                    "stringifyargs initialized with string kwargs now called with a none callable"
                    " first arg."
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


def mode_checker(func: Callable) -> Callable:
    """
    Decorator for functions that wrap a cmds function. This will raise an error when the function is called in
    query or edit mode and fails if the returned object is not a valid node or attribute.
    """
    mode_args = {"q", "query", "e", "edit"}

    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)

        except (ValueError, TypeError, AttributeError) as e:
            # Checking if a mode is given in kwargs and if any given mode is set to True
            if modes := [mode for mode in kwargs.keys() & mode_args if kwargs[mode]]:
                # Getting the mode long name to make the error message prettier.
                mode = {"q": "query", "e": "edit"}.get(modes[0], modes[0])
                raise RuntimeError(
                    f"The function ym.{func.__name__} in {mode} mode with the given kwargs did not"
                    f" return a valid node or attribute. Use cmds.{func.__name__} instead."
                )
            else:
                raise e

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


def closeNodeEditors(func: Callable = None, /, *, reopen: bool = False) -> Callable:
    """
    Decorator that safely closes all opened nodeEditor panels when calling the function it decorates nad reopens them
    after.
    Used to avoid the maya freezing when creating multiple nodes which get added to the node editor in real time.

    Can be used directly: @closeNodeEditors; or with reopen kwarg: @closeNodeEditors(reopen=False)

    Args:
        func: The decorated function if used without calling the decorator.
        reopen: If True, will reopen the primary node editor panel after calling the decorated function.
    """

    if func is not None and not callable(func):
        raise TypeError(f"Given func: {func} should be a callable not a {type(func).__name__}.")

    def closeNodeEditors_decorator(func_: Callable):
        if cmds.about(batch=True, q=True):
            return func_

        @wraps(func_)
        def closeNodeEditors_wrapper(*args, **kwargs):
            current_focus = cmds.getPanel(withFocus=True)
            panels = cmds.getPanel(scriptType="nodeEditorPanel") or []
            for panel in panels:
                if not cmds.panel(panel, exists=True):
                    continue
                panel_wrapper = f"{panel}Window"

                # Close Workspace Control (docked and modern floating panels)
                if cmds.workspaceControl(panel_wrapper, exists=True):
                    cmds.workspaceControl(panel_wrapper, edit=True, close=True)
                # Close Standard Window (legacy floating panels)
                if cmds.window(panel_wrapper, exists=True):
                    cmds.deleteUI(panel_wrapper, window=True)
                # Unparent the panel (panels manually shoved into a viewport pane)
                # safely detaches the UI without deleting the panel from memory.
                try:
                    cmds.scriptedPanel(panel, edit=True, unParent=True)
                except RuntimeError:
                    pass  # already unparented
                # Closes panels that are not the primary panel
                if panel != "nodeEditorPanel1":
                    cmds.deleteUI(panel, panel=True)

            try:
                result = func_(*args, **kwargs)

            finally:
                if panels and reopen:
                    mel.eval("nodeEditorWindow();")
                    if current_focus and (
                        cmds.control(current_focus, exists=True)
                        or cmds.panel(current_focus, exists=True)
                    ):

                        def _restoreFocus():
                            cmds.setFocus(current_focus)

                        cmds.evalDeferred(_restoreFocus)

            return result

        return closeNodeEditors_wrapper

    if func is None:
        return closeNodeEditors_decorator
    return closeNodeEditors_decorator(func)
