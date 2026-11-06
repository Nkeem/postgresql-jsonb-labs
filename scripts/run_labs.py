"""Import the demo database and run one or both labs through psql."""
from __future__ import annotations

import argparse
import subprocess
import sys

from postgres import Postgres, ROOT


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", choices=("native", "docker"), default="native")
    parser.add_argument("--lab", choices=("1", "2", "all"), default="all")
    args = parser.parse_args()
    postgres = Postgres(args.backend)
    databases = postgres.query_json("SELECT 1 AS present FROM pg_database WHERE datname = 'demo'", "postgres")
    if not databases:
        if args.lab in {"1", "all"}:
            dump = ROOT / "lab1/source/demo-small-pg18.sql"
            if not dump.is_file():
                parser.error("Run python scripts/prepare_demo.py before importing lab 1.")
            print("Importing the 2017 demo database...", flush=True)
            postgres.execute(path=dump, database="postgres")
        else:
            postgres.execute(sql="CREATE DATABASE demo", database="postgres")
    if args.lab in {"1", "all"}:
        source = postgres.query_json("SELECT to_regclass('bookings.bookings')::text AS name")
        if source[0]["name"] is None:
            parser.error("The existing demo database has no bookings schema; use a fresh PostgreSQL instance for lab 1.")
        print("Running lab 1...", flush=True)
        postgres.execute(path=ROOT / "lab1/lab1.sql")
    if args.lab in {"2", "all"}:
        print("Running lab 2...", flush=True)
        postgres.execute(path=ROOT / "lab2/01_load_data.sql")
        postgres.execute(path=ROOT / "lab2/02_queries.sql")
    print("Done. Database: demo. See the lab READMEs for verification commands.")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, subprocess.CalledProcessError) as error:
        print(f"Database run failed: {error}", file=sys.stderr)
        sys.exit(1)
