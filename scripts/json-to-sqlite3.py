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
            if count >= 1000*10:
                break

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

def generate_create_table_from_schema(schema, table_name, pk_col):
    assert '[' not in table_name
    assert ']' not in table_name
    chunks = [f'CREATE TABLE {table_name} (']
    first = True
    for col_path, col_type in flatten_schema(schema):
        if not first:
            chunks[-1] += ','
        else:
            first = False

        notes = ''
        if len(col_path) == 1 and col_path[0] == pk_col:
            notes += ' PRIMARY KEY'
        col_name = COL_PATH_JOINER.join([str(x) for x in col_path])
        chunks.append(f'{col_name} {col_type}{notes}')

    chunks.append(');')
    return '\n'.join(chunks)

def build_db_with_schema(db_path, ddl):
    db = sqlite3.connect(db_path)
    db.execute(ddl)
    db.commit()
    return db

def count_lines(fpath):
    count = 0
    with open(sys.argv[1]) as f:
        for _ in f:
            count += 1
    return count

def ingest_row_in_db(data, cursor):
    def recur(node, path):
        if isinstance(node, str) or isinstance(node, int) or isinstance(node, float):
            ingestion_fields.append(COL_PATH_JOINER.join([str(x) for x in path]))
            ingestion_values.append(node)
        elif isinstance(node, list):
            pass # TODO: Build separate table
        elif isinstance(node, dict):
            for k, v in node.items():
                recur(v, path + (k,))

    ingestion_fields = []
    ingestion_values = []
    for k, v in data.items():
        recur(v, (k,))
    print()
    print(ingestion_values)
    raise NotImplementedError()

def ingest_in_db(fpath, db, file_lines):
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
            ingest_row_in_db(data, cursor)
            count += 1
            if count >= 1000*10:
                break

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
    ingest_in_db(sys.argv[1], db, file_lines)
