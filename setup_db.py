"""Download and prepare the NYC Open Data collision database for the app."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

import pandas as pd

CSV_URL = "https://data.cityofnewyork.us/api/views/h9gi-nx95/rows.csv?accessType=DOWNLOAD"
DB_PATH = Path(os.getenv("NYC_CRASH_DB", "data/nyc_crashes.sqlite"))
CHUNK_SIZE = 100_000


def normalize_column(name: str) -> str:
    return (
        name.strip().lower().replace(" ", "_").replace("/", "_")
        .replace("-", "_").replace("__", "_")
    )


def main() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if DB_PATH.exists():
        DB_PATH.unlink()
    print(f"Downloading collision data and building {DB_PATH} …")
    total = 0
    for chunk in pd.read_csv(CSV_URL, chunksize=CHUNK_SIZE, low_memory=False):
        chunk.columns = [normalize_column(name) for name in chunk.columns]
        if "crash_date" not in chunk or "crash_time" not in chunk:
            raise RuntimeError("The NYC Open Data export is missing crash date/time columns.")
        crash_dt = pd.to_datetime(
            chunk["crash_date"].astype("string") + " " + chunk["crash_time"].astype("string"),
            format="mixed", errors="coerce",
        )
        chunk["crash_datetime"] = crash_dt
        chunk["crash_date"] = crash_dt.dt.strftime("%Y-%m-%d")
        chunk["crash_year"] = crash_dt.dt.year.astype("Int64")
        chunk["crash_month"] = crash_dt.dt.month.astype("Int64")
        chunk["crash_hour"] = crash_dt.dt.hour.astype("Int64")
        for column in ("borough", "on_street_name", "cross_street_name", "off_street_name"):
            if column in chunk:
                chunk[column] = chunk[column].astype("string").str.strip().str.upper()
        if "on_street_name" in chunk and "cross_street_name" in chunk:
            chunk["intersection"] = (
                chunk["on_street_name"].fillna("") + " @ " + chunk["cross_street_name"].fillna("")
            ).str.strip(" @")
            chunk.loc[chunk["intersection"].eq(""), "intersection"] = pd.NA
        chunk = chunk.dropna(subset=["crash_datetime"])
        # SQLite can store timestamps as ISO strings; pandas nullable integers are converted to floats.
        for column in chunk.select_dtypes(include="datetime").columns:
            chunk[column] = chunk[column].astype("string")
        chunk.to_sql("crashes", sqlite3.connect(DB_PATH), if_exists="append", index=False, chunksize=10_000)
        total += len(chunk)
        print(f"Loaded {total:,} rows", end="\r", flush=True)
    with sqlite3.connect(DB_PATH) as connection:
        connection.execute("CREATE INDEX IF NOT EXISTS idx_crashes_date ON crashes(crash_date)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_crashes_year_borough ON crashes(crash_year, borough)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_crashes_intersection ON crashes(intersection)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_crashes_hour ON crashes(crash_hour)")
    print(f"\nDone. Loaded {total:,} records into {DB_PATH}.")


if __name__ == "__main__":
    main()
