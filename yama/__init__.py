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
    return yams(cmds.ls(sl=True, fl=True))


def select(objs):
    # todo: unpack lists, add add and other cmds kwargs
    selection_list = om.MSelectionList()
    if isinstance(objs, basestring):
        objs = [objs]
    for obj in objs:
        if isinstance(obj, nodes.DependNode):
            selection_list.add(obj.mObject)
        else:
            selection_list.add(obj)
    om.MGlobal.selectCommand(selection_list)
