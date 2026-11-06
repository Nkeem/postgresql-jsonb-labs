"""Verify lab 1 invariants, safe repeated runs, and all five lab 2 query results."""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys

from postgres import Postgres, ROOT


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def fingerprint(postgres: Postgres, table: str, key: str) -> list[dict]:
    return postgres.query_json(
        f"SELECT count(*) AS records, md5(string_agg(md5(data::text), '' ORDER BY {key})) AS digest FROM {table}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", choices=("native", "docker"), default="native")
    parser.add_argument("--lab", choices=("1", "2", "all"), default="all")
    args = parser.parse_args()
    postgres = Postgres(args.backend)
    if args.lab in {"1", "all"}:
        sql = (ROOT / "lab1/03_check.sql").read_text(encoding="utf-8-sig")
        statements = [part.strip() for part in re.sub(r"--[^\n]*", "", sql).split(";") if part.strip()]
        results = [postgres.query_json(statement) for statement in statements if statement.startswith(("SELECT", "WITH"))]
        counts, invalid, passengers, comments, boundaries = [rows for rows in results[:5]]
        require(counts == [{"source_bookings": 262788, "json_bookings": 262788, "with_notes": 18799}], "Booking totals differ from the recorded demo snapshot.")
        require(invalid == [{"invalid_documents": 0}], "Invalid booking JSON documents.")
        require(passengers == [{"passenger_differences": 0}], "Passenger sets differ from the source tables.")
        require(comments == [{"expected_comments": 18799, "actual_comments": 18799, "missing_comments": 0, "extra_comments": 0}], "The airport time-zone condition was applied incorrectly.")
        require(len(boundaries) == 4 and all(row["passed"] for row in boundaries), "Time-zone boundary examples failed.")
        before = fingerprint(postgres, "bookings.bookings_json", "booking_id")
        postgres.execute(path=ROOT / "lab1/lab1.sql", capture=True)
        require(before == fingerprint(postgres, "bookings.bookings_json", "booking_id"), "Repeating lab 1 changed booking documents.")
        postgres.execute(path=ROOT / "lab1/results/04_behavior_checks.sql", capture=True)
        require(before == fingerprint(postgres, "bookings.bookings_json", "booking_id"), "The rolled-back note checks changed stored documents.")
        print("Lab 1: counts, JSON, passengers, time zones, repeat run and note preservation passed.", flush=True)
    if args.lab in {"2", "all"}:
        before = fingerprint(postgres, "lab2.startups_json", "id")
        postgres.execute(path=ROOT / "lab2/01_load_data.sql", capture=True)
        require(before == fingerprint(postgres, "lab2.startups_json", "id"), "Repeating lab 2 import changed startup documents.")
        subprocess.run([sys.executable, str(ROOT / "lab2/03_validate.py"), "--backend", args.backend], cwd=ROOT, check=True)
        print("Lab 2: saved HTML replay, extraction edge cases, repeat import and all SQL result rows passed.")
    print(json.dumps({"status": "passed", "lab": args.lab, "backend": args.backend}))


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, subprocess.CalledProcessError) as error:
        print(f"Verification failed: {error}", file=sys.stderr)
        sys.exit(1)
