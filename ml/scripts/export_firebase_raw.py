"""Export raw bracelet windows from Firebase RTDB to JSONL for training.

    python scripts/export_firebase_raw.py --db https://<project>.firebasedatabase.app --device SG-001 --out windows.jsonl

Reads rawPpg/<device>/<ts> written by firmware/suguard_raw_stream (MODE_COLLECT).
Pass --auth <token> if the database rules require authentication (they should).
"""

from __future__ import annotations

import argparse
import json
import urllib.parse
import urllib.request


def get(url: str):
    with urllib.request.urlopen(url, timeout=60) as r:
        return json.loads(r.read().decode())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--device", required=True)
    ap.add_argument("--out", default="windows.jsonl")
    ap.add_argument("--auth", default=None)
    a = ap.parse_args()
    q = {"shallow": "true"}
    if a.auth:
        q["auth"] = a.auth
    base = f"{a.db.rstrip('/')}/rawPpg/{urllib.parse.quote(a.device)}"
    keys = sorted((get(f"{base}.json?{urllib.parse.urlencode(q)}") or {}).keys())
    q.pop("shallow")
    n = 0
    with open(a.out, "w") as fh:
        for k in keys:
            w = get(f"{base}/{k}.json?{urllib.parse.urlencode(q)}")
            if w and "red" in w and "ir" in w:
                fh.write(json.dumps(w) + "\n")
                n += 1
    print(f"{n} windows -> {a.out}")


if __name__ == "__main__":
    main()
