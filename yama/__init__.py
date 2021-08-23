# encoding: utf8

import maya.cmds as mc
import nodes


yam = nodes.yam
yams = nodes.yams


def ls(*args, **kwargs):
    return yams(mc.ls(*args, **kwargs))


def selected():
    return yams(mc.ls(sl=True, fl=True))
