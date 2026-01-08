# encoding: utf8

from . import io


class WeightList(list):
    def __init__(self, data=None, /, *, min_value=None, max_value=None, decimals=None):
        super().__init__()

        # Forces initial arg to go through __setitem__ to verify values are floats, clamped and rounded
        if data:
            super().__init__(data)
        if min_value is not None or max_value is not None:
            self.clamp(min_value, max_value)
        if decimals is not None:
            self.round(decimals)

    def __repr__(self):
        return f"{self.__class__.__name__}({super().__repr__()})"

    def __getitem__(self, item):
        if isinstance(item, slice):
            return self.__class__(super().__getitem__(item))
        return super().__getitem__(item)

    @classmethod
    def fromLengthValue(cls, length, value=0.0):
        if not isinstance(length, int):
            raise TypeError(f"length must be int; got : {length}, {type(length).__name__}")
        try:
            value = float(value)
        except ValueError:
            raise ValueError(f"value must be float or string float; got : {value}, {type(value).__name__}")
        return cls(value for _ in range(length))

    def __add__(self, other):
        if isinstance(other, (int, float)):
            other = self.fromLengthValue(len(self), other)
        return self.__class__(x + y for (x, y) in zip(self, other))

    def __iadd__(self, other):
        if isinstance(other, (int, float)):
            other = self.fromLengthValue(len(self), other)
        for i, y in enumerate(other):
            self[i] += y
        return self

    def __sub__(self, other):
        if isinstance(other, (int, float)):
            other = self.fromLengthValue(len(self), other)
        return self.__class__(x - y for (x, y) in zip(self, other))

    def __isub__(self, other):
        if isinstance(other, (int, float)):
            other = self.fromLengthValue(len(self), other)
        for i, y in enumerate(other):
            self[i] -= y
        return self

    def __mul__(self, other):
        if isinstance(other, (int, float)):
            other = self.fromLengthValue(len(self), other)
        return self.__class__(x * y for (x, y) in zip(self, other))

    def __imul__(self, other):
        if isinstance(other, (int, float)):
            other = self.fromLengthValue(len(self), other)
        for i, y in enumerate(other):
            self[i] *= y
        return self

    def __truediv__(self, other):
        if isinstance(other, (int, float)):
            other = self.fromLengthValue(len(self), other)
        return self.__class__(x / y for (x, y) in zip(self, other))

    def __itruediv__(self, other):
        if isinstance(other, (int, float)):
            other = self.fromLengthValue(len(self), other)
        for i, y in enumerate(other):
            self[i] /= y
        return self

    def __neg__(self):
        return self.__class__(-x for x in self)

    def __invert__(self):
        return self.__class__(1 - x for x in self)

    def __eq__(self, other):
        if isinstance(other, (int, float)):
            other = self.fromLengthValue(len(self), other)
        return super().__eq__(other)

    def __hash__(self):
        return hash(tuple(self))

    def get(self, k, value=None, /):
        try:
            return self[k]
        except IndexError:
            return value

    def clamp(self, min_value=None, max_value=None):
        for i, value in enumerate(self):
            if not min_value < value < max_value:
                self[i] = max(min(value, max_value), min_value)

    def round(self, decimals=None, /):
        for i, value in enumerate(self):
            self[i] = round(value, decimals)

    def replaceWeights(self, weights, /):
        del self[:]
        for i in weights:
            self.append(i)

    def exportWeights(self, path):
        io.exportData(self, path)

    def importWeights(self, path, apply_data=True):
        data = io.importData(path)
        if apply_data:
            del self[:]
            for i in data:
                self.append(i)
        return data

    def copy(self, *, min_value=None, max_value=None, decimals=None):
        return self.__class__(self, min_value=min_value, max_value=max_value, decimals=decimals)


def normalizeWeights(weights, /, min_value=None, max_value=None, decimals=None):
    """
    Normalizes a list of weights.

    Args:
        weights (list): A list of weights. Each weight can be a WeightList object or a numeric value.
        min_value (float, optional): The minimum value for clamping. Defaults to None.
        max_value (float, optional): The maximum value for clamping. Defaults to None.
        decimals (int, optional): The number of decimal places to round the normalized values. Defaults to None.

    Returns:
        list: A list of normalized weights, where each weight is a WeightList object.

    Note:
        - If a weight in the 'weights' list is already a WeightList object, it will be used as is.
        - If 'decimals' is specified, the normalized values will be rounded to the specified decimal places.
    """
    # Checking that all given weights are WeightList
    weights = [
        (
            WeightList(weight, min_value=min_value, max_value=max_value, decimals=decimals)
            if not isinstance(weight, WeightList)
            else weight
        )
        for weight in weights
    ]
    new_weights = [WeightList() for _ in weights]
    for values in zip(*weights):
        mult = 1.0
        # Keeps everything to 0.0 if all values are at 0.0 and prevents a / by 0 error
        if any(values):
            try:
                mult = 1.0 / sum(values)
            except ZeroDivisionError as e:
                raise ZeroDivisionError(
                    f"The sum of values was equal to 0.0; Values : {values}; {e}"
                )
        for i, value in enumerate(values):
            new_weights[i].append(value * mult)
    return new_weights


def clampWeights(weights, min_value=None, max_value=None):
    return WeightList(weights, min_value=min_value, max_value=max_value)


def roundWeights(weights, decimals=3):
    return WeightList(weights, decimals=decimals)
