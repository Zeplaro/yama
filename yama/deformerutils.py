# encoding: utf8

import sys
from maya import cmds, mel
from . import nodes, decorators

# python 2 to 3 compatibility
_pyversion = sys.version_info[0]
if _pyversion == 3:
    basestring = str


def getSkinCluster(obj):
    skn = cmds.listHistory(str(obj), pdo=True)
    skn = cmds.ls(skn, type='skinCluster')
    return nodes.yam(skn[0]) if skn else None


def getSkinClusters(objs):
    return nodes.YamList([getSkinCluster(obj) for obj in objs])


def skinAs(objs=None, masterNamespace=None, slaveNamespace=None, useObjectNamespace=False):
    """
    Copies the skinning and skinCLuster settings of one skinned object to any other objects with a different topology.
    First object given in objs is the skinned object to copy from and the rest being the objects to copy the skin to, if
    no objects are given then this works on current scene selection.

    If the first object influences have a namespace and the other objects influences have a different namespace or don't
    have one then you can use masterNamespace to remove from the original influences, and/or slaveNamespace to add to
    the new influences. To get the namespace from the list of objects then set useObjectNamespace to True, in this case
    the masterNamespace and slaveNamespace are ignored and the namespace to remove from the original influences and to
    add to the new influences is determined per each object namespace.
    :param objs: list
    :param masterNamespace: str
    :param slaveNamespace: str
    :param useObjectNamespace: bool
    """
    from . import mayautils as mut

    if isinstance(objs, basestring):
        raise RuntimeError("first arg objs='{}' is of type {} "
                           "instead of expected type: list".format(objs, type(objs).__name__))
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
        cmds.warning("Please select at least two objects")
        return
    master = nodes.yam(objs[0])
    slaves = mut.hierarchize(objs[1:], reverse=True)

    masterskn = getSkinCluster(master)
    if not masterskn:
        cmds.warning('First object as no skinCluster attached')
        return
    master_infs = masterskn.influences()
    slave_infs = master_infs

    if useObjectNamespace:
        masterNamespace = ':'.join(master.name.split(':')[:-1])
    elif masterNamespace or slaveNamespace:
        if masterNamespace:
            replace_args = [masterNamespace + ':', '']
            if slaveNamespace:
                replace_args[1] = slaveNamespace + ':'
            slave_infs = nodes.yams(inf.name.replace(*replace_args) for inf in master_infs)
        else:
            slave_infs = nodes.yams(slaveNamespace + ':' + inf for inf in master_infs)

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

        if useObjectNamespace:  # getting slave influences namespace per slave
            slaveNamespace = ':'.join(slave.name.split(':')[:-1])
            if masterNamespace:
                replace_args = [masterNamespace + ':', '']
                if slaveNamespace:
                    replace_args[1] = slaveNamespace + ':'
                slave_infs = nodes.yams(inf.name.replace(*replace_args) for inf in master_infs)
            elif slaveNamespace:
                slave_infs = nodes.yams(slaveNamespace + ':' + inf for inf in master_infs)
            else:
                slave_infs = master_infs

        nodes.select(slave_infs, slave)
        slaveskn = nodes.yam(cmds.skinCluster(name='{}_SKN'.format(slave.shortName), **kwargs)[0])
        cmds.copySkinWeights(ss=masterskn.name, ds=slaveskn.name, nm=True, sa='closestPoint', smooth=True,
                             ia=('oneToOne', 'label', 'closestJoint'))
        print(slave + ' skinned -> ' + slaveskn.name)
        done.append(slave)
    return done


def reskin(objs=None):
    if not objs:
        objs = nodes.selected()
        if not objs:
            raise RuntimeError("No object given and no object selected")
    objs = nodes.yams(objs)
    for skn in getSkinClusters(objs):
        skn.reskin()


def mirrorWeights(weights, table):
    """
    Mirror weights according to the given mirror table.
    :param weights: dict of {'index': weight}
    :param table: mirror table from mayautils.getSymmetryTable
    :return: dict of {'index': weight}
    """
    mir_weights = weights.copy()
    for l_cp in table:
        mir_weights[table[l_cp]] = weights[l_cp]
    return mir_weights


def flipWeights(weights, table):
    flip_weights = weights.copy()
    for l_cp in table:
        flip_weights[l_cp] = weights[table[l_cp]]
        flip_weights[table[l_cp]] = weights[l_cp]
    return flip_weights


@decorators.keepsel
def copyDeformerWeights(sourceDeformer, destinationDeformer, sourceGeo=None, destinationGeo=None):
    """
    For two geometries with diffferent topologies, copies a given deformer weight to another given deformer.
    :param sourceDeformer: the deformer to copy the weights from, the given object needs to have a weights attribute
    :param destinationDeformer: the deformer to copy the weights on, the given object needs to have a weights attribute
    :param sourceGeo: the geo on which the sourceDeformer is applied; if None, the geo is taken from the sourceDeformer
    :param destinationGeo: the geo on which the destinationDeformer is applied; if None, the geo is taken from the
                           destinationDeformer
    """
    sourceDeformer, destinationDeformer = nodes.yams((sourceDeformer, destinationDeformer))
    if sourceGeo is None:
        sourceGeo = sourceDeformer.geometry()
    if destinationGeo is None:
        destinationGeo = destinationDeformer.geometry()
    
    assert hasattr(sourceDeformer, 'weights'), "'{}' of type '{}' has no 'weights' attributes." \
                                               "".format(sourceDeformer, type(sourceDeformer).__name__)
    assert hasattr(destinationDeformer, 'weights'), "'{}' of type '{}' has no 'weights' attributes." \
                                                    "".format(destinationDeformer, type(destinationDeformer).__name__)

    temp_source_geo, temp_dest_geo = nodes.yams(cmds.duplicate(sourceGeo.name, destinationGeo.name))
    temp_source_geo.name = 'temp_source_geo'
    temp_dest_geo.name = 'temp_dest_geo'
    # Removing shapeOrig
    cmds.delete([x.name for x in temp_source_geo.shapes(noIntermediate=False) if x.intermediateObject.value])
    cmds.delete([x.name for x in temp_dest_geo.shapes(noIntermediate=False) if x.intermediateObject.value])

    source_jnt = nodes.createNode('joint', name='temp_source_jnt')
    nodes.select(source_jnt, temp_source_geo)
    source_skn = nodes.yam(cmds.skinCluster(name='temp_source_skn', skinMethod=0, normalizeWeights=0,
                                            obeyMaxInfluences=False, weightDistribution=0, includeHiddenSelections=True,
                                            toSelectedBones=True)[0])
    source_skn.envelope.value = 0

    destination_jnt = nodes.createNode('joint', name='temp_destination_jnt')
    nodes.select(destination_jnt, temp_dest_geo)
    destination_skn = nodes.yam(cmds.skinCluster(name='temp_dest_skn', skinMethod=0, normalizeWeights=0,
                                                 obeyMaxInfluences=False, weightDistribution=0,
                                                 includeHiddenSelections=True, toSelectedBones=True)[0])
    destination_skn.envelope.value = 0

    source_weights = sourceDeformer.weights
    source_skn.weights = {i: {0: source_weights[i]} for i in source_weights}

    cmds.copySkinWeights(sourceSkin=source_skn.name, destinationSkin=destination_skn.name, noMirror=True,
                         surfaceAssociation='closestPoint', influenceAssociation=('oneToOne', 'label', 'closestJoint'),
                         smooth=True, normalize=False)

    destination_skn_weights = destination_skn.weights
    destinationDeformer.weights = {i: destination_skn_weights[i][0] for i in destination_skn_weights}

    cmds.delete(source_skn.name, destination_skn.name)
    cmds.delete(source_jnt.name, destination_jnt.name)
    cmds.delete(temp_source_geo.name, temp_dest_geo.name)


@decorators.keepsel
def hammerShells(vertices=None, reverse=False):
    """
    Hammer weights on the selected or given vertices even if they're part of different shells or mesh.
    :param vertices: list of MeshVertex components. If None, uses selected vertices.
    :param reverse: By default False, hammer weigths on the selected vertices. If True hammer weights on all other not
                    selected vertices per shell.
    """
    if not vertices:
        vertices = nodes.selected()
    data = {}
    for vtx in vertices:
        node = vtx.node.name  # Uses name as dict key instead of node itself for performance.
        if node in data:
            data[node].append(vtx)
        else:
            data[node] = [vtx]

    for node, vtxs in data.items():
        node = nodes.yam(node)
        shells = node.shells(indexOnly=True)  # Uses indexOnly for 'index in/not in shell' for much faster performance
        print("Found {} shells for '{}'".format(len(shells), node))
        for shell in shells:
            if reverse:
                vtxs_indexes = {vtx.index for vtx in vtxs}
                shell_vtxs = [node.vtx[index] for index in shell if index not in vtxs_indexes]
                if len(shell) == len(shell_vtxs):
                    continue
            else:
                shell_vtxs = [vtx for vtx in vtxs if vtx.index in shell]
            if shell_vtxs:
                nodes.select(shell_vtxs)
                cmds.WeightHammer()
