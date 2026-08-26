# 담당: A
# 합성 거래데이터(data/transactions.json, data/demo_cases.json)를 읽어
# 잠재적 피해 사례 목록/상세를 제공한다.

import json
import os

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")


def _load_json(filename):
    path = os.path.join(DATA_DIR, filename)
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def list_detected_cases():
    return _load_json("demo_cases.json")


def get_case(case_id):
    cases = list_detected_cases()
    return next((c for c in cases if c.get("case_id") == case_id), None)


def list_transactions():
    return _load_json("transactions.json")
