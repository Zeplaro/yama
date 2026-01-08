# encoding: utf8
import itertools

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
        return cls(value for _ in range(length))

    def __add__(self, other):
        if isinstance(other, (int, float)):
            return self.__class__(x + other for x in self)
        return self.__class__(x + y for (x, y) in zip(self, other))

    def __iadd__(self, other):
        if isinstance(other, (int, float)):
            for i in range(len(self)):
                self[i] += other
        else:
            for i, y in enumerate(other):
                self[i] += y
        return self

    __radd__ = __add__

    def __sub__(self, other):
        if isinstance(other, (int, float)):
            return self.__class__(x - other for x in self)
        return self.__class__(x - y for (x, y) in zip(self, other))

    def __isub__(self, other):
        if isinstance(other, (int, float)):
            for i in range(len(self)):
                self[i] -= other
        else:
            for i, y in enumerate(other):
                self[i] -= y
        return self

    def __rsub__(self, other):
        if isinstance(other, (int, float)):
            return self.__class__(other - x for x in self)
        return self.__class__(x - y for (x, y) in zip(other, self))

    def __mul__(self, other):
        if isinstance(other, (int, float)):
            return self.__class__(x * other for x in self)
        return self.__class__(x * y for (x, y) in zip(self, other))

    def __imul__(self, other):
        if isinstance(other, (int, float)):
            for i in range(len(self)):
                self[i] *= other
        else:
            for i, y in enumerate(other):
                self[i] *= y
        return self

    __rmul__ = __mul__

    def __truediv__(self, other):
        if isinstance(other, (int, float)):
            return self.__class__(x / other for x in self)
        return self.__class__(x / y for (x, y) in zip(self, other))

    def __itruediv__(self, other):
        if isinstance(other, (int, float)):
            for i in range(len(self)):
                self[i] /= other
        else:
            for i, y in enumerate(other):
                self[i] /= y
        return self

    def __rtruediv__(self, other):
        if isinstance(other, (int, float)):
            return self.__class__(other / x for x in self)
        return self.__class__(x / y for (x, y) in zip(other, self))

    def __floordiv__(self, other):
        if isinstance(other, (int, float)):
            return self.__class__(x // other for x in self)
        return self.__class__(x // y for (x, y) in zip(self, other))

    def __ifloordiv__(self, other):
        if isinstance(other, (int, float)):
            for i in range(len(self)):
                self[i] //= other
        else:
            for i, y in enumerate(other):
                self[i] //= y
        return self

    def __rfloordiv__(self, other):
        if isinstance(other, (int, float)):
            return self.__class__(other // x for x in self)
        return self.__class__(x // y for (x, y) in zip(other, self))

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
        if min_value is None and max_value is None:
            return
        elif min_value is not None and max_value is not None and min_value >= max_value:
            raise ValueError(f"min_value must be less than max_value; got : {min_value} >= {max_value}")

        if min_value is None:
            for i, value in enumerate(self):
                if value > max_value:
                    self[i] = max_value
        elif max_value is None:
            for i, value in enumerate(self):
                if value < min_value:
                    self[i] = min_value
        else:
            for i, value in enumerate(self):
                if value < min_value:
                    self[i] = min_value
                elif value > max_value:
                    self[i] = max_value

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


class VectorList(WeightList):
    def __init__(self, data=None, /, *, min_value=None, max_value=None, decimals=None):
        if data:
            super().__init__(WeightList(x, min_value=min_value, max_value=max_value, decimals=decimals) for x in data)

    def __str__(self):
        return f"{self.__class__.__name__}{[list(x) for x in self]}"

    def __repr__(self):
        return f"{self.__class__.__name__}({list(self)})"

    def append(self, values, /):
        super().append(WeightList(values))

    def extend(self, vectors, /):
        super().extend(VectorList(vectors))

    def insert(self, index, values, /):
        super().insert(index, WeightList(values))

    @classmethod
    def fromLengthValue(cls, length, value=(0.0, 0.0, 0.0), vector_length=3):
        if isinstance(value, (float, int)):
            value = tuple(value for _ in range(vector_length))
        else:
            value = tuple(value)
        return cls(WeightList(value) for _ in range(length))

    def copy(self, *, min_value=None, max_value=None, decimals=None):
        return self.__class__((x.copy() for x in self), min_value=min_value, max_value=max_value, decimals=decimals)

    def clamp(self, min_value=None, max_value=None):
        if min_value is None and max_value is None:
            return
        elif min_value is not None and max_value is not None and min_value >= max_value:
            raise ValueError(f"min_value must be less than max_value; got : {min_value} >= {max_value}")
        for vector in self:
            vector.clamp(min_value, max_value)

    def replaceWeights(self, weights, /):
        del self[:]
        for values in weights:
            self.append(values)

    def aslist(self):
        return [list(vector) for vector in self]


def normalizeWeights(weights, /, *, sum_value=1.0):
    """
    Normalizes a list of weights.

    Args:
        weights (list): A list of weights. Each weight can be a WeightList object or a numeric value.
        sum_value (float, optional): The value to which the weights should sum. Default is 1.0.

    Returns:
        list: A list of normalized weights, where each weight is a WeightList object.

    Note:
        - If a weight in the 'weights' list is already a WeightList object, it will be used as is.
        - If 'decimals' is specified, the normalized values will be rounded to the specified decimal places.
    """
    # Checking that all given weights are WeightList
    new_weights = [WeightList() for _ in weights]
    for values in itertools.zip_longest(*weights, fillvalue=0.0):
        divisor = sum(values) or 1.0
        for i, value in enumerate(values):
            new_weights[i].append(value / (divisor / sum_value))
    return new_weights


def clampWeights(weights, min_value=None, max_value=None):
    return WeightList(weights, min_value=min_value, max_value=max_value)


def roundWeights(weights, decimals=3):
    return WeightList(weights, decimals=decimals)
