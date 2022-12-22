# encoding: utf8

"""
Contains all the class and functions for maya attributes.
"""

from maya import cmds
import maya.api.OpenMaya as om
import maya.OpenMaya as om1
from . import config, nodes, weightslist, checks


def getAttribute(node, attr):
    """
    Gets the given attribute from the given node.
    :param node: DependNode
    :param attr: str
    :return: Attribute
    """
    if '.' in attr:
        attrs = attr.split('.')
        for attr in attrs:
            node = node.attr(attr)
        return node
    else:
        MPlug = getMPlug(node.name + '.' + attr)
        return Attribute(MPlug, node)


def getMPlug(attr):
    om_list = om.MSelectionList()
    try:
        om_list.add(attr)
    except RuntimeError:
        raise checks.ObjExistsError("Attribute '{}' does not exist".format(attr))
    try:
        MPlug = om_list.getPlug(0)
    except TypeError as e:
        raise TypeError("Failed to get plug : '{}'; {}".format(attr, e))
    return MPlug


class Attribute(nodes.Yam):
    """
    A class for handling a node attribute and sub-attributes.
    """

    def __init__(self, MPlug, node=None):
        """
        :param node (Depend): the node of the attribute attr.
        :param attr (OpenMaya.MPlug):
        """
        super(Attribute, self).__init__()
        assert isinstance(MPlug, om.MPlug), ("MPlug arg should be of type OpenMaya.MPlug not : '{}'".format(MPlug.__class__.__name__))
        if node:
            assert isinstance(node, nodes.DependNode)
        else:
            node = nodes.yam(MPlug.node())
        self.node = node
        self.MPlug = MPlug
        self._MPlug1 = None
        self._attributes = {}
        self._children_generated = False

    def __str__(self):
        return self.name

    def __repr__(self):
        return "{}('{}.{}')".format(self.__class__.__name__, self.node, self.attribute)

    def __getattr__(self, attr):
        """
        Gets sub attributes of self.
        :param attr (str): the sub-attribute name.
        :return: Attribute object.
        """
        return self.attr(attr)

    def __getitem__(self, item):
        """
        Gets the element of the array attribute at the given index.
        Returns a list of attribute if given a slice.
        """
        if item == '*':
            item = slice(None)
        if item.__class__ == slice:  # Not using isinstance() for efficiency
            return nodes.YamList(self[i] for i in range(len(self))[item])

        try:
            if item not in self._attributes:
                MPlug = self.MPlug.selectAncestorLogicalIndex(item)
                self._attributes[item] = Attribute(MPlug, self.node)
            return self._attributes[item]
        except RuntimeError:
            raise TypeError("'{}' is not an array attribute and cannot use __getitem__".format(self))

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
        return self.MPlug.numElements()

    def __bool__(self):
        """
        Needed for Truth testing since __len__ is defined but does not work on non array attributes.
        :return: True
        """
        return True

    def __nonzero__(self):
        return self.__bool__()

    def __iter__(self):
        if self.MPlug.isArray:
            for i in range(len(self)):
                yield self.node.attr(self.MPlug.selectAncestorLogicalIndex(i))
        else:
            raise TypeError("'{}' is not iterable".format(self))

    def __eq__(self, other):
        if hasattr(other, 'MPlug'):
            return self.MPlug == other.MPlug
        else:
            try:
                return self.MPlug == nodes.yam(other).MPlug
            except Exception:
                return False

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return hash((self.node.uuid(), self.attribute))

    @property
    def MPlug1(self):
        """
        Gets the associated api 1.0 MPlug
        :return: api 1.0 MPlug
        """
        if self._MPlug1 is None:
            l = om1.MSelectionList()
            l.add(self.name)
            self._MPlug1 = om1.MPlug()
            l.getPlug(0, self._MPlug1)
        return self._MPlug1

    @property
    def name(self):
        """
        The full node.attribute name.
        Not using self.MPlug.name() because, unlike node.name, it does not returned the node's  minimum string
        representation which will uniquely identify the path, in case the node has a non unique name.
        :return: str
        """
        return self.node.name + '.' + self.attribute

    def attr(self, attr):
        """
        Gets a children attribute
        :param attr: str
        :return: Attribute object
        """
        if attr in self._attributes:
            return self._attributes[attr]
        elif self.MPlug.isArray:
            return self[0].attr(attr)
        elif not self._children_generated:
            self.getChildren()
            return self.attr(attr)
        else:
            cmds.warning("Attribute was not generated with getChildren")
            MPlug = getMPlug(self.node.name + '.' + attr)
            attribute = Attribute(MPlug, self.node)
            cmds.warning("Attribute was not generated with getChildren but still exists ?!")
            self._attributes[attr] = attribute
            return self.attr(attr)

    def getChildren(self):
        if not self.MPlug.isCompound:
            raise AttributeError("'{}' is not an compound attribute and has no children attribute".format(self))
        for index in range(self.MPlug.numChildren()):
            child = self.MPlug.child(index)
            attribute = Attribute(child, self.node)
            name = child.partialName(useLongNames=True, includeInstancedIndices=True).split('.')[-1]
            short_name = child.partialName(includeInstancedIndices=True).split('.')[-1]
            self._attributes[name] = attribute
            self._attributes[short_name] = attribute
        self._children_generated = True

    @property
    def attribute(self):
        return self.MPlug.partialName(useLongNames=True, includeInstancedIndices=True)

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

    def get(self):
        """
        Alternative way to get the maya value.
        """
        return getAttr(self)

    def set(self, value):
        """
        Alternative way to set the maya value.
        """
        setAttr(self, value)

    def exists(self):
        """
        Checks if the attribute exists.
        :return: bool
        """
        return cmds.objExists(self.name)

    @property
    def index(self):
        return self.MPlug.logicalIndex()

    @property
    def parent(self):
        """
        The parent attribute.
        :return: Attribute object
        """
        if self.MPlug.isElement:
            return Attribute(self.MPlug.array(), self.node)
        else:
            return Attribute(self.MPlug.parent(), self.node)

    def isSettable(self):
        """
        Gets if the attribute is settable if it's not locked and either not connected, or has only keyframed animation.
        OpenMaya.MPlug.isFreeToChange returns 0 if the attribute is 'free' and 1 if it is not.
        Returns: bool
        """
        return not self.MPlug.isFreeToChange()

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
        """
        List the connections to this attribute via cmds.listConnections.
        By default, 'skipConversionNodes' and 'plugs' kwargs are set to True.
        :param kwargs: kwards to pass on to cmds.listConnections
        :return: YamList of Attribute or Yam node objects.
        """
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
        """
        List the attributes of this attribute via cmds.listAttr.
        :param kwargs: kwards to pass on to cmds.listAttr.
        :return: YamList of Attribute objects.
        """
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
        return self.MPlug.isLocked

    @locked.setter
    def locked(self, value):
        cmds.setAttr(self.name, lock=value)

    @property
    def keyable(self):
        return self.MPlug.isKeyable

    @keyable.setter
    def keyable(self, value):
        """
        When value is False, sets the attribute as channelBox (displayable).
        """
        cmds.setAttr(self.name, channelBox=True)
        cmds.setAttr(self.name, keyable=value)

    @property
    def channelBox(self):
        return self.MPlug.isChannelBox

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
    def __init__(self, MPlug, node, index):
        super(BlendshapeTarget, self).__init__(MPlug, node)
        self._index = index

    @property
    def weightsAttr(self):
        return self.node.inputTarget[0].inputTargetGroup[self.index].targetWeights

    @property
    def index(self):
        return self._index

    @property
    def weights(self):
        weightsAttr = self.weightsAttr
        return weightslist.WeightsList(weightsAttr[x].value for x in range(len(self.node.geometry)))

    @weights.setter
    def weights(self, weights):
        weightsAttr = self.weightsAttr
        for i, weight in enumerate(weights):
            weightsAttr[i].value = weight


def getAttr(attr):
    """
    Gets the attribute value.
    :param attr: Attibute object
    :return: the value of the attribute.
    """
    try:
        return getMPlugValue(attr.MPlug)
    except Exception as e:
        print('## failed to get MPlug value: {}'.format(e))

    value = cmds.getAttr(attr.name)
    # To simply return the tuple in the list that cmds returns for attribute like '.translate', '.rotate', etc...
    if value.__class__ == list and len(value) == 1 and value[0].__class__ == tuple:  # Not using isinstance() for efficiency
        return value[0]
    return value


def setAttr(attr, value, **kwargs):
    """
    Sets the attribute value.
    :param attr: Attribute object
    :param value: the value to set on the attribute
    :param kwargs: passed onto cmds.setAttr
    """
    if not config.undoable:
        try:
            setMPlugValue(attr.MPlug, value)
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


def getMPlugValue(MPlug):
    attribute = MPlug.attribute()
    attr_type = attribute.apiTypeStr
    if attr_type in ('kNumericAttribute', 'kDoubleLinearAttribute', ):
        return MPlug.asDouble()
    elif attr_type in ('kEnumAttribute', ):
        return MPlug.asInt()
    elif attr_type in ('kDistance', ):
        return MPlug.asMDistance().asUnits(om.MDistance.uiUnit())
    elif attr_type in ('kAngle', 'kDoubleAngleAttribute'):
        return MPlug.asMAngle().asUnits(om.MAngle.uiUnit())
    elif attr_type in ('kTypedAttribute', ):
        mfn = om.MFnTypedAttribute(attribute)
        if mfn.attrType() in (om.MFnData.kMatrix, ):
            mfn = om.MFnMatrixData(MPlug.asMObject())
            return mfn.matrix()
        return MPlug.asString()
    elif attr_type in ('kTimeAttribute', ):
        return MPlug.asMTime().asUnits(om.MTime.uiUnit())
    elif attr_type in ('kMatrixAttribute', 'kFloatMatrixAttribute', ):
        data_handle = MPlug.asMDataHandle()
        if attr_type == 'kMatrixAttribute':
            return data_handle.asMatrix()
        elif attr_type == 'kFloatMatrixAttribute':
            return data_handle.asFloatMatrix()
    elif MPlug.isCompound:
        values = []
        for child_index in range(MPlug.numChildren()):
            values.append(getMPlugValue(MPlug.child(child_index)))
        return values
    else:
        raise TypeError("Attribute '{}' of type '{}' not supported".format(MPlug.name(), attr_type))


def setMPlugValue(MPlug, value):
    attribute = MPlug.attribute()
    attr_type = attribute.apiTypeStr
    if attr_type in ('kNumericAttribute', 'kDoubleLinearAttribute', ):
        MPlug.setDouble(value)
    elif attr_type in ('kEnumAttribute', ):
        return MPlug.setInt(value)
    elif attr_type in ('kDistance', ):
        MPlug.setMDistance(om.MDistance(value, om.MDistance.uiUnit()))
    elif attr_type in ('kAngle', 'kDoubleAngleAttribute'):
        MPlug.setMAngle(om.MAngle(value, om.MAngle.uiUnit()))
    elif attr_type in ('kTypedAttribute', ):
        MPlug.setString(value)
    elif attr_type in ('kTimeAttribute', ):
        MPlug.setMTime(om.MTime(value, om.MTime.uiUnit()))
    elif attr_type in ('kMatrixAttribute', 'kFloatMatrixAttribute', ):
        data_handle = MPlug.asMDataHandle()
        if attr_type == 'kMatrixAttribute':
            data_handle.setMMatrix(value)
        elif attr_type == 'kFloatMatrixAttribute':
            data_handle.setMFloatMatrix(value)
        MPlug.setMDataHandle(data_handle)
    elif MPlug.isCompound:
        for child_index in range(MPlug.numChildren()):
            setMPlugValue(MPlug.child(child_index, value[child_index]))
    else:
        raise TypeError("Attribute '{}' of type '{}' not supported".format(MPlug.name(), attr_type))
