# encoding: utf8

from __future__ import division
from maya import cmds
import maya.api.OpenMaya as om

from . import nodes, components, decorators, utils


def align(objs=None, t=True, r=True):
    if not objs:
        if cmds.selectPref(q=True, tso=True) == 0:  # Allows you to get components order of selection
            cmds.selectPref(tso=True)
        objs = nodes.selected()
    assert objs and len(objs) > 2, "Not enough object selected"
    objs = nodes.yams(objs)
    poses = [x.getPosition(ws=True) for x in objs]
    if t:
        t_start, t_end = poses[0], poses[-1]
        t_step = [(t_end[x] - t_start[x]) / (len(objs) - 1.0) for x in range(3)]
    if r:
        r_start, r_end = [x.getXform(ro=True, ws=True) for x in (objs[0], objs[-1])]
        r_step = [(r_end[x] - r_start[x]) / (len(objs) - 1.0) for x in range(3)]

    for i, obj in enumerate(objs):
        if t:
            pos = [t_step[x] * i + t_start[x] for x in range(3)]
            obj.setPosition(pos, ws=True)
        if r:
            rot = [r_step[x] * i + r_start[x] for x in range(3)]
            obj.setXform(ro=rot, ws=True)

    if r and not t:
        for obj, pos in zip(objs, poses):
            obj.setPosition(pos, ws=True)


@decorators.keepsel
def aim(objs=None, aimVector=(0, 0, 1), upVector=(0, 1, 0), worldUpType='scene', worldUpObject=None, worldUpVector=(0, 1, 0)):
    """
    (objs=None, aimVector=(0, 0, 1), upVector=(0, 1, 0), worldUpType='scene', worldUpObject=None, worldUpVector=(0, 1, 0))
    Args:
        objs: [str, ...]
        aimVector: [float, float, float]
        upVector: [float, float, float]
        worldUpType: str, One of 5 values : "scene", "object", "objectrotation", "vector", or "none"
        worldUpObject: str, Use for worldUpType "object" and "objectrotation"
        worldUpVector: [float, float, float], Use for worldUpType "scene" and "objectrotation"
    """
    if worldUpType == 'object':
        if not worldUpObject:
            raise Exception("worldUpObject is required for worldUpType 'object'")
        assert cmds.objExists(worldUpObject), "Object '{}' does not exist".format(worldUpObject)
    if not objs:
        objs = nodes.selected()
    assert objs and len(objs) > 1, "Not enough object selected"
    objs = nodes.yams(objs)
    poses = [x.getXform(t=True, ws=True) for x in objs]
    nulls = nodes.YamList(nodes.createNode('transform') for _ in objs)
    for null, pos in zip(nulls, poses):
        null.setXform(t=pos, ws=True)
    world_null = nodes.createNode('transform', name='world_null')

    for obj, null, pos in zip(objs[:-1], nulls[1:], poses):
        obj.setXform(t=pos, ws=True)
        if worldUpType == 'scene':
            cmds.delete(cmds.aimConstraint(null.name, obj.name, aimVector=aimVector, upVector=upVector,
                                           worldUpType='objectrotation', worldUpObject=world_null.name,
                                           worldUpVector=worldUpVector, mo=False))
        elif worldUpType == 'object':
            cmds.delete(cmds.aimConstraint(null.name, obj.name, aimVector=aimVector, upVector=upVector,
                                           worldUpType='object', worldUpObject=worldUpObject, mo=False))
        elif worldUpType == 'objectrotation':
            cmds.delete(cmds.aimConstraint(null.name, obj.name, aimVector=aimVector, upVector=upVector,
                                           worldUpType='objectrotation', worldUpObject=worldUpObject,
                                           worldUpVector=worldUpVector, mo=False))
        else:
            cmds.delete(nulls.names, world_null.name)
            raise NotImplementedError

    objs[-1].setXform(t=poses[-1], ro=objs[-2].getXform(ro=True, ws=True), ws=True)
    cmds.delete(world_null.name, nulls.names)


def match(objs=None, t=True, r=True, s=False, m=False, ws=True):
    """
    Match the position, rotation and scale of the first object to the following objects.
    :param objs: [str, ...] or None to get selected objects.
    :param t: bool, True to match translation.
    :param r: bool, True to match rotation.
    :param s: bool, True to match scale.
    :param m: bool, True to match matrix.
    :param ws:  bool, True to match in world space.
    """
    if not objs:
        objs = nodes.selected()
    assert len(objs) > 1, "Less than 2 objects selected"
    objs = nodes.yams(objs)

    master, slaves = objs[0], objs[1:]
    pos = master.getPosition(ws=ws)
    if isinstance(master, components.Component):
        r = False
        s = False
    else:
        if r:
            rot = master.getXform(ro=True, ws=ws)
        if s:
            scale = master.getXform(s=True, ws=ws)
    if m:
        matrix = master.getXform(m=True, ws=ws)

    for slave in slaves:
        if isinstance(slave, nodes.Transform):
            if t:
                slave.setXform(t=pos, ws=ws)
            if r:
                slave.setXform(ro=rot, ws=ws)
            if s:
                slave.setXform(s=scale, ws=ws)
        elif isinstance(slave, components.Component):
            if t:
                slave.setPosition(pos, ws=ws)
        if m:
            slave.setXform(m=matrix, ws=ws)
        else:
            print("Cannot match '{}' of type '{}'".format(slave, type(slave).__name__))


@decorators.keepsel
def matchComponents(comps=None, slave=None, ws=False):
    """
    Match the position, rotation and scale of the given/selected components to the slave object.
    :param comps: [str, ...] or None to get selected components.
    :param slave: str, Name of the slave object or None to get last selected object.
    :param ws: bool, True to match in world space.
    """
    if not comps or not slave:
        comps = nodes.selected(fl=False)
        slave = comps.pop(-1)
    else:
        comps = nodes.yams(comps)
        slave = nodes.yam(slave)

    for comp in comps:
        slave.cp[comp.index].setPosition(comp.getPosition(ws=ws), ws=ws)


def getCenter(objs):
    assert objs, "No objects given"
    objs = nodes.yams(objs)
    xs, ys, zs = [], [], []
    for obj in objs:
        x, y, z = obj.getPosition(ws=True)
        xs.append(x)
        ys.append(y)
        zs.append(z)
    minx, maxx = min(xs), max(xs)
    miny, maxy = min(ys), max(ys)
    minz, maxz = min(zs), max(zs)
    x = (minx + maxx) / 2
    y = (miny + maxy) / 2
    z = (minz + maxz) / 2
    return [x, y, z]


def snapAlongCurve(objs=None, curve=None, reverse=False):
    """
    Snap a list of given objects along a given curve.
    If no objects or curve are not given : works on current selection with last selected being the curve.
    :param objs: list, A list of objects to be snapped along the curve.
    :param curve: nodes.NurbsCurve, A nurbs curve object along which the objects will be snapped.
    :param reverse: bool, If set to True, the objects will be snapped in reverse order. Default is False.
    """
    if not objs or not curve:
        objs = nodes.selected()
        if not objs:
            raise RuntimeError("No object given and object selected")
        if len(objs) < 2:
            raise RuntimeError("Not enough object given or selected")
        curve = objs.pop()

    if isinstance(curve, nodes.Transform):
        curve = curve.shape
    assert isinstance(curve, nodes.NurbsCurve), "No NurbsCurve found under given curve".format(curve)

    if reverse:
        objs = objs[::-1]
    step = curve.MFn.findParamFromLength(curve.arclen()) / (len(objs)-1.0)
    for i, obj in enumerate(objs):
        x, y, z, _ = curve.MFn.getPointAtParam(step * i, om.MSpace.kWorld)
        obj.setPosition([x, y, z], ws=True)


def mirrorPos(obj, table):
    for l_cp in table:
        l_pos = obj.cp[l_cp].getPosition()
        r_pos = utils.multList(l_pos, table.axis_mult)
        obj.cp[table[l_cp]].setPosition(r_pos)

    mid_mult = table.axis_mult[:]
    mid_mult['xyz'.index(table.axis)] *= 0
    for mid in table.mids:
        pos = utils.multList(obj.cp[mid].getPosition(), mid_mult)
        obj.cp[mid].setPosition(pos)


def flipPos(obj, table, reverse_face_normal=True):
    for l_cp in table:
        l_pos = obj.cp[l_cp].getPosition()
        r_pos = obj.cp[table[l_cp]].getPosition()

        obj.cp[l_cp].setPosition(utils.multList(l_pos, table.axis_mult))
        obj.cp[table[l_cp]].setPosition(utils.multList(r_pos, table.axis_mult))

    for mid in table.mids:
        pos = obj.cp[mid].getPosition()
        pos = utils.multList(pos, table.axis_mult)
        obj.cp[mid].setPosition(pos)

    if reverse_face_normal:
        cmds.polyNormal(obj.name, normalMode=3, constructionHistory=False)  # Flipping the face normals


def extractXYZ(neutral, pose, axis=('y', 'xz'), ws=False):
    """
    Extracts the vertex position difference between two shapes per each given axis or axis combination.
    :param neutral: neutral shape.
    :param pose: posed shape.
    :param axis: the axis or combination of axis to extract from.
    :param ws: Space in which to query the positions.
    :return: dictionary containing list of vertex positions per extracted axis

    TODO: Add support for other than world axis
    """
    neutral = nodes.yam(neutral)
    pose = nodes.yam(pose)
    n_pose = neutral.vtx.getPositions(ws=ws)
    pose_pos = pose.vtx.getPositions(ws=ws)
    data = {x: [] for x in axis}
    for n_vtx_pos, p_vtx_pos in zip(n_pose, pose_pos):
        for i in axis:
            pos = []
            for xyz, n_value, p_value in zip('xyz', n_vtx_pos, p_vtx_pos):
                if xyz in i:
                    pos.append(p_value)
                else:
                    pos.append(n_value)
            data[i].append(pos)
    return data
