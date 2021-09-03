# encoding: utf8

__author__ = "Robin Lavigne"
__email__ = "contact@robinlavigne.com"
__credits__ = {'emotionalSupport': "Emilie Jolin", 'spellchecking': "Pranil Naicker"}


import sys
from maya import cmds
import maya.api.OpenMaya as om

# python 2 to 3 compatibility
_pyversion = sys.version_info[0]
if _pyversion == 3:
    basestring = str
    from importlib import reload

import nodes
reload(nodes)  # Temporary, while in-dev; todo: remove that line


yam = nodes.yam
yams = nodes.yams
createNode = nodes.createNode


def ls(*args, **kwargs):
    return yams(cmds.ls(*args, **kwargs))


def selected():
    # todo: add support for component selection
    sel = om.MGlobal.getActiveSelectionList(orderedSelectionIfAvailable=True)
    return yams(sel.getDependNode(x) for x in range(sel.length()))


def select(*args, **kwargs):
    """
    Changes the scene active selection.
    This is maya undoable even if it uses the api.
    :param args: any objects or list of objects to select.
    :param kwargs: checks only for 'add' in kwargs to add to the current selection instead of replacing it.
    """
    add = kwargs.get('add', False)
    selection_list = om.MSelectionList()
    for arg in args:
        if isinstance(arg, (basestring, om.MObject, om.MDagPath)):
            selection_list.add(arg)
        elif isinstance(arg, nodes.DependNode):
            selection_list.add(arg.name)
        elif hasattr(arg, '__iter__'):
            for arg_ in arg:
                if isinstance(arg_, (basestring, om.MObject, om.MDagPath)):
                    selection_list.add(arg_)
                elif isinstance(arg_, nodes.DependNode):
                    selection_list.add(arg_.name)
        else:
            raise AttributeError('failed to select: {} of type {}'.format(arg, type(arg).__name__))
    if add:
        om.MGlobal.selectCommand(selection_list, listAdjustment=om.MGlobal.kAddToList)
    else:
        om.MGlobal.selectCommand(selection_list, listAdjustment=om.MGlobal.kReplaceList)
