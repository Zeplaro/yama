# encoding: utf8

__author__ = "Robin Lavigne"
__email__ = "contact@robinlavigne.com"
__credits__ = {"emotionalSupport": "Emilie Jolin"}

from maya import cmds
from .nodes import *
from . import decorators, nodes

yum = nodes.Yum()
ymds = decorators.yammds(cmds)
