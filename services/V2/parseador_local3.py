# -*- coding: utf-8 -*-
# parseador_local.py (v2.8.1)
# - Lee del stream 'pasarela:parse' (campos planos o 'data' JSON).
# - Reglas:
#     · score == 10  → ENQUEUE a MT4 añadiendo una línea JSON en queue_orders.jsonl (incluye score=10).
#     · score < 10   → GUARDAR TODO en SQLite (signals_raw) + trazas de tiempo.
# - Cambio mínimo: db_init asegura columna 'score' en BBDD antiguas (sin tocar nada más).

import os, json, asyncio, signal, sqlite3
from datetime import datetime, timezone
from redis.asyncio import Redis

# ====== Redis ======
REDIS_URL = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
STREAM    = "pasarela:parse"
GROUP     = "parser"
CONSUMER  = os.getenv("COMPUTERNAME", "local")

# ====== MT4 (ajusta el hash si tu terminal es otro) ======
APPDATA   = os.getenv("APPDATA")
MT4_ROOT  = os.path.join(APPDATA, "MetaQuotes", "Terminal")
FILES_DIR = os.path.join(MT4_ROOT, "BB190E062770E27C3E79391AB0D1A117", "MQL4", "Files")
QUEUE_JSONL = os.path.join(FILES_DIR, "queue_orders.jsonl")
os.makedirs(FILES_DIR, exist_ok=True)

# ====== BBDD (solo para score<10) ======
DB_PATH = os.getenv("PASARELA_DB", os.path.join(os.getcwd(), "pasarela.db"))

def now_utc_iso():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")

def db_init():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS signals_raw (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts_ingest_utc TEXT NOT NULL,
                redis_id TEXT NOT NULL,
                ch_id TEXT,
                msg_id TEXT,
                channel_title TEXT,
                text TEXT,
                score INTEGER,
                payload TEXT NOT NULL,
                ts_redis_ingest TEXT,
                ts_parse_start  TEXT,
                ts_parse_end    TEXT
            )
        """)
        # Migración mínima: asegura columnas por si la DB viene de versiones antiguas
        cols = {row[1] for row in conn.execute("PRAGMA table_info(signals_raw)")}
        # añadir 'score' si falta (clave para análisis posterior)
        if "score" not in cols:
            conn.execute("ALTER TABLE signals_raw ADD COLUMN score INTEGER")
        if "ts_redis_ingest" not in cols:
            conn.execute("ALTER TABLE signals_raw ADD COLUMN ts_redis_ingest TEXT")
        if "ts_parse_start" not in cols:
            conn.execute("ALTER TABLE signals_raw ADD COLUMN ts_parse_start TEXT")
        if "ts_parse_end" not in cols:
            conn.execute("ALTER TABLE signals_raw ADD COLUMN ts_parse_end TEXT")

def db_save_raw(redis_id: str,
                fields: dict,
                text: str,
                ch_id: str,
                msg_id: str,
                channel_title: str,
                score: int,
                ts_redis_ingest: str,
                ts_parse_start: str,
                ts_parse_end: str):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            INSERT INTO signals_raw (
                ts_ingest_utc, redis_id, ch_id, msg_id, channel_title, text, score, payload,
                ts_redis_ingest, ts_parse_start, ts_parse_end
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            now_utc_iso(),
            redis_id,
            str(ch_id) if ch_id is not None else None,
            str(msg_id) if msg_id is not None else None,
            channel_title,
            text,
            int(score) if score is not None else None,
            json.dumps(fields, ensure_ascii=False),
            ts_redis_ingest,
            ts_parse_start,
            ts_parse_end
        ))

# ====== Regla mínima de score ======
def parse_signal(text: str) -> dict:
    t = (text or "").lower()
    side = "buy" if "buy" in t else ("sell" if "sell" in t else None)
    sym  = None
    for s in ["eurusd","gbpusd","usdjpy","xauusd","gold","btc","eth"]:
        if s in t:
            sym = "XAUUSD" if s in ("gold","xauusd") else s.upper()
            break
    score = 10 if side and sym else 0
    return {"symbol": sym, "side": side, "score": score}

# ====== ENQUEUE a MT4: appendea en queue_orders.jsonl (con score=10) ======
def enqueue_mt4(order: dict):
    order = dict(order)
    order["score"] = 10                 # requerido por el EA (InpOnlyScore10=true)
    order["ts_mt4_queue"] = now_utc_iso()
    line = json.dumps(order, ensure_ascii=False)
    with open(QUEUE_JSONL, "a", encoding="utf-8", newline="\n") as f:
        f.write(line + "\n")
    return QUEUE_JSONL

async def ensure_group(r: Redis):
    try:
        await r.xgroup_create(STREAM, GROUP, id="$", mkstream=True)
    except Exception:
        pass  # ya existe

RUNNING = True
def handle_sig(*_):
    global RUNNING; RUNNING = False

def pick(d: dict, names, default=None):
    for n in names:
        if n in d and d[n] not in (None, ""):
            return d[n]
    return default

async def main():
    global RUNNING
    signal.signal(signal.SIGINT, handle_sig)
    signal.signal(signal.SIGTERM, handle_sig)

    db_init()

    r = Redis.from_url(REDIS_URL, decode_responses=True)
    await ensure_group(r)

    print(f"[{now_utc_iso()}] parseador conectado a {REDIS_URL} | stream={STREAM} | group={GROUP} | consumer={CONSUMER}")
    print("score==10: ENQUEUE a MT4 en queue_orders.jsonl (incluye score=10) | score<10: DB con trazas. Ctrl+C para salir.\n")

    while RUNNING:
        resp = await r.xreadgroup(GROUP, CONSUMER, streams={STREAM: '>'}, count=50, block=5000)
        if not resp:
            continue

        for _, entries in resp:
            for redis_id, fields in entries:
                ts_parse_start = now_utc_iso()

                # 1) Entrada: 'data' JSON o campos planos
                if "data" in fields:
                    payload = fields["data"]
                    try:
                        data = json.loads(payload) if isinstance(payload, str) else payload
                    except Exception as e:
                        print(f"[{now_utc_iso()}] ERROR JSON en {redis_id}: {e} | keys={list(fields.keys())}")
                        await r.xack(STREAM, GROUP, redis_id); continue
                else:
                    data = fields

                # 2) Aliases mínimos
                text    = pick(data, ["text","message","caption","raw","content"], "")
                ch_id   = pick(data, ["ch_id","channel_id","chat_id","peer_id"])
                msg_id  = pick(data, ["msg_id","message_id","id","mid"])
                title   = pick(data, ["channel_title","title","channel","chat_title","username","name"], "")
                ts_ing  = pick(data, ["ts_redis_ingest","ts_ingest","ts_stream"], None)

                # 3) Score y acción
                parsed = parse_signal(text)
                score  = parsed.get("score", 0)
                ts_parse_end = now_utc_iso()

                if score == 10:
                    order = {
                        "ts_utc": pick(data, ["ts_utc"], None),
                        "ts_redis_ingest": ts_ing,
                        "ch_id": ch_id,
                        "msg_id": str(msg_id),
                        "channel": title,
                        "symbol": parsed["symbol"],
                        "side": parsed["side"],
                        "raw": text
                    }
                    enqueue_mt4(order)
                    action = "ENQUEUE"
                else:
                    db_save_raw(redis_id, fields, text, ch_id, msg_id, title, score,
                                ts_ing, ts_parse_start, ts_parse_end)
                    action = "DB"

                print(f"[{now_utc_iso()}] ch_id={ch_id} | msg_id={msg_id} | canal={title} | score={score} -> {action}")
                await r.xack(STREAM, GROUP, redis_id)

    await r.close()
    print("\nCerrado parseador.")

if __name__ == "__main__":
    asyncio.run(main())
