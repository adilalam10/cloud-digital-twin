from .database import get_db, record_snapshot

INITIAL = [
    ("Cloud-Server-01", 42, 55, 48, 32, 40, "Running"),
    ("Cloud-Server-02", 61, 68, 62, 45, 58, "Running"),
    ("Cloud-Server-03", 28, 39, 35, 21, 30, "Running"),
    ("Cloud-Server-04", 76, 72, 70, 58, 74, "Running"),
]

def seed_if_empty():
    with get_db() as db:
        if db.execute("SELECT COUNT(*) FROM servers").fetchone()[0] == 0:
            db.executemany("""
                INSERT INTO servers(name,cpu,ram,storage,network,workload,status)
                VALUES(?,?,?,?,?,?,?)
            """, INITIAL)
        if db.execute("SELECT COUNT(*) FROM metrics").fetchone()[0] == 0:
            servers = db.execute("SELECT * FROM servers WHERE status='Running'").fetchall()
            # Twelve reproducible fleet snapshots, with one metric row per server per time point.
            for step in range(12):
                factor = 0.78 + step * 0.022
                for server in servers:
                    cpu = min(98, server["cpu"] * factor)
                    ram = min(98, server["ram"] * (0.88 + step * 0.012))
                    workload = min(98, server["workload"] * factor)
                    network = min(98, server["network"] * factor)
                    db.execute("""
                        INSERT INTO metrics(server_id,cpu,ram,network,workload)
                        VALUES(?,?,?,?,?)
                    """, (server["id"], cpu, ram, network, workload))
                # A fleet-level snapshot is created in the same transaction.
                rows = db.execute("""
                    SELECT cpu,ram,workload,network FROM metrics
                    WHERE id > (SELECT COALESCE(MAX(id),0)-? FROM metrics)
                    ORDER BY id DESC LIMIT ?
                """, (len(servers), len(servers))).fetchall()
                n = len(rows)
                if n:
                    db.execute("""
                        INSERT INTO metric_snapshots(cpu,ram,workload,network,server_count)
                        VALUES(?,?,?,?,?)
                    """, tuple(sum(float(r[k]) for r in rows)/n for k in ("cpu","ram","workload","network")) + (n,))
