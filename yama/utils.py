# encoding: utf8

"""
Contains non maya specific utils.
"""

from __future__ import division
from six import string_types


def multList(list_a, list_b):
    """
    Zips 'list_a' items with 'list_b' items and multiplies them together.
    :param list_a: list of digits
    :param list_b: list of digits
    :return: list of digits
    """
    return [x*y for x, y in zip(list_a, list_b)]


def addList(list_a, list_b):
    """
    Zips 'list_a' items with 'list_b' items and adds them together.
    :param list_a: list of digits
    :param list_b: list of digits
    :return: list of digits
    """
    return [x+y for x, y in zip(list_a, list_b)]


def decimalToAlphabetical(index):
    """
    Converts int to an alphabetical index.

    e.g.: 0 -> 'a', 1 -> 'b', 2 -> 'c', 'yama' -> 440414
    :param index: int
    :return: str
    """
    assert isinstance(index, int) and index >= 0
    from string import ascii_lowercase
    alphanum = ''
    index += 1  # because alphabet hase no 0 and starts with 'a'
    while index:
        index -= 1  # 'a' needs to be used as next 'decimal' unit when reaching 'z':  ..., 'y', 'z', 'aa', 'ab', ...
        left = index % 26
        index = index // 26
        alphanum = ascii_lowercase[left] + alphanum
    return alphanum


def alphabeticalToDecimal(alpha):
    """
    Converts str to an int index.

    e.g.: 'a' -> 0, 'b' -> 1, 'c' -> 2, 440414 -> 'yama'
    :param alpha: str
    :return: int
    """
    assert isinstance(alpha, string_types) and alpha
    from string import ascii_lowercase
    index = -1
    for step, letter in reversed(list(enumerate(reversed(alpha)))):
        letter_index = ascii_lowercase.index(letter)
        index += (letter_index+1)*(26**step)
    return index


def decimalToRoman(index):
    """Converts int to roman numeral"""
    assert isinstance(index, int) and index > 0
    roman = [(1000, 'M'), (900, 'CM'),
             (500, 'D'), (400, 'CD'),
             (100, 'C'), (90, 'XC'),
             (50, 'L'), (40, 'XL'),
             (10, 'X'), (9, 'IX'),
             (5, 'V'), (4, 'IV'),
             (1, 'I')]
    roman_num = ''
    while index:
        for value, num in roman:
            if index >= value:
                roman_num += num
                index -= value
                break
    return roman_num


def romanToDecimal(roman):
    """Converts roman numeral to int"""
    assert isinstance(roman, string_types) and roman
    values = [('M', 1000), ('CM', 900),
              ('D', 500), ('CD', 400),
              ('C', 100), ('XC', 90),
              ('L', 50), ('XL', 40),
              ('X', 10), ('IX', 9),
              ('V', 5), ('IV', 4),
              ('I', 1)]
    roman = roman.upper()
    diff = set(roman) - set([x for x, _ in values])
    if diff:
        raise ValueError("Only valid roman character accepted; found : {}".format(list(diff)))

    result = 0
    while roman:
        for sign, value in values:
            if roman.startswith(sign):
                result += value
                roman = roman[len(sign):]
                break
    return result
