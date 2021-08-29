# encoding: utf8

__author__ = "Robin Lavigne"
__email__ = "contact@robinlavigne.com"
__credits__ = {'emotionalSupport': "Emilie Jolin", 'spellchecking': "Pranil Naicker"}


import sys
import importlib
from maya import cmds

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
