# encoding: utf8

"""
Contains non maya specific utils.
"""


def multList(list_a, list_b):
    """
    Zips 'list_a' items with 'list_b' items and multiplies them together
    :param list_a: list of digits
    :param list_b: list of digits
    :return: list of digits
    """
    return [x*y for x, y in zip(list_a, list_b)]


def decimalToAlphabetical(index):
    """
    Converts int to an alphabetical index. e.g.: 0 -> 'a', 1 -> 'b', 2 -> 'c', 'yama' -> 440414
    :param index: int
    :return: str
    """
    assert isinstance(index, int) and index >= 0
    from string import ascii_lowercase
    alphanum = ''
    index += 1  # because alphabet hase no 0 and starts with 'a'
    while index:
        index -= 1  # 'a' needs to be used as next 'decimal' unit when reaching 'z':  ..., 'y', 'z', 'aa', 'ab', ...
        reste = index % 26
        index = index // 26
        alphanum = ascii_lowercase[reste] + alphanum
    return alphanum


def alphabeticalToDecimal(alpha):
    """
    Converts str to an int index. e.g.: 'a' -> 0, 'b' -> 1, 'c' -> 2, 440414 -> 'yama'
    :param alpha: str
    :return: int
    """
    assert isinstance(alpha, str) and alpha
    from string import ascii_lowercase
    index = -1
    steps = [(x, y) for x, y in enumerate(alpha[::-1])]
    for step, letter in steps[::-1]:
        letter_index = ascii_lowercase.index(letter)
        index += (letter_index+1)*(26**step)
    return index


def decimalToRoman(index):
    """Converts an int to a roman numerical index"""
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
