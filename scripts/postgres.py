"""Small psql adapter shared by the runner and the original lab validator."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]


class Postgres:
    def __init__(self, backend: str = "native"):
        if backend not in {"native", "docker"}:
            raise ValueError(f"Unknown PostgreSQL backend: {backend}")
        self.backend = backend

    def command(self, database: str | None = None) -> list[str]:
        database = database or "demo"
        if self.backend == "docker":
            return [
                "docker", "compose", "--project-directory", str(ROOT),
                "exec", "-T", "db", "psql", "-X", "-w",
                "-v", "ON_ERROR_STOP=1", "-U", "postgres", "-d", database,
            ]
        executable = os.environ.get("PSQL") or shutil.which("psql")
        if not executable and os.name == "nt":
            candidate = Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "PostgreSQL/18/bin/psql.exe"
            if candidate.is_file():
                executable = str(candidate)
        if not executable:
            raise RuntimeError("psql was not found. Add it to PATH, set PSQL, or use --backend docker.")
        return [
            executable, "-X", "-w", "-v", "ON_ERROR_STOP=1",
            "-h", os.environ.get("PGHOST", "127.0.0.1"),
            "-p", os.environ.get("PGPORT", "55432"),
            "-U", os.environ.get("PGUSER", "postgres"), "-d", database,
        ]

    def execute(self, *, sql: str | None = None, path: Path | None = None,
                database: str | None = None, capture: bool = False) -> str:
        if (sql is None) == (path is None):
            raise ValueError("Provide either SQL text or a file path.")
        command = self.command(database)
        if capture:
            command += ["-q", "-A", "-t"]
        options = dict(
            cwd=ROOT, env=dict(os.environ, PGCLIENTENCODING="UTF8"),
            text=True, encoding="utf-8", check=True,
            stdout=subprocess.PIPE if capture else None,
        )
        if path is not None:
            # Stream large dumps through stdin, without server-side paths or COPY privileges.
            with path.open("rb") as stream:
                result = subprocess.run(command + ["-f", "-"], stdin=stream, **options)
        else:
            # Windows psql re-encodes command-line arguments through the system
            # code page. UTF-8 stdin keeps Cyrillic SQL literals intact.
            result = subprocess.run(command, input=sql + "\n", **options)
        return result.stdout or ""

    def query_json(self, statement: str, database: str | None = None) -> list[dict]:
        statement = statement.strip().rstrip(";")
        wrapper = "SELECT COALESCE(json_agg(row_to_json(q)), '[]'::json) FROM (" + statement + ") AS q"
        return json.loads(self.execute(sql=wrapper, database=database, capture=True))
