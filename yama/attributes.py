# encoding: utf8

import maya.cmds as mc
import nodes

try:
    basestring
except NameError:
    basestring = str


def get_attribute(node, attr):
    if attr.endswith(']'):
        split = attr.split('[')
        index = int(split.pop(-1)[:-1])
        attr = '['.join(split)
        return MultiAttribute(node, attr, index)
    return Attribute(node, attr)


class Attribute(object):
    """
    A class for handling a node attribute and sub-attributes.
    """

    def __init__(self, node, attr):
        """
        :param parent (Depend/Attribute): the node or attribute parent to attr.
        :param attr (str):
        """
        assert isinstance(node, nodes.DependNode)
        assert isinstance(attr, (basestring, Attribute))
        self.node = node
        self.attribute = attr

    def __str__(self):
        return self.name

    def __repr__(self):
        return "{}({}, '{}')".format(self.__class__.__name__, repr(self.node), self.attribute)

    def __getattr__(self, item):
        """
        Gets sub attributes of self.
        :param item (str): the sub-attribute name.
        :return: Attribute object.
        """
        return self.attr(item)

    def __getitem__(self, item):
        """
        Gets attributes of type multi; for exemple a deformer weights attribute.
        :param item (int): the attribute index.
        :return: MultiAttribute object.
        """
        if isinstance(item, basestring):
            item = int(item)
        return MultiAttribute(self.node, self.attribute, item)

    def __add__(self, other):
        self.name.__add__(other)

    def __radd__(self, other):
        other.__add__(self.name)

    @property
    def name(self):
        return self.node + '.' + self.attribute

    def attr(self, attr):
        return get_attribute(self.node, self.attribute + '.' + attr)

    @property
    def value(self):
        print('getting', self.name)
        value = mc.getAttr(self.name)
        if isinstance(value, list) and len(value) == 1:
            value = value[0]
        return value

    @value.setter
    def value(self, value):
        print('setting')
        print(self, value)
        mc.setAttr(self.name, value)

    def connect_to(self, attr, *args, **kwargs):
        if isinstance(attr, Attribute):
            attr = attr.name
        mc.connectAttr(self.name, attr, *args, **kwargs)

    def connect_from(self, attr, *args, **kwargs):
        if isinstance(attr, Attribute):
            attr = attr.name
        mc.connectAttr(attr, self.name, *args, **kwargs)

    @property
    def type(self):
        """
        Returns the type of data currently in the attribute.
        :return: str
        """
        return mc.getAttr(self.name, type=True)

    @property
    def defaultValue(self):
        return mc.addAttr(self.name, q=True, defaultValue=True)

    @defaultValue.setter
    def defaultValue(self, value):
        mc.addAttr(self.name, e=True, defaultValue=value)

    @property
    def hasMinValue(self):
        return mc.attributeQuery(self.name, node=self.obj, minExists=True)

    @hasMinValue.setter
    def hasMinValue(self, value):
        """
        Maya can only toggle the minValue and can not set it to a certain state, regardless of passing True or False,
         which implies the following way of setting it.
        """
        if not bool(value) == bool(self.hasMinValue):
            mc.addAttr(self.name, e=True, hasMinValue=value)

    @property
    def minValue(self):
        return mc.attributeQuery(self._attr, node=self.obj, minimum=True)[0]

    @minValue.setter
    def minValue(self, value):
        mc.addAttr(self.name, e=True, minValue=value)

    @property
    def hasMaxValue(self):
        return mc.attributeQuery(self._attr, node=self.obj, maxExists=True)

    @hasMaxValue.setter
    def hasMaxValue(self, value):
        """
        Maya can only toggle the maxValue and can not set it to a certain state, regardless of passing True or False,
         which implies the following way of setting it.
        """
        if not bool(value) == bool(self.hasMaxValue):
            mc.addAttr(self, e=True, hasMaxValue=value)

    @property
    def maxValue(self):
        return mc.attributeQuery(self._attr, node=self.obj, maximum=True)[0]

    @maxValue.setter
    def maxValue(self, value):
        mc.addAttr(self, e=True, maxValue=value)

    @property
    def locked(self):
        return mc.getAttr(self, lock=True)

    @locked.setter
    def locked(self, value):
        mc.setAttr(self, lock=value)

    @property
    def keyable(self):
        return mc.getAttr(self, keyable=True)

    @keyable.setter
    def keyable(self, value):
        """
        When value is False, sets the attribute as channelBox (displayable).
        """
        mc.setAttr(self, keyable=value)
        mc.setAttr(self, channelBox=True)

    @property
    def channelBox(self):
        if not self.keyable and mc.getAttr(channelBox=True):
            return True
        return False

    @channelBox.setter
    def channelBox(self, value):
        """
        When value is False, sets the attribute as hidden.
        """
        if value:
            mc.setAttr(self, keyable=False)
            mc.setAttr(self, channelBox=True)
        else:
            mc.setAttr(self, keyable=False)
            mc.setAttr(self, channelBox=False)

    @property
    def hidden(self):
        if mc.getAttr(self, keyable=True) or mc.getAttr(self, channelBox=True):
            return False
        return True

    @hidden.setter
    def hidden(self, value):
        """
        When value is False, sets the attribute as channelBox (displayable).
        """
        if value:
            mc.setAttr(self, keyable=False)
            mc.setAttr(self, channelBox=False)
        else:
            mc.setAttr(self, keyable=False)
            mc.setAttr(self, channelBox=False)


class MultiAttribute(Attribute):
    """
    A sub-class to Attribute to handle attribute of type multi; for exemple a deformer weights attribute.
    """

    def __init__(self, node, attr, index):
        """
        :param parent (Attribute/MultiAttribute): The parent attribute of this attribute; Needs to be of type Attribute
                                                  or MultiAttribute.
        :param index: The index of this attribute
        """
        assert isinstance(node, nodes.DependNode) and isinstance(attr, basestring) and isinstance(index, int)
        super(MultiAttribute, self).__init__(node, attr)
        self.attribute = attr + '[' + str(index) + ']'
        self.index = index
        self.parent_attr = attr

    def __repr__(self):
        return '{}({}, {}, {})'.format(self.__class__.__name__, self.node, self.parent_attr, self.index)

    @property
    def parent(self):
        return get_attribute(self.node, self.parent_attr)
