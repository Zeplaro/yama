# encoding: utf8


def mult_list(list_a, list_b):
    return [x*y for x, y in zip(list_a, list_b)]


def decimalToAlpha_old(index):
    """Very Slow"""
    from string import ascii_lowercase
    alphanum = ['a']
    reste = index
    while reste:
        for i, l in enumerate(alphanum[:]):
            if l != 'z':
                alpha_index = ascii_lowercase.index(l)
                alphanum[i] = ascii_lowercase[alpha_index+1]
                break
            else:
                alphanum[i] = 'a'
            if i == len(alphanum)-1:
                alphanum.append('a')
        reste -= 1

    result = ''
    for i in alphanum[::-1]:
        result += i
    return result


def decimalToAlphabetical(index):
    from string import ascii_lowercase
    alphanum = ''
    index += 1  # because alphabet hase no 0 and starts with 'a'
    while index:
        # v alphabet has no 0 and 'a' needs to be used as next 'decimal' unit when reaching 'z':  'y', 'z', 'aa', 'ab'
        index -= 1
        reste = index % 26
        index = index // 26
        alphanum = ascii_lowercase[reste] + alphanum
    return alphanum
