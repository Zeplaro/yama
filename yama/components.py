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

import nodes


comp_Mfn = {'single': om.MFnSingleIndexedComponent,
            'double': om.MFnDoubleIndexedComponent,
            'triple': om.MFnTripleIndexedComponent,
            }

comp_MFn_id = {'kCurveCVComponent': ('cv', 'single'),  # 533
               'kCurveEPComponent': ('ep', 'single'),  # 534
               'kCurveParamComponent': ('u', 'single'),  # 536
               'kIsoparmComponent': ('v', 'double'),  # 537
               'kSurfaceCVComponent': ('cv', 'double'),  # 539
               'kLatticeComponent': ('pt', 'triple'),  # 543
               'kMeshEdgeComponent': ('e', 'single'),  # 548
               'kMeshPolygonComponent': ('f', 'single'),  # 549
               'kMeshVertComponent': ('vtx', 'single'),  # 551
               'kCharacterMappingData': ('vtxFace', 'double'),  # 741
               'kSurfaceFaceComponent': ('sf', 'double'),  # 774
               'kInt64ArrayData': ('map', 'single'),  # 813
               }

supported_types = {x for x, _ in comp_MFn_id.values()}


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

    if attr in supported_types:
        try:
            ls = om.MSelectionList()
            ls.add(node.name + '.' + attr + '[0]')
            dag, comp = ls.getComponent(0)
            api_type = comp.apiTypeStr
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
        except (RuntimeError, TypeError) as e:
            print('failed to get component: {}'.format(e))


class Component(nodes.Yam):
    """
    todo
    """

    def __init__(self, node, component_type, index, second_index=None, third_index=None):
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


class Components(nodes.Yam):
    """
    todo
    """

    def __init__(self, node, comp_type):
        assert isinstance(node, (nodes.ControlPoint, nodes.Transform))
        self.node = node
        self.type = comp_type

    def __iter__(self):
        """
        todo: make work with double and triple indexed components
        """
        for i in range(len(self)):
            yield self.index(i)

    def __getitem__(self, item):
        if item == '*':
            item = slice(None)
        if isinstance(item, slice):
            return nodes.YamList(self.index(i) for i in range(len(self.node))[item])
        return self.index(item)

    def __len__(self):
        return len(self.node)

    def index(self, index):
        assert isinstance(index, int)
        return Component(self.node, self.type, index)
