# -*- coding: utf-8 -*-
# visor.py — Monitor CLI tiempo real para Listener → Redis → Parseador → MT4
# Requisitos: Python 3.10+, redis (>=4.5). En Windows: 'pip install redis'.
# No toca tu pipeline. Solo LEE Redis, SQLite y la carpeta de cola MT4.

import os, sys, json, asyncio, sqlite3, glob, time
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from redis.asyncio import Redis

# ===== Config por entorno (cambia si lo necesitas) =====
REDIS_URL   = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
STREAM      = os.getenv("REDIS_STREAM", "pasarela:parse")
GROUP       = os.getenv("REDIS_GROUP", "parser")
CONSUMER    = os.getenv("REDIS_CONSUMER", "visor")

DB_PATH     = os.getenv("PASARELA_DB", os.path.join(os.getcwd(), "pasarela.db"))

APPDATA     = os.getenv("APPDATA") or ""
MT4_ROOT    = os.path.join(APPDATA, "MetaQuotes", "Terminal")
# Ajusta este hash si tu terminal es otro:
QUEUE_ORDER = os.path.join(MT4_ROOT, "BB190E062770E27C3E79391AB0D1A117", "MQL4", "Files", "queue_order")

REFRESH_SEC = float(os.getenv("VISOR_REFRESH_SEC", "2.0"))
LAST_N      = int(os.getenv("VISOR_LAST_N", "5"))  # últimos N items para mostrar

def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00","Z")

def ms_delta(a_iso: Optional[str], b_iso: Optional[str]) -> Optional[int]:
    """Devuelve b - a en ms (ambos ISO UTC)."""
    if not a_iso or not b_iso:
        return None
    try:
        a = datetime.fromisoformat(a_iso.replace("Z","+00:00"))
        b = datetime.fromisoformat(b_iso.replace("Z","+00:00"))
        return int((b - a).total_seconds()*1000)
    except Exception:
        return None

async def get_redis_metrics(r: Redis) -> Dict[str, Any]:
    info = {"ok": True, "err": None}
    try:
        # XINFO STREAM
        xinfo_stream = await r.execute_command("XINFO", "STREAM", STREAM)
        # XINFO GROUPS
        xinfo_groups = await r.execute_command("XINFO", "GROUPS", STREAM)
        # Últimos N mensajes (para mini feed)
        entries = await r.xrevrange(STREAM, count=LAST_N)

        # Normaliza XINFO STREAM
        xs = dict(zip(xinfo_stream[::2], xinfo_stream[1::2])) if isinstance(xinfo_stream, list) else {}
        length = xs.get("length", 0)
        last_generated_id = xs.get("last-generated-id", None)

        # Normaliza XINFO GROUPS (buscamos tu grupo)
        groups = []
        lag = None
        pending = 0
        for g in xinfo_groups or []:
            gd = dict(zip(g[::2], g[1::2])) if isinstance(g, list) else {}
            groups.append(gd)
            if gd.get("name") == GROUP:
                pending = gd.get("pending", 0)
                lag = gd.get("lag", None)  # Redis 7+
        info.update({
            "length": length,
            "last_generated_id": last_generated_id,
            "groups": groups,
            "pending": pending,
            "lag": lag,
            "last_entries": entries
        })
    except Exception as e:
        info.update({"ok": False, "err": str(e)})
    return info

def get_db_metrics() -> Dict[str, Any]:
    info = {"ok": True, "err": None, "count": 0, "last_row": None}
    if not os.path.exists(DB_PATH):
        info["ok"] = False
        info["err"] = f"DB not found: {DB_PATH}"
        return info
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) AS c FROM signals_raw")
            info["count"] = cur.fetchone()["c"]
            cur.execute("""
                SELECT ts_ingest_utc, ts_redis_ingest, ts_parse_start, ts_parse_end,
                       ch_id, msg_id, channel_title, score
                FROM signals_raw
                ORDER BY id DESC LIMIT 1
            """)
            row = cur.fetchone()
            if row:
                info["last_row"] = dict(row)
    except Exception as e:
        info.update({"ok": False, "err": str(e)})
    return info

def get_mt4_queue_metrics() -> Dict[str, Any]:
    info = {"ok": True, "err": None, "count": 0, "last_file": None, "latency_ms": None, "order": None}
    try:
        if not os.path.isdir(QUEUE_ORDER):
            info["ok"] = False
            info["err"] = f"Folder not found: {QUEUE_ORDER}"
            return info
        files = sorted(glob.glob(os.path.join(QUEUE_ORDER, "order_*.json")), key=os.path.getmtime, reverse=True)
        info["count"] = len(files)
        if files:
            lastf = files[0]
            info["last_file"] = lastf
            try:
                with open(lastf, "r", encoding="utf-8") as f:
                    order = json.load(f)
                info["order"] = {
                    "ch_id": order.get("ch_id"),
                    "msg_id": order.get("msg_id"),
                    "channel": order.get("channel"),
                    "symbol": order.get("symbol"),
                    "side": order.get("side"),
                    "ts_utc": order.get("ts_utc"),
                    "ts_redis_ingest": order.get("ts_redis_ingest"),
                    "ts_mt4_queue": order.get("ts_mt4_queue"),
                }
                info["latency_ms"] = ms_delta(order.get("ts_redis_ingest"), order.get("ts_mt4_queue"))
            except Exception as e:
                info["ok"] = False
                info["err"] = f"Read last order: {e}"
    except Exception as e:
        info["ok"] = False
        info["err"] = str(e)
    return info

def clear_screen():
    # ANSI clear
    sys.stdout.write("\033[2J\033[H")
    sys.stdout.flush()

def truncate(s: Any, n=80) -> str:
    s = "" if s is None else str(s)
    return (s[:n-1] + "…") if len(s) > n else s

def paint(ri: Dict[str,Any], db: Dict[str,Any], mt4: Dict[str,Any]):
    clear_screen()
    now = now_iso()
    print(f"VISOR — {now}")
    print("="*80)

    # 1) Redis
    ok_bad = "OK " if ri.get("ok") else "ERR"
    print(f"[Redis] {ok_bad}  stream='{STREAM}'  group='{GROUP}'")
    if ri.get("ok"):
        print(f"  length={ri.get('length')}  pending={ri.get('pending')}  lag={ri.get('lag')}  last_id={ri.get('last_generated_id')}")
        # feed breve
        ents = ri.get("last_entries") or []
        print("  Últimos mensajes en stream:")
        for e in ents:
            # e = (id, {field: value, ...})
            rid, fields = e
            typ = fields.get("type") or "-"
            mid = fields.get("msg_id") or fields.get("message_id") or "-"
            ch  = fields.get("channel_title") or fields.get("channel_username") or "-"
            txt = fields.get("text") or fields.get("message") or ""
            print(f"   • {rid} | {typ:<4} | msg_id={mid} | canal={truncate(ch,30)} | {truncate(txt,40)}")
    else:
        print(f"  error: {ri.get('err')}")

    print("-"*80)

    # 2) DB signals_raw
    ok_bad = "OK " if db.get("ok") else "ERR"
    print(f"[DB] {ok_bad}  path='{DB_PATH}'  table='signals_raw'  rows={db.get('count')}")
    lr = db.get("last_row")
    if lr:
        d1 = ms_delta(lr.get("ts_redis_ingest"), lr.get("ts_parse_start"))
        d2 = ms_delta(lr.get("ts_parse_start"),  lr.get("ts_parse_end"))
        dT = ms_delta(lr.get("ts_redis_ingest"), lr.get("ts_parse_end"))
        print(f"  Último (score<{10}): ch_id={lr.get('ch_id')} msg_id={lr.get('msg_id')} canal={truncate(lr.get('channel_title'),30)} score={lr.get('score')}")
        print(f"  ts_redis_ingest={lr.get('ts_redis_ingest')} ts_parse_start={lr.get('ts_parse_start')} ts_parse_end={lr.get('ts_parse_end')}")
        print(f"  latencias (ms): ingest→parse_start={d1}  parse_start→parse_end={d2}  ingest→parse_end={dT}")
    else:
        if not db.get("ok"):
            print(f"  error: {db.get('err')}")

    print("-"*80)

    # 3) MT4 queue
    ok_bad = "OK " if mt4.get("ok") else "ERR"
    print(f"[MT4 queue] {ok_bad}  dir='{QUEUE_ORDER}'  files={mt4.get('count')}")
    if mt4.get("order"):
        o = mt4["order"]
        print(f"  Última orden: ch_id={o.get('ch_id')} msg_id={o.get('msg_id')} canal={truncate(o.get('channel'),30)} {o.get('side')}/{o.get('symbol')}")
        print(f"  ts_redis_ingest={o.get('ts_redis_ingest')} ts_mt4_queue={o.get('ts_mt4_queue')}  latencia ingest→queue={mt4.get('latency_ms')} ms")
    elif not mt4.get("ok"):
        print(f"  error: {mt4.get('err')}")

    print("="*80)
    print("Notas: pending≈mensajes en vuelo del group | lag requiere Redis≥7 | refresco cada", REFRESH_SEC, "s")

async def loop():
    r = Redis.from_url(REDIS_URL, decode_responses=True)
    try:
        while True:
            ri  = await get_redis_metrics(r)
            db  = get_db_metrics()
            mt4 = get_mt4_queue_metrics()
            paint(ri, db, mt4)
            await asyncio.sleep(REFRESH_SEC)
    finally:
        await r.close()

if __name__ == "__main__":
    try:
        asyncio.run(loop())
    except KeyboardInterrupt:
        print("\nvisor: stopped")
