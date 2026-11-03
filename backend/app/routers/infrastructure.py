from fastapi import APIRouter, HTTPException
from ..database import get_db
from ..schemas import ServerCreate

router = APIRouter(prefix="/api/infrastructure", tags=["Infrastructure"])

@router.get("/servers")
def list_servers():
    with get_db() as db:
        return [dict(r) for r in db.execute("SELECT * FROM servers ORDER BY id").fetchall()]

@router.post("/servers")
def create_server(payload: ServerCreate):
    name = payload.name.strip()
    if not name:
        raise HTTPException(422, "Server name cannot be empty.")
    with get_db() as db:
        existing = db.execute("SELECT id FROM servers WHERE lower(name)=lower(?)", (name,)).fetchone()
        if existing:
            raise HTTPException(409, "A server with this name already exists.")
        cur = db.execute("""
            INSERT INTO servers(name,cpu,ram,storage,network,workload,status)
            VALUES(?,?,?,?,?,?, 'Running')
        """, (name, payload.cpu, payload.ram, payload.storage, payload.network, payload.workload))
        server = dict(db.execute("SELECT * FROM servers WHERE id=?", (cur.lastrowid,)).fetchone())
        db.execute("""
            INSERT INTO metrics(server_id,cpu,ram,network,workload) VALUES(?,?,?,?,?)
        """, (server["id"], server["cpu"], server["ram"], server["network"], server["workload"]))
        return server

@router.post("/servers/{server_id}/restore")
def restore(server_id: int):
    with get_db() as db:
        row = db.execute("SELECT * FROM servers WHERE id=?", (server_id,)).fetchone()
        if row is None:
            raise HTTPException(404, "Server not found.")
        db.execute("UPDATE servers SET status='Running' WHERE id=?", (server_id,))
        return {"message": f"{row['name']} restored."}
