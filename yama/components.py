# encoding: utf8

"""
Contains all the class and functions for maya components.
"""

import sys
from maya import cmds
import maya.api.OpenMaya as om

# python 2 to 3 compatibility
_pyversion = sys.version_info[0]
if _pyversion == 3:
    basestring = str

import config
import nodes


def getComponent(node, attr):
    """
    todo : docstring
    :param node:
    :param attr:
    :return:
    """
    indices = []
    if '.' in attr:
        return

    split = []
    if '[' in attr:  # Checking if getting a specific index
        split = attr.split('[')
        attr = split[0]

    if attr in supported_types:
        try:
            ls = om.MSelectionList()
            ls.add(node.name + '.' + attr + '[0]')
            dag, comp = ls.getComponent(0)
            api_type = comp.apiTypeStr
            if api_type in comp_MFn_id:
                comp_class, attr_name = comp_MFn_id[api_type]
                component = comp_class(node, attr_name)
                for i in split[1:]:
                    i = i[:-1]  # Removing the closing ']'
                    if i == '*':  # if using the maya wildcard symbol
                        indices.append(slice(None))
                    elif ':' in i:  # if using a slice to list multiple components
                        slice_args = [int(x) if x else None for x in
                                      i.split(':')]  # parsing the string into a proper slice
                        indices.append(slice(*slice_args))
                    else:
                        indices.append(int(i))
                while indices:
                    component = component[indices.pop(0)]
                return component
            raise TypeError("attr '{}' of api type '{}' not in supported types".format(attr, api_type))
        except (RuntimeError, TypeError) as e:
            print("failed to get component '{}' on '{}': {}".format(attr, node, e))
            raise e


class Components(nodes.Yam):
    """
    todo : docstring
    """
    def __init__(self, node, attribute_name):
        if type(self) is Components:
            raise TypeError("'{}' should not be directly instantiated".format(self.__class__.__name__))
        super(Components, self).__init__()
        if isinstance(node, nodes.Transform):
            node = node.shape
        assert isinstance(node, nodes.ControlPoint), "component node should be of type 'ControlPoint', " \
                                               "instead node type is '{}'".format(type(node).__name__)
        self.node = node
        self.attribute_name = attribute_name

    def __getitem__(self, item):
        if item == '*':
            item = slice(None)
        if isinstance(item, slice):
            return nodes.YamList(self.index(i) for i in range(len(self.node))[item])
        return self.index(item)

    def __len__(self):
        return len(self.node)

    def __str__(self):
        return self.name

    def __repr__(self):
        return "<class {}('{}', '{}')>".format(self.__class__.__name__, self.node.name, self.attribute_name)

    @property
    def name(self):
        return self.node + '.' + self.attribute_name

    def index(self, index, second_index=None, third_index=None):
        return supported_types[self.attribute_name](self.node, self, index, second_index, third_index)

    def getPositions(self, ws=False):
        return [x.getPosition(ws=ws) for x in self]

    def setPositions(self, values, ws=False):
        for x, value in zip(self, values):
            x.setPosition(value, ws=ws)


class SingleIndexed(Components):
    def __init__(self, *args, **kwargs):
        super(SingleIndexed, self).__init__(*args, **kwargs)

    def __iter__(self):
        for i in range(len(self)):
            yield self.index(i)


class DoubleIndexed(Components):
    def __init__(self, *args, **kwargs):
        super(DoubleIndexed, self).__init__(*args, **kwargs)

    def __iter__(self):
        for u in range(self.node.lenU()):
            for v in range(self.node.lenV()):
                yield self.index(u, v)


class TripleIndexed(Components):
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
    todo : docstring
    """

    def __init__(self, node, components, index, second_index=None, third_index=None):
        super(Component, self).__init__()
        if isinstance(node, nodes.Transform):
            node = node.shape
        self.node = node
        self.components = components
        self.index = index
        self.second_index = second_index
        self.third_index = third_index

    def __str__(self):
        return self.name

    def __repr__(self):
        if self.third_index is not None:
            return "<class {}('{}', '{}', {}, {}, {})>".format(self.__class__.__name__, self.node,
                                                               self.components.attribute_name, self.index,
                                                               self.second_index, self.third_index)
        elif self.second_index is not None:
            return "<class {}('{}', '{}', {}, {})>".format(self.__class__.__name__, self.node,
                                                           self.components.attribute_name, self.index, self.second_index)
        else:
            return "<class {}('{}', '{}', {})>".format(self.__class__.__name__, self.node,
                                                       self.components.attribute_name, self.index)

    def __getitem__(self, item):
        """
        todo : work with slice
        :param item:
        :return:
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

    def exists(self):
        return cmds.objExists(self.name)

    @property
    def name(self):
        return self.node + '.' + self.attribute

    @property
    def attribute(self):
        attribute = '{}[{}]'.format(self.components.attribute_name, self.index)
        if self.second_index is not None:
            attribute += '[{}]'.format(self.second_index)
        if self.third_index is not None:
            attribute += '[{}]'.format(self.third_index)
        return attribute

    def getPosition(self, ws=False):
        return cmds.xform(self.name, q=True, t=True, ws=ws, os=not ws)

    def setPosition(self, value, ws=False):
        cmds.xform(self.name, t=value, ws=ws, os=not ws)


class MeshVertex(Component):
    def __init__(self, *args, **kwargs):
        super(MeshVertex, self).__init__(*args, **kwargs)

    def getPosition(self, ws=False):
        if ws:
            space = om.MSpace.kWorld
        else:
            space = om.MSpace.kObject
        p = self.node.mFnMesh.getPoint(self.index, space)
        return [p.x, p.y, p.z]

    def setPosition(self, value, ws=False):
        if config.undoable:
            super(MeshVertex, self).setPosition(value, ws)
        else:
            if ws:
                space = om.MSpace.kWorld
            else:
                space = om.MSpace.kObject
            point = om.MPoint(*value)
            self.node.mFnMesh.setPoint(self.index, point, space)


class CurveCV(Component):
    def __init__(self, *args, **kwargs):
        super(CurveCV, self).__init__(*args, **kwargs)

    def getPosition(self, ws=False):
        if ws:
            space = om.MSpace.kWorld
        else:
            space = om.MSpace.kObject
        p = self.node.mFnNurbsCurve.cvPosition(self.index, space)
        return [p.x, p.y, p.z]

    def setPosition(self, value, ws=False):
        if config.undoable:
            super(CurveCV, self).setPosition(value, ws)
        else:
            if ws:
                space = om.MSpace.kWorld
            else:
                space = om.MSpace.kObject
            point = om.MPoint(*value)
            self.node.mFnNurbsCurve.setCVPosition(self.index, point, space)


supported_types = {'cv': Component,
                   'e': Component,
                   'ep': Component,
                   'f': Component,
                   'map': Component,
                   'pt': Component,
                   'sf': Component,
                   'u': Component,
                   'v': Component,
                   'vtx': MeshVertex,
                   'vtxFace': Component,
                   'cp': Component,
                   }

comp_MFn_id = {'kCurveCVComponent': (SingleIndexed, 'cv'),  # 533
               'kCurveEPComponent': (SingleIndexed, 'ep'),  # 534
               'kCurveParamComponent': (SingleIndexed, 'u'),  # 536
               'kIsoparmComponent': (DoubleIndexed, 'v'),  # 537
               'kSurfaceCVComponent': (DoubleIndexed, 'cv'),  # 539
               'kLatticeComponent': (TripleIndexed, 'pt'),  # 543
               'kMeshEdgeComponent': (SingleIndexed, 'e'),  # 548
               'kMeshPolygonComponent': (SingleIndexed, 'f'),  # 549
               'kMeshVertComponent': (SingleIndexed, 'vtx'),  # 551
               'kCharacterMappingData': (SingleIndexed, 'vtxFace'),  # 741
               'kSurfaceFaceComponent': (DoubleIndexed, 'sf'),  # 774
               'kInt64ArrayData': (SingleIndexed, 'map'),  # 813
               }
