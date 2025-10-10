# C:\Pasarela\services\ensure_trazas_unica.py
import sqlite3, os

DB = r"C:\Pasarela\services\pasarela.db"
TABLE = "Trazas_Unica"

DDL = f"""
CREATE TABLE IF NOT EXISTS {TABLE} (
  oid TEXT PRIMARY KEY,
  ts_utc TEXT,
  ts_redis_ingest TEXT,
  ch_id TEXT,
  msg_id TEXT,
  channel TEXT,
  channel_username TEXT,
  sender_id TEXT,
  text TEXT,
  score INTEGER,
  estado_operacion INTEGER,
  ts_mt4_queue TEXT,
  symbol TEXT,
  order_type TEXT,
  entry_price REAL,
  sl REAL,
  tp REAL,
  comment TEXT
);
"""

NEEDED_COLS = {
  "symbol":"TEXT",
  "order_type":"TEXT",
  "entry_price":"REAL",
  "sl":"REAL",
  "tp":"REAL",
  "comment":"TEXT",
}

if not os.path.exists(DB):
    raise SystemExit(f"No existe la BBDD: {DB}")

con = sqlite3.connect(DB)
cur = con.cursor()

# 1) Crear tabla si no existe
cur.execute(DDL)

# 2) Añadir columnas que falten
cols = {r[1] for r in cur.execute(f"PRAGMA table_info({TABLE})")}
for c, typ in NEEDED_COLS.items():
    if c not in cols:
        cur.execute(f"ALTER TABLE {TABLE} ADD COLUMN {c} {typ}")

# 3) Índice por oid
cur.execute(f"CREATE UNIQUE INDEX IF NOT EXISTS ix_{TABLE}_oid ON {TABLE}(oid)")

con.commit()
con.close()
print(f"[OK] {TABLE} asegurada en {DB}")

