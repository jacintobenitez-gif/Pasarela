# -*- coding: utf-8 -*-
# parseador_local.py (v2.6)
# - Lee del stream real 'pasarela:parse' con consumer group.
# - El listener publica un único campo 'data' (JSON) o campos planos.
#   ⇒ Deserializa 'data' si existe; si no, usa los campos planos tal cual.
# - Regla:
#     · score == 10  → ENQUEUE a MT4 (sin tocar nada más).
#     · score < 10   → GUARDAR TODO en BBDD SQLite (tabla signals_raw).
# - Trazas: [ts] ch_id | msg_id | canal | score -> ENQUEUE / DB

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
QUEUE_ORDER = os.path.join(MT4_ROOT, "BB190E062770E27C3E79391AB0D1A117", "MQL4", "Files", "queue_order")
os.makedirs(QUEUE_ORDER, exist_ok=True)

# ====== BBDD (solo para score<10) ======
DB_PATH = os.getenv("PASARELA_DB", os.path.join(os.getcwd(), "pasarela.db"))

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
                payload TEXT NOT NULL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_signals_raw_msg ON signals_raw(ch_id, msg_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_signals_raw_ts  ON signals_raw(ts_ingest_utc)")

def db_save_raw(redis_id: str, fields: dict, text: str, ch_id: str, msg_id: str, channel_title: str, score: int):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            INSERT INTO signals_raw (ts_ingest_utc, redis_id, ch_id, msg_id, channel_title, text, score, payload)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            redis_id, str(ch_id) if ch_id is not None else None,
            str(msg_id) if msg_id is not None else None,
            channel_title, text, int(score) if score is not None else None,
            json.dumps(fields, ensure_ascii=False)
        ))

def now_utc():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

# ====== Regla mínima de score (igual que acordamos) ======
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

# ====== Encolar a MT4 (sin cambios cuando score==10) ======
def enqueue_mt4(order: dict):
    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    fname = os.path.join(QUEUE_ORDER, f"order_{ts}.json")
    with open(fname, "w", encoding="utf-8") as f:
        json.dump(order, f, ensure_ascii=False)
    return fname

async def ensure_group(r: Redis):
    try:
        await r.xgroup_create(STREAM, GROUP, id="$", mkstream=True)
    except Exception:
        pass  # ya existe

RUNNING = True
def handle_sig(*_): 
    global RUNNING; RUNNING = False

# ====== Utilidad: coger el primer valor disponible entre alias ======
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

    print(f"[{now_utc()}] parseador conectado a {REDIS_URL} | stream={STREAM} | group={GROUP} | consumer={CONSUMER}")
    print("score==10: ENQUEUE MT4 | score<10: GUARDAR en BBDD (signals_raw). Ctrl+C para salir.\n")

    while RUNNING:
        resp = await r.xreadgroup(GROUP, CONSUMER, streams={STREAM: ">"}, count=50, block=5000)
        if not resp:
            continue

        for _, entries in resp:
            for redis_id, fields in entries:
                # 1) El listener puede publicar todo en 'data' (JSON) o en plano
                if "data" in fields:
                    payload = fields["data"]
                    try:
                        data = json.loads(payload) if isinstance(payload, str) else payload
                    except Exception as e:
                        print(f"[{now_utc()}] ERROR JSON en {redis_id}: {e} | keys={list(fields.keys())}")
                        await r.xack(STREAM, GROUP, redis_id); continue
                else:
                    data = fields  # campos planos

                # 2) Extraer con alias mínimos (sin “pajas”)
                text   = pick(data, ["text", "message", "caption", "raw", "content"], "")
                ch_id  = pick(data, ["ch_id", "channel_id", "chat_id", "peer_id"])
                msg_id = pick(data, ["msg_id", "message_id", "id", "mid"])
                title  = pick(data, ["channel_title", "title", "channel", "chat_title", "username", "name"], "")

                # 3) Calcular score y actuar
                parsed = parse_signal(text)
                score  = parsed.get("score", 0)

                if score == 10:
                    order = {
                        "ts_utc": now_utc(),
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
                    # Guarda TODO lo recibido (tal cual) para análisis
                    db_save_raw(redis_id, fields, text, ch_id, msg_id, title, score)
                    action = "DB"

                print(f"[{now_utc()}] ch_id={ch_id} | msg_id={msg_id} | canal={title} | score={score} -> {action}")
                await r.xack(STREAM, GROUP, redis_id)

    await r.close()
    print("\nCerrado parseador.")

if __name__ == "__main__":
    asyncio.run(main())
