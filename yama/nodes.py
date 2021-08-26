# encoding: utf8

__author__ = 'Robin Lavigne'
__spellchecking__ = 'Pranil Naicker'
__emotionalsupport__ = 'Emilie Jolin'


import maya.cmds as mc
import maya.mel as mel
import maya.api.OpenMaya as om
import maya.OpenMaya as om1
from math import sqrt

import weightsdict as wdt

try:
    basestring
except NameError:
    basestring = str


def createNode(*args, **kwargs):
    return yam(mc.createNode(*args, **kwargs))


def yam(node):
    """
    Handles all node class assignment to assign the proper class depending on the node type.
    todo : make it works when an attribute is given.

    examples :
    >> yam('skincluster42')
    SkinCluster('skincluster42')

    todo:
    >> yam('null0.translateX')
    Attribute('null0.translateX')
    """

    attr = None
    if isinstance(node, basestring):
        if '.' in node:  # checking if an attribute was given with the node
            split = node.split('.')
            node = split.pop(0)
            attr = '.'.join(split)
        mSelectionList = om.MSelectionList()
        try:
            mSelectionList.add(node)
        except RuntimeError:
            if mc.objExists(node):
                raise RuntimeError("more than one object called '{}'".format(node))
            raise RuntimeError("No '{}' object found in scene".format(node))
        mObject = mSelectionList.getDependNode(0)
        mfn = om.MFnDependencyNode(mObject)
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

    # checking if node type is a supported class, if not defaults to DependNode
    assigned_class = supported_classes.get(mfn.typeName)
    if not assigned_class:
        assigned_class = DependNode
        for node_type in mc.nodeType(node, i=True)[::-1]:
            if node_type in supported_classes:
                assigned_class = supported_classes[node_type]
                break
    if attr is not None:
        return assigned_class(mObject, mfn).attr(attr)
    return assigned_class(mObject, mfn)


def yams(nodes):
    return [yam(node) for node in nodes]


class YamNode(object):
    # todo
    pass


class DependNode(YamNode):
    def __init__(self, mObject, mFnDependencyNode):
        assert isinstance(mObject, om.MObject)
        self.mObject = mObject
        self._mObject1 = None
        self.mFnDependencyNode = mFnDependencyNode
        self._mDagPath = None

    def __repr__(self):
        return "{}('{}')".format(self.__class__.__name__, self.name)

    def __str__(self):
        return self.name

    def __getattr__(self, attr):
        return self.attr(attr)

    def __add__(self, other):
        return self.name.__add__(other)

    def __radd__(self, other):
        return other.__add__(self.name)

    # def __apiobject__(self):
    #     """
    #     This seems needed for reasons that I have not explored.
    #     Returns: OpenMaya 1.0 MObject
    #     """
    #     print('calling __apiobject__')
    #     return self.mObject1

    @property
    def mObject1(self):
        if self._mObject1 is None:
            mSelectionList = om1.MSelectionList()
            mSelectionList.add(self.name)
            mObject = om1.MObject()
            mSelectionList.getDependNode(0, mObject)
            self._mObject1 = mObject
        return self._mObject1

    @property
    def mDagPath(self):
        if self._mDagPath is None:
            self._mDagPath = om.MDagPath.getAPathTo(self.mObject)
        return self._mDagPath

    def rename(self, new_name):
        self.mFnDependencyNode.setName(new_name)

    @property
    def name(self):
        return self.mFnDependencyNode.name()

    @name.setter
    def name(self, value):
        self.rename(value)

    def attr(self, attr):
        import attributes
        reload(attributes)
        return attributes.get_attribute(self, attr)

    def listRelatives(self, *args, **kwargs):
        return yams(mc.listRelatives(self.name, *args, **kwargs) or [])

    def type(self):
        return self.mFnDependencyNode.typeName


class DagNode(DependNode):
    def __init__(self, mObject, mFnDependencyNode):
        super(DagNode, self).__init__(mObject, mFnDependencyNode)
        self._mFnDagNode = None

    @property
    def mFnDagNode(self):
        if self._mFnDagNode is None:
            self._mFnDagNode = om.MFnDagNode(self.mObject)
        return self._mFnDagNode

    @property
    def parent(self):
        return yam(self.mFnDagNode.parent(0))


class Transform(DagNode):
    def __init__(self, mObject, mFnDependencyNode):
        super(Transform, self).__init__(mObject, mFnDependencyNode)

    def children(self, noIntermediate=True, shapes=True):
        children = yams(self.mDagPath.child(x) for x in range(self.mDagPath.childCount()))
        if noIntermediate:
            children = [x for x in children if not x.mFnDagNode.isIntermediateObject]
        if not shapes:
            children = [x for x in children if not isinstance(x, Shape)]
        return children

    def shapes(self, noIntermediate=True):
        children = yams(self.mDagPath.child(x) for x in range(self.mDagPath.childCount()))
        children = [x for x in children if isinstance(x, Shape)]
        if noIntermediate:
            children = [x for x in children if not x.mFnDagNode.isIntermediateObject]
        return children

    @property
    def shape(self):
        shapes = self.shapes()
        return shapes[0] if shapes else None

    @property
    def worldTranslation(self):
        return mc.xform(self.name, q=True, ws=True, t=True)

    @worldTranslation.setter
    def worldTranslation(self, value):
        mc.xform(self.name, ws=True, t=value)

    @property
    def worldRotation(self):
        return mc.xform(self.name, q=True, ws=True, ro=True)

    @worldRotation.setter
    def worldRotation(self, value):
        mc.xform(self.name, ws=True, ro=value)

    @property
    def worldScale(self):
        return mc.xform(self.name, q=True, ws=True, s=True)

    @worldScale.setter
    def worldScale(self, value):
        mc.xform(self.name, ws=True, s=value)

    @property
    def rotatePivot(self):
        return mc.xform(self.name, q=True, os=True, rp=True)

    @rotatePivot.setter
    def rotatePivot(self, value):
        mc.xform(self.name, os=True, rp=value)

    @property
    def worldRotatePivot(self):
        return mc.xform(self.name, q=True, ws=True, rp=True)

    @worldRotatePivot.setter
    def worldRotatePivot(self, value):
        mc.xform(self.name, ws=True, rp=value)

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


class Mesh(Shape):
    def __init__(self, mObject, mFnDependencyNode):
        super(Mesh, self).__init__(mObject, mFnDependencyNode)
        self._mFnMesh = None

    def __len__(self):
        return self.mFnMesh.numVertices

    @property
    def mFnMesh(self):
        if self._mFnMesh is None:
            self._mFnMesh = om.MFnMesh(self.mObject)
        return self._mFnMesh

    def get_components(self):
        name = self.name
        return [name+'.vtx['+str(x)+']' for x in range(len(self))]

    def get_component_indexes(self):
        for i in range(len(self)):
            yield i


class NurbsCurve(Shape):
    def __init__(self, mObject, mFnDependencyNode):
        super(NurbsCurve, self).__init__(mObject, mFnDependencyNode)
        self._mFnNurbsCurve = None

    def __len__(self):
        return self.mFnNurbsCurve.numCVs

    @property
    def mFnNurbsCurve(self):
        if self._mFnNurbsCurve is None:
            self._mFnNurbsCurve = om.MFnNurbsCurve(self.mObject)
        return self._mFnNurbsCurve

    def get_components(self):
        name = self.name
        return [name+'.cv['+str(x)+']' for x in range(len(self))]

    def get_component_indexes(self):
        for i in range(len(self)):
            yield i

    @property
    def cps(self):
        cps = mc.ls('{}.cp[:]'.format(self.name), flatten=True)
        cps = [x.replace('.cv', '.cp') for x in cps]
        return cps

    @staticmethod
    def get_control_point_position(controls):
        return [mc.xform(x, q=True, os=True, t=True) for x in controls]

    @staticmethod
    def set_control_point_position(controls, positions):
        [mc.xform(control, os=True, t=position) for control in controls for position in positions]

    @property
    def arclen(self):
        return mc.arclen(self.name)

    @property
    def data(self):
        # todo: copied form old node work, needs cleanup
        data = {'name': self.name,
                'type': self.type,
                'spans': self.spans.value,
                'form': self.form.value,
                'degree': self.degree.value,
                'cps': self.get_control_point_position(self.cps),
                'knots': self.knots
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
            knots = list(range(nb_knots-(self.degree.value - 1) * 2))
            for i in range(self.degree.value - 1):
                knots = knots[:1] + knots
                knots += knots[-1:]
        else:
            knots = list(range(nb_knots-(self.degree.value - 1)))
            for i in range(self.degree.value - 1):
                knots.insert(0, knots[0]-1)

        if self.type == 'bezierCurve':
            knots = []
            for i in range(nb_knots/3):
                for j in range(3):
                    knots.append(i)
        knots = [float(x) for x in knots]
        return knots


class NurbsSurface(Shape):
    def __init__(self, mObject, mFnDependencyNode):
        super(NurbsSurface, self).__init__(mObject, mFnDependencyNode)


class Locator(Shape):
    def __init__(self, mObject, mFnDependencyNode):
        super(Locator, self).__init__(mObject, mFnDependencyNode)


class Lattice(Shape):
    def __init__(self, mObject, mFnDependencyNode):
        super(Lattice, self).__init__(mObject, mFnDependencyNode)


class GeometryFilter(DependNode):
    def __init__(self, mObject, mFnDependencyNode):
        super(GeometryFilter, self).__init__(mObject, mFnDependencyNode)

    @property
    def geometry(self):
        geo = mc.deformer(self.name, q=True, geometry=True)
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
        return self.weightList[0].weights[index]


class Cluster(WeightGeometryFilter):
    def __init__(self, mObject, mFnDependencyNode):
        super(Cluster, self).__init__(mObject, mFnDependencyNode)


class SkinCluster(GeometryFilter):
    def __init__(self, mObject, mFnDependencyNode):
        super(SkinCluster, self).__init__(mObject, mFnDependencyNode)
        self._weights_attr = None

    def influences(self):
        return yams(mc.skinCluster(self.name, q=True, inf=True)) or []

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
        for i, comp in enumerate(mc.ls('{}.weightList[*]'.format(self.name))):
            weight = self.blendWeights[i].value
            if weight:
                dq_weights[i] = weight
        return dq_weights

    @dq_weights.setter
    def dq_weights(self, data):
        data = wdt.WeightsDict(data)
        for vtx in data:
            self.blendWeights[vtx].value = data[vtx]
        for i, vtx in enumerate(mc.ls('{}.weightList[*]'.format(self))):
            if i not in data:
                self.blendWeights[i].value = 0

    def reskin(self):
        for inf in self.influences():
            conns = mc.listConnections(inf.worldMatrix, type='skinCluster', p=True)
            for conn in conns:
                bpm = conn.replace('matrix', 'bindPreMatrix')
                wim = inf.worldInverseMatrix.value
                if not mc.listConnections(bpm):
                    mc.setAttr(bpm, *wim, type='matrix')
                else:
                    print('{} is connected'.format(bpm))
        mc.skinCluster(self.name, e=True, rbm=True)

    @staticmethod
    def get_skinCluster(obj):
        skn = mel.eval('findRelatedSkinCluster ' + obj)
        return yam(skn) if skn else None


class BlendShape(GeometryFilter):
    def __init__(self, mObject, mFnDependencyNode):
        super(BlendShape, self).__init__(mObject, mFnDependencyNode)
        self._targets = []
        self._targets_names = {}
        self.get_targets()

    def get_targets(self):
        targets = mc.blendShape(self.name, q=True, target=True) or []
        self._targets = [BlendshapeTarget(self, n, i) for i, n in enumerate(targets)]
        self._targets_names = {target.name: target for target in self._targets}
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
        for c, _ in enumerate(self.geometry.get_components()):
            weights[c] = self.weights_attr(c).value
        return weights

    @weights.setter
    def weights(self, weights):
        for i, weight in weights.items():
            self.weights_attr(i).value = weight


class BlendshapeTarget(object):
    def __init__(self, node, name, index):
        self._name = name
        self._node = node
        self._index = index

    def __str__(self):
        return self._name

    def __repr__(self):
        return 'Target({}, {}, {})'.format(self._node, self._name, self._index)

    @property
    def name(self):
        return self._name

    @property
    def index(self):
        return self._index

    @property
    def node(self):
        return self._node

    def weights_attr(self, index):
        return self._node.inputTarget[0].inputTargetGroup[self._index].targetWeights[index]

    @property
    def weights(self):
        weights = wdt.WeightsDict()
        for c, _ in enumerate(self._node.geometry.get_components()):
            weights[c] = self.weights_attr(c).value
        return weights

    @weights.setter
    def weights(self, weights):
        for i, weight in weights.items():
            self.weights_attr(i).value = weight


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
                     'blendShape': BlendShape,
                     'transform': Transform,
                     'joint': Joint,
                     }
