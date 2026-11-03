from ..database import get_db, record_snapshot
from .recommendation import recommend

def run_simulation(scenario, workload_change=40, server_id=None):
    with get_db() as db:
        servers = [dict(x) for x in db.execute("SELECT * FROM servers ORDER BY id").fetchall()]
        running = [s for s in servers if s["status"] == "Running"]
        if not running:
            raise ValueError("There are no running servers to simulate.")

        before_cpu = sum(s["cpu"] for s in running) / len(running)
        before_ram = sum(s["ram"] for s in running) / len(running)
        failed = 0

        if scenario == "workload":
            factor = max(0.1, 1 + float(workload_change) / 100)
            for server in running:
                cpu = min(100, max(0, server["cpu"] * factor))
                ram = min(100, max(0, server["ram"] * (1 + float(workload_change) / 200)))
                network = min(100, max(0, server["network"] * factor))
                workload = min(100, max(0, server["workload"] * factor))
                db.execute(
                    "UPDATE servers SET cpu=?,ram=?,network=?,workload=? WHERE id=?",
                    (cpu, ram, network, workload, server["id"]),
                )
                db.execute(
                    "INSERT INTO metrics(server_id,cpu,ram,network,workload) VALUES(?,?,?,?,?)",
                    (server["id"], cpu, ram, network, workload),
                )
            description = f"Workload changed by {float(workload_change):+.0f}% across running servers."

        elif scenario == "failure":
            target = next(
                (s for s in running if s["id"] == server_id), None
            ) if server_id is not None else running[0]
            if target is None:
                raise ValueError("That server is no longer running. Refresh the server list and choose an active server.")
            db.execute("UPDATE servers SET status='Failed' WHERE id=?", (target["id"],))
            failed = 1
            remaining = [s for s in running if s["id"] != target["id"]]
            if remaining:
                bump = min(35, target["workload"] / len(remaining) * 0.45)
                for server in remaining:
                    cpu = min(100, server["cpu"] + bump)
                    ram = min(100, server["ram"] + bump * 0.55)
                    db.execute("UPDATE servers SET cpu=?,ram=? WHERE id=?", (cpu, ram, server["id"]))
                    db.execute(
                        "INSERT INTO metrics(server_id,cpu,ram,network,workload) VALUES(?,?,?,?,?)",
                        (server["id"], cpu, ram, server["network"], server["workload"] + target["workload"]/len(remaining)),
                    )
            description = f"Simulated failure of {target['name']}."
        else:
            raise ValueError("Unsupported simulation scenario.")

        after = [dict(x) for x in db.execute(
            "SELECT * FROM servers WHERE status='Running' ORDER BY id"
        ).fetchall()]
        after_cpu = sum(s["cpu"] for s in after) / len(after) if after else 100.0
        after_ram = sum(s["ram"] for s in after) / len(after) if after else 100.0
        recommendation = recommend(after_cpu, after_ram, failed)
        db.execute("""
            INSERT INTO simulations(scenario,description,before_cpu,after_cpu,before_ram,after_ram,recommendation)
            VALUES(?,?,?,?,?,?,?)
        """, (scenario, description, before_cpu, after_cpu, before_ram, after_ram, recommendation))
        if after:
            record_snapshot(db)

        return {
            "scenario": scenario,
            "description": description,
            "before_cpu": round(before_cpu, 2),
            "after_cpu": round(after_cpu, 2),
            "before_ram": round(before_ram, 2),
            "after_ram": round(after_ram, 2),
            "recommendation": recommendation,
            "failed_server_id": target["id"] if scenario == "failure" else None,
        }
