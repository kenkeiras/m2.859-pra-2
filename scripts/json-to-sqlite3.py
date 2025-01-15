#!/usr/bin/env python3

import json
import sys
import tqdm
import sqlite3
import os

COL_PATH_JOINER = '__'

def merge_schemas(s1, s2):
    if s1 in (int, str, float):
        assert s1 == s2, "Expected similar types, found: {} | {}".format(s1, s2)
        return s1

    assert type(s1) == type(s2)
    if isinstance(s1, list):
        if len(s1) == 0:
            return s2
        elif len(s2) == 0:
            return s1
        assert len(s1) == 1
        assert len(s2) == 1

        return [merge_schemas(s1[0], s2[0])]

    if isinstance(s1, dict):
        result = {}
        for k in set(s1.keys()) | set(s2.keys()):
            if k in s1 and k not in s2:
                result[k] = s1[k]
            elif k in s2 and k not in s1:
                result[k] = s2[k]
            else:
                assert k in s1 and k in s2
                result[k] = merge_schemas(s1[k], s2[k])
        return result

    raise ValueError('Unknown schema type: {}'.format(s1))


def get_data_schema(data):
    if isinstance(data, int):
        # We're dealing with json here
        return float
    elif isinstance(data, str):
        return str
    elif isinstance(data, float):
        return float
    elif isinstance(data, list):
        subschemas = [
            get_data_schema(item)
            for item in data
        ]
        if len(subschemas) == 0:
            return []
        schema = subschemas[0]
        for subschema in subschemas[1:]:
            schema = merge_schemas(schema, subschema)
        return [schema]
    elif isinstance(data, dict):
        assert all([isinstance(k, str) for k in data.keys()])
        schema = {}
        for k, v in data.items():
            schema[k] = get_data_schema(v)
        return schema
    else:
        raise ValueError('Unknown type: {}'.format(type(data)))

def get_schema_from_file(fpath, file_lines):
    schema = {}
    count = 0
    with open(fpath) as f:
        for line in tqdm.tqdm(
                f,
                total=file_lines,
                unit='l',
                desc='[1/2] Reading file & generating schema'
        ):
            data = json.loads(line)
            data_schema = get_data_schema(data)
            schema = merge_schemas(schema, data_schema)
            count += 1
            # if count >= 1000*10:
            #     break

    return schema

def flatten_schema(schema):
    def recur(node, path):
        if node in (str, float):
            _type = 'TEXT'
            if node == float:
                _type = 'NUMBER'
            yield (path, _type)
        elif isinstance(node, list):
            for idx, it in enumerate(node):
                assert idx < 1
                yield from recur(it, path + (idx,))
        elif isinstance(node, dict):
            for dk, dv in node.items():
                yield from recur(dv, path + (dk,))

    for k, v in schema.items():
        yield from recur(v, (k,))

def generate_create_table_from_schema(schema, main_table_name, pk_col) -> list[str]:
    assert '[' not in main_table_name
    assert ']' not in main_table_name
    first = True

    ddl = []

    tables = {}

    # Group paths
    graph_paths = []
    for col_path, col_type in flatten_schema(schema):
        graph_path = [(main_table_name, [])]
        for idx, col in enumerate(col_path):
            if isinstance(col, int):
                new_table_name = main_table_name + COL_PATH_JOINER + COL_PATH_JOINER.join(
                    (str(x) for x in col_path[:idx])
                )
                graph_path.append((new_table_name, []))
            else:
                graph_path[-1][1].append(col)
        graph_paths.append((graph_path, col_type))

    # Prepare tables
    graph_paths = sorted(graph_paths, key=lambda x: len(x[0]))
    parent_graph = {}
    for graph_path, col_type in graph_paths:
        inner = None
        for idx, tab in enumerate(graph_path):
            table, tab_path = tab
            if table not in tables:
                tables[table] = []

                # if table != main_table_name:
                #     tables[table].append(('__id__', 'int', ' PRIMARY KEY'))

                parent_graph[table] = inner
            inner = table

            if idx + 1 == len(graph_path):
                tables[table].append((COL_PATH_JOINER.join(graph_path[-1][1]), col_type, ''))

    for tab_name, fields in tables.items():
        tab_ddl = [f'CREATE TABLE {tab_name} (']

        first = True
        for field, _type, notes in fields:
            if not first:
                tab_ddl[-1] += ','
            else:
                first = False

            if tab_name == main_table_name and field == pk_col:
                notes += ' PRIMARY KEY'

            tab_ddl.append(f'{field or "__value__"} {_type}{notes}')

        if tab_name != main_table_name:
            assert table in parent_graph
            tab_ddl[-1] += ','
            tab_ddl.append('__parent__ INT,')
            tab_ddl.append('FOREIGN KEY(__parent__) REFERENCES {}(rowid)'.format(
                parent_graph[table],
            ))

        tab_ddl.append(');')
        ddl.append('\n'.join(tab_ddl))
    return ddl

def build_db_with_schema(db_path, ddl):
    db = sqlite3.connect(db_path)
    for stmt in ddl:
        db.execute(stmt)
        db.commit()
    return db

def count_lines(fpath):
    count = 0
    with open(sys.argv[1]) as f:
        for _ in f:
            count += 1
    return count

def ingest_row_in_db(data, cursor, main_table_name):
    def get_field_from_path(path):
        return COL_PATH_JOINER.join(path)

    def recur(node, path, parent_row_id, table_name):
        nonlocal ingestion_fields
        nonlocal ingestion_values
        if isinstance(node, str) or isinstance(node, int) or isinstance(node, float):
            ingestion_fields.append(get_field_from_path(path))
            ingestion_values.append(node)

        elif isinstance(node, list):
            for it in node:
                # Create row
                base_table_name = table_name
                if base_table_name != main_table_name:
                    base_table_name += COL_PATH_JOINER + '0'
                inner_table_name = base_table_name + COL_PATH_JOINER + get_field_from_path(path)

                cursor.execute(f'INSERT INTO {inner_table_name} (__parent__) VALUES (?);',
                               (parent_row_id,))
                inner_row_id = cursor.lastrowid

                outer_ingestion_fields = ingestion_fields
                outer_ingestion_values = ingestion_values

                ingestion_fields = []
                ingestion_values = []

                if isinstance(it, dict):
                    for k, v in it.items():
                        recur(v, (k,), inner_row_id, inner_table_name)
                else:
                    assert isinstance(it, str) or isinstance(it, float), "Unexpected type: {}".format(type(it))
                    ingestion_fields = ['__value__']
                    ingestion_values = [it]

                query = f'INSERT INTO {inner_table_name} ({", ".join(ingestion_fields)}) VALUES ({", ".join(["?"] * len(ingestion_values))});'
                if not ingestion_values:
                    # TODO: There's an issue here :\
                    # print("N", node)
                    pass
                else:
                    cursor.execute(query, ingestion_values)

                ingestion_fields = outer_ingestion_fields
                ingestion_values = outer_ingestion_values

        elif isinstance(node, dict):
            for k, v in node.items():
                recur(v, path + (k,), parent_row_id, table_name)

    ingestion_fields = []
    ingestion_values = []
    # First round with atomic values
    for k, v in data.items():
        if isinstance(v, str) or isinstance(v, int) or isinstance(v, float):
            ingestion_fields.append(k)
            ingestion_values.append(v)

    # Manually interpolating data into SQL statements is dangerous!
    query = f'INSERT INTO {main_table_name} ({", ".join(ingestion_fields)}) VALUES ({", ".join(["?"] * len(ingestion_values))});'
    cursor.execute(query, ingestion_values)
    main_row_id = cursor.lastrowid

    ingestion_fields = []
    ingestion_values = []
    for k, v in data.items():
        recur(v, (k,), main_row_id, main_table_name)

def ingest_in_db(fpath, db, main_table_name, file_lines):
    count = 0
    cursor = db.cursor()
    with open(fpath) as f:
        for line in tqdm.tqdm(
                f,
                total=file_lines,
                unit='l',
                desc='[2/2] Ingesting data'
        ):
            data = json.loads(line)
            ingest_row_in_db(data, cursor, main_table_name)
            count += 1
            # if count >= 1000*10:
            #     break
    cursor.close()
    db.commit()

if __name__ == '__main__':
    if len(sys.argv) != 5:
        print("{} <input.jsonl> <output.sqlite> <table name> <public key column>".format(sys.argv[0]))
        exit(0)

    if os.path.exists(sys.argv[2]):
        print("Output file {} already exists. Cowardly stopping".format(sys.argv[2]))
        exit(0)

    file_lines = count_lines(sys.argv[1])
    schema = get_schema_from_file(sys.argv[1], file_lines)
    ddl = generate_create_table_from_schema(schema, sys.argv[3], sys.argv[4])
    db = build_db_with_schema(sys.argv[2], ddl)
    ingest_in_db(sys.argv[1], db, sys.argv[3], file_lines)
    db.close()
