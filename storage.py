"""Result storage: PostgreSQL (primary) plus a local CSV backup of every trial.

Every trial is written the moment it finishes, so an aborted session still
keeps all completed trials. If the database is unreachable the experiment can
run in CSV-only mode (the operator is asked at start-up).
"""

from __future__ import annotations

import csv
import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from config import DatabaseConfig, ExperimentConfig

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    session_id   SERIAL PRIMARY KEY,
    subject_id   TEXT        NOT NULL,
    started_at   TIMESTAMPTZ NOT NULL,
    ended_at     TIMESTAMPTZ,
    status       TEXT        NOT NULL DEFAULT 'running',  -- running | completed | aborted
    seed         BIGINT      NOT NULL,
    config       JSONB       NOT NULL
);
CREATE INDEX IF NOT EXISTS sessions_subject_idx ON sessions (subject_id);

CREATE TABLE IF NOT EXISTS trials (
    trial_id        SERIAL PRIMARY KEY,
    session_id      INTEGER     NOT NULL REFERENCES sessions (session_id) ON DELETE CASCADE,
    trial_index     INTEGER     NOT NULL,
    strategy        TEXT        NOT NULL CHECK (strategy IN ('head', 'hands')),
    start_value     INTEGER     NOT NULL,
    steps           INTEGER[]   NOT NULL,
    correct_answer  INTEGER     NOT NULL,
    response        INTEGER,               -- NULL if the response timed out
    is_correct      BOOLEAN     NOT NULL,
    rt_seconds      DOUBLE PRECISION,      -- response-prompt onset -> Enter
    recorded_at     TIMESTAMPTZ NOT NULL,
    UNIQUE (session_id, trial_index)
);
"""

CSV_FIELDS = [
    "subject_id", "session_id", "trial_index", "strategy", "start_value", "steps",
    "correct_answer", "response", "is_correct", "rt_seconds", "recorded_at",
]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def ensure_database(db: DatabaseConfig) -> None:
    """Create the database if it does not exist yet (needs CREATEDB rights)."""
    import psycopg
    from psycopg import sql

    try:
        psycopg.connect(**_conn_kwargs(db)).close()
        return
    except psycopg.OperationalError as exc:
        if "does not exist" not in str(exc):
            raise
    with psycopg.connect(**_conn_kwargs(db, dbname="postgres"), autocommit=True) as conn:
        conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(db.dbname)))


def _conn_kwargs(db: DatabaseConfig, dbname: str | None = None) -> dict:
    return dict(
        host=db.host, port=db.port, dbname=dbname or db.dbname, user=db.user,
        password=db.password, connect_timeout=db.connect_timeout,
    )


class ResultStore:
    def __init__(
        self,
        subject_id: str,
        cfg: ExperimentConfig,
        seed: int,
        db: DatabaseConfig | None,
        data_dir: Path = Path("data"),
    ) -> None:
        self.subject_id = subject_id
        self.session_id: int | None = None
        self._conn = None
        started = _now()

        if db is not None:
            import psycopg

            ensure_database(db)
            self._conn = psycopg.connect(**_conn_kwargs(db), autocommit=True)
            self._conn.execute(SCHEMA)
            row = self._conn.execute(
                "INSERT INTO sessions (subject_id, started_at, seed, config) "
                "VALUES (%s, %s, %s, %s) RETURNING session_id",
                (subject_id, started, seed, json.dumps(asdict(cfg))),
            ).fetchone()
            self.session_id = row[0]

        data_dir.mkdir(parents=True, exist_ok=True)
        safe_id = "".join(c if c.isalnum() or c in "-_" else "_" for c in subject_id)
        stamp = started.astimezone().strftime("%Y%m%d_%H%M%S")
        self.csv_path = data_dir / f"{safe_id}_{stamp}.csv"
        with self.csv_path.open("w", newline="", encoding="utf-8") as f:
            csv.DictWriter(f, CSV_FIELDS).writeheader()
        # Config + seed next to the CSV, so the session can be reproduced.
        self.csv_path.with_suffix(".json").write_text(
            json.dumps({"subject_id": subject_id, "session_id": self.session_id,
                        "seed": seed, "config": asdict(cfg)}, indent=2),
            encoding="utf-8",
        )

    @property
    def uses_database(self) -> bool:
        return self._conn is not None

    def save_trial(
        self,
        trial_index: int,
        strategy: str,
        start_value: int,
        steps: tuple[int, ...],
        correct_answer: int,
        response: int | None,
        rt_seconds: float | None,
    ) -> bool:
        is_correct = response is not None and response == correct_answer
        recorded = _now()
        # CSV first: it is the safety net if the database call fails.
        with self.csv_path.open("a", newline="", encoding="utf-8") as f:
            csv.DictWriter(f, CSV_FIELDS).writerow({
                "subject_id": self.subject_id, "session_id": self.session_id,
                "trial_index": trial_index, "strategy": strategy,
                "start_value": start_value, "steps": " ".join(map(str, steps)),
                "correct_answer": correct_answer, "response": response,
                "is_correct": is_correct, "rt_seconds": rt_seconds,
                "recorded_at": recorded.isoformat(),
            })
        if self._conn is not None:
            self._conn.execute(
                "INSERT INTO trials (session_id, trial_index, strategy, start_value, steps, "
                "correct_answer, response, is_correct, rt_seconds, recorded_at) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (self.session_id, trial_index, strategy, start_value, list(steps),
                 correct_answer, response, is_correct, rt_seconds, recorded),
            )
        return is_correct

    def close(self, status: str) -> None:
        if self._conn is None:
            return
        try:
            self._conn.execute(
                "UPDATE sessions SET ended_at = %s, status = %s WHERE session_id = %s",
                (_now(), status, self.session_id),
            )
        finally:
            self._conn.close()
            self._conn = None
