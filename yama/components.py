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

from nodes import Yam, Transform, ControlPoint, YamList

single, double, triple = om.MFnSingleIndexedComponent, om.MFnDoubleIndexedComponent, om.MFnTripleIndexedComponent

supported_types = {'cv': single,
                   'e': single,
                   'ep': single,
                   'f': single,
                   'map': single,
                   'pt': triple,
                   'sf': double,
                   'u': single,
                   'v': double,
                   'vtx': single,
                   'vtxFace': double,
                   }

comp_MFn_id = {'kCurveCVComponent': 'cv',  # 533
               'kCurveEPComponent': 'ep',  # 534
               'kCurveParamComponent': 'u',  # 536
               'kIsoparmComponent': 'v',  # 537
               'kSurfaceCVComponent': 'cv',  # 539
               'kLatticeComponent': 'pt',  # 543
               'kMeshEdgeComponent': 'e',  # 548
               'kMeshPolygonComponent': 'f',  # 549
               'kMeshVertComponent': 'vtx',  # 551
               'kCharacterMappingData': 'vtxFace',  # 741
               'kSurfaceFaceComponent': 'sf',  # 774
               'kInt64ArrayData': 'map',  # 813
               }


def getComponent(node, attr):
    """
    todo
    :param node:
    :param attr:
    :return:
    """
    indices = []
    if '.' in attr:
        return

    split = []
    if '[' in attr:  # Cheking if getting a specific index
        split = attr.split('[')
        attr = split[0]

    if attr in supported_types or attr == 'cp':
        try:
            ls = om.MSelectionList()
            ls.add(node.name + '.' + attr + '[0]')
            dag, comp = ls.getComponent(0)
            api_type = comp.apiTypeStr
            if attr == 'cp':
                attr = comp_MFn_id.get(api_type, attr)
            if api_type in comp_MFn_id:
                component = Components(node, attr)
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
            # print("failed to get component '{}' on '{}': {}".format(attr, node, e))
            pass


class Component(Yam):
    """
    todo
    """

    def __init__(self, node, component_type, index, second_index=None, third_index=None):
        super(Component, self).__init__()
        self.node = node
        self.type = component_type
        self.index = index
        self.second_index = second_index
        self.third_index = third_index

    def __str__(self):
        return self.name

    def __repr__(self):
        if self.third_index is not None:
            return "<{}({}, {}, {}, {}, {})>".format(self.__class__.__name__, self.node.name, self.type, self.index,
                                                     self.second_index, self.third_index)
        elif self.second_index is not None:
            return "<{}({}, {}, {}, {})>".format(self.__class__.__name__, self.node.name, self.type, self.index,
                                                 self.second_index)
        else:
            return "<{}({}, {}, {})>".format(self.__class__.__name__, self.node.name, self.type, self.index)

    def __getitem__(self, item):
        """
        todo : work with slice
        :param item:
        :return:
        """
        assert isinstance(item, int)
        if self.third_index is not None:
            raise AttributeError("'{}' cannot get more than three indexes".format(self))
        elif self.second_index is not None:
            return self.__class__(self.node, self.type, self.index, self.second_index, item)
        else:
            return self.__class__(self.node, self.type, self.index, item)

    def __eq__(self, other):
        if self.name == str(other):
            return True
        return False

    def __ne__(self, other):
        return not self.__eq__(other)

    def exists(self):
        return cmds.objExists(self.name)

    @property
    def name(self):
        return self.node + '.' + self.attribute

    @property
    def attribute(self):
        attribute = '{}[{}]'.format(self.type, self.index)
        if self.second_index is not None:
            attribute += '[{}]'.format(self.second_index)
        if self.third_index is not None:
            attribute += '[{}]'.format(self.third_index)
        return attribute

    def getPosition(self, ws=False):
        return cmds.xform(self.name, q=True, t=True, ws=ws, os=not ws)

    def setPosition(self, value, ws=False):
        cmds.xform(self.name, t=value, ws=ws, os=not ws)


class Components(Yam):
    """
    todo
    """

    def __init__(self, node, comp_type):
        super(Components, self).__init__()
        if isinstance(node, Transform):
            node = node.shape
        assert isinstance(node, ControlPoint), "component node should be of type 'ControlPoint', " \
                                               "instead node type is '{}'".format(type(node).__name__)
        self.node = node
        self.type = comp_type

    def __iter__(self):
        if supported_types[self.type] == single:
            for i in range(len(self)):
                yield self.index(i)
        elif supported_types[self.type] == double:
            for u in range(self.node.lenU()):
                for v in range(self.node.lenV()):
                    yield self.index(u, v)
        else:
            lenx, leny, lenz = self.node.lenXYZ()
            for x in range(lenx):
                for y in range(leny):
                    for z in range(lenz):
                        yield self.index(x, y, z)

    def __getitem__(self, item):
        if item == '*':
            item = slice(None)
        if isinstance(item, slice):
            return YamList(self.index(i) for i in range(len(self.node))[item])
        return self.index(item)

    def __len__(self):
        return len(self.node)

    def index(self, index, second_index=None, third_index=None):
        return Component(self.node, self.type, index, second_index, third_index)
