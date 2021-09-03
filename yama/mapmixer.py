# encoding: utf8

from maya import cmds


def get_sym_data(axis='x'):
    obj = cmds.ls(sl=True)[0]
    r_vtxs = cmds.select(sys=1)
    l_vtxs = cmds.select(sys=2)
    mid_vtxs = cmds.select(sys=0)
    table = SymTable(axis=axis)
    for x, y in zip(l_vtxs, r_vtxs):
        table[comp_index(x)] = comp_index(y)
    table.mids = [comp_index(x) for x in mid_vtxs]
    return table


def comp_index(comp):
    return int(comp.split('[')[-1][:-1])


def mult_list(list_a, list_b):
    return [x*y for x, y in zip(list_a, list_b)]


def mirror_map(deformer, attr, table):
    # TODO : Average mid vtxs
    for l_vtx in table:
        l_weight = cmds.getAttr(deformer + '.' + attr.format(l_vtx))
        cmds.setAttr(deformer + '.' + attr.format(table[l_vtx]), l_weight)


def flip_map(deformer, attr, table):
    for l_vtx in table:
        r_vtx = table[l_vtx]
        l_weight = cmds.getAttr(deformer + '.' + attr.format(l_vtx))
        r_weight = cmds.getAttr(deformer + '.' + attr.format(r_vtx))
        cmds.setAttr(deformer + '.' + attr.format(table[l_vtx]), r_weight)
        cmds.setAttr(deformer + '.' + attr.format(table[r_vtx]), l_weight)


def mirror_pos(obj, table):
    for l_vtx in table:
        l_pos = cmds.xform('{}.vtx[{}]'.format(obj, l_vtx), q=True, t=True, os=True)
        r_pos = mult_list(l_pos, table.axis_mult)
        cmds.xform('{}.vtx[{}]'.format(obj, table[l_vtx]), t=r_pos, os=True)
    for mid in table.mids:
        cmds.xform('{}.vtx[{}]'.format(obj, mid), t=0.0, os=True)


def flip_pos(obj, table):
    for l_vtx in table:
        l_pos = cmds.xform('{}.vtx[{}]'.format(obj, l_vtx), q=True, t=True, os=True)
        r_pos = cmds.xform('{}.vtx[{}]'.format(obj, table[l_vtx]), q=True, t=True, os=True)

        cmds.xform('{}.vtx[{}]'.format(obj, l_vtx), t=r_pos, os=True)
        cmds.xform('{}.vtx[{}]'.format(obj, table[l_vtx]), t=l_pos, os=True)

    for mid in table.mids:
        pos = cmds.xform('{}.vtx[{}]'.format(obj, mid), q=True, t=True, os=True)
        pos = mult_list(pos, table.axis_mult)
        cmds.xform('{}.vtx[{}]'.format(obj, mid), t=pos, os=True)


def get_vtxs_positions(obj, precision=4):
    vtxs = cmds.ls(obj + '.vtx[*]', fl=True)
    positions = {}
    for vtx in vtxs:
        index = int(vtx.split('[')[-1][:-1])
        pos = cmds.xform(vtx, q=True, t=True, os=True)
        positions[index] = [round(x, precision) for x in pos]
    return positions


class SymTable(dict):
    def __init__(self, axis='x'):
        super(SymTable, self).__init__()
        self.axis = axis
        self._axis_mult = [1, 1, 1]
        self._axis_mult[('x', 'y', 'z').index(axis)] *= -1
        self.mids = []

    @property
    def axis_mult(self):
        return self._axis_mult
