# encoding: utf8

__author__ = "Robin Lavigne"
__email__ = "contact@robinlavigne.com"
__credits__ = {'emotionalSupport': "Emilie Jolin", 'spellchecking': "Pranil Naicker"}


import sys
import importlib
from maya import cmds
import maya.api.OpenMaya as om

# python 2 to 3 compatibility
_pyversion = sys.version_info[0]
if _pyversion == 3:
    basestring = str
    reload = importlib.reload

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


def select(*args, add=False, replace=True):
    # todo: check if it really is undoable
    """
    Selects the args in the scene.
    :param args:
    :param add:
    :param replace:
    :param hierarchy:
    """
    # Checks that only one kwarg is used at a time.
    assert add ^ replace, AttributeError("add and replace can not be used at the same time")

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
    if replace:
        om.MGlobal.selectCommand(selection_list, listAdjustment=om.MGlobal.kReplaceList)
    else:
        om.MGlobal.selectCommand(selection_list, listAdjustment=om.MGlobal.kAddToList)
