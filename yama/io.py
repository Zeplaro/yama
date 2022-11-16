# encoding: utf8

import json


def exportData(data, path):
    with open(path, 'w') as outfile:
        json.dump(data, outfile)


def importData(path):
    with open(path) as json_file:
        data = json.load(json_file)
    return data
