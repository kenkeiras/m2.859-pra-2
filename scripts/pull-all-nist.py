#!/usr/bin/env python

import requests
import time
import os
import logging
import json
import tempfile
import shutil
import datetime

SLEEP_TIME = 6 # According to https://nvd.nist.gov/developers/api-workflows
NIST_API_KEY = os.getenv('NIST_API_KEY')
NIST_RESULT_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..",
    "data",
    "nist",
    "data.json",
)

def swap_in_data(filepath, data):
    with tempfile.NamedTemporaryFile(mode='wt', delete=False) as tmpf:
        tmpf.write(data)
        tmp_name = tmpf.name
    shutil.move(tmp_name, filepath)


def main():
    assert NIST_API_KEY is not None
    session = requests.session()

    all_data = []

    t0 = datetime.datetime.now()
    start_index = 0
    total_results = None
    while total_results is None or start_index < total_results:
        now = datetime.datetime.now()
        logging.info('[{}%] startIndex={} of {} (ETA: {})'.format(
            "{:.2f}".format(start_index * 100 / total_results)
            if total_results is not None
            else '???',
            start_index,
            total_results or '???',
            (now - t0) / start_index * (total_results - start_index)
            if start_index > 0
            else '???'
        ))
        res = session.get(
            'https://services.nvd.nist.gov/rest/json/cves/2.0?startIndex={}'.format(
                start_index
            ),
            headers={
                'apiKey': NIST_API_KEY,
            }
        )
        data = res.json()
        total_results = data['totalResults']
        all_data.extend(data['vulnerabilities'])
        start_index += len(data['vulnerabilities'])
        time.sleep(SLEEP_TIME)

    swap_in_data(NIST_RESULT_FILE, json.dumps(data, indent=4))


if __name__ == '__main__':
    if NIST_API_KEY is None:
        print("Define environment variable NIST_API_KEY")
        exit(1)

    logging.basicConfig(level=logging.INFO)
    try:
        main()
        exit(0)
    except Exception:
        logging.exception("Error pulling NIST data")
        exit(2)
