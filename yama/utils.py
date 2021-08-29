# encoding: utf8

import sys
from maya import cmds

# python 2 to 3 compatibility
_pyversion = sys.version_info[0]
if _pyversion == 3:
    basestring = str


def create_hook(node, suffix_name='hook', parent=None):
    if cmds.objExists('{}_{}'.format(node.name, suffix_name)):
        suffix_name += '#'
    hook = cmds.group(em=True, n='{}_{}'.format(node, suffix_name))
    mmx = cmds.createNode('multMatrix', n='mmx_{}_{}'.format(node, suffix_name))
    dmx = cmds.createNode('decomposeMatrix', n='dmx_{}_{}'.format(node, suffix_name))
    cmds.connectAttr('{}.worldMatrix[0]'.format(node), '{}.matrixIn[1]'.format(mmx), f=True)
    cmds.connectAttr('{}.parentInverseMatrix[0]'.format(hook), '{}.matrixIn[2]'.format(mmx), f=True)
    cmds.connectAttr('{}.matrixSum'.format(mmx), '{}.inputMatrix'.format(dmx), f=True)
    cmds.connectAttr('{}.outputShear'.format(dmx), '{}.shear'.format(hook), f=True)
    cmds.connectAttr('{}.outputTranslate'.format(dmx), '{}.translate'.format(hook), f=True)
    cmds.connectAttr('{}.outputScale'.format(dmx), '{}.scale'.format(hook), f=True)
    cmds.connectAttr('{}.outputRotate'.format(dmx), '{}.rotate'.format(hook), f=True)
    if parent and cmds.objExists(parent):
        cmds.parent(hook, parent)
    return hook


def comp_range(node, comp, *args):
    """
    Returns a generator to iterate over a length of vertices full name
    :param node: the node containing the vertices
    :param comp: the component string; e.g.: 'vtx', 'cv', etc...
    :param args: passed on to 'range' function
    :return: generator
    """
    assert isinstance(comp, basestring)
    vtx_string = str(node)+'.'+comp+'[{}]'
    for i in range(*args):
        yield vtx_string.format(i)
