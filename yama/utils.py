# encoding: utf8

import sys
from maya import cmds, mel
import __init__ as ym
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


def component_range(node, comp, *args):
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


def get_skinCluster(obj):
    # todo: find a better way than 'mel.eval'
    skn = mel.eval('findRelatedSkinCluster {}'.format(obj))
    return nodes.yam(skn) if skn else None


def get_skinClusters(objs):
    return [get_skinCluster(obj) for obj in objs]


def skinas(slave_namespace=None, master=None, *slaves):
    if not master or not slaves:
        objs = cmds.ls(sl=True, tr=True, fl=True)
        if len(objs) < 2:
            cmds.warning('Please select at least two objects')
            return
        master = objs[0]
        slaves = objs[1:]
    master = ym.yam(master)
    slaves = ym.yams(slaves)

    masterskn = get_skinCluster(master)
    if not masterskn:
        cmds.warning('First object as no skinCluster attached')
        return
    infs = masterskn.influences()
    if slave_namespace is not None:
        infs = ym.yams(['{}:{}'.format(slave_namespace, inf) for inf in infs])
    sm = masterskn.skinningMethod.value
    mi = masterskn.maxInfluences.value
    nw = masterskn.normalizeWeights.value
    mmi = masterskn.maintainMaxInfluences.value
    wd = masterskn.weightDistribution.value
    done = []
    for slave in slaves:
        if get_skinCluster(slave):
            print(slave+' already has a skinCluster attached')
            continue
        cmds.select(infs.names, slave.name)
        slaveskn = cmds.skinCluster(name='skinCluster_{}#'.format(slave), sm=sm, mi=mi, nw=nw, omi=mmi, wd=wd,
                                    includeHiddenSelections=True, toSelectedBones=True)[0]
        cmds.copySkinWeights(ss=masterskn.name, ds=slaveskn.name, nm=True, sa='closestPoint',
                             ia=('oneToOne', 'label', 'closestJoint'))
        print(slave+' skinned')
        done.append(slave)
    return done


def hierarchize(objs, invert=False):
    objs = ym.yams(objs)
    objs = {obj.longname(): obj for obj in objs}
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


def mx_constraint(master=None, slave=None):
    # todo
    if not master or not slave:
        sel = ym.ls(sl=True, tr=True, fl=True)
        if len(sel) != 2:
            cmds.warning('Select two objects')
            return
        master, slave = ym.yams(sel)
        
    mmx = ym.createNode('multMatrix', n='{}_mmx'.format(master))
    dmx = ym.createNode('decomposeMatrix', n='{}_dmx'.format(master))
    cmx = ym.createNode('composeMatrix', n='{}_cmx'.format(master))
    cmx.outputMatrix.connectTo(mmx.matrixIn[0], f=True)
    master.worldMatrix[0].connectTo(mmx.matrixIn[1], f=True)
    slave.parentInverseMatrix[0].connectTo(mmx.matrixIn[2], f=True)
    mmx.matrixSum.connectTo(dmx.inputMatrix, f=True)

    loc1 = ym.yam(cmds.spaceLocator(n='{}_loc'.format(master))[0])
    ro = cmds.xform(master, q=True, ws=True, ro=True)
    t = cmds.xform(master, q=True, ws=True, t=True)
    cmds.xform(loc1, ws=True, ro=ro, t=t)
    loc2 = cmds.spaceLocator(n='{}_loc'.format(slave))[0]
    ro = cmds.xform(slave, q=True, ws=True, ro=True)
    t = cmds.xform(slave, q=True, ws=True, t=True)
    cmds.xform(loc2, ws=True, ro=ro, t=t)
    cmds.parent(loc2, loc1)

    cmds.setAttr('{}.inputTranslate'.format(cmx), *cmds.getAttr('{}.translate'.format(loc2))[0])
    cmds.setAttr('{}.inputRotate'.format(cmx), *cmds.getAttr('{}.rotate'.format(loc2))[0])
    cmds.setAttr('{}.inputScale'.format(cmx), *cmds.getAttr('{}.scale'.format(loc2))[0])
    cmds.setAttr('{}.inputShear'.format(cmx), *cmds.getAttr('{}.shear'.format(loc2))[0])

    cmds.connectAttr('{}.outputTranslate'.format(dmx), '{}.translate'.format(slave), f=True)
    cmds.connectAttr('{}.outputRotate'.format(dmx), '{}.rotate'.format(slave), f=True)
    cmds.connectAttr('{}.outputScale'.format(dmx), '{}.scale'.format(slave), f=True)
    cmds.connectAttr('{}.outputShear'.format(dmx), '{}.shear'.format(slave), f=True)

    cmds.delete(loc1, loc2)

    return target
