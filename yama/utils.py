# encoding: utf8

import sys
from maya import cmds
from . import select, yam, yams
import nodes

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
    Returns a generator to iterate over a length of vertices full name.
    :param node: str or YamNode; the node containing the vertices.
    :param comp: str; the component string; e.g.: 'vtx', 'cv', etc...
    :param args: int, int, int; start, stop and step as needed, passed on to 'range' function.
    :return: generator
    """
    assert isinstance(comp, basestring)
    vtx_string = str(node)+'.'+comp+'[{}]'
    for i in range(*args):
        yield vtx_string.format(i)


get_skinCluster = nodes.SkinCluster.get_skinCluster


def skinas(slave_namespace=None, master=None, *slaves):
    if not master or not slaves:
        objs = cmds.ls(sl=True, tr=True, fl=True)
        if len(objs) < 2:
            cmds.warning('Please select at least two objects')
            return
        master = objs[0]
        slaves = objs[1:]
    master = yam(master)
    slaves = yams(slaves)

    masterskn = get_skinCluster(master)
    if not masterskn:
        cmds.warning('First object as no skinCluster attached')
        return
    infs = masterskn.influences()
    if slave_namespace is not None:
        infs = yams(['{}:{}'.format(slave_namespace, inf) for inf in infs])
    sm = masterskn.skinMethod.value
    mi = masterskn.maximumInfluences.value
    nw = masterskn.normalizeWeights.value
    mmi = masterskn.maintainMaxInfluences.value
    wd = masterskn.weightDistribution.value
    done = []
    for slave in slaves:
        if nodes.SkinCluster.get_skinCluster(slave):
            print(slave+' already has a skin attached')
            continue
        select(infs, slave)
        cmds.skinCluster(name='skinCluster_{}#'.format(slave), sm=sm, mi=mi, nw=nw, omi=mmi, wd=wd, ihs=True, tsb=True)
        slaveskn = get_skinCluster(slave)
        cmds.copySkinWeights(ss=masterskn.name, ds=slaveskn.name, nm=True, sa='closestPoint',
                             ia=('oneToOne', 'label', 'closestJoint'))
        print(slave+' skinned')
        done.append(slave)
    return done


def hierarchize(objs, invert=False):
    objs = yams(objs)
    objs = {obj.longname: obj for obj in objs}
    longnames = list(objs)
    done = False
    while not done:
        done = True
        for i in range(len(longnames) - 1):
            if longnames[i].startswith(longnames[i + 1]):
                longnames.insert(i, longnames.pop(i + 1))
                done = False
    ordered = [objs[x] for x in longnames]
    return ordered if not invert else ordered[::-1]
