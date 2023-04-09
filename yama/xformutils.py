# encoding: utf8

from __future__ import division
from maya import cmds
import maya.api.OpenMaya as om

from . import nodes, components, decorators, utils, checks


def align(objs=None, t=True, r=True):
    if not objs:
        if cmds.selectPref(q=True, tso=True) == 0:  # Allows you to get components order of selection
            cmds.selectPref(tso=True)
        objs = nodes.selected()
    if not objs and len(objs) > 2:
        raise ValueError("Not enough object selected")
    objs = nodes.yams(objs)
    poses = [x.getPosition(ws=True) for x in objs]

    t_step, t_start, r_step, r_start = None, None, None, None
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
def aim(objs=None, aimVector=(1, 0, 0), upVector=(0, 1, 0), worldUpType='scene', worldUpObject=None, worldUpVector=(0, 1, 0)):
    """
    Args:
        objs: [str, ...]
        aimVector: [float, float, float]
        upVector: [float, float, float]
        worldUpType: str, One of 5 values : "scene", "object", "objectrotation", "vector", or "none"
        worldUpObject: str, Use for worldUpType "object" and "objectrotation"
        worldUpVector: [float, float, float], Use for worldUpType "scene" and "objectrotation"

    e.g.:
    >>> aim(objs='locator1', aimVector=(1, 0, 0), upVector=(0, 1, 0), worldUpType='scene', worldUpObject=None, worldUpVector=(0, 1, 0))
    """
    if worldUpType == 'object':
        if not worldUpObject:
            raise Exception("worldUpObject is required for worldUpType 'object'")
        checks.objExists(worldUpObject, raiseError=True)
    if not objs:
        objs = nodes.selected()
    if not objs and len(objs) > 1:
        raise ValueError("Not enough object selected")
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
    if not objs and len(objs) > 1:
        raise ValueError("Not enough object selected")
    objs = nodes.yams(objs)

    source, targets = objs[0], objs[1:]
    if isinstance(source, components.Component):
        r = False
        s = False

    pos, rot, scale, matrix = None, None, None, None
    if t:
        pos = source.getPosition(ws=ws)
    else:
        if r:
            rot = source.getXform(ro=True, ws=ws)
        if s:
            scale = source.getXform(s=True, ws=ws)
    if m:
        matrix = source.getXform(m=True, ws=ws)

    for target in targets:
        if isinstance(target, nodes.Transform):
            if t:
                target.setXform(t=pos, ws=ws)
            if r:
                target.setXform(ro=rot, ws=ws)
            if s:
                target.setXform(s=scale, ws=ws)
            if m:
                target.setXform(m=matrix, ws=ws)
        elif isinstance(target, components.Component):
            if t:
                target.setPosition(pos, ws=ws)
        else:
            raise RuntimeError("Cannot match '{}' of type '{}'".format(target, type(target).__name__))


@decorators.keepsel
def matchComponents(components=None, target=None, ws=False):
    """
    Match the position of the given/selected components to the target object.
    :param components: [str, ...] or None to get selected components.
    :param target: str, Name of the target object or None to get last selected object.
    :param ws: bool, True to match in world space.
    """
    if not components or not target:
        components = nodes.selected(fl=False)
        target = components.pop(-1)
    else:
        components = nodes.yams(components)
        target = nodes.yam(target)

    for comp in components:
        target.cp[comp.index].setPosition(comp.getPosition(ws=ws), ws=ws)


def getCenter(objs):
    objs = nodes.yams(objs)
    xs, ys, zs = [], [], []
    for obj in objs:
        x, y, z = obj.getPosition(ws=True)
        xs.append(x)
        ys.append(y)
        zs.append(z)
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    min_z, max_z = min(zs), max(zs)
    x = (min_x + max_x) / 2
    y = (min_y + max_y) / 2
    z = (min_z + max_z) / 2
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

    if not isinstance(curve, nodes.NurbsCurve):
        raise TypeError("No NurbsCurve found under given curve".format(curve))

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
    if not isinstance(neutral, nodes.Mesh) or not isinstance(pose, nodes.Mesh):
        raise TypeError("Given neutral and/or pose object are not mesh objects")
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
