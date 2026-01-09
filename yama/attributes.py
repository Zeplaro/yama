# encoding: utf8

"""
Contains all the class and functions for maya attributes.
"""
import functools

from maya import cmds, mel
import maya.api.OpenMaya as om
import maya.OpenMaya as om1

from . import config, nodes, weightlist, checks, mayautils


def getAttribute(node, attr):
    """
    Gets the given attribute from the given node.
    :param node: DependNode
    :param attr: str
    :return: Attribute
    """
    if "." in attr:
        attrs = attr.split(".")
        for attr in attrs:
            node = node.attr(attr)
        return node
    else:
        MPlug = getMPlug(node.name + "." + attr)
        return Attribute(MPlug, node)


def getMPlug(attr: str) -> om.MPlug:
    om_list = om.MSelectionList()

    try:
        om_list.add(attr)
    except RuntimeError:
        raise checks.AttributeExistsError(f"Attribute '{attr}' does not exist")

    try:
        MPlug = om_list.getPlug(0)
    except TypeError as e:
        if config.verbose:
            cmds.warning(f"Failed to use MSelectionList.getPlug : '{attr}'; {e}")
        node = om_list.getDependNode(0)
        attribute = attr.split(".", 1)[-1]
        try:
            MPlug = om.MFnDependencyNode(node).findPlug(attribute, False)
        except RuntimeError as e:
            if config.verbose:
                cmds.warning(f"Failed to use MFnDependencyNode.findPlug : '{attr}'; {e}")
            # TODO: Check if getting a .controlPoints[0]
            raise e

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
        if not isinstance(MPlug, om.MPlug):
            raise TypeError(
                f"MPlug arg should be of type OpenMaya.MPlug not : {MPlug.__class__.__name__}"
            )
        if MPlug.isNull:
            raise ValueError("Given MPlug is Null and does not contain a valid attribute.")

        if node:
            if not isinstance(node, nodes.DependNode):
                raise TypeError(
                    f"Given node arg should be of type DependNode not : {type(node).__name__}"
                )
            self.node = node
        else:
            self.node = nodes.yam(MPlug.node())
        self.MPlug = MPlug
        self._MPlug1 = None
        self._hashCode = None
        self._types = None

    def __repr__(self):
        return f"{self.__class__.__name__}('{self.node}.{self.attribute}')"

    def __getitem__(self, item):
        """
        Gets the element of the array attribute at the given index.
        Returns a list of attribute if given a slice.
        """
        if item == "*":
            item = slice(None)
        if isinstance(item, slice):  # Not using isinstance() for efficiency
            return nodes.YamList(self[i] for i in range(len(self))[item])

        try:
            return Attribute(self.MPlug.elementByLogicalIndex(item), self.node)
        except (RuntimeError, TypeError):
            raise TypeError(f"'{self}' is not an array attribute and cannot use __getitem__")

    def __add__(self, other):
        """
        Using self.name for + operator.
        :return: str
        """
        return f"{self.name}{other}"

    def __radd__(self, other):
        """
        Using self.name for reverse + operator.
        :return: str
        """
        return f"{other}{self.name}"

    def __contains__(self, item):
        """
        Using self.attribute for 'in' operator.
        :return: str
        """
        return item in self.attribute

    def __len__(self):
        return self.MPlug.numElements()

    def __iter__(self):
        if self.isArray():
            node = self.node
            for i in self.indices():
                MPlug = self.MPlug.elementByLogicalIndex(i)
                yield Attribute(MPlug, node)
        else:
            raise TypeError(f"'{self}' is not iterable")

    def __eq__(self, other):
        if hasattr(other, "MPlug"):
            return self.MPlug == other.MPlug
        else:
            try:
                return self.MPlug == nodes.yam(other).MPlug
            except (TypeError, checks.ObjExistsError, AttributeError):
                return False

    @property
    def MPlug1(self):
        """
        Gets the associated api 1.0 MPlug
        :return: api 1.0 MPlug
        """
        if self._MPlug1 is None:
            om_list = om1.MSelectionList()
            om_list.add(self.name)
            self._MPlug1 = om1.MPlug()
            om_list.getPlug(0, self._MPlug1)
        return self._MPlug1

    @property
    def name(self):
        """
        The full 'node.attribute' name using alias names when available.
        Not using self.MPlug.name() because, unlike node.name, it does not return the node's  minimum string
        representation which will uniquely identify the path, in case the node has a non-unique name.
        :return: str
        """
        return f"{self.node.name}.{self.alias}"

    def attr(self, attr):
        """
        Gets a children attribute
        :param attr: str
        :return: Attribute object
        """
        if self.isArray():  # If array attribute returns the attribute under the array index 0.
            return self[0].attr(attr)

        attribute = Attribute(getMPlug(f"{self.name}.{attr}"), self.node)
        return attribute

    __getattr__ = attr

    def hasattr(self, attr):
        return checks.objExists(f"{self}.{attr}")

    @property
    def attribute(self):
        """Returns the attribute long name by itself without the node name."""
        return self.alias

    @attribute.setter
    def attribute(self, newName):
        """Renames the attribute long name."""
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
        return self.value

    def set(self, value):
        """
        Alternative way to set the maya value.
        """
        self.value = value

    exists = checks.objExists

    @property
    def index(self):
        return self.MPlug.logicalIndex()

    def indices(self):
        return self.MPlug.getExistingArrayAttributeIndices()

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

    def connectTo(self, attr, /, **kwargs):
        """
        Connect this attribute to the given attr.
        kwargs are passed on to cmds.connectAttr
        """
        cmds.connectAttr(self.name, str(attr), **kwargs)

    __rshift__ = connectTo

    def connectFrom(self, attr, /, **kwargs):
        """
        Connect the given attr to this attribute.
        kwargs are passed on to cmds.connectAttr
        """
        cmds.connectAttr(str(attr), self.name, **kwargs)

    __lshift__ = connectFrom

    def disconnect(self, attr, /):
        """
        Disconnect the connection between self (source) and attr (destination)
        :param attr: str or Attribute
        """
        cmds.disconnectAttr(self.name, str(attr))

    __floordiv__ = disconnect

    def listConnections(self, **kwargs):
        """
        List the connections to this attribute via cmds.listConnections.
        By default, 'skipConversionNodes' and 'plugs' kwargs are set to True.
        :param kwargs: kwargs to pass on to cmds.listConnections
        :return: YamList of Attribute or Yam node objects.
        """
        if "p" not in kwargs and "plugs" not in kwargs:
            kwargs["plugs"] = True
        return nodes.listConnections(self.name, **kwargs)

    def input(self, **kwargs):
        connection = self.listConnections(destination=False, **kwargs)
        if connection:
            return connection[0]

    def inputs(self, **kwargs):
        if not self.isArray():
            raise RuntimeError(
                f"'{self}' is not an array attribute, use .input on none array attributes"
            )
        return nodes.YamList(attr.input(**kwargs) for attr in self)

    @property
    def source(self):
        try:
            return Attribute(self.MPlug.source())
        except AssertionError:
            raise RuntimeError(f"Attribute {self} does not have a source connection")

    outputs = functools.partial(listConnections, source=False)

    def breakConnection(self):
        connection = self.input()
        if connection:
            connection.disconnect(self)
            return connection

    listAttr = nodes.listAttr

    def types(self):
        if self._types is None:
            self._types = ["attribute", self.getType()]
        return self._types

    def type(self):
        return self.types()[-1]

    def getType(self):
        """
        Returns the type of data currently in the attribute.
        :return: str
        """
        def get_type_with_api(attr):
            attribute = attr.MObject
            api_type = attribute.apiType()

            if api_type == om.MFn.kTypedAttribute:
                typed_attribute = om.MFnTypedAttribute(attribute)
                api_type = typed_attribute.attrType()

            return MFN_TO_CMDS_ATTR_TYPES.get(api_type)

        try:
            attr_type = cmds.getAttr(self.name, type=True)
            if not attr_type:  # Attribute is valid but does not exist yet
                attr_type = get_type_with_api(self)
        except RuntimeError:
            attr_type = get_type_with_api(self)
            if not attr_type and self.isArray():  # failed because attribute is not initialized
                # setting the first array element to force initialize the attribute
                first_element = self[0]
                setAttr(first_element, first_element.get())
                attr_type = cmds.getAttr(self.name, type=True)

        if not attr_type:
            cmds.warning("Could not find attribute type")

        return attr_type

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

    def lock(self):
        self.locked = True

    def unlock(self):
        self.locked = False

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
        cmds.setAttr(self.name, keyable=False)
        cmds.setAttr(self.name, channelBox=value)

    @property
    def hidden(self):
        if self.keyable or self.channelBox:
            return False
        return True

    @hidden.setter
    def hidden(self, value):
        """
        When value is False, sets the attribute as channelBox (displayable).
        """
        cmds.setAttr(self.name, keyable=False)
        cmds.setAttr(self.name, channelBox=not value)

    @property
    def niceName(self):
        return cmds.attributeQuery(self.attribute, node=self.node.name, niceName=True)

    @niceName.setter
    def niceName(self, newName):
        if newName is None:
            newName = ""
        cmds.addAttr(self.name, e=True, niceName=newName)

    @property
    def shortName(self):
        return om.MFnAttribute(self.MPlug.attribute()).shortName

    @property
    def alias(self):
        return self.MPlug.partialName(
            useAlias=True,
            useLongNames=True,
            includeInstancedIndices=True,
            includeNonMandatoryIndices=True,
        )

    @alias.setter
    def alias(self, alias):
        # getting node.attribute name without alias
        real_name = self.MPlug.partialName(
            includeNodeName=True,
            useLongNames=True,
            includeInstancedIndices=True,
            includeNonMandatoryIndices=True,
        )
        try:
            cmds.aliasAttr(alias, real_name)
        except RuntimeError as e:
            raise RuntimeError(
                f"Could not rename attribute :'{real_name}', alias :'{self.attribute}', to"
                f" '{alias}'; {e}"
            )

    def hashCode(self):
        if self._hashCode is None:
            self._hashCode = om.MObjectHandle(self.MPlug.attribute()).hashCode()
        return self._hashCode

    __hash__ = hashCode

    def children(self):
        if not self.MPlug.isCompound:
            raise RuntimeError(
                f"'{self}' is not an compound attribute and has no children attribute"
            )
        if self.isArray():
            return self[0].children()

        children = []
        for index in range(self.MPlug.numChildren()):
            children.append(Attribute(self.MPlug.child(index), self.node))

        return children

    def isArray(self):
        return self.MPlug.isArray

    def nextAvailableElement(self):
        """
        Gets an Attribute for the next available array element of this attribute.

        @return: Attribute
        """
        if not self.isArray():
            raise RuntimeError("The attribute {} is not an array attribute.".format(repr(self)))
        existing_indices = self.indices() or [-1]
        next_index = existing_indices[-1] + 1
        return self[next_index]

    @property
    def enumNames(self):
        return cmds.addAttr(self.name, q=True, enumName=True).split(":")

    @enumNames.setter
    def enumNames(self, names):
        cmds.addAttr(self.name, enumName=":".join(names), e=True)


class BlendShapeTarget(Attribute):
    def __init__(self, MPlug, node=None):
        super().__init__(MPlug, node)

    @property
    def inputTargetGroupAttr(self):
        return self.node.inputTarget[0].inputTargetGroup[self.index]

    @property
    def weightsAttr(self):
        return self.inputTargetGroupAttr.targetWeights

    def getWeights(self, min_value=None, max_value=None, decimals=None):
        geometry = self.node.geometry
        if not geometry:
            raise RuntimeError(f"Deformer '{self.node}' is not connected to a geometry")
        weightsAttr = self.weightsAttr
        return weightlist.WeightList(
            (weightsAttr[x].value for x in range(len(geometry))),
            min_value=min_value,
            max_value=max_value,
            decimals=decimals,
        )

    def setWeights(self, weights):
        weightsAttr = self.weightsAttr
        for i, weight in enumerate(weights):
            weightsAttr[i].value = weight

    @property
    def weights(self):
        return self.getWeights()

    @weights.setter
    def weights(self, weights):
        self.setWeights(weights)

    def inputTargetItemIndices(self):
        return list(
            self.inputTargetGroupAttr.inputTargetItem.MPlug.getExistingArrayAttributeIndices()
        )

    def values(self):
        # rounding to avoid python approximation, e.g.: (5200 / 1000.0 - 5) -> 0.20000000000000018 instead of 0.2
        return [round(item_index / 1000.0 - 5, 6) for item_index in self.inputTargetItemIndices()]

    def getDeltas(self):
        """
        Gets the delta data for the target for each full and in-between target values.
        Deltas are stored in a dict per shape activation values. A simple target will be at value 1.0 and in-between
        targets under their activation values (usually between 0.0 and 1.0).

        Returns:
            dict : {target value: {influenced component: list of x, y, z component delta}}
        """
        return {value: self.getDelta(value) for value in self.values()}

    def setDeltas(self, deltas):
        """Sets the given delta data on the corresponding inputTargetItem"""
        inputTargetItem = self.node.inputTarget[0].inputTargetGroup[self.index].inputTargetItem
        for shape_value, data in deltas.items():
            # Needed if data comes from a json file with str keys
            shape_value = float(shape_value)
            self.setDelta(shape_value, data, inputTargetItem)

    def getDelta(self, target_value, item_index=None):
        """
        Gets the delta data for one specific in-between value of the target; same value you would set on the attribute
        of the blendShape node corresponding to this target, to "activate" the target or its in-between.
        I call it an "in-between value of the target" but if the value is 1.0, it's the target default deltas, usually
        just referred as : the target deltas.

        Args:
            target_value: float, value at which the full or in-between shape gets activated. If None, expects item_index
            item_index: int, if provided and target_value is None, uses this index for inputTargetItem plug.

        Returns:
            delta: dict of {influenced component: [vector list x, y, z for the component delta]}
        """

        if target_value is not None:
            item_index = int(target_value * 1000 + 5000)
        elif item_index is None:
            raise RuntimeError(
                "At least one of target_value or item_index needed to get deltas; got None."
            )

        delta_values = self.inputTargetGroupAttr.inputTargetItem[item_index].inputPointsTarget.value
        component_indices = self.inputTargetGroupAttr.inputTargetItem[
            item_index
        ].inputComponentsTarget.value
        if component_indices and isinstance(component_indices[0], str):
            component_indices = mayautils.componentListToIndices(component_indices)
        if len(delta_values) != len(component_indices):
            raise RuntimeError(
                f"BlendShape '{self.node}' inputPointsTarget values "
                "and inputComponentsTarget not in sync"
            )
        return component_indices, weightlist.VectorList(delta_values)

    def setDelta(self, value, delta, inputTargetItem=None):
        if not inputTargetItem:
            inputTargetItem = self.node.inputTarget[0].inputTargetGroup[self.index].inputTargetItem

        item_index = int(value * 1000 + 5000)

        plug = inputTargetItem[item_index]
        component_indexes, delta_values = delta
        # Needed if components come from a json file with str keys
        component_indexes = [int(x) for x in component_indexes]
        plug.inputPointsTarget.value = delta_values
        plug.inputComponentsTarget.value = component_indexes

    @property
    def geometry(self):
        """Returns the geometry shape connected on the target geometry input if any."""
        inputTargetItem_index = (
            self.inputTargetGroupAttr.inputTargetItem.MPlug.getExistingArrayAttributeIndices()[0]
        )
        inputGeomTarget = self.inputTargetGroupAttr.inputTargetItem[
            inputTargetItem_index
        ].inputGeomTarget
        input_attr = inputGeomTarget.input()
        if input_attr:
            return input_attr.node

    @geometry.setter
    def geometry(self, geometry):
        """
        Sets a new geometry shape as the target geometry input.
        Breaks the connection of the current geometry shape if one is already connected.
        Warning: this operation will rename the target alias to the given geometry name.
        Args:
            geometry: str, new shape to set as geometry shape for the target.
        """
        current_value = self.value

        # Force disconnects the current geometry shape
        inputGeomTarget = self.inputTargetGroupAttr.inputTargetItem[6000].inputGeomTarget
        if inputGeomTarget.input():
            inputGeomTarget.breakInput()

        cmds.blendShape(
            self.node.name, edit=True, target=(self.node.geometry, self.index, geometry, 1.0)
        )
        # Setting a new geometry for the target sets the current target value to 0.0.
        self.value = current_value

    def resetDeltas(self):
        """Resets the delta of this target"""
        cmds.blendShape(self.node.name, edit=True, resetTargetDelta=(0, self.index))

    def removeTarget(self):
        """
        Removes the target from the blendShape.

        If the target does not have a live geometry still connected then maya the remove kwarg on cmds.blendShape does
        not work, instead we're using the same mel command used by the shapeEditor UI.
        """
        if self.geometry:
            cmds.blendShape(
                self.node.name,
                e=True,
                remove=True,
                t=[self.node.geometry, 0, self.geometry, self.index],
            )
        else:
            mel.eval(f'blendShapeDeleteTargetGroup("{self.node.name}", "{self.index}");')


def getAttr(attr: Attribute):
    """
    Gets the attribute value.
    :param attr: Attribute object
    :return: the value of the attribute.
    """
    MPlug = attr.MPlug
    # if not MPlug.isArray:  # Getting full array is usually faster using cmds
    try:
        return getMPlugValue(MPlug)
    except NotImplementedError as e:
        if config.verbose:
            print(f"## Failed to get MPlug value on '{MPlug.name()}': {e}")
    except RuntimeError as e:
        raise RuntimeError(f"## Failed to get MPlug value on '{MPlug.name()}': {e}")

    value = cmds.getAttr(attr.name)
    # Fixing cmds.getattr to simply return the tuple in the list that cmds returns for attribute like '.translate',
    # '.rotate', etc...
    if isinstance(value, list) and len(value) == 1 and isinstance(value[0], tuple):
        return value[0]
    return value


def setAttr(attr, value, **kwargs):
    """
    Sets the attribute value.
    :param attr: Attribute object
    :param value: the value to set on the attribute
    :param kwargs: passed onto cmds.setAttr
    """
    if not config.undoable:  # and not attr.MPlug.isArray:
        MPlug = attr.MPlug
        try:
            setMPlugValue(MPlug, value)
            return
        except NotImplementedError as e:
            if config.verbose:
                print(f"## Failed to set MPlug value: {e}")
        except RuntimeError as e:
            raise RuntimeError(f"## Failed to get MPlug value on '{MPlug.name()}': {e}")

    attr_type = attr.type()
    if attr_type in [
        "double2",
        "double3",
        "float2",
        "float3",
        "long2",
        "long3",
        "short2",
        "matrix",
    ]:
        cmds.setAttr(attr.name, *value, type=attr_type)
    elif attr_type == "string":
        cmds.setAttr(attr.name, value, type=attr_type)
    elif attr_type == "TdataCompound":
        length = len(value)
        try:
            cmds.setAttr(attr.name + f"[:]", *value, size=length)
        except RuntimeError:
            cmds.setAttr(attr.name + f"[0:{length-1}]", *value, size=length)
    elif attr_type in ["componentList", "pointArray"]:
        if attr_type == "componentList":
            # TODO: make work with other than vtx
            # If given a list of integers, tries to set them as vertex components
            if isinstance(value, (list, tuple)) and all(isinstance(x, int) for x in value):
                value = [f"vtx[{x}]" for x in value]
        cmds.setAttr(attr.name, len(value), *value, type=attr_type)
    else:
        cmds.setAttr(attr.name, value, **kwargs)


def getMPlugValue(MPlug):
    if MPlug.isArray:
        return [
            getMPlugValue(MPlug.elementByLogicalIndex(i))
            for i in MPlug.getExistingArrayAttributeIndices()
        ]
    attribute = MPlug.attribute()
    attr_type = attribute.apiType()
    if attr_type in (om.MFn.kNumericAttribute, om.MFn.kDoubleLinearAttribute):
        return MPlug.asDouble()
    elif attr_type == om.MFn.kEnumAttribute:
        return MPlug.asInt()
    elif attr_type == om.MFn.kDistance:
        return MPlug.asMDistance().asUnits(om.MDistance.uiUnit())
    elif attr_type in (om.MFn.kAngle, om.MFn.kDoubleAngleAttribute):
        return MPlug.asMAngle().asUnits(om.MAngle.uiUnit())
    elif attr_type == om.MFn.kTypedAttribute:
        mfn = om.MFnTypedAttribute(attribute)
        attr_type = mfn.attrType()
        if attr_type == om.MFnData.kString:
            return MPlug.asString()
        elif attr_type == om.MFnData.kMatrix:
            try:
                mfn =  om.MFnMatrixData(MPlug.asMObject())
            except RuntimeError:
                return ([1.0] + [0.0] * 4) * 3 + [1.0]  # Zero matrix (I swear...)
            return list(mfn.matrix())
        elif attr_type == om.MFnData.kPointArray:
            # TODO: fails to get MPlug.asMObject() if empty data
            try:
                mfn = om.MFnPointArrayData(MPlug.asMObject())
            except RuntimeError:
                return []
            return [(x.x, x.y, x.z) for x in mfn.array()]
        elif attr_type == om.MFnData.kComponentList:
            from . import components

            try:
                mfn = om.MFnComponentListData(MPlug.asMObject())
            except RuntimeError:
                return []
            elements = []
            for i in range(mfn.length()):
                component = mfn.get(i)
                # Single indexed components, e.g.: mesh vertices
                if component.hasFn(om.MFn.kSingleIndexedComponent):
                    component_mfn = om.MFnSingleIndexedComponent(component)
                    type_preffix = components.SupportedTypes.MFNID_COMPONENT_CLASS[
                        component_mfn.componentType
                    ][0]
                    elements += [f"{type_preffix}[{x}]" for x in component_mfn.getElements()]
                # Double indexed components, e.g.: surface cvs
                elif component.hasFn(om.MFn.kDoubleIndexedComponent):
                    component_mfn = om.MFnDoubleIndexedComponent(component)
                    type_preffix = components.SupportedTypes.MFNID_COMPONENT_CLASS[
                        component_mfn.componentType
                    ][0]
                    elements += [
                        f"{type_preffix}[{x}][{y}]" for x, y in component_mfn.getElements()
                    ]
                # Triple indexed components, e.g.: lattice point
                else:
                    component_mfn = om.MFnTripleIndexedComponent(component)
                    type_preffix = components.SupportedTypes.MFNID_COMPONENT_CLASS[
                        component_mfn.componentType
                    ][0]
                    elements += [
                        f"{type_preffix}[{x}][{y}][{z}]" for x, y, z in component_mfn.getElements()
                    ]
            return elements
        else:
            raise NotImplementedError(
                f"Attribute '{MPlug.name()}' of MFnData type {attr_type} not supported."
            )
    elif attr_type == om.MFn.kTimeAttribute:
        return MPlug.asMTime().asUnits(om.MTime.uiUnit())
    elif attr_type in (om.MFn.kMatrixAttribute, om.MFn.kFloatMatrixAttribute):
        data_handle = MPlug.asMDataHandle()
        if attr_type == om.MFn.kMatrixAttribute:
            return list(data_handle.asMatrix())
        elif attr_type == om.MFn.kFloatMatrixAttribute:
            return list(data_handle.asFloatMatrix())
    elif MPlug.isCompound:
        values = []
        for child_index in range(MPlug.numChildren()):
            values.append(getMPlugValue(MPlug.child(child_index)))
        return values
    else:
        raise NotImplementedError(
            f"Attribute '{MPlug.name()}' of type '{nodes.MFN_TYPE_NAMES[attr_type]}' not supported"
        )


def setMPlugValue(MPlug, value):
    if MPlug.isArray:
        return [
            setMPlugValue(MPlug.elementByLogicalIndex(i), value)
            for i in MPlug.getExistingArrayAttributeIndices()
        ]
    attribute = MPlug.attribute()
    attr_type = attribute.apiType()
    if attr_type in (om.MFn.kNumericAttribute, om.MFn.kDoubleLinearAttribute):
        MPlug.setDouble(value)
    elif attr_type == om.MFn.kEnumAttribute:
        return MPlug.setInt(value)
    elif attr_type == om.MFn.kDistance:
        MPlug.setMDistance(om.MDistance(value, om.MDistance.uiUnit()))
    elif attr_type in (om.MFn.kAngle, om.MFn.kDoubleAngleAttribute):
        MPlug.setMAngle(om.MAngle(value, om.MAngle.uiUnit()))
    elif attr_type == om.MFn.kTypedAttribute:
        mfn = om.MFnTypedAttribute(attribute)
        attr_type = mfn.attrType()
        if attr_type == om.MFnData.kString:
            MPlug.setString(value)
        elif attr_type == om.MFnData.kPointArray:
            array = om.MPointArray([om.MPoint(x) for x in value])
            data = om.MFnPointArrayData().create(array)
            MPlug.setMObject(data)
        elif attr_type == om.MFnData.kMatrix:
            matrix = om.MMatrix(value)
            data = om.MFnMatrixData().create(matrix)
            MPlug.setMObject(data)
        elif attr_type == om.MFnData.kComponentList:
            # Getting a proper MFnComponentData
            mfnd = om.MFnComponentListData(MPlug.asMObject())
            # TODO : Fails to .get if empty list
            mo = mfnd.get(0)

            # Getting a proper MFn*IndexedComponent
            if mo.hasFn(om.MFn.kSingleIndexedComponent):
                mfn = om.MFnSingleIndexedComponent
            elif mo.hasFn(om.MFn.kDoubleIndexedComponent):
                mfn = om.MFnDoubleIndexedComponent
            elif mo.hasFn(om.MFn.kTripleIndexedComponent):
                mfn = om.MFnTripleIndexedComponent
            mfn = mfn(mo)
            # Clearing it by creating a new one with the mo type
            new_mo = mfn.create(getattr(om.MFn, mo.apiTypeStr))
            # Adding the wanted indexes
            mfn.addElements(value)

            # Clearing the MFnComponentData and adding the new MFn*IndexedComponent to it
            mfnd.clear()
            mfnd.add(new_mo)
            # Setting the MObject on the MPlug
            MPlug.setMObject(mfnd.object())
        else:
            raise NotImplementedError(
                f"Attribute of MFnData type '{nodes.MFNDATA_TYPE_NAMES[attr_type]}' not supported"
            )
    elif attr_type == om.MFn.kTimeAttribute:
        MPlug.setMTime(om.MTime(value, om.MTime.uiUnit()))
    elif attr_type in (om.MFn.kMatrixAttribute, om.MFn.kFloatMatrixAttribute):
        data_handle = MPlug.asMDataHandle()
        if attr_type == om.MFn.kMatrixAttribute:
            data_handle.setMMatrix(value)
        elif attr_type == om.MFn.kFloatMatrixAttribute:
            data_handle.setMFloatMatrix(value)
        MPlug.setMDataHandle(data_handle)
    elif MPlug.isCompound:
        for child_index in range(MPlug.numChildren()):
            setMPlugValue(MPlug.child(child_index), value[child_index])
    else:
        raise NotImplementedError(
            f"Attribute '{MPlug.name()}' of type '{nodes.MFN_TYPE_NAMES[attr_type]}' not supported"
        )


"""
Used to match the MPlug MFn type to its corresponding cmds type in case the attribute is valid but does not exist yet 
(e.g.: an unused component of an array attribute), to pass to a cmds.setAttr call for exemple.
"""
MFN_TO_CMDS_ATTR_TYPES = {
    om.MFnData.kPointArray: "pointArray",
    om.MFnData.kComponentList: "componentList",
    om.MFnData.kString: "string",
    om.MFn.kMatrixAttribute: "matrix",
    om.MFn.kFloatMatrixAttribute: "matrix",
    om.MFn.kAttribute2Double: "double2",
    om.MFn.kAttribute3Double: "double3",
    om.MFn.kCompoundAttribute: "TdataCompound",
    om.MFn.kNumericAttribute: "TdataCompound"
}