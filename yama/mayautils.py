# encoding: utf8

import sys
from maya import cmds, mel
import maya.api.OpenMaya as om
import nodes
import xformutils
import utils
import decorators

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


def getSkinCluster(obj):
    # todo: find a better way than 'mel.eval'
    skn = mel.eval('findRelatedSkinCluster {}'.format(obj))
    return nodes.yam(skn) if skn else None


def getSkinClusters(objs):
    return nodes.YamList([getSkinCluster(obj) for obj in objs])


def skinAs(objs=None, master_namespace=None, slave_namespace=None):
    if not objs:
        objs = nodes.ls(sl=True, tr=True, fl=True)

        def getSkinnable(objs_):
            skinnable = []
            for obj in objs_:
                if obj.shapes(type='controlPoint'):
                    skinnable.append(obj)
                else:
                    skinnable.extend(getSkinnable(obj.children(type='transform')))
            return skinnable

        objs = [objs[0]] + getSkinnable(objs[1:])
    if len(objs) < 2:
            cmds.warning('Please select at least two objects')
            return
    master = nodes.yam(objs[0])
    slaves = hierarchize(objs[1:], reverse=True)

    masterskn = getSkinCluster(master)
    if not masterskn:
        cmds.warning('First object as no skinCluster attached')
        return
    infs = masterskn.influences()

    if slave_namespace is not None:
        if master_namespace:
            infs = nodes.yams([inf.name.replace(master_namespace + ':', slave_namespace + ':') for inf in infs])
        else:
            infs = nodes.yams([slave_namespace + ':' + inf.name for inf in infs])
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
    objs = {obj.longName(): obj for obj in nodes.yams(objs)}
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
    if not master or not slave:
        sel = nodes.selected(type='transform')
        if len(sel) != 2:
            raise RuntimeError("two 'transform' needed; {} given".format(len(sel)))
        master, slave = sel
    else:
        master, slave = nodes.yams([master, slave])

    mmx = nodes.createNode('multMatrix', n='{}_mmx'.format(master))
    dmx = nodes.createNode('decomposeMatrix', n='{}_dmx'.format(master))
    cmx = nodes.createNode('composeMatrix', n='{}_cmx'.format(master))
    cmx.outputMatrix.connectTo(mmx.matrixIn[0], f=True)
    master.worldMatrix[0].connectTo(mmx.matrixIn[1], f=True)
    slave.parentInverseMatrix[0].connectTo(mmx.matrixIn[2], f=True)
    mmx.matrixSum.connectTo(dmx.inputMatrix, f=True)

    master_tmp = nodes.createNode('transform', n='{}_mastertmp'.format(master))
    slave_tmp = nodes.createNode('transform', n='{}_mastertmp'.format(slave))
    xformutils.match([master, master_tmp])
    xformutils.match([slave, slave_tmp])
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
        objs = nodes.selected(type='transform')
        if not objs:
            raise RuntimeError("No object given and no 'transform' selected")
    objs = nodes.yams(objs)

    tr = ''
    if t:
        tr += 't'
    if r:
        tr += 'r'
    for obj in objs:
        for axe in 'xyz':
            for tr_ in tr:
                attr = obj.attr(tr_ + axe)
                if attr.settable():
                    attr.value = 0
            if s:
                attr = obj.attr('s' + axe)
                if attr.settable():
                    attr.value = 1
        if v:
            attr = obj.v
            if attr.settable():
                attr.value = True
        if user:
            attrs = obj.listAttr(ud=True, scalar=True, visible=True)
            for attr in attrs:
                if not attr.settable():
                    continue
                attr.value = attr.defaultValue


def reskin(objs=None):
    if not objs:
        objs = nodes.selected()
        if not objs:
            raise RuntimeError("No object given and no object selected")
    objs = nodes.yams(objs)
    for skn in getSkinClusters(objs):
        skn.reskin()


def insertGroup(obj=None, suffix='GRP'):
    assert obj, "No obj given; Use 'insertGroups' to work on selection"
    obj = nodes.yam(obj)
    grp = nodes.createNode('transform', name='{}_{}'.format(obj, suffix))
    world_matrix = obj.getXform(m=True, ws=True)
    parent = obj.parent
    if parent:
        grp.parent = parent
    grp.setXform(m=world_matrix, ws=True)
    obj.parent = grp
    return grp


def insertGroups(objs=None, suffix='GRP'):
    if not objs:
        objs = nodes.selected(type='transform')
        if not objs:
            raise RuntimeError("No object given and no 'transform' selected")
    objs = nodes.yams(objs)
    grps = nodes.YamList()
    for obj in objs:
        grps.append(insertGroup(obj, suffix=suffix))
    return grps


def wrapMesh(objs=None, ws=True):
    if not objs:
        objs = nodes.selected(type=['transform', 'mesh'])
        if not objs:
            raise RuntimeError("No object given and no 'transform' or 'mesh' selected")
        if len(objs) < 2:
            raise RuntimeError("Not enough object given or selected")
    objs = nodes.yams(objs)
    master = objs[0]
    slaves = objs[1:]
    if isinstance(master, nodes.Transform):
        master = master.shape
        if not isinstance(master, nodes.Mesh):
            raise RuntimeError("first object '{}' is not a 'mesh'".format(master))
    master_mfn = master.mFnMesh
    if ws:
        space = om.MSpace.kworld
    else:
        space = om.MSpace.kObject
    for slave in slaves:
        if isinstance(slave, nodes.Transform):
            slave = slave.shape
            if not isinstance(slave, nodes.Mesh):
                cmds.warning("cannot match '{}' of type '{}'".format(slave, type(slave).__name__))
                continue
        slave_mfn = slave.mFnMesh
        for i in range(len(slave)):
            x, y, z, _ = master_mfn.getClosestPoint(slave_mfn.getPoint(i), space)[0]
            slave.vtx[i].setPosition([x, y, z], ws=True)


def matrixMayaToRow(matrix):
    return [matrix[0:4], matrix[4:8], matrix[8:12], matrix[12:16]]


def matrixRowToMaya(matrix):
    maya_matrix = []
    for m in matrix:
        maya_matrix += m
    return maya_matrix


@decorators.keepsel
def getSymmetryTable(obj=None, axis='x'):
    def selected():
        return cmds.ls(os=True, fl=True)

    def index(vtx):
        return int(vtx.split('[')[-1][:-1])

    if not obj:
        obj = selected()[0]
    cmds.select(str(obj))
    table = SymTable(axis=axis)
    cmds.select(sys=1)
    r_vtxs = selected()
    for r_vtx in r_vtxs:
        cmds.select(r_vtx, sym=True)
        r_vtx_, l_vtx = selected()
        if not r_vtx == r_vtx_:
            r_vtx_, l_vtx = l_vtx, r_vtx_
        table[index(l_vtx)] = index(r_vtx)
    cmds.select(sys=2)
    l_vtxs = selected()
    for l_vtx in l_vtxs:
        cmds.select(l_vtx, sym=True)
        l_vtx_, r_vtx = selected()
        if not l_vtx == l_vtx_:
            l_vtx_, r_vtx = r_vtx, l_vtx_
        table[index(l_vtx)] = index(r_vtx)
    cmds.select(sys=0)
    mid_vtxs = selected()
    table.mids = [index(mid_vtx) for mid_vtx in mid_vtxs]
    return table


class SymTable(dict):
    def __init__(self, axis='x'):
        assert axis in ('x', 'y', 'z')
        super(SymTable, self).__init__()
        self.axis = axis
        self.axis_mult = [1, 1, 1]
        self.axis_mult['xyz'.index(axis)] *= -1
        self.mids = []

    def __repr__(self):
        return "<{}>".format(self)

    def __str__(self):
        str_ = ''
        for key, value in self.items():
            str_ += '{}: {}, '.format(key, value)
        return "SymTable({})".format('{'+str_[:-2]+'}')


def mirrorMap(deformer, attr, table):
    # TODO : Average mid vtxs
    for l_vtx in table:
        l_weight = deformer.attr(attr.format(l_vtx)).value
        deformer.attr(attr.format(table[l_vtx])).value = l_weight


def flipMap(deformer, attr, table):
    for l_vtx in table:
        r_vtx = table[l_vtx]
        l_weight = deformer.attr(attr.format(l_vtx)).value
        r_weight = deformer.attr(attr.format(r_vtx)).value
        deformer.attr(attr.format(table[l_vtx])).value = r_weight
        deformer.attr(attr.format(table[r_vtx])).value = l_weight


def mirrorPos(obj, table):
    for l_vtx in table:
        l_pos = obj.vtx[l_vtx].getPosition()
        r_pos = utils.mult_list(l_pos, table.axis_mult)
        obj.vtx[table[l_vtx]].setPosition(r_pos)

    mid_mult = table.axis_mult[:]
    mid_mult['xyz'.index(table.axis)] *= 0
    for mid in table.mids:
        pos = utils.mult_list(obj.vtx[mid].getPosition(), mid_mult)
        obj.vtx[mid].setPosition(pos)


@decorators.keepsel
def flipPos(obj, table, reverse_face_normal=True):
    for l_vtx in table:
        l_pos = obj.vtx[l_vtx].getPosition()
        r_pos = obj.vtx[table[l_vtx]].getPosition()

        obj.vtx[l_vtx].setPosition(utils.mult_list(l_pos, table.axis_mult))
        obj.vtx[table[l_vtx]].setPosition(utils.mult_list(r_pos, table.axis_mult))

    for mid in table.mids:
        pos = obj.vtx[mid].getPosition()
        pos = utils.mult_list(pos, table.axis_mult)
        obj.vtx[mid].setPosition(pos)

    if reverse_face_normal:
        cmds.polyNormal(obj.name, normalMode=3, constructionHistory=False)


def snapToCurve(objs=None, curve=None):
    if not objs or not curve:
        objs = nodes.selected()
        if not objs:
            raise RuntimeError("No object given and object selected")
        if len(objs) < 3:
            raise RuntimeError("Not enough object given or selected")
        curve = objs.pop(0)

    if isinstance(curve, nodes.Transform):
        curve = curve.shape
    assert isinstance(curve, nodes.NurbsCurve), "First object '{}' is not or doesn't contain a NurbsCurve".format(curve)

    arclen = curve.arclen(ws=False)
    step = arclen / (len(objs) - 1.0)
    len_step = 0.0
    for i, obj in enumerate(objs):
        param = curve.mFnNurbsCurve.findParamFromLength(len_step)
        x, y, z, _ = curve.mFnNurbsCurve.getPointAtParam(param, om.MSpace.kWorld)
        obj.setPosition([x, y, z], ws=True)
        len_step += step
