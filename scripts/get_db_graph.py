#!/usr/bin/env python3

import re
import subprocess
import sys
import json

COL_PATH_JOINER = '__'
CREATE_TABLE_LINE_RE = re.compile(r'\s*CREATE TABLE(?: IF NOT EXISTS)?\s+"?(.+?)"?\s*\(\s*$')
CREATE_TABLE_FIELD_LINE_RE = re.compile('^\s*([a-zA-Z_]+)\s+([A-Z]+)\s*( PRIMARY KEY)?\s*,?\s*$')

def get_table_names(fpath):
    output = subprocess.check_output(
        ['sqlite3', fpath, '.schema']
    ).decode()
    create_table_lines = [
        line for line in output.split('\n') if 'CREATE TABLE' in line
    ]

    table_names = [
        CREATE_TABLE_LINE_RE.match(line).group(1)
        for line in create_table_lines
    ]

    return table_names

def rec_join_key_names(data):
    return {
        COL_PATH_JOINER.join(k): rec_join_key_names(v)
        for k, v in data.items()
    }

def get_table_hierarchy(table_names):
    table_names = sorted(table_names, key=lambda n: len(n))
    hierarchy = {}
    positions = {}
    for tab in table_names:
        tab_chunks = tuple(tab.split(COL_PATH_JOINER))  # Tuple so it's hashable
        if len(tab_chunks) == 1:
            # Non-nested tabs
            positions[tab_chunks] = hierarchy[tab_chunks] = {}
            continue

        for sz in range(len(tab_chunks) - 1, 0, -1):
            parent_candidate = tab_chunks[:sz]
            if parent_candidate in positions:
                break
        else:
            raise ValueError('Parent candidate for ‘{}’ not found'.format(tab_chunks))

        positions[tab_chunks] = positions[parent_candidate][tab_chunks] = {}
        
    return rec_join_key_names(hierarchy)

def get_fields_in_table(tab_name, fpath):
    output = subprocess.check_output(
        ['sqlite3', fpath, '.schema ' + tab_name]
    ).decode()

    fields = []
    for line in output.split('\n'):
        m = CREATE_TABLE_FIELD_LINE_RE.match(line)
        if m is not None:
            fields.append({ "name": m.group(1), "type": m.group(2), "primary_key": m.group(3) == 'PRIMARY KEY' })

    return fields


def rec_fill_fields_for_tables(hierarchy, fpath):
    for tab_name, contents in list(hierarchy.items()):
        rec_fill_fields_for_tables(hierarchy[tab_name], fpath)
        hierarchy[tab_name]['__fields__'] = get_fields_in_table(tab_name, fpath)

    return hierarchy

def hierarchy_to_graphviz(hierarchy):
    idx = 0
    def render_node(fields, name):
        nonlocal idx

        node_name = 'n_' + str(idx)
        idx += 1

        label = ["<name> {}".format(name.upper())]
        label.append('')  # Separation between name and fields
        for field in fields:
            fname = field['name']
            ftype = field['type']
            fispk = field['primary_key']

            if fname == '__parent__':
                # Internal fields
                continue

            label.append('{}{}'.format(
                '<pk> ' if fispk else '',
                fname,
            ))

        node_data = [node_name, ' [']
        node_data.append('label="{}"'.format('|'.join(label)))
        node_data.append(', shape="record"];')
        result.append(''.join(node_data))
        return node_name

    def rec(node, name, parent):
        node_name = render_node(node['__fields__'], name)
        if parent is not None:
            result.append('{} -> {}'.format(node_name, parent))
        for tab, contents in node.items():
            if tab != '__fields__':
                rec(contents, tab, node_name)

    result = ['digraph {', 'rankdir=LR;']
    for tab, contents in hierarchy.items():
        rec(contents, tab, None)
    result.append('}')
    return '\n'.join(result)

if __name__ == '__main__':
    if len(sys.argv) != 3:
        print("{} <input.sqlite> <out.dot>".format(sys.argv[0]))
        exit(0)
    
    table_names = get_table_names(sys.argv[1])
    hierarchy = get_table_hierarchy(table_names)
    hierarchy = rec_fill_fields_for_tables(hierarchy, sys.argv[1]) 
    print(json.dumps(hierarchy, indent=4), file=sys.stderr)
    with open(sys.argv[2], 'wt') as f:
        print(hierarchy_to_graphviz(hierarchy), file=f)