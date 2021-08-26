# encoding: utf8

__author__ = "Robin Lavigne"
__email__ = "contact@robinlavigne.com"
__credits__ = {'emotionalsupport': "Emilie Jolin", 'spellchecking': "Pranil Naicker"}


import maya.cmds as mc
import nodes
reload(nodes)  # Temporary, while in-dev


yam = nodes.yam
yams = nodes.yams
createNode = nodes.createNode


def ls(*args, **kwargs):
    return yams(mc.ls(*args, **kwargs))


def selected():
    return yams(mc.ls(sl=True, fl=True))
