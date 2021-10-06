# encoding: utf8

import sys
from maya import cmds, mel
import __init__ as ym
import nodes

# python 2 to 3 compatibility
_pyversion = sys.version_info[0]
if _pyversion == 3:
    basestring = str


def createHook(node, suffix_name='hook', parent=None):
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


def componentRange(node, comp, *args):
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


def getSkinCluster(obj):
    # todo: find a better way than 'mel.eval'
    skn = mel.eval('findRelatedSkinCluster {}'.format(obj))
    return nodes.yam(skn) if skn else None


def getSkinClusters(objs):
    return nodes.YamList([getSkinCluster(obj) for obj in objs])


def skinAs(master=None, slaves=None, master_namespace=None, slave_namespace=None):
    if not master or not slaves:
        objs = ym.ls(sl=True, tr=True, fl=True)
        if len(objs) < 2:
            cmds.warning('Please select at least two objects')
            return

        def get_skinnable(objs):
            skinnable = nodes.YamList()
            for obj in objs:
                if obj.shapes(type='controlPoint'):
                    skinnable.append(obj)
                else:
                    skinnable.extend(get_skinnable(obj.children(type='transform')))
            return skinnable

        master = objs[0]
        slaves = get_skinnable(objs[1:])
    else:
        master = ym.yam(master)
        slaves = ym.yams(slaves)
    slaves = hierarchize(slaves, reverse=True)

    masterskn = getSkinCluster(master)
    if not masterskn:
        cmds.warning('First object as no skinCluster attached')
        return
    infs = masterskn.influences()

    if slave_namespace is not None:
        if master_namespace:
            infs = ym.yams([inf.name.replace(master_namespace + ':', slave_namespace + ':') for inf in infs])
        else:
            infs = ym.yams([slave_namespace + ':' + inf.name for inf in infs])
    done = []
    kwargs = {'skinMethod': masterskn.skinningMethod.value,
              'maximumInfluences': masterskn.maxInfluences.value,
              'normalizeWeights': masterskn.normalizeWeights.value,
              'obeyMaxInfluences': masterskn.maintainMaxInfluences.value,
              'weightDistribution': masterskn.weightDistribution.value,
              'includeHiddenSelections': True,
              'toSelectedBones': True,
              }
    for slave in slaves:
        if getSkinCluster(slave):
            print(slave + ' already has a skinCluster attached')
            continue
        cmds.select(infs.names(), slave.name)
        slaveskn = nodes.yam(cmds.skinCluster(name='{}_SKN'.format(slave), **kwargs)[0])
        cmds.copySkinWeights(ss=masterskn.name, ds=slaveskn.name, nm=True, sa='closestPoint',
                             ia=('oneToOne', 'label', 'closestJoint'))
        print(slave + ' skinned -> ' + slaveskn.name)
        done.append(slave)
    return done


def hierarchize(objs, reverse=False):
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
    ordered = nodes.YamList([objs[x] for x in longnames])
    if reverse:
        ordered.reverse()
    return ordered


def mxConstraint(master=None, slave=None):
    # todo
    if not master or not slave:
        sel = ym.ls(sl=True, tr=True, fl=True)
        if len(sel) != 2:
            cmds.warning('Select two objects')
            return
        master, slave = ym.yams(sel)
    else:
        master, slave = ym.yams([master, slave])
        
    mmx = ym.createNode('multMatrix', n='{}_mmx'.format(master))
    dmx = ym.createNode('decomposeMatrix', n='{}_dmx'.format(master))
    cmx = ym.createNode('composeMatrix', n='{}_cmx'.format(master))
    cmx.outputMatrix.connectTo(mmx.matrixIn[0], f=True)
    master.worldMatrix[0].connectTo(mmx.matrixIn[1], f=True)
    slave.parentInverseMatrix[0].connectTo(mmx.matrixIn[2], f=True)
    mmx.matrixSum.connectTo(dmx.inputMatrix, f=True)

    master_tmp = ym.createNode('transform', n='{}_mastertmp'.format(master))
    slave_tmp = ym.createNode('transform', n='{}_mastertmp'.format(slave))
    master_tmp.setXform(m=master.getXform(m=True, ws=True), ws=True)
    slave_tmp.setXform(m=slave.getXform(m=True, ws=True), ws=True)
    slave_tmp.parent = master_tmp

    cmx.inputTranslate.value = slave_tmp.translate.value
    cmx.inputRotate.value = slave_tmp.rotate.value
    cmx.inputScale.value = slave_tmp.scale.value
    cmx.inputShear.value = slave_tmp.shear.value

    dmx.outputTranslate.connectTo(slave.translate, f=True)
    dmx.outputRotate.connectTo(slave.rotate, f=True)
    dmx.outputScale.connectTo(slave.scale, f=True)
    dmx.outputShear.connectTo(slave.shear, f=True)

    cmds.delete(master_tmp.name, slave_tmp.name)


def resetAttrs(objs=None, t=True, r=True, s=True, v=True, user=False):
    """
    Resets the objs translate, rotate, scale, visibility and/or user defined attributes to their default values.
    :param objs: list of objects to reset the attributes on. If None then the selected objects are reset.
    :param t: if True resets the translate value to 0
    :param r: if True resets the rotate value to 0
    :param s: if True resets the scale value to 1
    :param v: if True resets the visibility value to 1
    :param user: if True resets the user attributes values to their respective default values.
    """
    if not objs:
        objs = cmds.ls(sl=True, fl=True)
        if not objs:
            cmds.warning('Select a least one object')
            return
    objs = nodes.yams(objs)

    tr = ''
    if t:
        tr += 't'
    if r:
        tr += 'r'
    for obj in objs:
        for axe in 'xyz':
            for tr_ in tr:
                if obj.attr(tr_+axe).settable():
                    obj.attr(tr_+axe).value = 0
            if s:
                if obj.attr('s'+axe).settable():
                    obj.attr('s'+axe).value = 1
        if v:
            if obj.v.settable():
                obj.v.value = True
        if user:
            attrs = obj.listAttr(ud=True, scalar=True, visible=True)
            for attr in attrs:
                if not attr.settable():
                    continue
                attr.value = attr.defaultValue
