# encoding: utf8

from __future__ import division
import sys

from . import io


class WeightsList(list):
    def __init__(self, arg=None, force_clamp=True, min_value=0.0, max_value=1.0):
        super(WeightsList, self).__init__()
        self.min_value = min_value
        self.max_value = max_value
        self.force_clamp = force_clamp

        # Forces initial arg to go through __setitem__ to verify values are floats and clamped
        if arg:
            for i in arg:
                self.append(i)

    def __repr__(self):
        return "WeightsList({})".format(super(WeightsList, self).__repr__())

    def __getitem__(self, item):
        if item.__class__ == slice:
            return self.emptyCopy(super(WeightsList, self).__getitem__(item))
        return super(WeightsList, self).__getitem__(item)

    if sys.version_info.major == 2:
        def __getslice__(self, start, stop):
            return self.emptyCopy(super(WeightsList, self).__getslice__(start, stop))

    @classmethod
    def fromLengthValue(cls, length, value=0.0, force_clamp=True, min_value=0.0, max_value=1.0):
        assert isinstance(length, int), "length must be int; got : {}, {}".format(length, type(length).__name__)
        try:
            value = float(value)
        except ValueError:
            raise ValueError("value must be float or string float; got : {}, {}".format(value, type(value).__name__))
        return cls((value for _ in range(length)), force_clamp=force_clamp, min_value=min_value, max_value=max_value)

    def __setitem__(self, key, value):
        try:
            value = float(value)
        except ValueError:
            raise ValueError("value must be float or string float; got : {}, {}".format(value, type(value).__name__))

        if self.force_clamp:
            value = max(min(value, self.max_value), self.min_value)

        super(WeightsList, self).__setitem__(key, value)

    def __add__(self, other):
        if isinstance(other, (int, float)):
            other = self.fromLengthValue(len(self), other, force_clamp=False)
        return self.emptyCopy(x + y for (x, y) in zip(self, other))

    def __iadd__(self, other):
        if isinstance(other, (int, float)):
            other = self.fromLengthValue(len(self), other, force_clamp=False)
        for i, y in enumerate(other):
            self[i] += y

    def __sub__(self, other):
        if isinstance(other, (int, float)):
            other = self.fromLengthValue(len(self), other, force_clamp=False)
        return self.emptyCopy(x - y for (x, y) in zip(self, other))

    def __isub__(self, other):
        if isinstance(other, (int, float)):
            other = self.fromLengthValue(len(self), other, force_clamp=False)
        for i, y in enumerate(other):
            self[i] -= y

    def __mul__(self, other):
        if isinstance(other, (int, float)):
            other = self.fromLengthValue(len(self), other, force_clamp=False)
        return self.emptyCopy(x * y for (x, y) in zip(self, other))

    def __imul__(self, other):
        if isinstance(other, (int, float)):
            other = self.fromLengthValue(len(self), other, force_clamp=False)
        for i, y in enumerate(other):
            self[i] *= y

    def __div__(self, other):
        if isinstance(other, (int, float)):
            other = self.fromLengthValue(len(self), other, force_clamp=False)
        return self.emptyCopy(x / y for (x, y) in zip(self, other))

    def __idiv__(self, other):
        if isinstance(other, (int, float)):
            other = self.fromLengthValue(len(self), other, force_clamp=False)
        for i, y in enumerate(other):
            self[i] /= y

    def __neg__(self):
        return self.emptyCopy(-x for x in self)

    def __invert__(self):
        return self.emptyCopy(1 - x for x in self)

    def __eq__(self, other):
        if isinstance(other, (int, float)):
            other = self.fromLengthValue(len(self), other)
        return super(WeightsList, self).__eq__(other)

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return hash(tuple(self))

    def get(self, k, value=None):
        try:
            return self[k]
        except IndexError:
            return value

    def append(self, value):
        try:
            value = float(value)
        except ValueError:
            raise ValueError("value must be float or string float; got : {}, {}".format(value, type(value).__name__))
        if self.force_clamp:
            value = min(max(value, self.min_value), self.max_value)
        super(WeightsList, self).append(value)

    def extend(self, other):
        for i in other:
            self.append(i)

    def insert(self, index, value):
        try:
            value = float(value)
        except ValueError:
            raise ValueError("value must be float or string float; got : {}, {}".format(value, type(value).__name__))
        if self.force_clamp:
            value = min(max(value, self.min_value), self.max_value)
        super(WeightsList, self).insert(index, value)

    def clamp(self, min_value=None, max_value=None):
        if min_value is None:
            min_value = self.min_value
        if max_value is None:
            max_value = self.max_value
        for i, value in enumerate(self):
            if not min_value < value < max_value:
                self[i] = max(min(value, max_value), min_value)

    def replaceWeights(self, weights):
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

    def emptyCopy(self, arg=None):
        return WeightsList(arg, force_clamp=self.force_clamp, min_value=self.min_value, max_value=self.max_value)

    def copy(self):
        return self.emptyCopy(self)


def normalizeWeights(weights, force_clamp=True, min_value=0.0, max_value=1.0):
    # Checking that all given weights are WeightsList
    weights = [WeightsList(weight, force_clamp=force_clamp, min_value=min_value, max_value=max_value)
               if not isinstance(weight, WeightsList) else weight for weight in weights]
    new_weights = [weight.emptyCopy() for weight in weights]
    for values in zip(*weights):
        mult = 1.0
        if any(values):  # Keeps everything to 0.0 if all values are at 0.0 and prevents a / by 0 error
            try:
                mult = 1.0 / sum(values)
            except ZeroDivisionError as e:
                raise ZeroDivisionError("The sum of values was equal to 0.0; Values : {}\n{}".format(values, e))
        for i, value in enumerate(values):
            new_weights[i].append(value * mult)
    return new_weights


def clampWeights(weights, min_value=0.0, max_value=1.0):
    return WeightsList(weights, force_clamp=True, min_value=min_value, max_value=max_value)
