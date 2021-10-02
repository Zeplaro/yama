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
    from importlib import reload

import components
import weightsdict as wdt
import utils


def createNode(*args, **kwargs):
    """
    Creates a node and returns it as its appropriate class depending on its type.
    :param args: cmds args for cmds.createNode
    :param kwargs: cmds kwargs for cmds.createNode
    :return: a YamNode object
    """
    return yam(cmds.createNode(*args, **kwargs))


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

    elif isinstance(node, YamNode):
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
        raise TypeError("yam() str or OpenMaya.MObject of OpenMaya.MDagPath expected,"
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
    Returns each nodes or attributes initialized as their appropriate YamNode or Attribute. See 'yam' function.
    :param nodes: (list) list of str of existing nodes.
    :return: list of YamNode
    """
    return YamList(yam(node) for node in nodes)


class YamNode(object):
    # todo
    pass


class DependNode(YamNode):
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
        :param other: str or YamNode
        :return: str
        """
        return self.name + other

    def __radd__(self, other):
        """
        Adds the node's name and returns a str.
        :param other: str or YamNode
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

    def __apiobject__(self):
        """
        Gets the maya api 1.0 MObject for this object.
        Seems needed for reasons I did not explore yet. And it's implemented like that in pymel so...
        """
        print('calling __apiobject__ for ' + self.name)
        raise RuntimeError("Probably passed a yam node into a cmds object")
        return self.mObject1

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
        return attributes.get_attribute(self, attr)

    def listRelatives(self, **kwargs):
        """
        Returns the maya cmds.listRelatives as YamNode objects.
        :param kwargs: kwargs passed on to cmds.listRelatives
        :return: list[YamNode, ...]
        """
        return yams(cmds.listRelatives(self.name, **kwargs) or [])

    def listConnections(self, **kwargs):
        """
        Returns the maya cmds.listConnections as YamNode objects or Attribute objects.
        By default if not in kwargs, 'skipConversionNodes' is passed as True.
        :param kwargs: kwargs passed on to cmds.listConnections
        :return: list[Attribute, ...]
        """
        if 'scn' not in kwargs and 'skipConversionNodes' not in kwargs:
            kwargs['scn'] = True
        return yams(cmds.listConnections(self.name, **kwargs) or [])

    def source_connections(self, **kwargs):
        """
        Returns listConnections with destination connections disabled.
        See listConnections for more info.
        """
        return self.listConnections(destination=False, **kwargs)

    def destination_connections(self, **kwargs):
        """
        Returns listConnections with source connections disabled.
        See listConnections for more info.
        """
        return self.listConnections(source=False, **kwargs)

    def listAttr(self, **kwargs):
        """
        Returns the maya cmds.listAttr as YamNode objects or Attribute objects.
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

    def inherited_types(self):
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

    def __apiobject__(self):
        """
        Gets the maya api 1.0 MDagPath for this object
        Seems needed for reasons I did not explore yet. And it's implemented like that in pymel so...
        """
        print('calling __apiobject__ from dagNode for ' + self.name)
        return self.mDagPath1

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
        :return: YamNode or None
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
        super(DagNode, self).name = value

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

    def __getattr__(self, item):
        if item in components.supported_components:
            return components.Components(self, item)
        return super(Transform, self).__getattr__(item)

    def children(self, noIntermediate=True, type=None):
        """
        Gets all the node's children as a list of YamNode.
        :param noIntermediate: if True skips intermediate shapes.
        :return: list of YamNode
        """
        children = yams(self.mDagPath.child(x) for x in range(self.mDagPath.childCount()))
        if noIntermediate:
            children = YamList(x for x in children if not x.mFnDagNode.isIntermediateObject)
        if type:
            children.keep_type(type=type)
        return children

    def shapes(self, noIntermediate=True):
        """
        Gets the shapes of the transform as YamNode.
        :param noIntermediate: if True skips intermediate shapes.
        :return: list of Shape object
        """
        children = yams(self.mDagPath.child(x) for x in range(self.mDagPath.childCount()))
        children = YamList(x for x in children if isinstance(x, Shape))
        if noIntermediate:
            children = YamList(x for x in children if not x.mFnDagNode.isIntermediateObject)
        return children

    @property
    def shape(self, noIntermediate=True):
        """
        Returns the first shape if it exists.
        :return: Shape object
        """
        shapes = self.shapes(noIntermediate=noIntermediate)
        return shapes[0] if shapes else None

    def get_translation(self, ws=False):
        os = not ws
        return cmds.xform(self.name, q=True, t=True, ws=ws, os=os)

    def set_translation(self, value, ws=False):
        os = not ws
        cmds.xform(self.name, t=value, ws=ws, os=os)

    def get_rotation(self, ws=False):
        os = not ws
        return cmds.xform(self.name, q=True, ro=True, ws=ws, os=os)

    def set_rotation(self, value, ws=False):
        os = not ws
        cmds.xform(self.name, ro=value, ws=ws, os=os)

    def get_scale(self, ws=False):
        os = not ws
        return cmds.xform(self.name, q=True, s=True, ws=ws, os=os)

    def set_scale(self, value, ws=False):
        os = not ws
        cmds.xform(self.name, s=value, ws=ws, os=os)

    def get_rotate_pivot(self, ws=False):
        os = not ws
        return cmds.xform(self.name, q=True, rp=True, ws=ws, os=os)

    def set_rotate_pivot(self, value, ws=False):
        os = not ws
        cmds.xform(self.name, rp=value, ws=ws, os=os)

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

    def __getattr__(self, item):
        if item in components.supported_components:
            return components.Components(self, item)
        return super(ControlPoint, self).__getattr__(item)


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

    def get_vtx_position(self, ws=False):
        pos = []
        os = not ws
        for vtx in utils.component_range(self, 'vtx', len(self)):
            pos.append(cmds.xform(vtx, q=True, t=True, ws=ws, os=os))
        return pos

    def set_vtx_position(self, data, ws=False):
        os = not ws
        for vtx, pos in zip(utils.component_range(self, 'vtx', len(self)), data):
            cmds.xform(vtx, t=pos, ws=ws, os=os)


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

    def get_cvs_position(self, ws=False):
        pos = []
        os = not ws
        for cv in utils.component_range(self, 'cv', len(self)):
            pos.append(cmds.xform(cv, q=True, t=True, ws=ws, os=os))
        return pos

    def set_cvs_position(self, data, ws=False):
        os = not ws
        for cv, pos in zip(utils.component_range(self, 'cv', len(self)), data):
            cmds.xform(cv, t=pos, ws=ws, os=os)

    @staticmethod
    def get_control_point_position(controls):
        # todo: copied form old node work, needs cleanup
        return [cmds.xform(x, q=True, os=True, t=True) for x in controls]

    @staticmethod
    def set_control_point_position(controls, positions):
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
                'knots': self.mFnNurbsCurve.knots(),
                'degree': self.mFnNurbsCurve.degree,
                'form': self.mFnNurbsCurve.form,
                }
        return data

    @data.setter
    def data(self, data):
        # todo: copied form old node work, needs cleanup
        for d in data:
            setattr(d, data[d])

    @property
    def knots(self):
        # todo: copied form old node work, needs cleanup
        nb_knots = len(self) + self.degree.value - 1
        print('Nb of knots: {}'.format(nb_knots))

        if self.form.value == 0:
            knots = list(range(nb_knots - (self.degree.value - 1) * 2))
            for i in range(self.degree.value - 1):
                knots = knots[:1] + knots
                knots += knots[-1:]
        else:
            knots = list(range(nb_knots - (self.degree.value - 1)))
            for i in range(self.degree.value - 1):
                knots.insert(0, knots[0] - 1)

        if self.type == 'bezierCurve':
            knots = []
            for i in range(nb_knots / 3):
                for j in range(3):
                    knots.append(i)
        knots = [float(x) for x in knots]
        return knots


class NurbsSurface(ControlPoint):
    def __init__(self, mObject, mFnDependencyNode):
        super(NurbsSurface, self).__init__(mObject, mFnDependencyNode)


class Lattice(ControlPoint):
    def __init__(self, mObject, mFnDependencyNode):
        super(Lattice, self).__init__(mObject, mFnDependencyNode)


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
        weights = wdt.WeightsDict(self)
        for i in self.geometry.get_components_index():
            weights[i] = self.weights_attr(i).value
        return weights

    @weights.setter
    def weights(self, weights):
        for i, weight in weights.items():
            self.weights_attr(i).value = weight

    def weights_attr(self, index):
        """
        Gets the standard deformer weight attribute at the given index
        :param index:
        :return:
        """
        return self.weightList[0].weights[index]


class Cluster(WeightGeometryFilter):
    def __init__(self, mObject, mFnDependencyNode):
        super(Cluster, self).__init__(mObject, mFnDependencyNode)

    def convert_to_root(self):
        # todo
        handle_shape = self.handle_shape
        if not handle_shape:
            raise RuntimeError('No clusterHandle found connected to ' + self.name)

        root_grp = createNode('transform', name=self.name+'_clusterRoot')
        cluster_grp = createNode('transform', name=self.name+'_cluster')

        cluster_grp.worldMatrix[0].connect_to(self.matrix, force=True)
        cluster_grp.matrix.connect_to(self.weightedMatrix, force=True)
        root_grp.worldInverseMatrix[0].connect_to(self.bindPreMatrix, force=True)
        root_grp.worldInverseMatrix[0].connect_to(self.preMatrix, force=True)
        self.clusterXforms.breakConnections()
        cmds.delete(handle_shape)

    @property
    def handle_shape(self):
        return self.clusterXforms.source_connection(plugs=False)


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
            weights[i] = wdt.WeightsDict()
            for jnt, _ in enumerate(self.influences()):
                weights[i][jnt] = self.weightList[i].weights[jnt].value
        return weights

    @weights.setter
    def weights(self, weights):
        for vtx in weights:
            for jnt in weights[vtx]:
                self.weightList[vtx].weights[jnt].value = weights[vtx][jnt]

    @property
    def dq_weights(self):
        dq_weights = wdt.WeightsDict()
        for i in range(len(self.geometry)):
            dq_weights[i] = self.blendWeights[i].value
        return dq_weights

    @dq_weights.setter
    def dq_weights(self, data):
        data = wdt.WeightsDict(data)
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
            conns = (x for x in inf.worldMatrix.destination_connections(type='skinCluster') if x.node == self)
            for conn in conns:
                bpm = self.bindPreMatrix[conn.index]
                if bpm.source_connections():
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
        self.get_targets()

    def get_targets(self):
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

    def weights_attr(self, index):
        return self.inputTarget[0].baseWeights[index]

    @property
    def weights(self):
        weights = wdt.WeightsDict()
        for index in range(len(self.geometry)):
            weights[index] = self.weights_attr(index).value
        return weights

    @weights.setter
    def weights(self, weights):
        for i, weight in weights.items():
            self.weights_attr(i).value = weight


class BlendshapeTarget(object):
    def __init__(self, node, target_node, index):
        self.target_node = target_node
        self.node = node
        self.index = index
        self.attribute = node.attr(target_node.name)

    def __str__(self):
        return self.attribute.name

    def __repr__(self):
        return "Target({}, {}, {})".format(self.node, self.target_node, self.index)

    def weights_attr(self, index):
        return self.node.inputTarget[0].inputTargetGroup[self.index].targetWeights[index]

    @property
    def weights(self):
        weights = wdt.WeightsDict()
        for i in range(len(self.node.geometry)):
            weights[i] = self.weights_attr(i).value
        return weights

    @weights.setter
    def weights(self, weights):
        for i, weight in weights.items():
            self.weights_attr(i).value = weight

    @property
    def value(self):
        return self.attribute.value

    @value.setter
    def value(self, value):
        self.attribute.value = value


# Lists the supported types of maya nodes. Any new node class should be added to this list to be able to get it from
# the yam method. Follow this syntax -> 'mayaType': class)
supported_classes = {'skinCluster': SkinCluster,
                     'shape': Shape,
                     'mesh': Mesh,
                     'nurbsCurve': NurbsCurve,
                     'nurbsSurface': NurbsSurface,
                     'locator': Locator,
                     'lattice': Lattice,
                     'geometryFilter': GeometryFilter,
                     'weightGeometryFilter': WeightGeometryFilter,
                     'cluster': Cluster,
                     'blendShape': BlendShape,
                     'transform': Transform,
                     'joint': Joint,
                     }


class YamList(list):
    def __init__(self, arg):
        super(YamList, self).__init__(arg)
        self._check()

    def __repr__(self):
        return "<YamList({})>".format(list(self))

    def __str__(self):
        return "YamList({})".format(self.names)

    def _check(self, item=None):
        if item is not None:
            assert hasattr(item, 'name')
        else:
            for i in self:
                assert hasattr(i, 'name')

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

    @property
    def names(self):
        return [x.name for x in self]

    @property
    def mObject(self):
        return [x.mObject for x in self]

    def remove_type(self, type=None, inherited=True):
        assert type and isinstance(type, basestring)
        for i, item in reversed(list(enumerate(self))):
            if inherited:
                if type in item.inherited_types():
                    self.pop(i)
            else:
                if type == item.type():
                    self.pop(i)

    def keep_type(self, type=None, inherited=True):
        assert type and isinstance(type, basestring)
        for i, item in reversed(list(enumerate(self))):
            if inherited:
                if type not in item.inherited_types():
                    self.pop(i)
            else:
                if type != item.type():
                    self.pop(i)
