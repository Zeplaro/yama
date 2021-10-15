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


supported_components = {'cv',  # Nurbs control vertex
                        'cp',  # Nurbs control point, actually the same a cv
                        'ep',  # Nurbs edit point
                        'u',  # NurbsSurface u "edge"
                        'v',  # NurbsSurface v "edge"
                        'pt',  # Lattice point
                        'e',  # Mesh edge
                        'f',  # Mesh face
                        'vtx',  # Mesh vertex
                        'vtxFace',  # Mesh vertexFace point
                        'sf',  # NurbsSurface patch
                        'map',
                        }

comp_Mfn = {'single': om.MFnSingleIndexedComponent,
            'double': om.MFnDoubleIndexedComponent,
            'triple': om.MFnTripleIndexedComponent,
            }

comp_MFn_id = {533: ('cv', 'single'),  # kCurveCVComponent
               534: ('ep', 'single'),  # kCurveEPComponent
               536: ('u', 'single'),  # kCurveParamComponent
               537: ('v', 'double'),  # kIsoparmComponent
               539: ('cv', 'double'),  # kSurfaceCVComponent
               543: ('pt', 'triple'),  # kLatticeComponent
               548: ('e', 'single'),  # kMeshEdgeComponent
               549: ('f', 'single'),  # kMeshPolygonComponent
               551: ('vtx', 'single'),  # kMeshVertComponent
               741: ('vtxFace', 'double'),  # kCharacterMappingData
               774: ('sf', 'double'),  # kSurfaceFaceComponent
               813: ('map', 'single'),  # kInt64ArrayData
               }


class Component(nodes.Yam):
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
            raise AttributeError("'{}' cannot get more than three indexes")
        elif self.second_index is not None:
            return self.__class__(self.node, self.index, self.second_index, item)
        else:
            return self.__class__(self.node, self.index, item)

    def exists(self):
        return cmds.objExists(self.name)

    @property
    def name(self):
        name = '{}.{}[{}]'.format(self.node, self.type, self.index)
        if self.second_index is not None:
            name += '[{}]'.format(self.second_index)
        if self.third_index is not None:
            name += '[{}]'.format(self.third_index)
        return name

    def get_position(self, ws=False):
        return cmds.xform(self.name, q=True, t=True, ws=ws, os=not ws)

    def set_position(self, value, ws=False):
        cmds.xform(self.name, t=value, ws=ws, os=not ws)


class Components(nodes.Yam):
    def __init__(self, node, comp_type):
        assert isinstance(node, nodes.DependNode)
        self.node = node
        self.type = comp_type

    def __iter__(self):
        if isinstance(self.node, nodes.Transform):
            if self.node.shape:
                try:
                    length = len(self.node.shape)
                except TypeError:
                    raise NotImplementedError("Cannot iterate, "
                                              "len() not implemented on node shape '{}'".format(self.node.shape))
            else:
                raise AttributeError("'{}' has no shape to get the component from".format(self.type, self.node))

        elif isinstance(self.node, nodes.ControlPoint):
            try:
                length = len(self.node)
            except TypeError:
                raise NotImplementedError("Cannot iterate, node '{}' has no len()".format(self.node))

        else:
            raise NotImplementedError("Cannot iterate, node '{}' has no len()".format(self.node.shape))

        for i in range(length):
            yield self.index(i)

    def __getitem__(self, item):
        return self.index(item)

    def index(self, index):
        assert isinstance(index, int)
        return Component(self.node, self.type, index)
