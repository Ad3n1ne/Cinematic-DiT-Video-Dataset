#!/usr/bin/env python3
"""Load the dataset metadata table from a local file."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("metadata", type=Path, help="Path to metadata.parquet")
    args = parser.parse_args()

    df = pd.read_parquet(args.metadata)
    print(df.head())
    print()
    print("rows:", len(df))
    print("by resolution:")
    print(df["resolution"].value_counts().sort_index())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

