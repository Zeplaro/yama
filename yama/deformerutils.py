# encoding: utf8

from six import string_types
from copy import copy
from maya import cmds, mel

from . import nodes, decorators, components, config, weightlist


def getSkinCluster(obj, firstOnly=True):
    # type: (nodes.Yam, bool) -> nodes.SkinCluster | nodes.YamList[nodes.SkinCluster] | None
    """TODO: which way is better : listHistory or ls ?"""
    skns = cmds.listHistory(str(obj), pdo=True)
    skns = cmds.ls(skns, type='skinCluster')
    if firstOnly:
        return nodes.yam(skns[0]) if skns else None
    return nodes.yams(skns) if skns else nodes.YamList()


def getSkinClusters(objs, firstOnly=True):
    return nodes.YamList([getSkinCluster(obj, firstOnly=firstOnly) for obj in objs])


def skinAs(objs=None, sourceNamespace=None, targetNamespace=None, useObjectNamespace=False, prompt=True):
    # type: ([str | nodes.Transform | nodes.Shape], str, str, bool, bool) -> nodes.YamList[nodes.SkinCluster] | None
    """
    Copies the skinning and skinCLuster settings of one skinned object to any other objects with a different topology.
    First object given in objs is the skinned object to copy from and the rest being the objects to copy the skin to, if
    no objects are given then this works on current scene selection.

    If the first object influences have a namespace and the other objects influences have a different namespace or don't
    have one then you can use sourceNamespace to remove from the original influences, and/or targetNamespace to add to
    the new influences. To get the namespace from the list of objects then set useObjectNamespace to True, in this case
    the sourceNamespace and targetNamespace are ignored and the namespace to remove from the original influences and to
    add to the new influences is determined per each object namespace.
    :param objs: List of objects. The first object's skinCluster is copied to the other objects.
    :param sourceNamespace: Namespace of the joints skinning the source object.
    :param targetNamespace: Namespace to use to find the joints that will skin the target objects.
    :param useObjectNamespace: If True: uses each objects namespace to determine the source and target namespaces.
    :param prompt: If True: will show a dialogue box asking to delete the intermediate shapes before skinning if
                   intermediate shapes are found on the target objects
    """
    from . import mayautils as mut

    if isinstance(objs, string_types):
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
        raise ValueError("Please select at least two objects")
    source = nodes.yam(objs[0])
    targets = mut.hierarchize(objs[1:], reverse=True)

    free_targets = []
    for target in targets:
        # Checking for already attached skin on target
        if getSkinCluster(target):
            if config.verbose:
                cmds.warning(target + ' already has a skinCluster attached')
            continue
        else:
            free_targets.append(target)

        # Checking for intermediate shapes on target
        intermediate_shapes = [shape for shape in target.shapes(noIntermediate=False) if shape.intermediateObject.value]
        if intermediate_shapes and prompt:
            result = cmds.confirmDialog(title="Confirm",
                                        message="These targets already have intermediate shapes on them : {}\n"
                                                "Do you want to continue ?".format(intermediate_shapes),
                                        button=["Yes", "Cancel", "Delete them"], defaultButton="Yes",
                                        cancelButton="Cancel", dismissString="Cancel")
            if result == "Cancel":
                cmds.warning("SkinAs operation cancelled")
                return
            elif result == "Delete them":
                cmds.delete(intermediate_shapes)
                return skinAs(objs, sourceNamespace, targetNamespace, useObjectNamespace)

    source_skn = getSkinCluster(source)
    if not source_skn:
        raise ValueError('First object as no skinCluster attached')
    source_influences = source_skn.influences()
    target_influences = source_influences

    if useObjectNamespace:
        sourceNamespace = ':'.join(source.name.split(':')[:-1])
    elif sourceNamespace or targetNamespace:
        if sourceNamespace:
            replace_args = [sourceNamespace + ':', '']
            if targetNamespace:
                replace_args[1] = targetNamespace + ':'
            target_influences = nodes.yams(inf.name.replace(*replace_args) for inf in source_influences)
        else:
            target_influences = nodes.yams(targetNamespace + ':' + inf for inf in source_influences)

    skinClusters = nodes.YamList()
    kwargs = {'skinMethod': source_skn.skinningMethod.value,
              'maximumInfluences': source_skn.maxInfluences.value,
              'normalizeWeights': source_skn.normalizeWeights.value,
              'obeyMaxInfluences': source_skn.maintainMaxInfluences.value,
              'weightDistribution': source_skn.weightDistribution.value,
              'includeHiddenSelections': True,
              'toSelectedBones': True,
              }
    for target in free_targets:
        if useObjectNamespace:  # getting target influences namespace per target
            targetNamespace = ':'.join(target.name.split(':')[:-1])
            if sourceNamespace:
                replace_args = [sourceNamespace + ':', '']
                if targetNamespace:
                    replace_args[1] = targetNamespace + ':'
                target_influences = nodes.yams(inf.name.replace(*replace_args) for inf in source_influences)
            elif targetNamespace:
                target_influences = nodes.yams(targetNamespace + ':' + inf for inf in source_influences)
            else:
                target_influences = source_influences

        nodes.select(target_influences, target)
        target_skinCluster = nodes.yam(cmds.skinCluster(name='{}_SKN'.format(target.shortName), **kwargs)[0])
        cmds.copySkinWeights(ss=source_skn.name, ds=target_skinCluster.name, nm=True, sa='closestPoint', smooth=True,
                             ia=('oneToOne', 'label', 'closestJoint'))
        if config.verbose:
            print(target + ' skinned -> ' + target_skinCluster.name)
        skinClusters.append(target_skinCluster)
    return skinClusters


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
    mir_weights = copy(weights)
    for l_cp in table:
        mir_weights[table[l_cp]] = weights[l_cp]
    return mir_weights


def flipWeights(weights, table):
    flip_weights = copy(weights)
    for l_cp in table:
        flip_weights[l_cp] = weights[table[l_cp]]
        flip_weights[table[l_cp]] = weights[l_cp]
    return flip_weights


@decorators.keepsel
def copyDeformerWeights(sourceDeformer, destinationDeformer, sourceGeo=None, destinationGeo=None):
    """
    For two geometries with different topologies, copies a given deformer weight to another given deformer.
    :param sourceDeformer: the deformer to copy the weights from, the object needs to have a 'weights' attribute
    :param destinationDeformer: the deformer to copy the weights on, the object needs to have a 'weights' attribute
    :param sourceGeo: the geo on which the sourceDeformer is applied; if None, the geo is taken from the sourceDeformer
    :param destinationGeo: the geo on which the destinationDeformer is applied; if None, the geo is taken from the
                           destinationDeformer
    """
    sourceDeformer, destinationDeformer = nodes.yams((sourceDeformer, destinationDeformer))
    if sourceGeo is None:
        sourceGeo = sourceDeformer.geometry
    if destinationGeo is None:
        destinationGeo = destinationDeformer.geometry

    if not hasattr(sourceDeformer, 'weights'):
        raise TypeError("'{}' of type '{}' has no 'weights' attributes."
                        "".format(sourceDeformer, type(sourceDeformer).__name__))
    if not hasattr(destinationDeformer, 'weights'):
        raise TypeError("'{}' of type '{}' has no 'weights' attributes."
                        "".format(destinationDeformer, type(destinationDeformer).__name__))

    # Creating temp geos
    temp_source_geo, temp_dest_geo = nodes.yams(cmds.duplicate(sourceGeo.name, destinationGeo.name))
    temp_source_geo.name = 'temp_source_geo'
    temp_dest_geo.name = 'temp_dest_geo'
    # Removing shapeOrig
    cmds.delete([x.name for x in temp_source_geo.shapes(noIntermediate=False) if x.intermediateObject.value])
    cmds.delete([x.name for x in temp_dest_geo.shapes(noIntermediate=False) if x.intermediateObject.value])

    # Creating temp skinClusters to copy weights
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
    source_skn.weights = [[value] for value in source_weights]

    cmds.copySkinWeights(sourceSkin=source_skn.name, destinationSkin=destination_skn.name, noMirror=True,
                         surfaceAssociation='closestPoint', influenceAssociation=('oneToOne', 'label', 'closestJoint'),
                         smooth=True, normalize=False)

    destination_skn_weights = destination_skn.weights
    destinationDeformer.weights = weightlist.WeightList([value[0] for value in destination_skn_weights])

    cmds.delete(source_skn.name, destination_skn.name)
    cmds.delete(source_jnt.name, destination_jnt.name)
    cmds.delete(temp_source_geo.name, temp_dest_geo.name)


@decorators.keepsel
def hammerShells(vertices=None, reverse=False):
    """
    Hammer weights on the selected or given vertices even if they're part of different shells or mesh.
    :param vertices: list of MeshVertex components. If None, uses selected vertices.
    :param reverse: False by default, hammer weights on the selected vertices. If True hammer weights on all other not
                    selected vertices per shell.
    """
    if not vertices:
        vertices = nodes.selected()
        vertices.keepType(components.Component)
        if not vertices:
            raise RuntimeError("No vertices given or selected")

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


def transferInfluenceWeights(skinCluster, influences, target_influence, add_missing_target=True):
    """
    Transfer weights from a list of influences to a target influence.
    :param skinCluster: any type that can be passed to nodes.yam; the skinCluster to work on.
    :param influences: list; influences to transfer weights from.
    :param target_influence: any type that can be passed to nodes.yam; the influence to transfer weights to.
    :param add_missing_target: bool; if True, adds missing target influences to the skinCluster.
    """
    skinCluster = nodes.yam(skinCluster)
    influence_indexes = []
    all_influences = skinCluster.influences()

    # Checks the target influence
    target_influence = nodes.yam(target_influence)
    if target_influence in all_influences:
        target_index = skinCluster.indexForInfluenceObject(target_influence)
    elif add_missing_target:
        cmds.skinCluster(skinCluster.name, e=True, addInfluence=target_influence.name, lockWeights=True, weight=0.0)
        target_index = skinCluster.indexForInfluenceObject(target_influence)
    else:
        cmds.warning("Target influence not found in skinCluster '{}': '{}'".format(skinCluster, target_influence))
        return False

    # Checks the influences
    missing_influences = []
    for inf in influences:
        inf = nodes.yam(inf)
        if inf in all_influences:
            influence_indexes.append([inf, skinCluster.indexForInfluenceObject(inf)])
        else:
            missing_influences.append(inf)
    if not influence_indexes:
        cmds.warning("None of the influences were found in skinCluster '{}': {}".format(skinCluster, influences))
        return False
    if missing_influences:
        cmds.warning("Influences not found in skinCluster '{}': {}".format(skinCluster, missing_influences))

    for inf, index in influence_indexes:
        for vtx in skinCluster.getPointsAffectedByInfluence(inf):
            skinCluster.weightList[vtx.index].weights[target_index].value += skinCluster.weightList[vtx.index].weights[
                index].value
            skinCluster.weightList[vtx.index].weights[index].value = 0.0
    return True


def skinAsNurbs(source=None, target=None):
    if not source or not target:
        source, target = nodes.selected()
    else:
        source, target = nodes.yams([source, target])
    if not source.shape or not target.shape:
        raise RuntimeError("Given source and/or target does not have a shape")
    if not isinstance(target.shape, nodes.NurbsSurface):
        raise TypeError("Given target does not contain a nurbsSurface")

    plane, poly = nodes.yams(cmds.polyPlane(sx=target.shape.lenU(), sy=target.shape.lenV()))

    # Using a try except do be sure to delete the temp plane
    try:
        plane.shape.vtx.setPositions(target.shape.cv.getPositions(ws=True), ws=True)

        plane_skin = skinAs([source, plane])[0]
        target_skn = getSkinCluster(target)
        if target_skn:
            raise RuntimeError("Given target already has a skinCluster attached : {}; {}".format(target, target_skn))

        target_skin = skinAs([source, target])
        target_skin = target_skin[0]

        for i, _ in enumerate(target.shape.cv):
            for j, _ in enumerate(plane_skin.influences()):
                target_skin.weightList[i].weights[j].value = plane_skin.weightList[i].weights[j].value
    except Exception as e:
        raise e
    # Making sure the temp plane gets deleted
    finally:
        cmds.delete(plane.name)
