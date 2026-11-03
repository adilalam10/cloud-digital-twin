import sqlite3
from pathlib import Path
from contextlib import contextmanager

DB_PATH = Path(__file__).resolve().parents[1] / "digital_twin.db"

@contextmanager
def get_db():
    db = sqlite3.connect(DB_PATH, timeout=15)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    db.execute("PRAGMA busy_timeout = 15000")
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

def init_db():
    with get_db() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS servers(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            cpu REAL NOT NULL,
            ram REAL NOT NULL,
            storage REAL NOT NULL,
            network REAL NOT NULL,
            workload REAL NOT NULL,
            status TEXT NOT NULL DEFAULT 'Running'
        );
        CREATE TABLE IF NOT EXISTS metrics(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
            server_id INTEGER,
            cpu REAL,
            ram REAL,
            network REAL,
            workload REAL
        );
        CREATE TABLE IF NOT EXISTS metric_snapshots(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
            cpu REAL NOT NULL,
            ram REAL NOT NULL,
            workload REAL NOT NULL,
            network REAL NOT NULL,
            server_count INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS simulations(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
            scenario TEXT,
            description TEXT,
            before_cpu REAL,
            after_cpu REAL,
            before_ram REAL,
            after_ram REAL,
            recommendation TEXT
        );
        CREATE TABLE IF NOT EXISTS predictions(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
            current_cpu REAL,
            predicted_cpu REAL,
            current_ram REAL,
            predicted_ram REAL,
            risk TEXT,
            recommendation TEXT,
            method TEXT,
            mae_cpu REAL,
            rmse_cpu REAL,
            mae_ram REAL,
            rmse_ram REAL
        );
        CREATE INDEX IF NOT EXISTS idx_metrics_server_id ON metrics(server_id, id);
        CREATE INDEX IF NOT EXISTS idx_snapshots_id ON metric_snapshots(id);
        """)
        # Safe schema migration for databases created by the earlier project ZIP.
        existing = {row["name"] for row in db.execute("PRAGMA table_info(predictions)")}
        for name, sql_type in [
            ("method", "TEXT"),
            ("mae_cpu", "REAL"),
            ("rmse_cpu", "REAL"),
            ("mae_ram", "REAL"),
            ("rmse_ram", "REAL"),
        ]:
            if name not in existing:
                db.execute(f"ALTER TABLE predictions ADD COLUMN {name} {sql_type}")

def backfill_snapshots():
    """Convert the original per-server seed metrics into fleet-level time points once."""
    with get_db() as db:
        count = db.execute("SELECT COUNT(*) FROM metric_snapshots").fetchone()[0]
        if count:
            return
        rows = db.execute("""
            SELECT server_id, timestamp, cpu, ram, workload, network, id
            FROM metrics ORDER BY server_id, id
        """).fetchall()
        grouped = {}
        for row in rows:
            grouped.setdefault(row["server_id"], []).append(dict(row))
        if not grouped:
            return
        max_points = max(len(items) for items in grouped.values())
        for i in range(max_points):
            sample = [items[i] for items in grouped.values() if i < len(items)]
            if not sample:
                continue
            db.execute("""
                INSERT INTO metric_snapshots(timestamp,cpu,ram,workload,network,server_count)
                VALUES(?,?,?,?,?,?)
            """, (
                sample[-1]["timestamp"],
                sum(x["cpu"] for x in sample) / len(sample),
                sum(x["ram"] for x in sample) / len(sample),
                sum(x["workload"] for x in sample) / len(sample),
                sum(x["network"] for x in sample) / len(sample),
                len(sample),
            ))

def record_snapshot(db):
    rows = db.execute("SELECT cpu,ram,workload,network FROM servers WHERE status='Running'").fetchall()
    if not rows:
        return
    n = len(rows)
    db.execute("""
        INSERT INTO metric_snapshots(cpu,ram,workload,network,server_count)
        VALUES(?,?,?,?,?)
    """, tuple(sum(float(r[k]) for r in rows) / n for k in ("cpu","ram","workload","network")) + (n,))
