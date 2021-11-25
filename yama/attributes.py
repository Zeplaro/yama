# encoding: utf8

"""
Contains all the class and functions for maya attributes.
"""

import sys
from maya import cmds
import maya.api.OpenMaya as om
import config
import nodes
import components

# python 2 to 3 compatibility
_pyversion = sys.version_info[0]
if _pyversion == 3:
    basestring = str


def getAttribute(node, attr):
    """
    todo
    :param node:
    :param attr:
    :return:
    """
    component = components.getComponent(node, attr)  # Trying to get component if one
    if component is not None:
        return component

    if attr.endswith(']'):  # Checking is index ArrayAttribute
        split = attr.split('[')
        index = split.pop(-1)[:-1]
        if index == '*':  # if using the maya wildcard symbol
            index = slice(None)
        elif ':' in index:  # if using a slice to list multiple components
            slice_args = [int(x) if x else None for x in
                          index.split(':')]  # parsing the string into a proper slice
            index = slice(*slice_args)
        else:
            index = int(index)
        attr = '['.join(split)
        return ArrayAttribute(node, attr, index)
    return Attribute(node, attr)


class Attribute(nodes.Yam):
    """
    A class for handling a node attribute and sub-attributes.
    """

    def __init__(self, node, attr):
        """
        :param parent (Depend/Attribute): the node or attribute parent to attr.
        :param attr (str):
        """
        super(Attribute, self).__init__()
        assert isinstance(node, nodes.DependNode)
        assert isinstance(attr, (basestring, Attribute))
        self.node = node
        self.attribute = attr
        self._mPlug = None

    def __str__(self):
        return self.name

    def __repr__(self):
        return "<class {}('{}', '{}') {}>".format(self.__class__.__name__, self.node, self.attribute, "Exists" if self.exists() else "Doesn't Exists")

    def __getattr__(self, item):
        """
        Gets sub attributes of self.
        :param item (str): the sub-attribute name.
        :return: Attribute object.
        """
        return self.attr(item)

    def __getitem__(self, item):
        """
        todo
        """
        if item == '*':
            item = slice(None)
        if isinstance(item, slice):
            return nodes.YamList(getAttribute(self.node, '{}[{}]'.format(self.attribute, i)) for i in range(len(self))[item])
        return getAttribute(self.node, '{}[{}]'.format(self.attribute, item))

    def __iter__(self):
        raise NotImplementedError("cannot iterate on '{}'".format(self.name))

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

    def __call__(self, *args, **kwargs):
        if not self.exists():
            raise ValueError("No object matches name: {}".format(self.name))
        raise TypeError("'{}' object is not callable".format(self.__class__.__name__))

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

    @property
    def mPlug(self):
        if self._mPlug is None:
            m_list = om.MSelectionList()
            m_list.add(self.name)
            self._mPlug = m_list.getPlug(0)
        return self._mPlug

    @property
    def name(self):
        """
        The full node.attribute name.
        :return: str
        """
        return self.node + '.' + self.attribute

    def attr(self, attr):
        """
        Gets a children attribute
        :param attr: str
        :return: Attribute object
        """
        return getAttribute(self.node, self.attribute + '.' + attr)

    @property
    def value(self):
        """
        Gets the maya value.
        """
        try:
            return getAttr(self)
        except:
            pass
        type = self.type()
        if type == 'double3':
            value = getAttr(self, type='double3')
        elif type == 'matrix':
            value = getAttr(self, type='matrix')
        elif type == 'double2':
            value = getAttr(self, type='double2')
        elif type == 'string':
            value = getAttr(self, type='string')
        else:
            value = getAttr(self)
        # checks if the values are in a list in a list as maya does sometimes
        if isinstance(value, list) and len(value) == 1:
            value = value[0]
        return value

    @value.setter
    def value(self, value):
        """
        Sets the maya value.
        """
        try:
            setAttr(self, value)
        except:
            pass
        type = self.type()
        if type == 'double3':
            setAttr(self.name, *value, type='double3')
        elif type == 'matrix':
            setAttr(self.name, value, type='matrix')
        elif type == 'double2':
            setAttr(self.name, *value, type='double2')
        elif type == 'string':
            setAttr(self.name, value, type='string')
        else:
            setAttr(self.name, value)

    def exists(self):
        return cmds.objExists(self.name)

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
        return cmds.attributeQuery(self.name, node=self.obj, minExists=True)

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
        return cmds.attributeQuery(self.attribute, node=self.obj, minimum=True)[0]

    @minValue.setter
    def minValue(self, value):
        cmds.addAttr(self.name, e=True, minValue=value)

    @property
    def hasMaxValue(self):
        return cmds.attributeQuery(self.attribute, node=self.obj, maxExists=True)

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
        return cmds.attributeQuery(self.attribute, node=self.obj, maximum=True)[0]

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


class ArrayAttribute(Attribute):
    """
    A sub-class to Attribute to handle attribute of type multi; for exemple a deformer weights attribute.
    """

    def __init__(self, node, attr, index):
        """
        :param parent (Attribute/ArrayAttribute): The parent attribute of this attribute; Needs to be of type Attribute
                                                  or ArrayAttribute.
        :param index: The index of this attribute
        """
        assert isinstance(node, nodes.DependNode) and isinstance(attr, basestring) and isinstance(index, int)
        super(ArrayAttribute, self).__init__(node, attr)
        self.attribute = attr + '[' + str(index) + ']'
        self.index = index
        self.parentAttr = attr

    def __repr__(self):
        return "<class {}('{}', '{}', {})>".format(self.__class__.__name__, self.node, self.parentAttr, self.index)

    @property
    def parent(self):
        return getAttribute(self.node, self.parentAttr)


def getAttr(attr, **kwargs):
    try:
        plug = getMPlug(attr)
        return getMPlugValue(plug)
    except Exception as e:
        print('failed to get plug or plug value: {}'.format(e))

    return cmds.getAttr(str(attr), **kwargs)


def setAttr(attr, value, **kwargs):
    if not config.undoable:
        try:
            setMPlugValue(getMPlug(attr), value)
            return
        except Exception as e:
            print("failed to get MPlug or set MPlug value: {}".format(e))

    cmds.setAttr(str(attr), value, **kwargs)


def getMPlug(plug):
    if isinstance(plug, Attribute):
        attrs = plug.attribute.split('.')
        node = plug.node
    else:
        attrs = plug.split('.')
        node = attrs.pop(0)
    data = []
    for attr in attrs:
        index = None
        if '[' in attr:
            attr, index = attr.split('[')
            index = int(index[:-1])
        data.append((attr, index))
    if not isinstance(node, nodes.DependNode):
        sel = om.MSelectionList()
        sel.add(node)
        mObject = sel.getDependNode(0)
        dep_node = om.MFnDependencyNode(mObject)
    else:
        dep_node = node.mFnDependencyNode
    plug = dep_node.findPlug(data[-1][0], True)
    for attr, index in data:
        sub_plug = dep_node.findPlug(attr, True).attribute()
        if index is not None:
            plug.selectAncestorLogicalIndex(index, sub_plug)
    return plug


def getMPlugValue(mPlug):
    attr_type = mPlug.attribute().apiTypeStr
    if attr_type in ('kNumericAttribute', ):
        return mPlug.asDouble()
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
            values.append(getMPlugValue(mPlug.chid(child_index)))
        return values
    elif attr_type in ('kMatrixAttribute', 'kFloatMatrixAttribute', ):
        data_handle = mPlug.MDataHandle()
        if attr_type == 'kMatrixAttribute':
            return data_handle.asMatrix()
        elif attr_type == 'kFloatMatrixAttribute':
            return data_handle.asFloatMatrix()


def setMPlugValue(mPlug, plug_value):
    attr_type = mPlug.attribute().apiTypeStr
    if attr_type in ('kNumericAttribute', ):
        mPlug.setDouble(plug_value)
    elif attr_type in ('kDistance', ):
        mPlug.setMDistance(om.MDistance(plug_value, om.MDistance.uiUnit()))
    elif attr_type in ('kAngle', ):
        mPlug.setMAngle(om.MAngle(plug_value, om.MAngle.uiUnits()))
    elif attr_type in ('kTypedAttribute', ):
        mPlug.setString(plug_value)
    elif attr_type in ('kTimeAttribute', ):
        mPlug.setMTime(om.MTime(plug_value, om.MTime.uiUnits()))
    elif attr_type in ('kAttribute2Double', 'kAttribute3Double', 'kAttribute4Double', ):
        for child_index in range(mPlug.numChildren()):
            setMPlugValue(mPlug.chid(child_index, plug_value[child_index]))
    elif attr_type in ('kMatrixAttribute', 'kFloatMatrixAttribute', ):
        data_handle = mPlug.MDataHandle()
        if attr_type == 'kMatrixAttribute':
            data_handle.setMMatrix(plug_value)
        elif attr_type == 'kFloatMatrixAttribute':
            data_handle.setMFloatMatrix(plug_value)
        mPlug.setMDataHandle(data_handle)
