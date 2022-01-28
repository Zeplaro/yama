# encoding: utf8

"""
Contains all the class and functions for maya attributes.
"""

import sys
from maya import cmds
import maya.api.OpenMaya as om
from . import config, nodes, weightsdict

# python 2 to 3 compatibility
_pyversion = sys.version_info[0]
if _pyversion == 3:
    basestring = str


def getAttribute(node, attr):
    """
    Gets the given attribute from the given node.
    :param node: DependNode
    :param attr: str or OpenMaya.MPlug
    :return: Attribute
    """
    if isinstance(attr, basestring):
        attr = getMPlug(node + '.' + attr)
    assert isinstance(attr, om.MPlug), "'str' or 'OpenMaya.MPlug' expected, got '{}'".format(type(attr).__name__)
    return Attribute(node, attr)


def getMPlug(attr):
    om_list = om.MSelectionList()
    try:
        om_list.add(attr)
    except RuntimeError as e:
        raise AttributeError("Attribute '{}' does not exist".format(attr))

    try:
        mPlug = om_list.getPlug(0)  # Fails to get plug on some compound attributes
    except TypeError:
        mObject = om_list.getDependNode(0)
        mfn = om.MFnDependencyNode(mObject)
        attrs = attr.split('.')[1:]
        data = []
        for attr in attrs:
            index = None
            if '[' in attr:
                attr, index = attr.split('[')
                index = int(index[:-1])
            data.append((attr, index))
        mPlug = mfn.findPlug(data[-1][0], True)
        for attr, index in data:
            sub_plug = mfn.findPlug(attr, True).attribute()
            if index is not None:
                mPlug.selectAncestorLogicalIndex(index, sub_plug)
    return mPlug


class Attribute(nodes.Yam):
    """
    A class for handling a node attribute and sub-attributes.
    """

    def __init__(self, node, mPlug):
        """
        :param node (Depend): the node of the attribute attr.
        :param attr (OpenMaya.MPlug):
        """
        super(Attribute, self).__init__()
        assert isinstance(node, nodes.DependNode)
        assert isinstance(mPlug, om.MPlug)
        self.node = node
        self.mPlug = mPlug

    def __str__(self):
        return self.name

    def __repr__(self):
        return "<class {}('{}.{}')>".format(self.__class__.__name__, self.node, self.attribute)

    def __getattr__(self, item):
        """
        Gets sub attributes of self.
        :param item (str): the sub-attribute name.
        :return: Attribute object.
        """
        return self.attr(item)

    def __getitem__(self, item):
        """
        Gets the element of the array attribute at the given index.
        Returns a list of attribute if given a slice.
        """
        if item == '*':
            item = slice(None)
        if isinstance(item, slice):
            return nodes.YamList(Attribute(self.node, self.mPlug.selectAncestorLogicalIndex(i))
                                 for i in range(len(self))[item])

        try:
            return Attribute(self.node, self.mPlug.selectAncestorLogicalIndex(item))
        except RuntimeError:
            raise RuntimeError("'{}' is not an array attribute and cannot use __getitem__".format(self))

    def __add__(self, other):
        """
        Using self.name for + operator.
        :return: str
        """
        return self.name + other

    def __radd__(self, other):
        """
        Using self.name for reverse + operator.
        :return: str
        """
        return other + self.name

    def __contains__(self, item):
        """
        Using self.attribute for 'in' operator.
        :return: str
        """
        return self.attribute.__contains__(item)

    def __rshift__(self, other):
        """
        Using the >> operator to connect self to the other attribute.
        :return: None
        """
        self.connectTo(other)

    def __lshift__(self, other):
        """
        Using the << operator to connect the other attribute to self.
        :return: None
        """
        self.connectFrom(other)

    def __floordiv__(self, other):
        """
        Using the // operator to disconnect self from the other attribute.
        :return: None
        """
        self.disconnect(other)

    def __len__(self):
        return self.mPlug.numElements()

    def __bool__(self):
        """
        Needed for Truth testing since __len__ is defined but does not work on non array attributes.
        :return: True
        """
        return True

    def __nonzero__(self):
        return self.__bool__()

    def __iter__(self):
        if self.mPlug.isArray:
            for i in range(len(self)):
                yield self.node.attr(self.mPlug.selectAncestorLogicalIndex(i))
        else:
            raise TypeError("'{}' is not iterable".format(self))

    def __eq__(self, other):
        if hasattr(other, 'mPlug'):
            return self.mPlug == other.mPlug
        else:
            try:
                return self.mPlug == nodes.yam(other).mPlug
            except Exception:
                return False

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return hash((self.node.uuid(), self.attribute))

    @property
    def name(self):
        """
        The full node.attribute name.
        :return: str
        """
        return self.mPlug.name()

    def attr(self, attr):
        """
        Gets a children attribute
        :param attr: str
        :return: Attribute object
        """
        return getAttribute(self.node, self.attribute + '.' + attr)

    @property
    def attribute(self):
        return self.mPlug.partialName(useLongNames=True, includeInstancedIndices=True)

    @attribute.setter
    def attribute(self, newName):
        cmds.renameAttr(self.name, newName)

    @property
    def value(self):
        """
        Gets the maya value.
        """
        return getAttr(self)

    @value.setter
    def value(self, value):
        """
        Sets the maya value.
        """
        setAttr(self, value)

    def exists(self):
        return cmds.objExists(self.name)

    @property
    def index(self):
        return self.mPlug.logocalIndex()

    @property
    def parent(self):
        if self.mPlug.isElement:
            return Attribute(self.node, self.mPlug.array())
        else:
            return Attribute(self.node, self.mPlug.parent())

    def settable(self):
        """
        Gets if the attribute is settable if it's not locked and either not connected, or has only keyframed animation.
        Returns: bool
        """
        return cmds.getAttr(self.name, settable=True)

    def connectTo(self, attr, **kwargs):
        """
        Connect this attribute to the given attr.
        kwargs are passed on to cmds.connectAttr
        """
        if isinstance(attr, Attribute):
            attr = attr.name
        cmds.connectAttr(self.name, attr, **kwargs)

    def connectFrom(self, attr, **kwargs):
        """
        Connect the given attr to this attribute.
        kwargs are passed on to cmds.connectAttr
        """
        if isinstance(attr, Attribute):
            attr = attr.name
        cmds.connectAttr(attr, self.name, **kwargs)

    def disconnect(self, attr):
        """
        Disconnect the the connection between self (source) and attr (destination)
        :param attr: str or Attribute
        """
        if isinstance(attr, Attribute):
            attr = attr.name
        cmds.disconnectAttr(self.name, attr)

    def listConnections(self, **kwargs):
        if 'scn' not in kwargs and 'skipConversionNodes' not in kwargs:
            kwargs['skipConversionNodes'] = True
        if 'p' not in kwargs and 'plugs' not in kwargs:
            kwargs['plugs'] = True
        return nodes.yams(cmds.listConnections(self.name, **kwargs) or [])

    def sourceConnection(self, **kwargs):
        connection = self.listConnections(destination=False, **kwargs)
        if connection:
            return connection[0]

    def destinationConnections(self, **kwargs):
        return self.listConnections(source=False, **kwargs)

    def breakConnections(self, source=True, destination=False):
        if source:
            connection = self.sourceConnection()
            if connection:
                connection.disconnect(self)
        if destination:
            for c in self.destinationConnections():
                self.disconnect(c)

    def listAttr(self, **kwargs):
        return nodes.listAttr(self, **kwargs)

    def type(self):
        """
        Returns the type of data currently in the attribute.
        :return: str
        """
        return cmds.getAttr(self.name, type=True)

    @property
    def defaultValue(self):
        return cmds.addAttr(self.name, q=True, defaultValue=True)

    @defaultValue.setter
    def defaultValue(self, value):
        cmds.addAttr(self.name, e=True, defaultValue=value)

    @property
    def hasMinValue(self):
        return cmds.attributeQuery(self.attribute, node=self.node.name, minExists=True)

    @hasMinValue.setter
    def hasMinValue(self, value):
        """
        Maya can only toggle the minValue and cannot set it to a certain state, regardless of passing True or False,
        which implies the following way of setting it.
        """
        if not bool(value) == bool(self.hasMinValue):
            cmds.addAttr(self.name, e=True, hasMinValue=value)

    @property
    def minValue(self):
        return cmds.attributeQuery(self.attribute, node=self.node.name, minimum=True)[0]

    @minValue.setter
    def minValue(self, value):
        cmds.addAttr(self.name, e=True, minValue=value)

    @property
    def hasMaxValue(self):
        return cmds.attributeQuery(self.attribute, node=self.node.name, maxExists=True)

    @hasMaxValue.setter
    def hasMaxValue(self, value):
        """
        Maya can only toggle the maxValue and cannot set it to a certain state, regardless of passing True or False,
        which implies the following way of setting it.
        """
        if not bool(value) == bool(self.hasMaxValue):
            cmds.addAttr(self.name, e=True, hasMaxValue=value)

    @property
    def maxValue(self):
        return cmds.attributeQuery(self.attribute, node=self.node.name, maximum=True)[0]

    @maxValue.setter
    def maxValue(self, value):
        cmds.addAttr(self.name, e=True, maxValue=value)

    @property
    def locked(self):
        return cmds.getAttr(self.name, lock=True)

    @locked.setter
    def locked(self, value):
        cmds.setAttr(self.name, lock=value)

    @property
    def keyable(self):
        return cmds.getAttr(self.name, keyable=True)

    @keyable.setter
    def keyable(self, value):
        """
        When value is False, sets the attribute as channelBox (displayable).
        """
        cmds.setAttr(self.name, channelBox=True)
        cmds.setAttr(self.name, keyable=value)

    @property
    def channelBox(self):
        if not cmds.getAttr(self.name, keyable=True) and cmds.getAttr(self.name, channelBox=True):
            return True
        return False

    @channelBox.setter
    def channelBox(self, value):
        """
        When value is False, sets the attribute as hidden.
        """
        if value:
            cmds.setAttr(self.name, keyable=False)
            cmds.setAttr(self.name, channelBox=True)
        else:
            cmds.setAttr(self.name, keyable=False)
            cmds.setAttr(self.name, channelBox=False)

    @property
    def hidden(self):
        if cmds.getAttr(self.name, keyable=True) or cmds.getAttr(self.name, channelBox=True):
            return False
        return True

    @hidden.setter
    def hidden(self, value):
        """
        When value is False, sets the attribute as channelBox (displayable).
        """
        if value:
            cmds.setAttr(self.name, keyable=False)
            cmds.setAttr(self.name, channelBox=False)
        else:
            cmds.setAttr(self.name, keyable=False)
            cmds.setAttr(self.name, channelBox=True)

    @property
    def niceName(self):
        return cmds.attributeQuery(self.attribute, node=self.node, niceName=True)

    @niceName.setter
    def niceName(self, newName):
        if newName is None:
            newName = ''
        cmds.addAttr(self.name, e=True, niceName=newName)


class BlendshapeTarget(Attribute):
    def __init__(self, node, mPlug, index):
        super(BlendshapeTarget, self).__init__(node, mPlug)
        self._index = index

    @property
    def weightsAttr(self):
        return self.node.inputTarget[0].inputTargetGroup[self.index].targetWeights

    @property
    def index(self):
        return self._index

    @property
    def weights(self):
        weights = weightsdict.WeightsDict()
        weightsAttr = self.weightsAttr
        for i in range(len(self.node.geometry)):
            weights[i] = weightsAttr[i].value
        return weights

    @weights.setter
    def weights(self, weights):
        weightsAttr = self.weightsAttr
        for i, weight in weights.items():
            weightsAttr[i].value = weight


def getAttr(attr):
    if not isinstance(attr, Attribute):
        attr = nodes.yam(attr)

    try:
        return getMPlugValue(attr.mPlug)
    except Exception as e:
        print('## failed to get MPlug value: {}'.format(e))

    return cmds.getAttr(attr.name)


def setAttr(attr, value, **kwargs):
    if not isinstance(attr, Attribute):
        attr = nodes.yam(attr)

    if not config.undoable:
        try:
            setMPlugValue(attr.mPlug, value)
            return
        except Exception as e:
            print("## failed to set MPlug value: {}".format(e))

    type = attr.type()
    if type in ['double3', 'double2']:
        cmds.setAttr(attr.name, *value, type=type)
    elif type in ['matrix', 'string']:
        cmds.setAttr(attr.name, value, type=type)
    else:
        cmds.setAttr(attr.name, value, **kwargs)


def getMPlugValue(mPlug):
    assert isinstance(mPlug, om.MPlug), "'OpenMaya.MPlug' object expected, " \
                                        "instead got : '{}' of type '{}'".format(mPlug, type(mPlug).__name__)
    attr_type = mPlug.attribute().apiTypeStr
    if attr_type in ('kNumericAttribute', 'kDoubleLinearAttribute', ):
        return mPlug.asDouble()
    elif attr_type in ('kEnumAttribute', ):
        return mPlug.asInt()
    elif attr_type in ('kDistance', ):
        return mPlug.asMDistance().asUnits(om.MDistance.uiUnit())
    elif attr_type in ('kAngle', ):
        return mPlug.asMAngle().asUnits(om.MAngle.uiUnits())
    elif attr_type in ('kTypedAttribute', ):
        return mPlug.asString()
    elif attr_type in ('kTimeAttribute', ):
        return mPlug.asMTime().asUnits(om.MTime.uiUnits())
    elif attr_type in ('kAttribute2Double', 'kAttribute3Double', 'kAttribute4Double', ):
        values = []
        for child_index in range(mPlug.numChildren()):
            values.append(getMPlugValue(mPlug.child(child_index)))
        return values
    elif attr_type in ('kMatrixAttribute', 'kFloatMatrixAttribute', ):
        data_handle = mPlug.asMDataHandle()
        if attr_type == 'kMatrixAttribute':
            return data_handle.asMatrix()
        elif attr_type == 'kFloatMatrixAttribute':
            return data_handle.asFloatMatrix()
    else:
        raise TypeError("Attribute '{}' of type '{}' not supported".format(mPlug.name(), attr_type))


def setMPlugValue(mPlug, value):
    assert isinstance(mPlug, om.MPlug), "'OpenMaya.MPlug' object expected, instead got : " \
                                        "'{}' of type '{}'".format(mPlug, type(mPlug).__name__)
    attr_type = mPlug.attribute().apiTypeStr
    if attr_type in ('kNumericAttribute', 'kDoubleLinearAttribute', ):
        mPlug.setDouble(value)
    elif attr_type in ('kEnumAttribute', ):
        return mPlug.setInt(value)
    elif attr_type in ('kDistance', ):
        mPlug.setMDistance(om.MDistance(value, om.MDistance.uiUnit()))
    elif attr_type in ('kAngle', ):
        mPlug.setMAngle(om.MAngle(value, om.MAngle.uiUnits()))
    elif attr_type in ('kTypedAttribute', ):
        mPlug.setString(value)
    elif attr_type in ('kTimeAttribute', ):
        mPlug.setMTime(om.MTime(value, om.MTime.uiUnits()))
    elif attr_type in ('kAttribute2Double', 'kAttribute3Double', 'kAttribute4Double', ):
        for child_index in range(mPlug.numChildren()):
            setMPlugValue(mPlug.child(child_index, value[child_index]))
    elif attr_type in ('kMatrixAttribute', 'kFloatMatrixAttribute', ):
        data_handle = mPlug.asMDataHandle()
        if attr_type == 'kMatrixAttribute':
            data_handle.setMMatrix(value)
        elif attr_type == 'kFloatMatrixAttribute':
            data_handle.setMFloatMatrix(value)
        mPlug.setMDataHandle(data_handle)
    else:
        raise TypeError("Attribute '{}' of type '{}' not supported".format(mPlug.name(), attr_type))
