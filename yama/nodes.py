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

from . import weightlist, config, checks


def getMObject(node):  # type: (str) -> om.MObject
    """
    Gets the associated OpenMaya.MObject for the given node.
    :param node: str, node unique name
    :return: OpenMaya.MObject
    """
    mSelectionList = om.MSelectionList()
    try:
        mSelectionList.add(node)
    except RuntimeError:
        if checks.objExists(node):
            raise Exception("more than one object called '{}'".format(node))
        checks.objExists(node, raiseError=True)
    try:
        MObject = mSelectionList.getDependNode(0)
    except Exception as e:
        raise Exception("Failed to getDependNode on : '{}'; {}".format(node, e))
    return MObject


gmo = getMObject


def yam(node):  # type: (Yam, str, om.MObject, om.MDagPath, om.MPlug) -> Yam
    """
    Handles all node class assignment to assign the proper class depending on the node type.
    Also works with passing a 'node.attribute'.

    examples :
    >> yam('skincluster42')
    ---> SkinCluster('skincluster42')

    >> yam('pCube1.tz')
    ---> Attribute('pCube1.tz')
    """

    attribute = None

    if hasattr(node, 'isAYamObject'):
        return node

    elif isinstance(node, string_types):
        if '.' in node:  # checking if an attribute or component was given with the node
            node, attribute = node.split('.', 1)
        MObject = getMObject(node)

    elif node.__class__ == om.MObject:  # Not using isinstance() for efficiency
        MObject = node

    elif node.__class__ == om.MDagPath:  # Not using isinstance() for efficiency
        MObject = node.node()

    elif node.__class__ == om.MPlug:  # Not using isinstance() for efficiency
        from . import attributes
        return attributes.Attribute(MPlug=node)

    else:
        raise TypeError("yam(): str, OpenMaya.MObject, OpenMaya.MDagPath or OpenMaya.MPlug expected,"
                        " got {}.".format(node.__class__.__name__))

    yam_node = Singleton(MObject)
    if attribute:
        return yam_node.attr(attribute)
    return yam_node


def yams(nodes):  # type: ([Yam, str, om.MObject, om.MDagPath, om.MPlug]) -> YamList
    """
    Returns each node or attributes initialized as their appropriate DependNode or Attribute. See 'yam' function.
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


def duplicate(objs, **kwargs):
    """Wrapper for cmds.duplicate"""
    return yams(cmds.duplicate(objs, **kwargs))


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
    :param obj : DependNode, Attribute or str.
    :param kwargs: kwargs passed on to cmds.listAttr
    :return: YamList([Attribute, ...])
    """
    if not hasattr(obj, 'isAYamNode'):
        obj = yam(obj)
    return YamList(obj.attr(attr) for attr in cmds.listAttr(obj.name, **kwargs) or [])


class Singleton(object):
    """
    Handles the instances of Yam nodes to return already instantiated nodes instead of creating a new object if the node
    has already been instantiated.
    """
    _instances = {}

    def __new__(cls, MObject):
        """
        Returns the node instance corresponding to the given MObject if it has already been instantiated, otherwise it
        returns a new instance of the given nodeClass corresponding to the given MObject.
        :param MObject: A valid OpenMaya MObject corresponding to a node.
        """
        try:  # Faster than checking for type using isinstance
            handle = om.MObjectHandle(MObject)
        except ValueError:
            raise TypeError("Expected OpenMaya.MObject type, instead got : '{}'".format(type(MObject).__name__))
        if not handle.isValid():
            raise ValueError("Given MObject does not contain a valid node")
        hash_code = handle.hashCode()

        if config.use_singleton and hash_code in cls._instances:
            return cls._instances[hash_code]

        else:  # finding if node type has a supported class
            type_id = MObject.apiType()
            # skips the SupportedTypes.getclass if exact type is in supported_class
            if type_id in SupportedTypes.classes_MFn:
                assigned_class = SupportedTypes.classes_MFn[type_id]
            else:
                assigned_class = cls.getclass(MObject)
            yam_node = assigned_class(MObject)
            cls._instances[hash_code] = yam_node
            return yam_node

    @classmethod
    def getclass(cls, MObject):
        """
        Gets the class that most closely corresponds to the given MObject.

        Raises an error if no corresponding class was found, not even DependNode, meaning that
        MObject.hasFn(om.MFn.KDependencyNode) returned : False.
        :param MObject: A valid OpenMaya.MObject
        :return: assigned class
        """
        def getit(data, assigned=None):
            for (child, fn), sub_data in data.items():
                if MObject.hasFn(fn):
                    return getit(sub_data, child)
            return assigned
        assigned = getit(SupportedTypes.inheritance_tree)
        if assigned:
            return assigned
        raise ValueError("Given MObject does not contain a valid dependencyNode.")

    @classmethod
    def getclass_cmds(cls, MObject):
        """
        Old way to get the class that most closely corresponds to the given MObject.

        Slower than getclass but could be useful for more granular class assignment;
        i.e., there is no way to check for a node that would inherit from ControlPoint only, because there is no
        kControlPoint in om.MFn, but this is possible using cmds.nodeType(node_name, inherited=True) and match the
        returned type to the closest supported class.

        Raises an error if no corresponding class was found, not even DependNode, meaning that
        OpenMaya.MFnDependencyNode(MObject).name() failed.
        :param MObject: A valid OpenMaya.MObject
        :return: assigned class
        """
        # checking if node type has a supported class, if not defaults to DependNode
        if MObject.hasFn(om.MFn.kDagNode):
            node_name = om.MDagPath.getAPathTo(MObject).partialPathName()  # Getting the shortest unique name
        else:
            try:
                node_name = om.MFnDependencyNode(MObject).name()
            except RuntimeError as e:
                raise ValueError("Given MObject does not contain a valid dependencyNode; {}".format(e))
        for node_type in reversed(cmds.nodeType(node_name, i=True)):  # checks each inherited types for the node
            if node_type in SupportedTypes.classes_str:
                return SupportedTypes.classes_str[node_type]
        return DependNode

    @classmethod
    def clear(cls):
        cls._instances = {}

    @classmethod
    def exists(cls, MObject):
        try:  # Faster than checking for type using isinstance
            handle = om.MObjectHandle(MObject)
        except ValueError:
            raise TypeError("Expected OpenMaya.MObject type, instead got : '{}'".format(type(MObject).__name__))

        hash_code = handle.hashCode()
        if hash_code in cls._instances:
            return cls._instances[hash_code]
        return False


class Yam(object):
    """
    Abstract class for all objects related to maya nodes, attributes and other components.
    Should not be instantiated by itself.
    """
    __metaclass__ = ABCMeta

    if PY2:  # if python 2, use abstractproperty
        @abstractproperty
        def name(self):
            raise NotImplementedError
    else:  # else use the preferred property on abstractmethod
        @property
        @abstractmethod
        def name(self):
            raise NotImplementedError

    @property
    def isAYamObject(self):
        """Used to check if an object is an instance of Yam with the faster hasattr instead of slower isinstance."""
        return True


class DependNode(Yam):
    """
    Main maya node type that all nodes inherits from.
    Links the node to its maya api 2.0 MObject to access many of the faster api functions and classes (MFn), and also in
    case the node name changes.

    All implemented maya api functions and variables are from api 2.0; api 1.0 functions and variables that are
    implemented, are defined with a '1' suffix.
    e.g.:
    >>> node = yam('pCube1')
    >>> node.MObject   # <-- returns a api 2.0 object
    >>> node.MObject1  # <-- returns a api 1.0 object
    """

    def __init__(self, MObject):
        """
        Needs a maya api 2.0 MObject associated to the node and a MFnDependencyNode initialized with the MObject.
        :param MObject: maya api MObject
        """
        super(DependNode, self).__init__()
        self.MObject = MObject
        self._MObject1 = None
        self._MFnFnc = om.MFnDependencyNode
        self._MFnObject = 'MObject'
        self._MFn = None
        self._attributes = {}
        self._hashCode = None

    @property
    def isAYamNode(self):
        """Used to check if an object is an instance of DependNode with the faster hasattr instead of slower
        isinstance."""
        return True

    @property
    def MFn(self):
        """
        Gets the associated api 2.0 MFn object
        :return: api 2.0 MFn Object
        """
        if self._MFn is None:
            self._MFn = self._MFnFnc(getattr(self, self._MFnObject))
        return self._MFn

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
        if hasattr(other, 'MObject'):
            return self.MObject == other.MObject
        else:
            try:
                return self.MObject == yam(other).MObject
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
        return self.hashCode

    @property
    def MObject1(self):
        """
        Gets the associated api 1.0 MObject
        :return: api 1.0 MObject
        """
        if self._MObject1 is None:
            mSelectionList = om1.MSelectionList()
            mSelectionList.add(self.name)
            MObject = om1.MObject()
            mSelectionList.getDependNode(0, MObject)
            self._MObject1 = MObject
        return self._MObject1

    def rename(self, newName):
        """
        Renames the node.
        Needs to use cmds to be undoable.
        :param newName: str
        """
        if not config.undoable:
            self.MFn.setName(newName)
        cmds.rename(self.name, newName)

    @property
    def name(self):
        return self.MFn.name()

    @name.setter
    def name(self, value):
        self.rename(value)

    @property
    def shortName(self):
        """Returns the node name only, without any '|' and 'parent' in case other nodes have the same name"""
        return self.MFn.name()

    def attr(self, attr):
        """
        Gets an Attribute object for the given attr.
        This function should be use in case the attr conflicts with a function or attribute of the class.
        :param attr: str
        :return: Attribute object
        """
        from . import attributes
        if config.use_singleton:
            if attr in self._attributes and not self._attributes[attr].MPlug.isNull:
                return self._attributes[attr]

        attribute = attributes.getAttribute(self, attr)
        self._attributes[attr] = attribute
        return attribute

    def addAttr(self, longName, **kwargs):
        # Checks if 'attributeType' or 'at' is in kwargs and has a value
        if not kwargs.get('at') and not kwargs.get('attributeType'):
            raise RuntimeError("No attribute type given")

        cmds.addAttr(self.name, longName=longName, **kwargs)
        return self.attr(longName)

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
        'skipConversionNodes' set to True by default if not in kwargs.
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
        return self.MFn.typeName

    def inheritedTypes(self):
        """
        Lists the inherited maya types.
        e.g.: for a joint -> ['containerBase', 'entity', 'dagNode', 'transform', 'joint']
        :return: list of inherited maya types
        """
        return cmds.nodeType(self.name, inherited=True)

    def isa(self, nodeType):
        """Returns True is self is of the given type."""
        return nodeType in self.inheritedTypes()

    @property
    def hashCode(self):
        if not self._hashCode:
            self._hashCode = om.MObjectHandle(self.MObject).hashCode()
        return self._hashCode

    def uuid(self, asString=True):
        if asString:
            return self.MFn.uuid().asString()
        return self.MFn.uuid()


class DagNode(DependNode):
    """
    Subclass for all maya dag nodes.
    """

    def __init__(self, MObject):
        super(DagNode, self).__init__(MObject)
        self._MFnFnc = om.MFnDagNode
        self._MDagPath = None
        self._MDagPath1 = None

    @property
    def MDagPath(self):
        """
        Gets the associated api 2.0 MDagPath
        :return: api 2.0 MDagPath
        """
        if self._MDagPath is None or not self._MDagPath.isValid():
            self._MDagPath = om.MDagPath.getAPathTo(self.MObject)
        return self._MDagPath

    @property
    def MDagPath1(self):
        """
        Gets the associated api 1.0 MDagPath
        :return: api 1.0 MDagPath
        """
        if self._MDagPath1 is None:
            self._MDagPath1 = om1.MDagPath.getAPathTo(self.MObject1)
        return self._MDagPath1

    @property
    def parent(self):
        """
        Gets the node parent node or None if in world.
        :return: DependNode or None
        """
        parent = self.MFn.parent(0)
        if parent.apiTypeStr == 'kWorld':
            return None
        return yam(parent)

    @parent.setter
    def parent(self, parent):
        """
        Sets the node under the given parent or world if None.
        :return: DependNode or None
        """
        if self.parent == parent:
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
        return self.MDagPath.partialPathName()

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
        return self.MDagPath.fullPathName()

    @property
    def fullPath(self):
        return self.longName


class Transform(DagNode):
    def __init__(self, MObject):
        super(Transform, self).__init__(MObject)
        self._MFnFnc = om.MFnTransform

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

    def attr(self, attr):
        """
        Gets an Attribute or Component object for the given attr.
        This function should be use in case the attr conflicts with a function or attribute of the class.
        :param attr: str
        :return: Attribute object
        """
        from . import components
        try:
            return components.getComponent(self, attr)  # Trying to get component if one
        except (RuntimeError, TypeError):
            return super(Transform, self).attr(attr)

    def children(self, type=None, noIntermediate=True):
        """
        Gets all the node's children as a list of DependNode.
        :param type: Only returns nodes of the given type.
        :param noIntermediate: if True skips intermediate shapes.
        :return: list of DependNode
        """
        children = yams(self.MDagPath.child(x) for x in range(self.MDagPath.childCount()))
        if noIntermediate:
            children = YamList(x for x in children if not x.MFn.isIntermediateObject)
        if type:
            children.keepType(type)
        return children

    def shapes(self, type=None, noIntermediate=True):
        """
        Gets the shapes of the transform as DependNode.
        :param noIntermediate: if True skips intermediate shapes.
        :return: list of Shape object
        """
        children = yams(self.MDagPath.child(x) for x in range(self.MDagPath.childCount()))
        children = YamList(x for x in children if isinstance(x, Shape))
        if noIntermediate:
            children = YamList(x for x in children if not x.MFn.isIntermediateObject)
        if type:
            children.keepType(type)
        return children

    @property
    def shape(self):
        """
        Returns the first shape if it exists.
        :return: Shape object
        """
        shapes = self.shapes()
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


class Shape(DagNode):
    def __init__(self, MObject):
        super(Shape, self).__init__(MObject)

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

    def __init__(self, MObject):
        super(ControlPoint, self).__init__(MObject)

    def __len__(self):
        return len(cmds.ls(self.name + '.cp[*]', fl=True))

    def getPositions(self, ws=False):
        return [cp.getPosition(ws=ws) for cp in self.cp]

    def setPositions(self, data, ws=False):
        for cp, pos in zip(self.cp, data):
            cp.setPosition(pos, ws=ws)

    def attr(self, attr):
        """
        Gets an Attribute or Component object for the given attr.
        This function should be use in case the attr conflicts with a function or attribute of the class.
        :param attr: str
        :return: Attribute object
        """
        try:
            from . import components
            return components.getComponent(self, attr)  # Trying to get component if one
        except (RuntimeError, TypeError):
            return super(ControlPoint, self).attr(attr)


class SurfaceShape(ControlPoint):
    """
    Handles control point shapes that have a surface; e.g.: Mesh and NurbsSurface
    Mainly used to check object isinstance.
    """
    def __init__(self, MObject):
        super(SurfaceShape, self).__init__(MObject)


class Mesh(SurfaceShape):
    def __init__(self, MObject):
        super(Mesh, self).__init__(MObject)
        self._MFnFnc = om.MFnMesh
        self._MFnObject = 'MDagPath'

    def __len__(self):
        """
        Returns the mesh number of vertices.
        :return: int
        """
        return self.MFn.numVertices

    def shells(self, indexOnly=False):
        polygon_counts, polygon_connects = self.MFn.getVertices()
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
    def __init__(self, MObject):
        super(NurbsCurve, self).__init__(MObject)
        self._MFnFnc = om.MFnNurbsCurve
        self._MFnObject = 'MDagPath'

    def __len__(self):
        """
        Returns the mesh number of cvs.
        :return: int
        """
        return self.MFn.numCVs

    @staticmethod
    def create(cvs, knots, degree, form, parent):
        if isinstance(parent, string_types):
            parent = yam(parent).MObject
        elif isinstance(parent, DependNode):
            parent = parent.MObject
        assert isinstance(parent, om.MObject)
        curve = om.MFnNurbsCurve().create(cvs, knots, degree, form, False, True, parent)
        return yam(curve)

    def arclen(self, ws=False):
        """
        Gets the world space or object space arc length of the curve.
        :param ws: if False return the objectSpace length.
        :return: float
        """
        if not ws:
            return self.MFn.length()
        return cmds.arclen(self.name)

    @property
    def data(self):
        data = {'cvs': self.MFn.cvPositions(),
                'knots': self.knots(),
                'degree': self.degree(),
                'form': self.form(),
                }
        return data

    def knots(self):
        return list(self.MFn.knots())

    def degree(self):
        return self.MFn.degree

    def form(self):
        return self.MFn.form


class NurbsSurface(SurfaceShape):
    def __init__(self, MObject):
        super(NurbsSurface, self).__init__(MObject)
        self._MFnFnc = om.MFnNurbsSurface
        self._MFnObject = 'MDagPath'

    def __len__(self):
        return self.lenU() * self.lenV()

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
        return self.MFn.numCVsInU

    def lenV(self):
        """
        Gets the number of cvs in V
        :return: int
        """
        return self.MFn.numCVsInV


class Lattice(ControlPoint):
    def __init__(self, MObject):
        super(Lattice, self).__init__(MObject)

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


class GeometryFilter(DependNode):
    def __init__(self, MObject):
        super(GeometryFilter, self).__init__(MObject)
        self._MFnFnc = oma.MFnGeometryFilter

    @property
    def geometry(self):
        geo = cmds.deformer(self.name, q=True, geometry=True)
        return yam(geo[0]) if geo else None

    def getDeformerSetGeoAndComponents(self):
        """
        Gets the OpenMaya conponents influenced by the deformer and the deformed geometry
        :return: (om.MDagPath, om.MObject)
        """
        mfn_set = om.MFnSet(self.MFn.deformerSet)
        return mfn_set.getMembers(True).getComponent(0)


class WeightGeometryFilter(GeometryFilter):
    # TODO : update all inheriting classes to get weights or array attr values directly; Or not because not used array
    #  plugs don't exist yet
    def __init__(self, MObject):
        super(WeightGeometryFilter, self).__init__(MObject)

    @property
    def weights(self):
        geometry = self.geometry
        if not geometry:
            raise RuntimeError("Deformer '{}' is not connected to a geometry".format(self.node))
        weightsAttr = self.weightsAttr
        return weightlist.WeightList(weightsAttr[x].value for x in range(len(geometry)))

    @weights.setter
    def weights(self, weights):
        weightsAttr = self.weightsAttr
        for i, weight in enumerate(weights):
            weightsAttr[i].value = weight

    @property
    def weightsAttr(self):
        """
        Gets easy access to the standard deformer weight attribute.
        :return: Attribute
        """
        return self.weightList[0].weights


class Cluster(WeightGeometryFilter):
    def __init__(self, MObject):
        super(Cluster, self).__init__(MObject)

    def convertToRoot(self):
        """
        Adds a 'root' node as parent of the cluster. The root can be moved around without the cluster having an
        influence on the deformed shape.
        :return: the new root transform of the cluster.
        """
        handle_shape = self.handleShape
        if not handle_shape:
            raise RuntimeError('No clusterHandle found connected to ' + self.name)

        root_grp = createNode('transform', name=self.shortName + '_clusterRoot', parent=handle_shape.parent.parent)
        cluster_grp = createNode('transform', name=self.shortName + '_cluster', parent=root_grp)

        cluster_grp.worldMatrix[0].connectTo(self.matrix, force=True)
        cluster_grp.matrix.connectTo(self.weightedMatrix, force=True)
        cluster_grp.parentInverseMatrix[0].connectTo(self.bindPreMatrix, force=True)
        cluster_grp.parentMatrix[0].connectTo(self.preMatrix, force=True)
        self.clusterXforms.breakConnections()
        cmds.delete(handle_shape.parent.name)
        return root_grp

    @property
    def handleShape(self):
        return self.clusterXforms.source.node


class SoftMod(WeightGeometryFilter):
    def __init__(self, MObject):
        super(SoftMod, self).__init__(MObject)

    def convertToRoot(self):
        """
        Adds a 'root' node as parent of the softMod. The root can be moved around to change from where the softMod
        starts its influence.
        :return: the new root transform of the softMod.
        """
        handle_shape = self.handleShape
        if not handle_shape:
            raise RuntimeError('No softModHandle found connected to ' + self.name)

        root_grp = createNode('transform', name=self.shortName + '_softModRoot', parent=handle_shape.parent.parent)
        softMod_grp = createNode('transform', name=self.shortName + '_softMod', parent=root_grp)
        falloffRadius = softMod_grp.addAttr('falloffRadius', attributeType='double', keyable=True, hasMinValue=True,
                                            minValue=0.0, defaultValue=self.falloffRadius.value)
        falloffRadius.connectTo(self.falloffRadius, force=True)

        softMod_grp.matrix.connectTo(self.weightedMatrix, force=True)
        softMod_grp.parentInverseMatrix[0].connectTo(self.bindPreMatrix, force=True)
        softMod_grp.parentMatrix[0].connectTo(self.preMatrix, force=True)
        softMod_grp.worldMatrix[0].connectTo(self.matrix, force=True)
        dmx = createNode('decomposeMatrix', name=self.shortName + '_DMX')
        softMod_grp.parentMatrix.connectTo(dmx.inputMatrix)
        dmx.outputTranslate.connectTo(self.falloffCenter, force=True)

        self.softModXforms.breakConnections()
        cmds.delete(handle_shape.parent.name)
        return root_grp

    @property
    def handleShape(self):
        return self.softModXforms.source.node


class SkinCluster(GeometryFilter):
    def __init__(self, MObject):
        super(SkinCluster, self).__init__(MObject)
        self._weights_attr = None
        self._MFnFnc = oma.MFnSkinCluster

    def influences(self):
        return yams(self.MFn.influenceObjects())

    def getVertexWeight(self, index, influence_indexes=None):
        if influence_indexes is None:
            influence_indexes = self.getInfluenceIndexes()
        weights = weightlist.WeightList()
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
        return weightlist.WeightList(self.MFn.getWeights(geo, components, influence))

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

        self.MFn.setWeights(geo, components, om.MIntArray([inf_index]), om.MDoubleArray(weights))

    @property
    def weights(self):
        weights = []
        # Getting the weights
        weights_array, num_influences = self.MFn.getWeights(*self.getDeformerSetGeoAndComponents())

        for i in range(0, len(weights_array), num_influences):
            weights.append(weightlist.WeightList(weights_array[i:i + num_influences]))
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
        self.MFn.setWeights(geo, components, influence_array, flat_weights)

    @property
    def dqWeights(self):
        return weightlist.WeightList(self.MFn.getBlendWeights(*self.getDeformerSetGeoAndComponents()))

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
        self.MFn.setBlendWeights(geo, components, data)

    def getPointsAffectedByInfluence(self, influence):
        """
        Returns the points affected by the given influence
        :param influence: DependNode
        :return: YamList of components
        """
        if influence in self.influences():
            influence = influence.MDagPath
        else:
            if not isinstance(influence, DagNode):
                raise TypeError("Influence should be of type 'DependNode' not '{}'".format(type(influence).__name__))
            raise RuntimeError("Influence not found in skin cluster")

        vtx_list = yams(self.MFn.getPointsAffectedByInfluence(influence)[0].getSelectionStrings())
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
                    if config.verbose:
                        cmds.warning("{} is connected and can't be reset".format(bpm))
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
        return self.MFn.indexForInfluenceObject(influence.MDagPath)

    def getInfluenceIndexes(self):
        return [self.indexForInfluenceObject(inf) for inf in self.influences()]

    @staticmethod
    def convertWeightsDataToPerVertex(data):
        num_vtx = len(data[0])
        range_influence = range(len(data))
        new_data = []
        for vtx in range(num_vtx):
            weights = weightlist.WeightList()
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
            weights = weightlist.WeightList()
            for vtx in range_vtx:
                weights.append(data[vtx][inf])
            new_data.append(weights)
        return new_data

    @property
    def data(self):
        return {'influences': self.influences().names,
                'weights': self.weights,
                'dqWeights': self.dqWeights,
                'skinningMethod': self.skinningMethod.value,
                'maxInfluences': self.maxInfluences.value,
                'normalizeWeights': self.normalizeWeights.value,
                'maintainMaxInfluences': self.maintainMaxInfluences.value,
                'weightDistribution': self.weightDistribution.value,
                }

    @data.setter
    def data(self, data):
        missing = []
        to_add = []
        influences = self.influences()
        for influence in data['influences']:
            if not checks.objExists(influence):
                missing.append(influence)
            elif influence not in influences:
                to_add.append(influence)
        if missing:
            raise RuntimeError('Influences not found in scene : {}'.format(missing))
        self.addInfluences(to_add)

        self.skinningMethod.value = data['skinningMethod']
        self.maxInfluences.value = data['maxInfluences']
        self.normalizeWeights.value = data['normalizeWeights']
        self.maintainMaxInfluences.value = data['maintainMaxInfluences']
        self.weightDistribution.value = data['weightDistribution']
        self.weights = data['weights']
        self.dqWeights = data['dqWeights']

    def addInfluence(self, influence):
        if hasattr(influence, 'isAYamNode'):
            influence = influence.name
        cmds.skinCluster(self.name, edit=True, addInfluence=influence, weight=0.0)

    def addInfluences(self, influences):
        for inf in influences:
            self.addInfluence(inf)


class BlendShape(WeightGeometryFilter):
    def __init__(self, MObject):
        super(BlendShape, self).__init__(MObject)
        self._targets = []
        self._targets_names = {}
        self.getTargets()

    def __getitem__(self, item):
        # TODO: add support for string, shape name, getting
        return self.getTarget(item)

    def getTargets(self):
        from . import attributes
        try:
            targets = cmds.listAttr(self.name + '.weight[:]')
        except ValueError:
            targets = []
        self._targets = YamList()
        self._targets.no_check = True
        self._targets_names = {}
        for index, target in enumerate(targets):
            bs_target = attributes.BlendShapeTarget(attributes.getMPlug(self.name + '.' + target), self, index)
            self._targets.append(bs_target)
            self._targets_names[target] = bs_target
        return self._targets

    def getTarget(self, target):
        try:
            if isinstance(target, int):
                return self._targets[target]
            elif isinstance(target, string_types):
                return self._targets_names[target]
            else:
                raise KeyError(target)
        except IndexError:
            self.getTargets()
            if isinstance(target, int):
                return self._targets[target]
            elif isinstance(target, string_types):
                return self._targets_names[target]
            else:
                raise KeyError(target)

    @property
    def weightsAttr(self):
        return self.inputTarget[0].baseWeights

    @property
    def data(self):
        targets = self.getTargets()
        return {'targets': self._targets_names.keys(),
                'weights': self.weights,
                'targetWeights': [target.weights for target in targets],
                }

    @data.setter
    def data(self, data):
        self.weights = data['weights']
        for i, target in enumerate(self.getTargets()):
            target.weights = data['targetWeights'][i]


class UVPin(DependNode):
    def __init__(self, MObject):
        super(UVPin, self).__init__(MObject)

    @staticmethod
    def createUVPin(mesh, name=None):
        mesh = yam(mesh)
        if isinstance(mesh, Transform) and mesh.shape:
            mesh = mesh.shape
        assert isinstance(mesh, SurfaceShape), "Target object must be a surface shape"

        if name is None:
            name = '{}_UVP'.format(mesh)
        pin = createNode('uvPin', name=name)
        pin.geometry = mesh
        return pin

    @property
    def geometry(self):
        connection = self.deformedGeometry.sourceConnection()
        if connection:
            return connection.node

    @geometry.setter
    def geometry(self, geo):
        geo = yam(geo)
        if isinstance(geo, Transform):
            geo = geo.shape
        if not isinstance(geo, SurfaceShape):
            raise ValueError("Geometry must be a SurfaceShape; got {} -> {}".format(geo, type(geo).__name__))

        if isinstance(geo, Mesh):
            out_attr = geo.worldMesh
        elif isinstance(geo, NurbsSurface):
            out_attr = geo.worldSpace
        else:
            raise NotImplementedError("Geometry '{}' of type '{}' not implemeted.".format(geo, type(geo).__name__))

        out_attr.connectTo(self.deformedGeometry, force=True)

    def connectTransform(self, target, coordinates, index=None):
        target = yam(target)
        assert isinstance(target, Transform), "Target must be a transform"
        assert len(coordinates) == 2, "Invalid UV coordinates given"

        if index is None:
            index = len(self.coordinate)
        self.coordinate[index].coordinateU.value = coordinates[0]
        self.coordinate[index].coordinateV.value = coordinates[1]
        mmx = createNode('multMatrix', name='{}_MMX'.format(self))
        dmx = createNode('decomposeMatrix', name='{}_DMX'.format(self))
        self.outputMatrix[index].connectTo(mmx.matrixIn[0])
        target.parentInverseMatrix.connectTo(mmx.matrixIn[1])
        mmx.matrixSum.connectTo(dmx.inputMatrix)
        dmx.outputTranslate.connectTo(target.translate, force=True)
        dmx.outputRotate.connectTo(target.rotate, force=True)
        dmx.outputScale.connectTo(target.scale, force=True)
        dmx.outputShear.connectTo(target.shear, force=True)

    def attachToClosestPoint(self, target):
        target = yam(target)
        assert isinstance(target, Transform), "Given target is not a transform"
        assert self.geometry, "No geometry connected to the uvPin"

        geo = self.geometry
        point = om.MPoint(target.getXform(t=True, ws=True))
        if isinstance(geo, Mesh):
            u, v, _ = geo.MFn.getUVAtPoint(point, space=om.MSpace.kWorld)
        elif isinstance(geo, NurbsSurface):
            point, _, _ = geo.MFn.closestPoint(point, space=om.MSpace.kObject)  # TODO : fails to do it world space
            u, v = geo.MFn.getParamAtPoint(point, True)
        else:
            raise NotImplementedError("Geometry '{}' of type '{}' not implemeted.".format(geo, type(geo).__name__))
        self.normalizedIsoParms.value = False
        self.connectTransform(target, [u, v])


class SupportedTypes(object):
    """
    Data of supported types of maya nodes.

    Any new node class should be added to the inheritance_tree dict to be able to get it from the yam method and to
    classes_MFn dict for faster type lookup. New node class should also be added to the classes_str dict to be
    compatible with getclass_cnds.

    classes_MFn syntax is : {om.MFn.kNodeMFnType: class,} where om.MFn.kNodeMFnType is a valid corresponding value from om.MFn
    classes_str syntax is : {'mayaType': class,} where 'mayaType' is the type you get when using cmds.nodeType('node').
    """

    # Inheritance tree for all defined classes and their MFn types relative to each others.
    inheritance_tree = {
        (DependNode, om.MFn.kDependencyNode): {
            (DagNode, om.MFn.kDagNode): {
                (Transform, om.MFn.kTransform): {},
                (Shape, om.MFn.kShape): {
                    (Mesh, om.MFn.kMesh): {},
                    (NurbsCurve, om.MFn.kNurbsCurve): {},
                    (NurbsSurface, om.MFn.kNurbsSurface): {},
                    (Lattice, om.MFn.kLattice): {},
                },
            },
            (GeometryFilter, om.MFn.kGeometryFilt): {
                (WeightGeometryFilter, om.MFn.kWeightGeometryFilt): {
                    (Cluster, om.MFn.kClusterFilter): {},
                    (BlendShape, om.MFn.kBlendShape): {},
                    (SoftMod, om.MFn.kSoftModFilter): {},
                },
                (SkinCluster, om.MFn.kSkinClusterFilter): {},
            },
            (UVPin, om.MFn.kUVPin): {},
        },
    }

    # dict of MFn id to assigned yam class
    classes_MFn = {
        om.MFn.kDependencyNode: DependNode,  # 4
        om.MFn.kDagNode: DagNode,  # 107
        om.MFn.kTransform: Transform,  # 110
        om.MFn.kJoint: Transform,  # 121
        om.MFn.kConstraint: Transform,  # 928
        om.MFn.kParentConstraint: Transform,  # 242
        om.MFn.kPointConstraint: Transform,  # 240
        om.MFn.kOrientConstraint: Transform,  # 239
        om.MFn.kScaleConstraint: Transform,  # 244
        om.MFn.kAimConstraint: Transform,  # 111
        om.MFn.kShape: Shape,  # 248
        om.MFn.kCluster: Shape,  # 251
        om.MFn.kSurface: SurfaceShape,  # 293
        om.MFn.kMesh: Mesh,  # 296
        om.MFn.kNurbsCurve: NurbsCurve,  # 267
        om.MFn.kNurbsSurface: NurbsSurface,  # 294
        om.MFn.kLattice: Lattice,  # 279
        om.MFn.kLocator: Shape,  # 281
        om.MFn.kGeometryFilt: GeometryFilter,  # 334
        om.MFn.kWeightGeometryFilt: WeightGeometryFilter,  # 346
        om.MFn.kClusterFilter: Cluster,  # 347
        om.MFn.kSkinClusterFilter: SkinCluster,  # 682
        om.MFn.kBlendShape: BlendShape,  # 336
        om.MFn.kCamera: Shape,  # 250
        om.MFn.kSoftModFilter: SoftMod,  # 348
        om.MFn.kUVPin: UVPin,  # 990; 986 in Maya 2020 ?! ¯\_(ツ)_/¯
    }
    # Some of the most commonly used DependNode classes for faster assigned class lookup
    supported_dependNodes = {
        om.MFn.kMatrixMult,  # 393
        om.MFn.kDecomposeMatrix,  # 1131
        om.MFn.kComposeMatrix,  # 1132
        om.MFn.kControllerTag,  # 1124
        om.MFn.kMultDoubleLinear,  # 770
        om.MFn.kUnitConversion,  # 526
        om.MFn.kPickMatrix,  # 1134
        om.MFn.kPlusMinusAverage,  # 458
        om.MFn.kBlendColors,  # 31
        om.MFn.kChoice,  # 36
        om.MFn.kCondition,  # 37
        om.MFn.kRemapValue,  # 933
        om.MFn.kReverse,  # 465
        om.MFn.kAddDoubleLinear,  # 5
        om.MFn.kMultiplyDivide,  # 445
        om.MFn.kDistanceBetween,  # 322
        om.MFn.kPluginDependNode,  # 456
    }
    for i in supported_dependNodes:
        classes_MFn[i] = DependNode

    # dict of maya nodeType to assigned yam class
    classes_str = {
        'dagNode': DagNode,
        'transform': Transform,
        'joint': Transform,
        'constraint': Transform,
        'parentConstraint': Transform,
        'pointConstraint': Transform,
        'orientConstraint': Transform,
        'scaleConstraint': Transform,
        'aimConstraint': Transform,
        'shape': Shape,
        'surfaceShape': SurfaceShape,
        'controlPoint': ControlPoint,
        'mesh': Mesh,
        'nurbsCurve': NurbsCurve,
        'nurbsSurface': NurbsSurface,
        'lattice': Lattice,
        'locator': Shape,
        'camera': Shape,
        'geometryFilter': GeometryFilter,
        'weightGeometryFilter': WeightGeometryFilter,
        'cluster': Cluster,
        'skinCluster': SkinCluster,
        'blendShape': BlendShape,
        'softMod': SoftMod,
        'uvPin': UVPin,
    }
    # Some of the most commonly used DependNode classes for faster assigned class lookup
    dependNodes_str = {
        'multMatrix',
        'decomposeMatrix',
        'composeMatrix',
        'controller',
        'multDoubleLinear',
        'unitConversion',
        'pickMatrix',
        'plusMinusAverage',
        'blendColors',
        'choice',
        'condition',
        'remapValue',
        'reverse',
        'addDoubleLinear',
        'multiplyDivide',
        'distanceBetween',
    }
    for i in dependNodes_str:
        classes_str[i] = DependNode

    # set of all assignable yam classes
    all_classes = {DependNode} | set(classes_str.values())

    # Warning in case a new class was added to the classes_MFn dict and not the classes_str dict
    diff = set(classes_MFn.values()) - all_classes
    if diff:
        cmds.warning("#" * 82)
        cmds.warning("There is a node class in classes_MFn dict that is not listed in classes_str : '{}'".format(diff))
        cmds.warning("#" * 82)


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
        return "{}({})".format(self.__class__.__name__, super(YamList, self).__repr__())

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
                    raise TypeError("YamList can only contain Yam objects. "
                                    "'{}' is '{}'".format(item, type(item).__name__))

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

    def MObjects(self):
        return [x.MObject for x in self]

    def getattrs(self, attr, call=False):
        if call:
            return [getattr(x, attr)() for x in self]
        return [getattr(x, attr) for x in self]

    def keepType(self, nodeType):
        """
        Remove all nodes that are not of the given type.
        :param node_type: str or list, e.g.: 'joint' or ['blendShape', 'skinCluster']
        """
        if not isinstance(nodeType, (tuple, list)):
            nodeType = [nodeType]
        if not all(isinstance(x, string_types) or hasattr(x, 'isAYamObject') for x in nodeType):
            raise TypeError("Expected : 'str' or Yam or 'list(str, Yam, ...)' but was given '{}'".format(nodeType))
        for i, item in reversed(list(enumerate(self))):
            inherited_types = item.inheritedTypes()
            for type_ in nodeType:
                if hasattr(type_, 'isAYamObject'):
                    if not isinstance(item, type_):
                        self.pop(i)
                else:
                    if type_ not in inherited_types:
                        self.pop(i)

    def popType(self, nodeType):
        """
        Removes all nodes of given type from current object and returns them in a new YamList.
        :param nodeType: str or list, e.g.: 'joint' or ['blendShape', 'skinCluster']
        :param inherited: bool, if True keep nodes whose type is inheriting from given type.
        :return: YamList of the removed nodes
        """
        popped = YamList()
        if not isinstance(nodeType, (tuple, list)):
            nodeType = [nodeType]
        if not all(isinstance(x, string_types) or hasattr(x, 'isAYamObject') for x in nodeType):
            raise TypeError("Expected : 'str' or Yam or 'list(str, Yam, ...)' but was given '{}'".format(nodeType))
        for i, item in reversed(list(enumerate(self))):
            inherited_types = item.inheritedTypes()
            for type_ in nodeType:
                if hasattr(type_, 'isAYamObject'):
                    if not isinstance(item, type_):
                        self.pop(i)
                else:
                    if type_ in inherited_types:
                        popped.append(self.pop(i))
        return popped

    def copy(self):
        return YamList(self, no_init_check=True)


class Yum(object):
    """
    Lazy way to initialize an existing Yam node.

    Saves 3 characters by not having to type yam('nodeName') and the hassle of having to reach ( and ' which are very
    far on the keyboard and need the shift modifier.
    This expects that Yum was initialized at import and stored in variable yum

    Initialize it on a variable (usually already done at import of yama module)
    e.g. :
    >>> yum = Yum()
    And get node :
    >>> yum.nodeName
    """
    def __init__(self):
        super(Yum, self).__init__()

    def __getattr__(self, item):
        return yam(item)


yum = Yum()
