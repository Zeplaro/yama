# encoding: utf8

"""
Contains all the class and functions for maya components.
"""

from abc import ABCMeta, abstractmethod
import sys
from maya import cmds
import maya.api.OpenMaya as om

# python 2 to 3 compatibility
_pyversion = sys.version_info[0]
if _pyversion == 3:
    basestring = str

from . import config, nodes


def getComponent(node, attr):
    """
    Returns the proper component object for the given node and component name and index.
    :param node: The node to get the component from.
    :param attr: The component name to get the component from.
    :return: The component object.
    """
    indices = []
    if '.' in attr:
        raise TypeError("component '{}' not in supported types".format(attr))

    split = []
    if '[' in attr:  # Checking if getting a specific index
        split = attr.split('[')
        attr = split.pop(0)

    if attr not in supported_types:
        raise TypeError("component '{}' not in supported types".format(attr))

    # Changing node to its shape if given a transform
    if isinstance(node, nodes.Transform):
        shape = node.shape
        if not shape:
            raise RuntimeError("node '{}' has no shape to get component on".format(node))
        node = shape

    if attr == 'cp':
        attr = shape_component.get(type(node), 'cp')

    # Getting api_type to get the proper class for the component
    api_type = component_shape_MFnid.get((attr, type(node)))
    if api_type is None:
        om_list = om.MSelectionList()
        om_list.add(node.name + '.' + attr + '[0]')
        dag, comp = om_list.getComponent(0)
        api_type = comp.apiTypeStr

    if api_type not in mFnid_component_class:
        raise TypeError("component '{}' of api type '{}' not in supported types".format(attr, api_type))

    comp_class = mFnid_component_class[api_type][1]
    component = comp_class(node, api_type)
    for index in split:
        index = index[:-1]  # Removing the closing ']'
        if index == '*':  # if using the maya wildcard symbol
            indices.append(slice(None))
        elif ':' in index:  # if using a slice to list multiple components
            slice_args = [int(x) if x else None for x in
                          index.split(':')]  # parsing the string into a proper slice
            indices.append(slice(*slice_args))
        else:
            indices.append(int(index))
    while indices:
        component = component[indices.pop(0)]
    return component


class Components(nodes.Yam):
    """
    Base class for components not indexed.
    """
    __metaclass__ = ABCMeta

    def __init__(self, node, apiType):
        super(Components, self).__init__()
        assert isinstance(node, nodes.ControlPoint), "component node should be of type 'ControlPoint', " \
                                                     "instead node type is '{}'".format(type(node).__name__)
        self.node = node
        self.api_type = apiType
        self.component_name = mFnid_component_class[apiType][0]
        self.component_class = mFnid_component_class[apiType][2]

    def __getitem__(self, item):
        if item == '*':
            item = slice(None)
        if isinstance(item, slice):
            # Maya component slice includes the stop index, e.g.: mesh.vtx[2:12] <-- includes vertex #12
            item = slice(item.start, item.stop+1, item.step)
            return ComponentsSlice(self.node, self, item)
        return self.index(item)

    def __len__(self):
        return len(self.node)

    def __str__(self):
        return self.name

    def __repr__(self):
        return "<class {}('{}', '{}')>".format(self.__class__.__name__, self.node.name, self.component_name)

    @abstractmethod
    def __iter__(self):
        pass

    def __eq__(self, other):
        if isinstance(other, Component):
            return self.__hash__() == hash(other)
        else:
            try:
                return self == nodes.yam(other)
            except Exception:
                return False

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return hash((self.node.uuid(), self.api_type))

    @property
    def name(self):
        return self.node + '.' + self.component_name + '[:]'

    def index(self, index, secondIndex=None, thirdIndex=None):
        return self.component_class(self.node, self, index, secondIndex, thirdIndex)

    def getPositions(self, ws=False):
        return [x.getPosition(ws=ws) for x in self]

    def setPositions(self, values, ws=False):
        for x, value in zip(self, values):
            x.setPosition(value, ws=ws)

    def type(self):
        return self.api_type

    def inheritedTypes(self):
        return ['component', self.api_type]


class SingleIndexed(Components):
    """
    Base class for components indexed by a single index.
    """
    def __init__(self, *args, **kwargs):
        super(SingleIndexed, self).__init__(*args, **kwargs)

    def __iter__(self):
        for i in range(len(self)):
            yield self.index(i)


class MeshVertices(SingleIndexed):
    """
    Class for mesh vertices.
    """
    def __init__(self, *args, **kwargs):
        super(MeshVertices, self).__init__(*args, **kwargs)
        if not config.undoable:
            self.setPositions = self.setPositionsOM

    def getPositions(self, ws=False):
        if ws:
            space = om.MSpace.kWorld
        else:
            space = om.MSpace.kObject
        return [[p.x, p.y, p.z] for p in self.node.mFnMesh.getPoints(space)]

    def setPositionsOM(self, values, ws=False):
        if ws:
            space = om.MSpace.kWorld
        else:
            space = om.MSpace.kObject
        mps = [om.MPoint(x) for x in values]
        self.node.mFnMesh.setPoints(mps, space)


class CurveCVs(SingleIndexed):
    """
    Class for curve cvs.
    """
    def __init__(self, *args, **kwargs):
        super(CurveCVs, self).__init__(*args, **kwargs)
        if not config.undoable:
            self.setPositions = self.setPositionsOM

    def getPositions(self, ws=False):
        if ws:
            space = om.MSpace.kWorld
        else:
            space = om.MSpace.kObject
        return [[p.x, p.y, p.z] for p in self.node.MFnNurbsCurve.cvPositions(space)]

    def setPositionsOM(self, values, ws=False):
        if ws:
            space = om.MSpace.kWorld
        else:
            space = om.MSpace.kObject
        mps = [om.MPoint(x) for x in values]
        self.node.mFnNurbsCurve.setCVPositions(mps, space)


class DoubleIndexed(Components):
    """
    Base class for components indexed by two indices.
    """
    def __init__(self, *args, **kwargs):
        super(DoubleIndexed, self).__init__(*args, **kwargs)

    def __iter__(self):
        for u in range(self.node.lenU()):
            for v in range(self.node.lenV()):
                yield self.index(u, v)


class TripleIndexed(Components):
    """
    Base class for components indexed by three indices.
    """
    def __init__(self, *args, **kwargs):
        super(TripleIndexed, self).__init__(*args, **kwargs)

    def __iter__(self):
        lenx, leny, lenz = self.node.lenXYZ()
        for x in range(lenx):
            for y in range(leny):
                for z in range(lenz):
                    yield self.index(x, y, z)


class Component(nodes.Yam):
    """
    Base class for indexed component.
    """
    def __init__(self, node, components, index, secondIndex=None, thirdIndex=None):
        super(Component, self).__init__()
        if isinstance(node, nodes.Transform):
            node = node.shape
        self.node = node
        self.components = components
        self.index = index
        self.second_index = secondIndex
        self.third_index = thirdIndex

    def __str__(self):
        return self.name

    def __repr__(self):
        if self.third_index is not None:
            return "<class {}('{}', '{}', {}, {}, {})>".format(self.__class__.__name__, self.node,
                                                               self.components.component_name, self.index,
                                                               self.second_index, self.third_index)
        elif self.second_index is not None:
            return "<class {}('{}', '{}', {}, {})>".format(self.__class__.__name__, self.node,
                                                           self.components.component_name, self.index,
                                                           self.second_index)
        else:
            return "<class {}('{}', '{}', {})>".format(self.__class__.__name__, self.node,
                                                       self.components.component_name, self.index)

    def __getitem__(self, item):
        """
        todo : work with slices
        """
        assert isinstance(item, int)
        if isinstance(self.components, SingleIndexed):
            raise IndexError("'{}' is a single index component and cannot get a second index".format(self))

        if self.second_index is None:
            return self.__class__(self.node, self.components, self.index, item)

        elif self.third_index is None:
            if isinstance(self.components, TripleIndexed):
                return self.__class__(self.node, self.components, self.index, self.second_index, item)
            else:
                raise IndexError("'{}' is a double index component and cannot get a third index".format(self))
        raise IndexError("'{}' cannot get four index")

    def __eq__(self, other):
        return self.__hash__() == hash(other)

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return hash((self.node.uuid(), self.type(), self.indices()))

    def exists(self):
        return cmds.objExists(self.name)

    @property
    def name(self):
        return self.node + '.' + self.attribute

    @property
    def attribute(self):
        attribute = self.components.component_name + '[' + str(self.index) + ']'
        if self.second_index is not None:
            attribute += '[' + str(self.second_index) + ']'
        if self.third_index is not None:
            attribute += '[' + str(self.third_index) + ']'
        return attribute

    def indices(self):
        return self.index, self.second_index, self.third_index

    def getPosition(self, ws=False):
        return cmds.xform(self.name, q=True, t=True, ws=ws, os=not ws)

    def setPosition(self, value, ws=False):
        cmds.xform(self.name, t=value, ws=ws, os=not ws)

    def type(self):
        return self.components.api_type

    def inheritedTypes(self):
        return ['component', self.components.api_type]


class MeshVertex(Component):
    def __init__(self, *args, **kwargs):
        super(MeshVertex, self).__init__(*args, **kwargs)
        if not config.undoable:
            self.setPosition = self.setPositionOM

    def getPosition(self, ws=False):
        if ws:
            space = om.MSpace.kWorld
        else:
            space = om.MSpace.kObject
        p = self.node.mFnMesh.getPoint(self.index, space)
        return [p.x, p.y, p.z]

    def setPositionOM(self, value, ws=False):
        if ws:
            space = om.MSpace.kWorld
        else:
            space = om.MSpace.kObject
        point = om.MPoint(value)
        self.node.mFnMesh.setPoint(self.index, point, space)


class CurveCV(Component):
    def __init__(self, *args, **kwargs):
        super(CurveCV, self).__init__(*args, **kwargs)
        if not config.undoable:
            self.setPosition = self.setPositionOM

    def getPosition(self, ws=False):
        if ws:
            space = om.MSpace.kWorld
        else:
            space = om.MSpace.kObject
        p = self.node.mFnNurbsCurve.cvPosition(self.index, space)
        return [p.x, p.y, p.z]

    def setPositionOM(self, value, ws=False):
        if ws:
            space = om.MSpace.kWorld
        else:
            space = om.MSpace.kObject
        point = om.MPoint(*value)
        self.node.mFnNurbsCurve.setCVPosition(self.index, point, space)


class ComponentsSlice(nodes.Yam):
    """
    A slice object to work with maya slices.
    Warning : ComponentsSlice does contain the last index of the slice unlike in a Python slice.
    """
    def __init__(self, node, components, components_slice):
        super(ComponentsSlice, self).__init__()
        self.node = node
        self.components = components
        self.slice = components_slice
        if components_slice.step is not None:
            self._indices = tuple(range(components_slice.start, components_slice.stop, components_slice.step))
        else:
            self._indices = tuple(range(components_slice.start, components_slice.stop))

    def __str__(self):
        return self.name

    def __repr__(self):
        return "<class {}('{}', '{}', {})>".format(self.__class__.__name__, self.node, self.components.component_name,
                                                   self.slice)

    def __getitem__(self, item):
        if isinstance(item, slice):
            raise RuntimeError("cannot slice a ComponentsSlice object")
        return self.components.index(self._indices[item])

    def __len__(self):
        return len(self._indices)

    def __iter__(self):
        for i in self._indices:
            yield self.components.index(i)

    def __eq__(self, other):
        if isinstance(other, ComponentsSlice):
            return self._indices == other.indices
        return False

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return hash((self.node.uuid(), self.components.api_type, self._indices))

    @property
    def name(self):
        start_stop = [str(s) if s is not None else '' for s in (self.slice.start, self.slice.stop - 1)]
        return self.node + '.' + self.components.component_name + '[' + ':'.join(start_stop) + ']'

    @property
    def index(self):
        return self.slice

    def indices(self):
        return self._indices

    def type(self):
        return self.components.api_type

    def inheritedTypes(self):
        return ['component', self.components.api_type]

    def getPositions(self, ws=False):
        return [x.getPosition(ws=ws) for x in self]

    def setPositions(self, values, ws=False):
        for x, value in zip(self, values):
            x.setPosition(value, ws=ws)

    def getPosition(self, ws=False):
        return self.getPositions(ws=ws)

    def setPosition(self, value, ws=False):
        self.setPositions(value, ws=ws)


# Removed 'v' because rarely used and similar to short name for 'visibility'
supported_types = {'cv', 'e', 'ep', 'f', 'map', 'pt', 'sf', 'u', '#v', 'vtx', 'vtxFace', 'cp', }

mFnid_component_class = {'kCurveCVComponent': ('cv', CurveCVs, CurveCV),  # 533
                         'kCurveEPComponent': ('ep', SingleIndexed, Component),  # 534
                         'kCurveParamComponent': ('u', SingleIndexed, Component),  # 536
                         'kIsoparmComponent': ('v', DoubleIndexed, Component),  # 537
                         'kSurfaceCVComponent': ('cv', DoubleIndexed, Component),  # 539
                         'kLatticeComponent': ('pt', TripleIndexed, Component),  # 543
                         'kMeshEdgeComponent': ('e', SingleIndexed, Component),  # 548
                         'kMeshPolygonComponent': ('f', SingleIndexed, Component),  # 549
                         'kMeshVertComponent': ('vtx', MeshVertices, MeshVertex),  # 551
                         'kCharacterMappingData': ('vtxFace', SingleIndexed, Component),  # 741
                         'kSurfaceFaceComponent': ('sf', DoubleIndexed, Component),  # 774
                         'kMeshMapComponent': ('map', SingleIndexed, Component),  # 813
                         }

component_shape_MFnid = {('cv', nodes.NurbsCurve): 'kCurveCVComponent',
                         ('cv', nodes.NurbsSurface): 'kSurfaceCVComponent',
                         ('e', nodes.Mesh): 'kMeshEdgeComponent',
                         ('ep', nodes.NurbsCurve): 'kCurveEPComponent',
                         ('f', nodes.Mesh): 'kMeshPolygonComponent',
                         ('map', nodes.Mesh): 'kMeshMapComponent',
                         ('pt', nodes.Lattice): 'kLatticeComponent',
                         ('sf', nodes.NurbsSurface): 'kSurfaceFaceComponent',
                         ('u', nodes.NurbsCurve): 'kCurveParamComponent',
                         ('u', nodes.NurbsSurface): 'kIsoparmComponent',
                         ('v', nodes.NurbsSurface): 'kIsoparmComponent',
                         ('vtx', nodes.Mesh): 'kMeshVertComponent',
                         ('vtxFace', nodes.Mesh): 'kCharacterMappingData',
                         }

shape_component = {nodes.Mesh: 'vtx',
                   nodes.NurbsCurve: 'cv',
                   nodes.NurbsSurface: 'cv',
                   nodes.Lattice: 'pt',
                   }
