# encoding: utf8

from __future__ import division

from . import io


class WeightsList(list):
    def __init__(self, *args, **kwargs):
        super(WeightsList, self).__init__()
        for i in list(*args, **kwargs):
            self.append(i)

    def __repr__(self):
        return 'WeightsList' + super(WeightsList, self).__repr__()

    def __getitem__(self, item):
        try:
            return super(WeightsList, self).__getitem__(item)
        except TypeError:
            try:
                return super(WeightsList, self).__getitem__(int(item))
            except TypeError:
                raise TypeError("list indices must be integers or string number, not {}".format(type(item).__name__))

    @classmethod
    def fromLengthValue(cls, length, value=0.0):
        return cls(float(value) for _ in range(length))

    def __setitem__(self, key, value):
        super(WeightsList, self).__setitem__(key, float(value))

    def __add__(self, other):
        if isinstance(other, (int, float)):
            other = self.fromLengthValue(len(self), other)
        return WeightsList(x + y for (x, y) in zip(self, other))

    def __iadd__(self, other):
        if isinstance(other, (int, float)):
            other = self.fromLengthValue(len(self), other)
        for i, (_, y) in enumerate(zip(self, other)):
            self[i] += y

    def __sub__(self, other):
        if isinstance(other, (int, float)):
            other = self.fromLengthValue(len(self), other)
        return WeightsList(x - y for (x, y) in zip(self, other))

    def __isub__(self, other):
        if isinstance(other, (int, float)):
            other = self.fromLengthValue(len(self), other)
        for i, (_, y) in enumerate(zip(self, other)):
            self[i] -= y

    def __mul__(self, other):
        if isinstance(other, (int, float)):
            other = self.fromLengthValue(len(self), other)
        return WeightsList(x * y for (x, y) in zip(self, other))

    def __imul__(self, other):
        if isinstance(other, (int, float)):
            other = self.fromLengthValue(len(self), other)
        for i, (_, y) in enumerate(zip(self, other)):
            self[i] *= y

    def __div__(self, other):
        if isinstance(other, (int, float)):
            other = self.fromLengthValue(len(self), other)
        return WeightsList(x / y for (x, y) in zip(self, other))

    def __idiv__(self, other):
        if isinstance(other, (int, float)):
            other = self.fromLengthValue(len(self), other)
        for i, (_, y) in enumerate(zip(self, other)):
            self[i] /= y

    def __neg__(self):
        return WeightsList(-x for x in self)

    def __invert__(self):
        return WeightsList(1 - x for x in self)

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

    def clamp(self, min_value=0.0, max_value=1.0):
        for i, x in enumerate(self):
            if not min_value < x < max_value:
                self[i] = max(min(x, max_value), min_value)

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


def normalizeWeights(*weights):
    lists = [WeightsList() for _ in range(len(weights))]
    for values in zip(*weights):
        mult = 1.0
        if any(values):  # Keeps everything to 0.0 if all values are at 0.0 and prevents a / by 0 error
            mult = 1.0 / sum(values)
        for i, value in enumerate(values):
            lists[i].append(value * mult)
    return lists
