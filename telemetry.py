"""
Export Supabase tables to local CSV/Parquet files.

Usage:
  export SUPABASE_URL="https://<your-ref>.supabase.co"
  export SUPABASE_KEY="<service_or_readonly_key>"
  python supabase_export.py

Outputs:
  data/exports/<table>-YYYYMMDD_HHMMSS.csv
  data/exports/<table>-YYYYMMDD_HHMMSS.parquet   (if PARQUET=1)
"""

import os
import time
from datetime import datetime
from typing import List, Dict, Any, Optional

import pandas as pd
from supabase import create_client

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
TABLES = os.environ.get("TABLES", "sessions,questionnaires,conversations").split(",")


# Export folder
OUT_DIR = os.path.join("data", "exports")

# Page size for PostgREST range queries
PAGE_SIZE = int(os.environ.get("PAGE_SIZE", "2000"))


def _assert_env():
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise SystemExit(
            "Missing SUPABASE_URL or SUPABASE_KEY env vars.\n"
            "Set them, e.g.:\n"
            '  export SUPABASE_URL="https://<your-ref>.supabase.co"\n'
            '  export SUPABASE_KEY="<your-key>"'
        )


def connect():
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def fetch_all_rows(db, table: str) -> List[Dict[str, Any]]:
    """
    Pull all rows using range pagination to avoid 1k row caps.
    """
    rows: List[Dict[str, Any]] = []
    start = 0
    while True:
        end = start + PAGE_SIZE - 1
        # PostgREST range
        res = db.table(table).select("*").range(start, end).execute()
        data = res.data or []
        rows.extend(data)
        if len(data) < PAGE_SIZE:
            break
        start += PAGE_SIZE
        # polite pacing
        time.sleep(0.05)
    return rows


def normalise(df: pd.DataFrame) -> pd.DataFrame:
    """
    Flatten any JSON columns (answers, scenario, rag_trace, meta) into top-level columns.
    Keeps originals too (rename with _json).
    """
    if df.empty:
        return df
    # detect dict-like columns
    json_cols = [c for c in df.columns if df[c].map(lambda x: isinstance(x, dict)).any()]
    for c in json_cols:
        flat = pd.json_normalize(df[c]).add_prefix(f"{c}.")
        df = df.drop(columns=[c]).join(flat)
        # keep original as string for reference
        df[f"{c}_json"] = df[c] if c in df.columns else None
    return df


def export_table(db, table: str, ts: str):
    os.makedirs(OUT_DIR, exist_ok=True)
    rows = fetch_all_rows(db, table)
    df = pd.DataFrame(rows)
    # optional flatten
    df = normalise(df)

    csv_path = os.path.join(OUT_DIR, f"{table}-{ts}.csv")
    df.to_csv(csv_path, index=False)
    print(f"✅ Wrote {len(df):>5} rows to {csv_path}")

    if WRITE_PARQUET:
        pq_path = os.path.join(OUT_DIR, f"{table}-{ts}.parquet")
        df.to_parquet(pq_path, index=False)
        print(f"✅ Wrote Parquet to {pq_path}")


def main():
    _assert_env()
    db = connect()
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    for table in [t.strip() for t in TABLES if t.strip()]:
        try:
            export_table(db, table, ts)
        except Exception as e:
            print(f" Failed exporting {table}: {e}")


if __name__ == "__main__":
    main()
