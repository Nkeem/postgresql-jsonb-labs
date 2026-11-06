"""Download and verify the exact 2017 demo-small archive used by lab 1."""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import shutil
from urllib.request import Request, urlopen
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
URL = "https://edu.postgrespro.ru/demo-small.zip"
SHA256 = "4fb07944ea715f93e9cafb9173ef9b594be377d8eda984cbce29d8866ea32632"
MEMBER = "demo-small-20170815.sql"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, help="Use an existing archive instead of downloading.")
    args = parser.parse_args()
    destination = ROOT / "lab1/source"
    destination.mkdir(parents=True, exist_ok=True)
    archive = args.archive or destination / "demo-small.zip"
    if not archive.is_file():
        if args.archive:
            parser.error(f"Archive does not exist: {archive}")
        pending = archive.with_suffix(".download")
        try:
            request = Request(URL, headers={"User-Agent": "PostgreSQL-JSONB-Labs/1.0"})
            with urlopen(request, timeout=120) as response, pending.open("wb") as output:
                shutil.copyfileobj(response, output)
            pending.replace(archive)
        finally:
            pending.unlink(missing_ok=True)
    digest = hashlib.sha256()
    with archive.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    if digest.hexdigest() != SHA256:
        raise RuntimeError("Archive SHA-256 differs from the recorded 2017 snapshot; import was not prepared.")
    target = destination / "demo-small-pg18.sql"
    temporary = target.with_suffix(".tmp")
    skipped = {b"DROP DATABASE demo;", b"SET default_with_oids = false;"}
    removed = 0
    try:
        with ZipFile(archive) as bundle, bundle.open(MEMBER) as source, temporary.open("wb") as output:
            for line in source:
                if line.strip() in skipped:
                    removed += 1
                    continue
                output.write(line)
        if removed != 2:
            raise RuntimeError(f"Unexpected dump layout: expected two compatibility edits, found {removed}.")
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)
    print(f"Verified SHA-256: {SHA256}")
    print(f"Prepared {target.relative_to(ROOT)} ({target.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
