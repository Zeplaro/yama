from maya import cmds
import nodes
import components
import decorators


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
            cmds.delete(cmds.aimConstraint(null.name, obj.name, aimVector=aimVector, upVector=upVector, worldUpType='object',
                                           worldUpObject=worldUpObject, mo=False))
        else:
            cmds.delet(nulls.names(), world_null.name)
            raise NotImplementedError

    objs[-1].setXform(t=poses[-1], ro=objs[-2].getXform(ro=True, ws=True), ws=True)
    cmds.delete(world_null.name, nulls.names())


def match(objs=None, t=True, r=True, s=False):
    if not objs:
        objs = nodes.selected()
    assert objs > 1, "Less than 2 objects selected"
    objs = nodes.yams(objs)

    master, slaves = objs[0], objs[1:]
    pos = master.getPosition(ws=True)
    if isinstance(master, components.Component):
        r = False
        s = False
    else:
        if r:
            rot = master.getXform(ro=True, ws=True)
        if s:
            scale = master.getXform(s=True, ws=True)

    for slave in slaves:
        if isinstance(slave, nodes.Transform):
            if t:
                slave.setXform(t=pos, ws=True)
            if r:
                slave.setXform(ro=rot, ws=True)
            if s:
                slave.setXform(s=scale, ws=True)
        elif isinstance(slave, components.Component):
            if t:
                slave.setPosition(pos, ws=True)
        else:
            print("Cannot match '{}' of type '{}'".format(slave, type(slave).__name__))


def getCenter(objs):
    objs = nodes.yams(objs)
    assert objs, "No objects given"
    poses = [x.getPosition(ws=True) for x in objs]
    xs = [x for x, y, z in poses]
    ys = [y for x, y, z in poses]
    zs = [z for x, y, z in poses]
    minx, maxx = min(xs), max(xs)
    miny, maxy = min(ys), max(ys)
    minz, maxz = min(zs), max(zs)
    x = (minx + maxx) / 2
    y = (miny + maxy) / 2
    z = (minz + maxz) / 2
    return [x, y, z]
