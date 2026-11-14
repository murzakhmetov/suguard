"""Build the paired PPG/CGM table from the BIG IDEAs dataset (run in Colab).

Download (~ several GB) first, either from PhysioNet:
    wget -r -N -c -np -nH --cut-dirs=3 -P big-ideas https://physionet.org/files/big-ideas-glycemic-wearable/1.1.2/
or from the AWS open-data mirror (faster, no account needed):
    pip install awscli
    aws s3 sync --no-sign-request s3://physionet-open/big-ideas-glycemic-wearable/1.1.2/ big-ideas

Then:
    python scripts/build_bigideas_table.py --root big-ideas --out data/bigideas_paired.parquet --every-n 3
    python scripts/train_glucose.py --table data/bigideas_paired.parquet --out models --name bigideas
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from suguard_ml.data.bigideas import build_table  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True, help="folder holding 001..016 and Demographics.csv")
    ap.add_argument("--out", default="data/bigideas_paired.parquet")
    ap.add_argument("--every-n", type=int, default=3, help="use every n-th CGM reading (1 = every 5 min)")
    a = ap.parse_args()
    df = build_table(a.root, every_n=a.every_n)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(a.out) if a.out.endswith(".parquet") else df.to_csv(a.out, index=False)
    print(f"{len(df)} rows, {df.subject_id.nunique() if len(df) else 0} subjects -> {a.out}")


if __name__ == "__main__":
    main()
