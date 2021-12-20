# encoding: utf8

"""
Contains all the class for maya node types, and all nodes related functions.
The main functions used would be createNode to create a new node and get it initialized as its proper class type; and
yam or yams to initialize existing objects into their proper class type.
"""

from abc import ABCMeta, abstractproperty, abstractmethod
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
import config


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

    mPlug = None
    component = None
    if isinstance(node, basestring):
        # Getting the mObject associated with the given node uses 'try' in case the node does not exists or multiple
        # objects with the same name exists.
        mSelectionList = om.MSelectionList()
        try:
            mSelectionList.add(node)
        except RuntimeError:
            if cmds.objExists(node):
                raise RuntimeError("more than one object called '{}'".format(node))
            raise RuntimeError("No '{}' object found in scene".format(node))

        if '.' in node:  # checking if an attribute was given with the node
            try:
                mPlug = mSelectionList.getPlug(0)
            except TypeError:
                component = node.split('.')[-1]

        mObject = mSelectionList.getDependNode(0)
        mfn = om.MFnDependencyNode(mObject)

    elif isinstance(node, Yam):
        return node

    elif isinstance(node, om.MObject):
        mObject = node
        mfn = om.MFnDependencyNode(mObject)

    elif isinstance(node, om.MDagPath):
        mObject = node.node()
        mfn = om.MFnDependencyNode(mObject)

    elif isinstance(node, om.MPlug):
        mPlug = node
        mObject = mPlug.node()
        mfn = om.MFnDependencyNode(mObject)

    else:
        raise TypeError("yam(): str, OpenMaya.MObject, OpenMaya.MDagPath or OpenMaya.MPlug expected,"
                        " got {}.".format(node.__class__.__name__))

    # checking if node type has a supported class, if not defaults to DependNode
    type_name = mfn.typeName
    if type_name in supported_classes:
        assigned_class = supported_classes[type_name]  # skips the mc.nodeType if exact type is in supported_class
    else:
        node = mfn.name()
        assigned_class = DependNode
        for node_type in reversed(cmds.nodeType(node, i=True)):  # checks each inherited types for the node
            if node_type in supported_classes:
                assigned_class = supported_classes[node_type]
                break

    yam_node = assigned_class(mObject, mfn)
    if mPlug is not None:
        import attributes
        return attributes.Attribute(yam_node, mPlug)
    elif component is not None:
        import components
        try:
            return components.getComponent(yam_node, component)
        except TypeError as e:
            if not cmds.objExists(node):
                raise RuntimeError("No '{}' object found in scene".format(node))
            raise e
    return yam_node


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


def spaceLocator(name, pos=(0, 0, 0), rot=(0, 0, 0), parent=None, ws=False):
    """
    Creates a locator.
    :param name: str, the locator name
    :param pos: list(float, float, float), the locator position after being parented
    :param rot: list(float, float, float), the locator rotation after being parented
    :param parent: the locator parent
    :param ws: if true sets the pos and rot values in world space
    :return: the locator Transform node object
    """
    loc = yam(cmds.spaceLocator(name=name)[0])
    loc.parent = parent
    loc.setXform(t=pos, ro=rot, ws=ws)
    return loc


def ls(*args, **kwargs):
    """Wrapper for 'maya.cmds.ls' but returning yam objects."""
    if 'fl' not in kwargs and 'flatten' not in kwargs:
        kwargs['fl'] = True
    return yams(cmds.ls(*args, **kwargs))


def selected(**kwargs):
    """Returns current scene selection as yam objects; kwargs are passed on to 'ls'."""
    return ls(os=True, **kwargs)


def select(*args, **kwargs):
    """Set current scene selection with given args and kwargs. Allows to pass yam object into the select function."""
    sel = []
    for arg in args:
        if isinstance(arg, YamList):
            sel.append(arg.names)
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


def listAttr(obj, **kwargs):
    """
    Returns the maya cmds.listAttr as Attribute objects.
    If the attr returned by the cmds is part of an array attribute but the array attr has no index it will fail because
    the child attribute doesn't really exists under the parent without index. This tries to fix that by adding a default
    index of 0 to the parent array before returning the full attribute.
    This workaround is not perfect and will only list attrs under the index 0 of array attrs
    :param obj : DependNode or Attribute
    :param kwargs: kwargs passed on to cmds.listAttr
    :return: YamList([Attribute, ...])
    """
    obj = yam(obj)
    import attributes
    isAttr = False
    if isinstance(obj, attributes.Attribute):
        isAttr = True
        if obj.mPlug.isArray:
            obj = obj[0]
    attrs = YamList()
    for attr in cmds.listAttr(obj.name, **kwargs):
        if isAttr:
            # If obj is Attribute then removing the obj.attribute from the beginning of the listed attr
            if kwargs.get('shortNames', False) or kwargs.get('sn', False):
                attr = attr[len(obj.mPlug.partialName()):]
            else:
                attr = attr[len(obj.attribute):]
        try:
            attr = obj.attr(attr)
            attrs.append(attr)
        except AttributeError:
            if '.' in attr:
                try:
                    split = attr.split('.')
                    attr = obj.attr(split.pop(0))
                    while split:
                        if attr.mPlug.isArray:
                            attr = attr[0]  # sets the array attr index to 0 to get a valid existing attribute 'child'
                        attr = attr.attr(split.pop(0))
                    attrs.append(attr)
                except AttributeError as e:
                    print("Failed to get attribute '{}' on '{}': {}".format(attr, obj, e))
    return attrs


class Yam(object):
    """
    Abstract class for all objects related to maya nodes, attributes and other components.
    Should not be instantiated by itself.
    """
    __metaclass__ = ABCMeta

    if _pyversion == 2:  # if python 2, using use abstractproperty
        @abstractproperty
        def name(self):
            pass
    else:  # else use the preferred property on abstractmethod
        @property
        @abstractmethod
        def name(self):
            pass

    def __eq__(self, other):
        if str(self) == str(other):
            return True
        return False

    def __ne__(self, other):
        return not self.__eq__(other)


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

    def __iadd__(self, other):
        self.rename(self.name + str(other))

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

    def rename(self, newName):
        """
        Renames the node.
        Needs to use cmds to be undoable.
        :param new_name: str
        """
        if not config.undoable:
            self.mFnDependencyNode.setName(newName)
        cmds.rename(self.name, newName)

    @property
    def name(self):
        return self.mFnDependencyNode.name()

    @name.setter
    def name(self, value):
        self.rename(value)

    @property
    def shortName(self):
        """Returns the node name only, without any '|' and 'parent' in case other nodes have the same name"""
        return self.mFnDependencyNode.name()

    def attr(self, attr):
        """
        Gets an Attribute or Component object for the given attr.
        This function should be use in case the attr conflicts with a function or attribute of the class.
        :param attr: str
        :return: Attribute object
        """
        assert attr, "No attribute given"

        try:
            import components
            return components.getComponent(self, attr)  # Trying to get component if one
        except (RuntimeError, TypeError):
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
        Returns the maya cmds.listConnections as DependNode, Attribute or Component objects.
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
        return listAttr(self, **kwargs)

    def listHistory(self, **kwargs):
        """
        Returns the maya cmds.listHistory as DependNode, Attribute or Component objects.
        Allows the kwarg 'type' (unlike cmds.listHistory) to only return objects of given type.
        :param kwargs: kwargs passed on to cmds.listConnections
        :return: list[Attribute, ...]
        :param kwargs:
        :return:
        """
        type = None
        if 'type' in kwargs:
            type = kwargs.pop('type')
        nodes = yams(cmds.listHistory(self.name, **kwargs))
        if type:
            nodes.keepType(type)
        return nodes

    def type(self):
        """
        Returns the node type name
        :return: str
        """
        return self.mFnDependencyNode.typeName

    def inheritedTypes(self):
        """
        Lists the inherited maya types.
        e.g.: for a joint -> ['']
        :return:
        """
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
        """
        Sets the node under the given parent or world if None.
        :return: DependNode or None
        """
        if self.parent is parent:
            return
        elif parent is None:
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

    @property
    def longName(self):
        """
        Gets the full path name of the object including the leading |.
        :return: str
        """
        return self.mDagPath.fullPathName()

    @property
    def fullPath(self):
        return self.longName


class Transform(DagNode):
    def __init__(self, mObject, mFnDependencyNode):
        super(Transform, self).__init__(mObject, mFnDependencyNode)

    def __len__(self):
        shape = self.shape
        if shape:
            return len(shape)
        raise TypeError("object has no shape and type '{}' has no len()".format(self.__class__.__name__))

    def __contains__(self, item):
        """
        Checks if the item is a children of self.
        """
        if not isinstance(item, DependNode):
            try:
                item = yam(item)
            except Exception as e:
                raise RuntimeError("in '{}.__contains__('{}')'; {}".format(self, item, e))
        return item.longName.startswith(self.longName)

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
        """
        Wraps the query of cmds.xform, the kwarg query=True is not needed and will be set to True.
        :param kwargs: any kwargs queryable from cmds.xform
        :return: the queried value/s
        """
        kwargs['q'] = True
        return cmds.xform(self.name, **kwargs)

    def setXform(self, **kwargs):
        """
        Wraps the of cmds.xform, the kwarg query=True cannot be used.
        :param kwargs: any kwargs settable with cmds.xform
        :return: the queried value/s
        """
        if 'q' in kwargs or 'query' in kwargs:
            raise RuntimeError("setXform kwargs cannot contain 'q' or 'query'")
        cmds.xform(self.name, **kwargs)

    def getPosition(self, ws=False):
        """
        Gets the translate position of the node.
        :param ws: If True returns the world space position of the node
        :return: [float, float, float]
        """
        return self.getXform(t=True, ws=ws, os=not ws)

    def setPosition(self, value, ws=False):
        """
        Sets the translate position of the node.
        :param value: [float, float, float]
        :param ws: If True sets the world space position of the node
        """
        self.setXform(t=value, ws=ws, os=not ws)

    def distance(self, obj):
        """
        Gets the distance between self and given obj
        :param obj: Transform, Component or str
        :return: float
        """
        if isinstance(obj, basestring):
            obj = yam(obj)
        import components
        if not isinstance(obj, (Transform, components.Component)):
            raise AttributeError("wrong type given, expected : 'Transform', 'Component' or 'str', "
                                 "got : {}".format(obj.__class__.__name__))
        pos, obj_pos = self.getPosition(ws=True), obj.getPosition(ws=True)
        dist = sqrt(pow(pos[0] - obj_pos[0], 2) + pow(pos[1] - obj_pos[1], 2) + pow(pos[2] - obj_pos[2], 2))
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
        if self.parent is parent:
            return
        cmds.parent(self.name, parent, r=True, s=True)


class ControlPoint(Shape):
    """
    Handles shape that have control point; e.g.: Mesh, NurbsCurve, NurbsSurface, Lattice
    """

    def __init__(self, mObject, mFnDependencyNode):
        super(ControlPoint, self).__init__(mObject, mFnDependencyNode)

    def __len__(self):
        return len(cmds.ls(self.name+'.cp[*]', fl=True))

    def getPositions(self, ws=False):
        return [cp.getPosition(ws=ws) for cp in self.cp]

    def setPositions(self, data, ws=False):
        for cp, pos in zip(self.cp, data):
            cp.setPosition(pos, ws=ws)


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
            self._mFnMesh = om.MFnMesh(self.mDagPath)
        return self._mFnMesh

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
            self._mFnNurbsCurve = om.MFnNurbsCurve(self.mDagPath)
        return self._mFnNurbsCurve

    def arclen(self, ws=False):
        """
        Gets the world space or object space arc length of the curve.
        :param ws: if False return the objectSpace length.
        :return: float
        """
        if not ws:
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
            self._mFnNurbsSurface = om.MFnNurbsSurface(self.mDagPath)
        return self._mFnNurbsSurface

    def lenUV(self):
        """
        Gets the number of cvs in U and V
        :return: [int, int]
        """
        return [self.lenU(), self.lenV()]

    def lenU(self):
        """
        Gets the number of cvs in U
        :return: int
        """
        return self.mFnNurbsSurface.numCVsInU

    def lenV(self):
        """
        Gets the number of cvs in V
        :return: int
        """
        return self.mFnNurbsSurface.numCVsInV


class Lattice(ControlPoint):
    def __init__(self, mObject, mFnDependencyNode):
        super(Lattice, self).__init__(mObject, mFnDependencyNode)

    def __len__(self):
        """
        Returns the number of points in the lattice
        :return:
        """
        x, y, z = self.lenXYZ()
        return x * y * z

    def lenXYZ(self):
        """
        Returns the number of points in X, Y and Z
        :return: [int, int, int]
        """
        return cmds.lattice(self.name, divisions=True, q=True)

    def lenX(self):
        """
        Returns the number of points in X
        :return: int
        """
        return self.lenXYZ()[0]

    def lenY(self):
        """
        Returns the number of points in Y
        :return: int
        """
        return self.lenXYZ()[1]

    def lenZ(self):
        """
        Returns the number of points in Z
        :return: int
        """
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
        weights = weightsdict.WeightsDict()
        weightsAttr = self.weightsAttr
        for i in range(len(self.geometry)):
            weights[i] = weightsAttr[i].value
        return weights

    @weights.setter
    def weights(self, weights):
        weightsAttr = self.weightsAttr
        for i, weight in weights.items():
            weightsAttr[i].value = weight

    @property
    def weightsAttr(self):
        """
        Gets an easy access to the standard deformer weight attribute
        :return: Attribute
        """
        return self.weightList[0].weights


class Cluster(WeightGeometryFilter):
    def __init__(self, mObject, mFnDependencyNode):
        super(Cluster, self).__init__(mObject, mFnDependencyNode)

    def convertToRoot(self):
        """
        Adds a 'root' node as parent of the cluster. The root can be moved around without the cluster having an
        influence on the deformed shape.
        :return: the new root node of the cluster.
        """
        handle_shape = self.handleShape
        if not handle_shape:
            raise RuntimeError('No clusterHandle found connected to ' + self.name)

        root_grp = createNode('transform', name=self.shortName + '_clusterRoot')
        cluster_grp = createNode('transform', name=self.shortName + '_cluster')

        cluster_grp.worldMatrix[0].connectTo(self.matrix, force=True)
        cluster_grp.matrix.connectTo(self.weightedMatrix, force=True)
        root_grp.worldInverseMatrix[0].connectTo(self.bindPreMatrix, force=True)
        root_grp.worldInverseMatrix[0].connectTo(self.preMatrix, force=True)
        self.clusterXforms.breakConnections()
        cmds.delete(handle_shape)
        return root_grp

    @property
    def handleShape(self):
        return self.clusterXforms.sourceConnection(plugs=False)


class SkinCluster(GeometryFilter):
    def __init__(self, mObject, mFnDependencyNode):
        super(SkinCluster, self).__init__(mObject, mFnDependencyNode)
        self._weights_attr = None

    def influences(self):
        return yams(cmds.skinCluster(self.name, q=True, inf=True)) or []

    def getVertexWeight(self, index, numInfluences=None):
        if numInfluences is None:
            numInfluences = len(self.influences())
        weights = weightsdict.WeightsDict()
        weightsAttr = self.weightList[index].weights
        for jnt in range(numInfluences):
            weights[jnt] = weightsAttr[jnt].value
        return weights

    def setVertexWeight(self, index, values):
        weightsAttr = self.weightList[index].weights
        for jnt, value in values.items():
            weightsAttr[jnt].value = value

    @property
    def weights(self):
        weights = {}
        numInfluences = len(self.influences())
        for i in range(len(self.geometry)):
            weights[i] = self.getVertexWeight(i, numInfluences)
        return weights

    @weights.setter
    def weights(self, weights):
        for vtx in weights:
            self.setVertexWeight(vtx, weights[vtx])

    @property
    def dqWeights(self):
        dq_weights = weightsdict.WeightsDict()
        weightsAttr = self.blendWeights
        for i in range(len(self.geometry)):
            dq_weights[i] = weightsAttr[i].value
        return dq_weights

    @dqWeights.setter
    def dqWeights(self, data):
        weightsAttr = self.blendWeights
        for vtx in data:
            weightsAttr[vtx].value = data[vtx]

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
        import attributes as attrs
        targets = cmds.listAttr(self.name + '.weight[:]')
        self._targets = []
        self._targets_names = {}
        for index, target in enumerate(targets):
            bs_target = attrs.BlendshapeTarget(self, attrs.getMPlug(self.name + '.' + target), index)
            self._targets.append(bs_target)
            self._targets_names[target] = bs_target
        return self._targets

    def targets(self, target):
        if isinstance(target, int):
            return self._targets[target]
        elif isinstance(target, basestring):
            return self._targets_names[target]
        else:
            raise KeyError(target)

    @property
    def weightsAttr(self):
        return self.inputTarget[0].baseWeights

    @property
    def weights(self):
        weights = weightsdict.WeightsDict()
        weightsAttr = self.weightsAttr
        for index in range(len(self.geometry)):
            weights[index] = weightsAttr[index].value
        return weights

    @weights.setter
    def weights(self, weights):
        weightsAttr = self.weightsAttr
        for i, weight in weights.items():
            weightsAttr[i].value = weight


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
    """
    A list like class to contain any Yam objects and facilitate their handling.
    A YamList can only contain objects that inherits from the Yam class.

    Mainly used to call .names on the YamList to return a list of str object names that can be passed to cmds commands.
    Can be used to keep a type of node or remove a type of node from the list using .keepType and .popType
    """

    def __init__(self, *arg):
        super(YamList, self).__init__(*arg)
        self._check()

    def __repr__(self):
        return "<class {}({})>".format(self.__class__.__name__, list(self))

    def __str__(self):
        return "{}({})".format(self.__class__.__name__, self.names)

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

    @property
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
        assert all(isinstance(x, basestring) for x in type), "arg 'type' expected : 'str' or 'list(str, ...)' but " \
                                                             "was given '{}'".format(type)
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
        assert all(isinstance(x, basestring) for x in type), "arg 'type' expected : 'str' or 'list(str, ...)' but " \
                                                             "was given '{}'".format(type)
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
