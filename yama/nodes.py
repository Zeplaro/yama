# encoding: utf8

"""
Contains all the class for maya node types, and all nodes related functions.
The main functions used would be createNode to create a new node and get it initialized as its proper class type; and
yam or yams to initialize existing objects into their proper class type.
"""

from abc import ABCMeta, abstractproperty, abstractmethod
from six import string_types, PY2
from math import sqrt
from maya import cmds
import maya.api.OpenMaya as om
import maya.api.OpenMayaAnim as oma
import maya.OpenMaya as om1

from . import weightslist, config


def yam(node):
    """
    Handles all node class assignment to assign the proper class depending on the node type.
    Also works with passing a 'node.attribute'.

    examples :
    >> yam('skincluster42')
    ---> SkinCluster('skincluster42')

    >> yam('pCube1.tz')
    ---> Attribute('pCube1.tz')
    """

    mPlug = None
    component = None
    if hasattr(node, 'isAYamObject'):
        return node

    elif isinstance(node, string_types):
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

    elif node.__class__ == om.MObject:  # Not using isinstance() for efficiency
        mObject = node
        mfn = om.MFnDependencyNode(mObject)

    elif node.__class__ == om.MDagPath:  # Not using isinstance() for efficiency
        mObject = node.node()
        mfn = om.MFnDependencyNode(mObject)

    elif node.__class__ == om.MPlug:  # Not using isinstance() for efficiency
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
        if not mfn.hasUniqueName():
            node = om.MDagPath.getAPathTo(mObject).partialPathName()
        else:
            node = mfn.name()
        assigned_class = DependNode
        for node_type in reversed(cmds.nodeType(node, i=True)):  # checks each inherited types for the node
            if node_type in supported_classes:
                assigned_class = supported_classes[node_type]
                break

    yam_node = assigned_class(mObject, mfn)
    if mPlug is not None:
        from . import attributes
        return attributes.Attribute(yam_node, mPlug)
    elif component is not None:
        from . import components
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
    if 'ss' not in kwargs and 'skipSelect' not in kwargs:
        kwargs['ss'] = True
    return yam(cmds.createNode(*args, **kwargs))


def spaceLocator(name='locator', pos=(0, 0, 0), rot=(0, 0, 0), parent=None, ws=False):
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
    if 'os' not in kwargs and 'sl' not in kwargs and 'orderedSelection' not in kwargs and 'selection' not in kwargs:
        kwargs['os'] = True
    return ls(**kwargs)


def select(*args, **kwargs):
    """Set current scene selection with given args and kwargs. Allows to pass yam object into the select function."""
    sel = []
    for arg in args:
        if isinstance(arg, YamList):
            sel.append(arg.names)
        elif hasattr(arg, 'isAYamNode'):
            sel.append(str(arg))
        elif isinstance(arg, (list, tuple, dict, set)):
            new = []
            for arg_ in arg:
                if hasattr(arg_, 'isAYamNode'):
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
    from . import attributes
    is_attr = False
    if isinstance(obj, attributes.Attribute):
        is_attr = True
        if obj.mPlug.isArray:
            obj = obj[0]
    attrs = YamList()
    for attr in cmds.listAttr(obj.name, **kwargs):
        if is_attr:
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

    if PY2:  # if python 2, using use abstractproperty
        @abstractproperty
        def name(self):
            pass
    else:  # else use the preferred property on abstractmethod
        @property
        @abstractmethod
        def name(self):
            pass

    @property
    def isAYamObject(self):
        """Used to check if an object is an instance of Yam with the faster hasattr instead of slower isinstance."""
        return True


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
        Needs a maya api 2.0 MObject associated to the node and a MFnDependencyNode initialized with the mObject.
        :param mObject: maya api MObject
        :param mFnDependencyNode:
        """
        super(DependNode, self).__init__()
        self.mObject = mObject
        self._mObject1 = None
        self.mFnDependencyNode = mFnDependencyNode

    @property
    def isAYamNode(self):
        """Used to check if an object is an instance of DependNode with the faster hasattr instead of slower
        isinstance."""
        return True

    def __repr__(self):
        """
        Not a valid Python expression that could be used to recreate an object with the same value since the MObject and
        MFnDependencyNode don't have clean str representation.
        """
        return "{}('{}')".format(self.__class__.__name__, self.name)

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
        if hasattr(other, 'mObject'):
            return self.mObject == other.mObject
        else:
            try:
                return self.mObject == yam(other).mObject
            except (RuntimeError, TypeError):
                return False

    def __ne__(self, other):
        return not self.__eq__(other)

    def __bool__(self):
        """
        Needed for Truth testing since __len__ is defined but does not work on non array attributes.
        :return: True
        """
        return True

    def __nonzero__(self):
        return self.__bool__()

    def __hash__(self):
        return hash(self.mFnDependencyNode.uuid().asString())

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
        :param newName: str
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
            from . import components
            return components.getComponent(self, attr)  # Trying to get component if one
        except (RuntimeError, TypeError):
            from . import attributes
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
        type_ = None
        if 'type' in kwargs:
            type_ = kwargs.pop('type')
        nodes = yams(cmds.listHistory(self.name, **kwargs))
        if type_:
            nodes.keepType(type_)
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

    def isa(self, nodeType):
        """Returns True is self is of the given type."""
        return nodeType in self.inheritedTypes()

    def uuid(self, asString=True):
        if asString:
            return self.mFnDependencyNode.uuid().asString()
        return self.mFnDependencyNode.uuid()


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
        :param type: Only returns nodes of the given type.
        :param noIntermediate: if True skips intermediate shapes.
        :return: list of DependNode
        """
        children = yams(self.mDagPath.child(x) for x in range(self.mDagPath.childCount()))
        if noIntermediate:
            children = YamList(x for x in children if not x.mFnDagNode.isIntermediateObject)
        if type:
            children.keepType(type)
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
        :return: the queried value·s
        """
        kwargs['q'] = True
        return cmds.xform(self.name, **kwargs)

    def setXform(self, **kwargs):
        """
        Wraps the of cmds.xform, the kwarg query=True cannot be used.
        :param kwargs: any kwargs settable with cmds.xform
        :return: the queried value·s
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
        if isinstance(obj, string_types):
            obj = yam(obj)
        from . import components
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

    def shells(self, indexOnly=False):
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
        if indexOnly:
            return shells
        vtxs = []
        for shell in shells:
            vtxs.append(YamList(self.vtx[x] for x in shell))
        return vtxs


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
        if isinstance(parent, string_types):
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
        self._mFnGeometryFilter = None

    @property
    def mFnGeometryFilter(self):
        if not self._mFnGeometryFilter:
            self._mFnGeometryFilter = oma.MFnGeometryFilter(self.mObject)
        return self._mFnGeometryFilter

    @property
    def geometry(self):
        geo = cmds.deformer(self.name, q=True, geometry=True)
        return yam(geo[0]) if geo else None

    def getDeformerSetGeoAndComponents(self):
        """
        Gets the OpenMaya conponents influenced by the deformer and the deformed geometry
        :return: (om.MDagPath, om.MObject)
        """
        mfn_set = om.MFnSet(self.mFnGeometryFilter.deformerSet)
        return mfn_set.getMembers(True).getComponent(0)


class WeightGeometryFilter(GeometryFilter):
    def __init__(self, mObject, mFnDependencyNode):
        super(WeightGeometryFilter, self).__init__(mObject, mFnDependencyNode)

    @property
    def weights(self):
        weightsAttr = self.weightsAttr
        return weightslist.WeightsList(weightsAttr[x].value for x in range(len(self.geometry)))

    @weights.setter
    def weights(self, weights):
        weightsAttr = self.weightsAttr
        for i, weight in enumerate(weights):
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
        self._mFnSkinCluster = None

    @property
    def mFnSkinCluster(self):
        if self._mFnSkinCluster is None:
            self._mFnSkinCluster = oma.MFnSkinCluster(self.mObject)
        return self._mFnSkinCluster

    def influences(self):
        return yams(self.mFnSkinCluster.influenceObjects())

    def getVertexWeight(self, index, influence_indexes=None):
        if influence_indexes is None:
            influence_indexes = self.getInfluenceIndexes()
        weights = weightslist.WeightsList()
        weightsAttr = self.weightList[index].weights
        for i, jnt_index in enumerate(influence_indexes):
            weights.append(weightsAttr[jnt_index].value)
        return weights

    def setVertexWeight(self, index, values, influence_indexes=None):
        if influence_indexes is None:
            influence_indexes = self.getInfluenceIndexes()
        weightsAttr = self.weightList[index].weights
        for index, value in enumerate(values):
            weightsAttr[influence_indexes[index]].value = value

    def getInfluenceWeights(self, influence, geo=None, components=None):
        """
        Gets the weights of the given influence.
        :param influence: int or Joint object
        :param geo: om.MDagPath of the deformed geometry
        :param components: om.MObject of the deformed components
        :return: WeightList
        """
        if hasattr(influence, 'isAYamNode') or isinstance(influence, string_types):
            influence = self.influences().index(influence)
        if not geo or not components:
            geo, components = self.getDeformerSetGeoAndComponents()
        return weightslist.WeightsList(self.mFnSkinCluster.getWeights(geo, components, influence))

    def setInfluenceWeights(self, influence, weights, geo=None, components=None):
        if not config.undoable:
            return self.setInfluenceWeightsOM(influence=influence, weights=weights, geo=geo, components=components)

        if not hasattr(influence, 'isAYamNode'):
            influence = self.influences()[influence]

        attr_index = self.indexForInfluenceObject(influence)

        for i, weight in enumerate(weights):
            self.weightList[i].weights[attr_index].value = weight

    def setInfluenceWeightsOM(self, influence, weights, geo=None, components=None):
        if hasattr(influence, 'isAYamNode'):
            inf_index = self.influences().index(influence)
        else:
            inf_index = influence
        if not geo or not components:
            geo, components = self.getDeformerSetGeoAndComponents()

        self.mFnSkinCluster.setWeights(geo, components, om.MIntArray([inf_index]), om.MDoubleArray(weights))

    @property
    def weights(self):
        weights = []
        # Getting the weights
        weights_array, num_influences = self.mFnSkinCluster.getWeights(*self.getDeformerSetGeoAndComponents())

        for i in range(0, len(weights_array), num_influences):
            weights.append(weightslist.WeightsList(weights_array[i:i + num_influences]))
        return weights

    @weights.setter
    def weights(self, weights):
        if config.undoable:
            self.setWeights(weights)
        else:
            self.setWeightsOM(weights)

    def setWeights(self, weights):
        for vtx, weight in enumerate(weights):
            self.setVertexWeight(index=vtx, values=weight)

    def setWeightsOM(self, weights):
        geo, components = self.getDeformerSetGeoAndComponents()
        # Getting an array of the influences indexes
        num_influences = len(self.influences())
        influence_array = om.MIntArray(range(num_influences))
        # Flattening the list of weights into a single list
        flat_weights = om.MDoubleArray([i[j] for i in weights for j in range(num_influences)])
        # Setting the weights
        self.mFnSkinCluster.setWeights(geo, components, influence_array, flat_weights)

    @property
    def dqWeights(self):
        return weightslist.WeightsList(self.mFnSkinCluster.getBlendWeights(*self.getDeformerSetGeoAndComponents()))

    @dqWeights.setter
    def dqWeights(self, data):
        if config.undoable:
            self.setDqWeights(data)
        else:
            self.setDqWeightsOM(data)

    def setDqWeights(self, data):
        weightsAttr = self.blendWeights
        for vtx, value in enumerate(data):
            weightsAttr[vtx].value = value

    def setDqWeightsOM(self, data):
        geo, components = self.getDeformerSetGeoAndComponents()
        # Converting the data into maya array
        data = om.MDoubleArray(data)
        # Setting the weights
        self.mFnSkinCluster.setBlendWeights(geo, components, data)

    def getPointsAffectedByInfluence(self, influence):
        """
        Returns the points affected by the given influence
        :param influence: DependNode
        :return: YamList of components
        """
        import components
        if influence in self.influences():
            influence = influence.mDagPath
        else:
            if not isinstance(influence, DagNode):
                raise TypeError("Influence should be of type 'DependNode' not '{}'".format(type(influence).__name__))
            raise RuntimeError("Influence not found in skin cluster")

        vtx_list = yams(self.mFnSkinCluster.getPointsAffectedByInfluence(influence)[0].getSelectionStrings())
        vtxs = YamList()
        for vtx in vtx_list:
            if hasattr(vtx, 'isAYamComponent'):
                vtxs.append(vtx)
            else:
                for vtx_ in vtx:
                    vtxs.append(vtx_)
        return vtxs

    def reskin(self):
        """
        Resets the skinCluster and mesh to the current influences position.
        """
        for inf in self.influences():
            conns = (x for x in inf.worldMatrix.destinationConnections(type='skinCluster') if x.node == self)
            for conn in conns:
                bpm = self.bindPreMatrix[conn.index]
                if bpm.sourceConnection():
                    print("{} is connected and can't be reset".format(bpm))
                    continue
                wim = inf.worldInverseMatrix.value
                cmds.setAttr(bpm.name, *wim, type='matrix')
        cmds.skinCluster(self.name, e=True, rbm=True)

    def indexForInfluenceObject(self, influence):
        """
        Returns the influence connection index on the skinCluster.
        :param influence: DagNode
        :return: int
        """
        return self.mFnSkinCluster.indexForInfluenceObject(influence.mDagPath)

    def getInfluenceIndexes(self):
        return [self.indexForInfluenceObject(inf) for inf in self.influences()]

    @staticmethod
    def convertWeightsDataToPerVertex(data):
        num_vtx = len(data[0])
        range_influence = range(len(data))
        new_data = []
        for vtx in range(num_vtx):
            weights = weightslist.WeightsList()
            for inf in range_influence:
                weights.append(data[inf][vtx])
            new_data.append(weights)
        return new_data

    @staticmethod
    def convertWeightsDataToPerInfluence(data):
        range_vtx = range(len(data))
        num_influence = len(data[0])
        new_data = []
        for inf in range(num_influence):
            weights = weightslist.WeightsList()
            for vtx in range_vtx:
                weights.append(data[vtx][inf])
            new_data.append(weights)
        return new_data


class BlendShape(WeightGeometryFilter):
    def __init__(self, mObject, mFnDependencyNode):
        super(BlendShape, self).__init__(mObject, mFnDependencyNode)
        self._targets = []
        self._targets_names = {}
        self.getTargets()

    def getTargets(self):
        from . import attributes as attrs
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
        elif isinstance(target, string_types):
            return self._targets_names[target]
        else:
            raise KeyError(target)

    @property
    def weightsAttr(self):
        return self.inputTarget[0].baseWeights


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

    def __init__(self, items=(), no_init_check=False):
        super(YamList, self).__init__(items)
        self.no_check = False
        if not no_init_check:
            self._check_all()

    def __repr__(self):
        return "{}{}".format(self.__class__.__name__, list(self))

    def __str__(self):
        return "{}{}".format(self.__class__.__name__, self.names)

    def __eq__(self, other):
        if isinstance(other, YamList):
            return str(list(self)) == str(list(other))
        return str(list(self)) == str(other)

    def __ne__(self, other):
        return not self.__eq__(other)

    def __getitem__(self, item):
        item = super(YamList, self).__getitem__(item)
        if not hasattr(item, 'isAYamObject'):  # In case item is a slice, returns a new YamList
            return YamList(item, no_init_check=True)
        return item

    if PY2:  # if python 2, defining the __getslice__ method.
        def __getslice__(self, *args):
            items = super(YamList, self).__getslice__(*args)
            return YamList(items, no_init_check=True)

    def _check(self, item):
        """
        Check that the given item is a Yam object and raises an error if it is not.
        :param item: object to check
        """
        if not self.no_check:
            if not hasattr(item, 'isAYamObject'):
                raise TypeError("YamList can only contain Yam objects. '{}' is '{}'".format(item, type(item).__name__))

    def _check_all(self):
        """
        Check that all the items in the current object are Yam objects and raises an error if they are not.
        """
        if not self.no_check:
            for item in self:
                if not hasattr(item, 'isAYamObject'):
                    raise TypeError("YamList can only contain Yam objects. '{}' is '{}'".format(item, type(item).__name__))

    def append(self, item):
        if not self.no_check:
            self._check(item)
        super(YamList, self).append(item)

    def extend(self, items):
        if not self.no_check:
            if not isinstance(items, YamList):
                for item in items:
                    self._check(item)
        super(YamList, self).extend(items)

    def no_check_extend(self, items):
        """Extends the list with the given items but skips the type check of the items for efficiency."""
        no_check = self.no_check  # To keep the current status of no_check
        self.no_check = True
        self.extend(items)
        self.no_check = no_check

    def insert(self, index, item):
        self._check(item)
        super(YamList, self).insert(index, item)

    def sort(self, key=None, reverse=False):
        if key is None:
            def name(x): return x.name
            key = name
        super(YamList, self).sort(key=key, reverse=reverse)

    def attrs(self, attr):
        return YamList((x.attr(attr) for x in self), no_init_check=True)

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

    def keepType(self, node_type):
        """
        Remove all nodes that are not of the given type.
        :param node_type: str or list, e.g.: 'joint' or ['blendShape', 'skinCluster']
        """
        if isinstance(node_type, string_types):
            node_type = [node_type]
        for i, item in reversed(list(enumerate(self))):
            inherited_types = item.inheritedTypes()
            for type_ in node_type:
                if type_ not in inherited_types:
                    self.pop(i)

    def popType(self, nodeType):
        """
        Removes all nodes of given type from current object and returns them in a new YamList.
        :param nodeType: str or list, e.g.: 'joint' or ['blendShape', 'skinCluster']
        :param inherited: bool, if True keep nodes who's type is inheriting from given type.
        :return: YamList of the removed nodes
        """
        popped = YamList()
        if isinstance(nodeType, string_types):
            nodeType = [nodeType]
        assert all(isinstance(x, string_types) for x in nodeType), "arg 'type' expected : 'str' or 'list(str, ...)' " \
                                                                   "but was given '{}'".format(nodeType)
        for i, item in reversed(list(enumerate(self))):
            inherited_types = item.inheritedTypes()
            for type_ in nodeType:
                if type_ in inherited_types:
                    popped.append(self.pop(i))
        return popped

    def copy(self):
        return YamList(self, no_init_check=True)
