"""Export raw bracelet windows from Firebase to windows.jsonl for training.

    python scripts/export_firebase_raw.py --db https://<project>.firebasedatabase.app \
        --email participant@example.com --user u17 --out windows.jsonl

Reads ``rawPpg/<uid>/<key>`` written by the firmware when ``upload_raw`` is on
(``<uid>`` is derived from the account e-mail exactly as in the app and the
firmware). Pass ``--auth <token>`` if the database rules require it.
Output format: ml/docs/DATA_COLLECTION.md.
"""

from __future__ import annotations

import argparse
import json
import urllib.parse
import urllib.request


def email_to_uid(email: str) -> str:
    """FirebaseService._emailToUid of the Flutter app / sg_email_to_uid of the firmware."""
    return email.lower().strip().replace(".", "_dot_").replace("@", "_at_")


def get(url: str):
    with urllib.request.urlopen(url, timeout=60) as r:
        return json.loads(r.read().decode())


def to_record(w: dict, user: str) -> dict:
    return {"user_id": user, "device_id": w.get("device"), "ts": w["ts"], "fs": w.get("fs", 50.0),
            "seq": w.get("seq"), "temp_c": w.get("temp_c"), "led_red": w.get("ledRed"), "led_ir": w.get("ledIr"),
            "flags": w.get("flags", 0), "red": w["red"], "ir": w["ir"]}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", required=True, help="database URL")
    ap.add_argument("--email", required=True, help="account e-mail configured on the bracelet ('user' setting)")
    ap.add_argument("--user", required=True, help="participant id to write into the file")
    ap.add_argument("--out", default="windows.jsonl")
    ap.add_argument("--auth", default=None)
    a = ap.parse_args()

    base = f"{a.db.rstrip('/')}/rawPpg/{urllib.parse.quote(email_to_uid(a.email), safe='')}"
    query = {"auth": a.auth} if a.auth else {}
    keys = sorted((get(f"{base}.json?{urllib.parse.urlencode({**query, 'shallow': 'true'})}") or {}).keys())
    n = 0
    with open(a.out, "w") as fh:
        for key in keys:
            w = get(f"{base}/{urllib.parse.quote(key, safe='')}.json?{urllib.parse.urlencode(query)}")
            if w and "red" in w and "ir" in w:
                fh.write(json.dumps(to_record(w, a.user)) + "\n")
                n += 1
    print(f"{n} windows -> {a.out}")


if __name__ == "__main__":
    main()
