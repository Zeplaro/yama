# encoding: utf8

"""
Contains all the class for maya node types, and all nodes related functions.
The main functions used would be createNode to create a new node and get it initialized as its proper class type; and
yam or yams to initialize existing objects into their proper class type.
"""

import sys
from math import sqrt
from maya import cmds
import maya.api.OpenMaya as om
import maya.OpenMaya as om1

# python 2 to 3 compatibility
_pyversion = sys.version_info[0]
if _pyversion == 3:
    basestring = str

import weightsdict


def yam(node):
    """
    Handles all node class assignment to assign the proper class depending on the node type.
    Also works with passing a 'node.attribute'.

    examples :
    >> yam('skincluster42')
    SkinCluster('skincluster42')

    >> yam('pCube1.tz')
    Attribute('pCube1.tz')
    """

    attr = None
    if isinstance(node, basestring):
        if '.' in node:  # checking if an attribute was given with the node and splits it to call it later
            split = node.split('.')
            node = split.pop(0)
            attr = '.'.join(split)
        # Getting the mObject associated with the given node uses 'try' in case the node does not exists or multiple
        # objects with the same name exists.
        mSelectionList = om.MSelectionList()
        try:
            mSelectionList.add(node)
        except RuntimeError:
            if cmds.objExists(node):
                raise RuntimeError("more than one object called '{}'".format(node))
            raise RuntimeError("No '{}' object found in scene".format(node))
        mObject = mSelectionList.getDependNode(0)
        mfn = om.MFnDependencyNode(mObject)

    elif isinstance(node, Yam):
        return node

    elif isinstance(node, om.MObject):
        mObject = node
        mfn = om.MFnDependencyNode(mObject)
        node = mfn.name()

    elif isinstance(node, om.MDagPath):
        mObject = node.node()
        mfn = om.MFnDependencyNode(mObject)
        node = mfn.name()

    else:
        raise TypeError("yam(): str, OpenMaya.MObject or OpenMaya.MDagPath expected,"
                        " got {}.".format(node.__class__.__name__))

    # checking if node type has a supported class, if not defaults to DependNode
    assigned_class = supported_classes.get(mfn.typeName)  # skips the mc.nodeType if exact type is in supported_class
    if not assigned_class:
        assigned_class = DependNode
        for node_type in cmds.nodeType(node, i=True)[::-1]:  # checks each inherited types for the node
            if node_type in supported_classes:
                assigned_class = supported_classes[node_type]
                break

    if attr is not None:
        return assigned_class(mObject, mfn).attr(attr)  # gets and returns an Attribute object if an attribute was given
    return assigned_class(mObject, mfn)


def yams(nodes):
    """
    Returns each nodes or attributes initialized as their appropriate DependNode or Attribute. See 'yam' function.
    :param nodes: (list) list of str of existing nodes.
    :return: list of DependNode
    """
    return YamList(yam(node) for node in nodes)


def createNode(*args, **kwargs):
    """
    Creates a node and returns it as its appropriate class depending on its type.
    :param args: cmds args for cmds.createNode
    :param kwargs: cmds kwargs for cmds.createNode
    :return: a DependNode object
    """
    return yam(cmds.createNode(*args, **kwargs))


def ls(*args, **kwargs):
    if 'fl' not in kwargs and 'flatten' not in kwargs:
        kwargs['fl'] = True
    return yams(cmds.ls(*args, **kwargs))


def selected(**kwargs):
    return ls(os=True, **kwargs)


def select(*args, **kwargs):
    sel = []
    for arg in args:
        if isinstance(arg, YamList):
            sel.append(arg.names())
        elif isinstance(arg, Yam):
            sel.append(str(arg))
        elif isinstance(arg, (list, tuple, dict, set)):
            new = []
            for arg_ in arg:
                if isinstance(arg_, Yam):
                    new.append(str(arg_))
                else:
                    new.append(arg_)
            sel.append(new)
        else:
            sel.append(arg)
    cmds.select(*sel, **kwargs)


class Yam(object):
    pass


class DependNode(Yam):
    """
    Main maya node type that all nodes inherits from.
    Links the node to its maya api 2.0 MObject to access many of the faster api functions and classes (MFn), and also in
    case the node name changes.

    All implemented maya api functions and variables are from api 2.0; for api 1.0 the functions and variables are
    defined with a '1' suffix;
    e.g.: >>> node.mObject  <-- gives a api 2.0 object
    -     >>> node.mObject1 <-- gives a api 1.0 object
    """

    def __init__(self, mObject, mFnDependencyNode):
        """
        Needs an maya api 2.0 MObject associated to the node and a MFnDependencyNode initialized with the mObject.
        :param mObject: maya api MObject
        :param mFnDependencyNode:
        """
        super(DependNode, self).__init__()
        assert isinstance(mObject, om.MObject)
        self.mObject = mObject
        self._mObject1 = None
        self.mFnDependencyNode = mFnDependencyNode

    def __repr__(self):
        """
        Not a valid Python expression that could be used to recreate an object with the same value since the MObject and
        MFnDependencyNode don't have clean str representation.
        """
        return "<class {}('{}')>".format(self.__class__.__name__, self.name)

    def __str__(self):
        """
        The current node name.
        """
        return self.name

    def __getattr__(self, attr):
        """
        Returns an Attribute linked to self.
        :param attr: str
        :return: Attribute object
        """
        return self.attr(attr)

    def __add__(self, other):
        """
        Adds the node's name and returns a str
        :param other: str or DependNode
        :return: str
        """
        return self.name + other

    def __radd__(self, other):
        """
        Adds the node's name and returns a str.
        :param other: str or DependNode
        :return: str
        """
        return other + self.name

    def __eq__(self, other):
        """
        Compare the api 2.0 MObject for the == operator.
        :param other:
        :return:
        """
        if not isinstance(other, DependNode):
            other = yam(other)
        return self.mObject == other.mObject

    def __contains__(self, item):
        """
        Checks if the item is a children of self.
        """
        raise NotImplementedError

    def __bool__(self):
        """
        Needed for Truth testing since __len__ is defined but does not work on non array attributes.
        :return: True
        """
        return True

    def __nonzero__(self):
        return self.__bool__()

    @property
    def mObject1(self):
        """
        Gets the associated api 1.0 MObject
        :return: api 1.0 MObject
        """
        if self._mObject1 is None:
            mSelectionList = om1.MSelectionList()
            mSelectionList.add(self.name)
            mObject = om1.MObject()
            mSelectionList.getDependNode(0, mObject)
            self._mObject1 = mObject
        return self._mObject1

    def rename(self, new_name):
        """
        Renames the node.
        Needs to use cmds to be undoable.
        :param new_name: str
        """
        # self.mFnDependencyNode.setName(new_name)
        cmds.rename(self.name, new_name)

    @property
    def name(self):
        return self.mFnDependencyNode.name()

    @name.setter
    def name(self, value):
        self.rename(value)

    def attr(self, attr):
        """
        Gets an Attribute object for the given attr.
        This function should be use in case the attr conflicts with a function or attribute of the class.
        :param attr: str
        :return: Attribute object
        """
        assert attr
        import attributes
        return attributes.getAttribute(self, attr)

    def listRelatives(self, **kwargs):
        """
        Returns the maya cmds.listRelatives as DependNode objects.
        :param kwargs: kwargs passed on to cmds.listRelatives
        :return: list[DependNode, ...]
        """
        kwargs['fullPath'] = True  # Needed in case of multiple obj with same name
        return yams(cmds.listRelatives(self.name, **kwargs) or [])

    def listConnections(self, **kwargs):
        """
        Returns the maya cmds.listConnections as DependNode objects or Attribute objects.
        By default if not in kwargs, 'skipConversionNodes' is passed as True.
        :param kwargs: kwargs passed on to cmds.listConnections
        :return: list[Attribute, ...]
        """
        if 'scn' not in kwargs and 'skipConversionNodes' not in kwargs:
            kwargs['scn'] = True
        return yams(cmds.listConnections(self.name, **kwargs) or [])

    def sourceConnections(self, **kwargs):
        """
        Returns listConnections with destination connections disabled.
        See listConnections for more info.
        """
        return self.listConnections(destination=False, **kwargs)

    def destinationConnections(self, **kwargs):
        """
        Returns listConnections with source connections disabled.
        See listConnections for more info.
        """
        return self.listConnections(source=False, **kwargs)

    def listAttr(self, **kwargs):
        """
        Returns the maya cmds.listAttr as DependNode objects or Attribute objects.
        :param kwargs: kwargs passed on to cmds.listAttr
        :return: list[Attribute, ...]
        """
        return yams(cmds.listAttr(self.name, **kwargs) or [])

    def type(self):
        """
        Returns the node type name
        :return: str
        """
        return self.mFnDependencyNode.typeName

    def inheritedTypes(self):
        return cmds.nodeType(self.name, inherited=True)


class DagNode(DependNode):
    """
    Subclass for all maya dag nodes.
    """

    def __init__(self, mObject, mFnDependencyNode):
        super(DagNode, self).__init__(mObject, mFnDependencyNode)
        self._mDagPath = None
        self._mDagPath1 = None
        self._mFnDagNode = None

    def __contains__(self, item):
        """
        Checks if the item is a children of self.
        """
        if not isinstance(item, DependNode):
            item = yam(item)
        return item.longname().startswith(self.longname())

    @property
    def mDagPath(self):
        """
        Gets the associated api 2.0 MDagPath
        :return: api 2.0 MDagPath
        """
        if self._mDagPath is None:
            self._mDagPath = om.MDagPath.getAPathTo(self.mObject)
        return self._mDagPath

    @property
    def mDagPath1(self):
        """
        Gets the associated api 1.0 MDagPath
        :return: api 1.0 MDagPath
        """
        if self._mDagPath1 is None:
            self._mDagPath1 = om1.MDagPath.getApAthTo(self.mObject1)
        return self._mDagPath1

    @property
    def mFnDagNode(self):
        """
        Gets the associated api 2.0 MFnDagNode
        :return: api 2.0 MFnDagNode
        """
        if self._mFnDagNode is None:
            self._mFnDagNode = om.MFnDagNode(self.mObject)
        return self._mFnDagNode

    @property
    def parent(self):
        """
        Gets the node parent node or None if in world.
        :return: DependNode or None
        """
        p = self.mFnDagNode.parent(0)
        if p.apiTypeStr == 'kWorld':
            return None
        return yam(p)

    @parent.setter
    def parent(self, parent):
        if parent is None:
            cmds.parent(self.name, world=True)
        else:
            cmds.parent(self.name, parent)

    @property
    def name(self):
        """
        Returns the minimum string representation in case of other objects with same name.
        """
        return self.mFnDagNode.partialPathName()

    @name.setter
    def name(self, value):
        """
        Property setter needed again even if defined in parent class.
        """
        self.rename(value)

    def longname(self):
        """
        Gets the full path name of the object including the leading |.
        :return: str
        """
        return self.mDagPath.fullPathName()

    fullPath = longname


class Transform(DagNode):
    def __init__(self, mObject, mFnDependencyNode):
        super(Transform, self).__init__(mObject, mFnDependencyNode)

    def __len__(self):
        shape = self.shape
        if shape:
            return len(shape)
        raise TypeError("object has no shape and type '{}' has no len()".format(self.__class__.__name__))

    def children(self, type=None, noIntermediate=True):
        """
        Gets all the node's children as a list of DependNode.
        :param noIntermediate: if True skips intermediate shapes.
        :return: list of DependNode
        """
        children = yams(self.mDagPath.child(x) for x in range(self.mDagPath.childCount()))
        if noIntermediate:
            children = YamList(x for x in children if not x.mFnDagNode.isIntermediateObject)
        if type:
            children.keepType(type=type)
        return children

    def shapes(self, type=None, noIntermediate=True):
        """
        Gets the shapes of the transform as DependNode.
        :param noIntermediate: if True skips intermediate shapes.
        :return: list of Shape object
        """
        children = yams(self.mDagPath.child(x) for x in range(self.mDagPath.childCount()))
        children = YamList(x for x in children if isinstance(x, Shape))
        if noIntermediate:
            children = YamList(x for x in children if not x.mFnDagNode.isIntermediateObject)
        if type:
            children.keepType(type)
        return children

    @property
    def shape(self, noIntermediate=True):
        """
        Returns the first shape if it exists.
        :return: Shape object
        """
        shapes = self.shapes(noIntermediate=noIntermediate)
        return shapes[0] if shapes else None

    def allDescendents(self, type=None):
        if type:
            return self.listRelatives(allDescendents=True, type=type)
        return self.listRelatives(allDescendents=True)

    def getXform(self, **kwargs):
        kwargs['q'] = True
        return cmds.xform(self.name, **kwargs)

    def setXform(self, **kwargs):
        if 'q' in kwargs or 'query' in kwargs:
            raise RuntimeError("setXform kwargs cannot contain 'q' or 'query'")
        cmds.xform(self.name, **kwargs)

    def getPosition(self, ws=False):
        return self.getXform(t=True, ws=ws, os=not ws)

    def setPosition(self, value, ws=False):
        self.setXform(t=value, ws=ws, os=not ws)

    def distance(self, obj):
        if isinstance(obj, Transform):
            wt = obj.worldTranslation
        elif isinstance(obj, basestring):
            wt = yam(obj).worldTranslation
        else:
            raise AttributeError("wrong type given, expected : 'Transform' or 'str', "
                                 "got : {}".format(obj.__class__.__name__))
        node_wt = self.worldTranslation
        dist = sqrt(pow(node_wt[0] - wt[0], 2) + pow(node_wt[1] - wt[1], 2) + pow(node_wt[2] - wt[2], 2))
        return dist


class Joint(Transform):
    def __init__(self, mObject, mFnDependencyNode):
        super(Transform, self).__init__(mObject, mFnDependencyNode)


class Constraint(Transform):
    def __init__(self, mObject, mFnDependencyNode):
        super(Constraint, self).__init__(mObject, mFnDependencyNode)


class Shape(DagNode):
    def __init__(self, mObject, mFnDependencyNode):
        super(Shape, self).__init__(mObject, mFnDependencyNode)

    @property
    def parent(self):
        return super(Shape, self).parent

    @parent.setter
    def parent(self, parent):
        cmds.parent(self.name, parent, r=True, s=True)


class ControlPoint(Shape):
    """
    Handles shape that have control point; e.g.: Mesh, NurbsCurve, NurbsSurface, Lattice
    """
    def __init__(self, mObject, mFnDependencyNode):
        super(ControlPoint, self).__init__(mObject, mFnDependencyNode)

    def __len__(self):
        return len(cmds.ls(self.name+'.cp[*]', fl=True))


class Mesh(ControlPoint):
    def __init__(self, mObject, mFnDependencyNode):
        super(Mesh, self).__init__(mObject, mFnDependencyNode)
        self._mFnMesh = None

    def __len__(self):
        """
        Returns the mesh number of vertices.
        :return: int
        """
        return self.mFnMesh.numVertices

    @property
    def mFnMesh(self):
        if self._mFnMesh is None:
            self._mFnMesh = om.MFnMesh(self.mObject)
        return self._mFnMesh

    def getVtxPosition(self, ws=False):
        import mayautils
        pos = []
        os = not ws
        for vtx in mayautils.componentRange(self, 'vtx', len(self)):
            pos.append(cmds.xform(vtx, q=True, t=True, ws=ws, os=os))
        return pos

    def setVtxPosition(self, data, ws=False):
        import mayautils
        os = not ws
        for vtx, pos in zip(mayautils.componentRange(self, 'vtx', len(self)), data):
            cmds.xform(vtx, t=pos, ws=ws, os=os)

    def shells(self):
        polygon_counts, polygon_connects = self.mFnMesh.getVertices()
        faces_vtxs = []
        i = 0
        for poly_count in polygon_counts:
            faces_vtxs.append(polygon_connects[i:poly_count + i])
            i += poly_count

        shells = []
        finished = False
        while not finished:
            finished = True
            for face_vtxs in faces_vtxs:
                added = False
                for shell in shells:
                    for vtx in face_vtxs:
                        if vtx in shell:
                            shell.update(face_vtxs)
                            added = True
                            finished = False
                            break
                    if added:
                        break
                if not added:
                    shells.append(set(face_vtxs))
            if not finished:
                faces_vtxs = shells
                shells = []
        return shells


class NurbsCurve(ControlPoint):
    def __init__(self, mObject, mFnDependencyNode):
        super(NurbsCurve, self).__init__(mObject, mFnDependencyNode)
        self._mFnNurbsCurve = None

    def __len__(self):
        """
        Returns the mesh number of cvs.
        :return: int
        """
        return self.mFnNurbsCurve.numCVs

    @staticmethod
    def create(cvs, knots, degree, form, parent):
        if isinstance(parent, basestring):
            parent = yam(parent).mObject
        elif isinstance(parent, DependNode):
            parent = parent.mObject
        assert isinstance(parent, om.MObject)
        curve = om.MFnNurbsCurve().create(cvs, knots, degree, form, False, True, parent)
        return yam(curve)

    @property
    def mFnNurbsCurve(self):
        if self._mFnNurbsCurve is None:
            self._mFnNurbsCurve = om.MFnNurbsCurve(self.mObject)
        return self._mFnNurbsCurve

    def getCvsPosition(self, ws=False):
        import mayautils
        pos = []
        for cv in mayautils.componentRange(self, 'cv', len(self)):
            pos.append(cmds.xform(cv, q=True, t=True, ws=ws, os=not ws))
        return pos

    def setCvsPosition(self, data, ws=False):
        import mayautils
        for cv, pos in zip(mayautils.componentRange(self, 'cv', len(self)), data):
            cmds.xform(cv, t=pos, ws=ws, os=not ws)

    @staticmethod
    def getControlPointPosition(controls):
        # todo: copied form old node work, needs cleanup
        return [cmds.xform(x, q=True, os=True, t=True) for x in controls]

    @staticmethod
    def setControlPointPosition(controls, positions):
        # todo: copied form old node work, needs cleanup
        [cmds.xform(control, os=True, t=position) for control in controls for position in positions]

    @property
    def arclen(self, os=False):
        """
        Gets the world space or object space arc length of the curve.
        :param os: if True return the objectSpace length.
        :return: float
        """
        if os:
            return self.mFnNurbsCurve.length()
        return cmds.arclen(self.name)

    @property
    def data(self):
        data = {'cvs': self.mFnNurbsCurve.cvPositions(),
                'knots': self.knots(),
                'degree': self.degree(),
                'form': self.form(),
                }
        return data

    @data.setter
    def data(self, data):
        # todo: copied form old node work, needs cleanup
        for d in data:
            setattr(d, data[d])

    def knots(self):
        return list(self.mFnNurbsCurve.knots())

    def degree(self):
        return self.mFnNurbsCurve.degree

    def form(self):
        return self.mFnNurbsCurve.form


class NurbsSurface(ControlPoint):
    def __init__(self, mObject, mFnDependencyNode):
        super(NurbsSurface, self).__init__(mObject, mFnDependencyNode)
        self._mFnNurbsSurface = None

    def __len__(self):
        return self.lenU() * self.lenV()

    @property
    def mFnNurbsSurface(self):
        if self._mFnNurbsSurface is None:
            self._mFnNurbsSurface = om.MFnNurbsSurface(self.mObject)
        return self._mFnNurbsSurface

    def lenUV(self):
        return [self.lenU(), self.lenV()]

    def lenU(self):
        return self.mFnNurbsSurface.numCVsInU

    def lenV(self):
        return self.mFnNurbsSurface.numCVsInV


class Lattice(ControlPoint):
    def __init__(self, mObject, mFnDependencyNode):
        super(Lattice, self).__init__(mObject, mFnDependencyNode)

    def __len__(self):
        x, y, z = self.lenXYZ()
        return x * y * z

    def lenXYZ(self):
        return cmds.lattice(self.name, divisions=True, q=True)

    def lenX(self):
        return self.lenXYZ()[0]

    def lenY(self):
        return self.lenXYZ()[1]

    def lenZ(self):
        return self.lenXYZ()[2]


class Locator(Shape):
    def __init__(self, mObject, mFnDependencyNode):
        super(Locator, self).__init__(mObject, mFnDependencyNode)


class GeometryFilter(DependNode):
    def __init__(self, mObject, mFnDependencyNode):
        super(GeometryFilter, self).__init__(mObject, mFnDependencyNode)

    @property
    def geometry(self):
        geo = cmds.deformer(self.name, q=True, geometry=True)
        return yam(geo[0]) if geo else None


class WeightGeometryFilter(GeometryFilter):
    def __init__(self, mObject, mFnDependencyNode):
        super(WeightGeometryFilter, self).__init__(mObject, mFnDependencyNode)

    @property
    def weights(self):
        weights = weightsdict.WeightsDict(self)
        for i in self.geometry.get_components_index():
            weights[i] = self.weightsAttr(i).value
        return weights

    @weights.setter
    def weights(self, weights):
        for i, weight in weights.items():
            self.weightsAttr(i).value = weight

    def weightsAttr(self, index):
        """
        Gets the standard deformer weight attribute at the given index
        :param index:
        :return:
        """
        return self.weightList[0].weights[index]


class Cluster(WeightGeometryFilter):
    def __init__(self, mObject, mFnDependencyNode):
        super(Cluster, self).__init__(mObject, mFnDependencyNode)

    def convertToRoot(self):
        # todo
        handle_shape = self.handleShape
        if not handle_shape:
            raise RuntimeError('No clusterHandle found connected to ' + self.name)

        root_grp = createNode('transform', name=self.name+'_clusterRoot')
        cluster_grp = createNode('transform', name=self.name+'_cluster')

        cluster_grp.worldMatrix[0].connectTo(self.matrix, force=True)
        cluster_grp.matrix.connectTo(self.weightedMatrix, force=True)
        root_grp.worldInverseMatrix[0].connectTo(self.bindPreMatrix, force=True)
        root_grp.worldInverseMatrix[0].connectTo(self.preMatrix, force=True)
        self.clusterXforms.breakConnections()
        cmds.delete(handle_shape)

    @property
    def handleShape(self):
        return self.clusterXforms.sourceConnection(plugs=False)


class SkinCluster(GeometryFilter):
    def __init__(self, mObject, mFnDependencyNode):
        super(SkinCluster, self).__init__(mObject, mFnDependencyNode)
        self._weights_attr = None

    def influences(self):
        return yams(cmds.skinCluster(self.name, q=True, inf=True)) or []

    @property
    def weights(self):
        weights = {}
        for i in self.geometry.get_component_indexes():
            weights[i] = weightsdict.WeightsDict()
            for jnt, _ in enumerate(self.influences()):
                weights[i][jnt] = self.weightList[i].weights[jnt].value
        return weights

    @weights.setter
    def weights(self, weights):
        for vtx in weights:
            for jnt in weights[vtx]:
                self.weightList[vtx].weights[jnt].value = weights[vtx][jnt]

    @property
    def dqWeights(self):
        dq_weights = weightsdict.WeightsDict()
        for i in range(len(self.geometry)):
            dq_weights[i] = self.blendWeights[i].value
        return dq_weights

    @dqWeights.setter
    def dqWeights(self, data):
        data = weightsdict.WeightsDict(data)
        for vtx in data:
            self.blendWeights[vtx].value = data[vtx]
        for i, vtx in enumerate(cmds.ls('{}.weightList[*]'.format(self))):
            if i not in data:
                self.blendWeights[i].value = 0

    def reskin(self):
        """
        Resets the skinCluster and mesh to the current influences position.
        """
        for inf in self.influences():
            conns = (x for x in inf.worldMatrix.destinationConnections(type='skinCluster') if x.node == self)
            for conn in conns:
                bpm = self.bindPreMatrix[conn.index]
                if bpm.sourceConnections():
                    print("{} is connected and can't be reset".format(bpm))
                    continue
                wim = inf.worldInverseMatrix.value
                cmds.setAttr(bpm.name, *wim, type='matrix')
        cmds.skinCluster(self.name, e=True, rbm=True)


class BlendShape(GeometryFilter):
    def __init__(self, mObject, mFnDependencyNode):
        super(BlendShape, self).__init__(mObject, mFnDependencyNode)
        self._targets = []
        self._targets_names = {}
        self.getTargets()

    def getTargets(self):
        targets_nodes = yams(cmds.blendShape(self.name, q=True, target=True)) or []
        self._targets = [BlendshapeTarget(self, target_node, index) for index, target_node in enumerate(targets_nodes)]
        self._targets_names = {target.target_node.name: target for target in self._targets}
        return self._targets

    def targets(self, target):
        if isinstance(target, int):
            return self._targets[target]
        elif isinstance(target, basestring):
            return self._targets_names[target]
        else:
            raise KeyError(target)

    def weightsAttr(self, index):
        return self.inputTarget[0].baseWeights[index]

    @property
    def weights(self):
        weights = weightsdict.WeightsDict()
        for index in range(len(self.geometry)):
            weights[index] = self.weightsAttr(index).value
        return weights

    @weights.setter
    def weights(self, weights):
        for i, weight in weights.items():
            self.weightsAttr(i).value = weight


class BlendshapeTarget(Yam):
    def __init__(self, node, target_node, index):
        super(BlendshapeTarget, self).__init__()
        self.target_node = target_node
        self.node = node
        self.index = index
        self.attribute = node.attr(target_node.name)

    def __str__(self):
        return self.attribute.name

    def __repr__(self):
        return "Target({}, {}, {})".format(self.node, self.target_node, self.index)

    def weightsAttr(self, index):
        return self.node.inputTarget[0].inputTargetGroup[self.index].targetWeights[index]

    @property
    def weights(self):
        weights = weightsdict.WeightsDict()
        for i in range(len(self.node.geometry)):
            weights[i] = self.weightsAttr(i).value
        return weights

    @weights.setter
    def weights(self, weights):
        for i, weight in weights.items():
            self.weightsAttr(i).value = weight

    @property
    def value(self):
        return self.attribute.value

    @value.setter
    def value(self, value):
        self.attribute.value = value


# Lists the supported types of maya nodes. Any new node class should be added to this list to be able to get it from
# the yam method. Follow this syntax -> 'mayaType': class)
supported_classes = {'dagNode': DagNode,
                     'transform': Transform,
                     'joint': Joint,
                     'constraint': Constraint,
                     'shape': Shape,
                     'controlPoint': ControlPoint,
                     'mesh': Mesh,
                     'nurbsCurve': NurbsCurve,
                     'nurbsSurface': NurbsSurface,
                     'lattice': Lattice,
                     'locator': Locator,
                     'geometryFilter': GeometryFilter,
                     'weightGeometryFilter': WeightGeometryFilter,
                     'cluster': Cluster,
                     'skinCluster': SkinCluster,
                     'blendShape': BlendShape,
                     }


class YamList(list):
    def __init__(self, *arg):
        super(YamList, self).__init__(*arg)
        self._check()

    def __repr__(self):
        return "<YamList({})>".format(list(self))

    def __str__(self):
        return "YamList({})".format(self.names())

    def _check(self, item=None):
        if item is not None:
            if not isinstance(item, Yam):
                raise TypeError("YamList can only contain Yam objects. '{}' is '{}'".format(item, type(item).__name__))
        else:
            for i in self:
                if not isinstance(i, Yam):
                    raise TypeError("YamList can only contain Yam objects. '{}' is '{}'".format(i, type(i).__name__))

    def append(self, item):
        self._check(item)
        super(YamList, self).append(item)

    def extend(self, items):
        if not isinstance(items, YamList):
            for item in items:
                self._check(item)
        super(YamList, self).extend(items)

    def insert(self, index, item):
        self._check(item)
        super(YamList, self).insert(index, item)

    def sort(self, key=None, reverse=False):
        if key is None:
            def name(x): return x.name
            key = name
        super(YamList, self).sort(key=key, reverse=reverse)

    def attrs(self, attr):
        return [x.attr(attr) for x in self]

    def values(self, attr=None):
        if attr:
            return [x.attr(attr).value for x in self]
        return [x.value for x in self]

    def names(self):
        return [x.name for x in self]

    def mObjects(self):
        return [x.mObject for x in self]

    def getattrs(self, attr, call=False):
        if call:
            return [getattr(x, attr)() for x in self]
        return [getattr(x, attr) for x in self]

    def keepType(self, type, inherited=True):
        if isinstance(type, basestring):
            type = [type]
        assert type and isinstance(type, (list, tuple))
        for i, item in reversed(list(enumerate(self))):
            for type_ in type:
                if inherited:
                    if type_ not in item.inheritedTypes():
                        self.pop(i)
                else:
                    if type_ != item.type():
                        self.pop(i)

    def popType(self, type, inherited=True):
        popped = YamList()
        if isinstance(type, basestring):
            type = [type]
        assert type and isinstance(type, (list, tuple))
        for i, item in reversed(list(enumerate(self))):
            for type_ in type:
                if inherited:
                    if type_ in item.inheritedTypes():
                        popped.append(self.pop(i))
                else:
                    if type_ == item.type():
                        popped.append(self.pop(i))
        return popped

    def copy(self):
        return YamList(self)
