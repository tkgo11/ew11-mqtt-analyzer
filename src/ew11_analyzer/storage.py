"""SQLite storage for packets, markers and settings.

WAL mode allows concurrent readers while the ingest task writes. A ring cap
(max_packets) keeps the DB bounded for 24/7 capture.
"""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path
from typing import Any

from .classify import Marker
from .packets import Packet

_SCHEMA = """
CREATE TABLE IF NOT EXISTS packets (
    seq     INTEGER PRIMARY KEY,
    ts      REAL NOT NULL,
    topic   TEXT NOT NULL,
    fmt     TEXT NOT NULL,
    payload BLOB NOT NULL,
    raw     TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_packets_ts ON packets(ts);

CREATE TABLE IF NOT EXISTS markers (
    id    INTEGER PRIMARY KEY AUTOINCREMENT,
    ts    REAL NOT NULL,
    label TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS meta (
    k TEXT PRIMARY KEY,
    v TEXT
);
"""

PRUNE_BATCH = 5000


class Storage:
    def __init__(self, path: Path | str, max_packets: int = 200_000):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.max_packets = max_packets
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")
            self._conn.executescript(_SCHEMA)
            self._conn.commit()
        self._buf: list[Packet] = []

    # ---- packets -----------------------------------------------------------
    def add_packet(self, pkt: Packet) -> None:
        with self._lock:
            self._buf.append(pkt)
            if len(self._buf) >= 100:
                self._flush_locked()

    def flush(self) -> None:
        with self._lock:
            self._flush_locked()

    def _flush_locked(self) -> None:
        if not self._buf:
            return
        self._conn.executemany(
            "INSERT INTO packets(seq, ts, topic, fmt, payload, raw) VALUES (?,?,?,?,?,?)",
            [(p.seq, p.ts, p.topic, p.fmt, p.payload, p.raw) for p in self._buf],
        )
        self._conn.commit()
        self._buf.clear()
        self._prune_locked()

    def _prune_locked(self) -> None:
        (cnt,) = self._conn.execute("SELECT COUNT(*) FROM packets").fetchone()
        # amortized pruning: only delete once we've overflowed by a watermark
        watermark = max(64, self.max_packets // 10)
        if cnt > self.max_packets + watermark:
            cutoff = cnt - self.max_packets
            self._conn.execute(
                "DELETE FROM packets WHERE seq IN (SELECT seq FROM packets ORDER BY seq LIMIT ?)",
                (cutoff,),
            )
            self._conn.commit()

    @staticmethod
    def _row_to_packet(r: sqlite3.Row) -> Packet:
        return Packet(
            seq=r["seq"],
            ts=r["ts"],
            topic=r["topic"],
            fmt=r["fmt"],
            payload=bytes(r["payload"]),
            raw=r["raw"],
        )

    def query(
        self,
        *,
        since: float | None = None,
        until: float | None = None,
        topic: str | None = None,
        limit: int | None = None,
        before_seq: int | None = None,
        newest_first: bool = False,
    ) -> list[Packet]:
        sql = "SELECT * FROM packets WHERE 1=1"
        args: list[Any] = []
        if since is not None:
            sql += " AND ts >= ?"
            args.append(since)
        if until is not None:
            sql += " AND ts <= ?"
            args.append(until)
        if topic:
            sql += " AND topic LIKE ?"
            args.append(topic)
        if before_seq is not None:
            sql += " AND seq < ?"
            args.append(before_seq)
        sql += " ORDER BY seq " + ("DESC" if newest_first else "ASC")
        if limit:
            sql += " LIMIT ?"
            args.append(limit)
        with self._lock:
            rows = self._conn.execute(sql, args).fetchall()
        return [self._row_to_packet(r) for r in rows]

    def count(self) -> int:
        with self._lock:
            return int(self._conn.execute("SELECT COUNT(*) FROM packets").fetchone()[0])

    def ts_range(self) -> tuple[float, float]:
        with self._lock:
            row = self._conn.execute("SELECT MIN(ts), MAX(ts) FROM packets").fetchone()
        return (float(row[0] or 0.0), float(row[1] or 0.0))

    def max_seq(self) -> int:
        with self._lock:
            return int(self._conn.execute("SELECT COALESCE(MAX(seq),0) FROM packets").fetchone()[0])

    def topics(self) -> list[str]:
        with self._lock:
            rows = self._conn.execute("SELECT DISTINCT topic FROM packets ORDER BY topic").fetchall()
        return [r[0] for r in rows]

    def clear_packets(self) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM packets")
            self._conn.commit()

    # ---- markers -----------------------------------------------------------
    def add_marker(self, ts: float, label: str) -> Marker:
        with self._lock:
            cur = self._conn.execute("INSERT INTO markers(ts, label) VALUES (?, ?)", (ts, label))
            self._conn.commit()
            return Marker(id=int(cur.lastrowid or 0), ts=ts, label=label)

    def markers(self) -> list[Marker]:
        with self._lock:
            rows = self._conn.execute("SELECT id, ts, label FROM markers ORDER BY ts").fetchall()
        return [Marker(id=r["id"], ts=r["ts"], label=r["label"]) for r in rows]

    def delete_marker(self, marker_id: int) -> bool:
        with self._lock:
            cur = self._conn.execute("DELETE FROM markers WHERE id = ?", (marker_id,))
            self._conn.commit()
            return cur.rowcount > 0

    def clear_markers(self) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM markers")
            self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._flush_locked()
            self._conn.close()
