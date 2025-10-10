# -*- coding: utf-8 -*-
# listener_pinned_v3p_fix2.py — Solo PINNED (+ linked) con fix chat.id y modo seguro CAPTURE_ALL
# - Corrige filtro: usa Channel.id (positivo) en vez de event.chat_id
# - Incluye linked_chat_id de cada canal fijado
# - Captura edits (MessageEdited)
# - Modo recuperación: CAPTURE_ALL=1 → captura todo canal/megagrupo (ignora filtro pinned)
#
# Uso modo seguro (Windows):  set CAPTURE_ALL=1
# Uso modo seguro (Linux/Mac): export CAPTURE_ALL=1

import os, csv, json, asyncio
from datetime import datetime, timezone
from telethon import TelegramClient, events, functions, types
from telethon.tl.types import Channel
from redis.asyncio import Redis

# ========= (PATCH) imports para .env =========
from pathlib import Path
from dotenv import load_dotenv, find_dotenv

# ========= (PATCH) carga robusta de .env =========
# 1º intenta encontrar .env desde el cwd; si no, usa la ruta del proyecto (.../services/.env)
ENV_PATH = find_dotenv(usecwd=True) or str(Path(__file__).resolve().parents[1].parent / ".env")
load_dotenv(ENV_PATH, override=True)

def _must(varname: str) -> str:
    v = os.getenv(varname, "").strip()
    if not v:
        raise SystemExit(f"[ERROR] Falta {varname} en {ENV_PATH}")
    return v

# ========= CREDENCIALES TELEGRAM =========
api_id       = int(_must("TELEGRAM_API_ID"))                # (PATCH) antes: valor por defecto hardcodeado
api_hash     = _must("TELEGRAM_API_HASH")                   # (PATCH)
phone        = os.getenv("TELEGRAM_PHONE", "+34607190588")  # sin cambios funcionales (permite override por .env)
session_name = os.getenv("TELEGRAM_SESSION", "telethon_session")  # sin cambios

# ========= OPCIONES CSV =========
WRITE_CSV = False  # <--- por defecto OFF (pon True si quieres registro en CSV)
CSV_PATH  = os.getenv("CSV_PATH", r"C:\Pasarela\data\mensajes_raw.csv")

EXCLUDE_USERNAMES = set()
EXCLUDE_TITLES    = set()

# ========= REDIS (Streams) =========
REDIS_URL     = os.getenv("REDIS_URL", "redis://localhost:6379/0")
PARSE_STREAM  = os.getenv("REDIS_STREAM", "pasarela:parse")
DEDUP_TTL_SEC = int(os.getenv("DEDUP_TTL", str(15*24*3600)))  # 15 días
STREAM_MAXLEN = int(os.getenv("STREAM_MAXLEN", "200000"))

# ========= HELPERS =========
def utc_iso(dt):
    if dt is None:
        dt = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")

def ensure_csv_header(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if not os.path.exists(path):
        with open(path, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(
                ["type","channel_id","channel_title","channel_username","msg_id","revision","ts_utc","sender_id","text"]
            )

def append_csv(row):
    with open(CSV_PATH, "a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow(row)

def log(msg: str):
    print(f"[listener] {datetime.now(timezone.utc).isoformat()} {msg}")

# ========= REDIS UTILS (async) =========
async def get_or_set_rev_on_new(r: Redis, channel_id: int, msg_id: int) -> int:
    rev_key = f"tg:rev:{channel_id}:{msg_id}"
    await r.set(rev_key, 1, nx=True)
    val = await r.get(rev_key)
    try: return int(val or 1)
    except: return 1

async def next_rev_on_edit(r: Redis, channel_id: int, msg_id: int) -> int:
    rev_key = f"tg:rev:{channel_id}:{msg_id}"
    new_val = await r.incr(rev_key)
    if new_val < 2:
        await r.set(rev_key, 2)
        return 2
    return new_val

async def dedup_once(r: Redis, channel_id: int, msg_id: int, revision: int) -> bool:
    dkey = f"tg:dedup:{channel_id}:{msg_id}:{revision}"
    ok = await r.set(dkey, "1", nx=True, ex=DEDUP_TTL_SEC)
    return bool(ok)

async def publish_to_stream(r: Redis, fields: dict):
    sec, micro = await r.time()
    sec = int(sec); micro = int(micro)
    dt = datetime.fromtimestamp(sec + micro / 1_000_000, tz=timezone.utc)
    ts_redis_ingest = dt.isoformat(timespec="milliseconds").replace("+00:00", "Z")
    to_send = dict(fields)
    to_send["ts_redis_ingest"] = ts_redis_ingest
    await r.xadd(PARSE_STREAM, to_send, maxlen=STREAM_MAXLEN, approximate=True)

# ========= TELETHON CLIENT =========
client = TelegramClient(session_name, api_id, api_hash)

# ========= PINNED ALLOWLIST =========
PINNED_IDS = set()
CAPTURE_ALL = os.getenv("CAPTURE_ALL", "0") == "1"  # modo seguro: captura todo canal/megagrupo

async def load_pinned_allowlist():
    """Actualiza la lista de chats/canales fijados (pinned) y añade sus linked_chat_id si existen."""
    global PINNED_IDS
    new_ids = set()
    pinned_list = []  # [(id, title)]
    async for d in client.iter_dialogs():
        ent = d.entity
        if isinstance(ent, Channel) and not getattr(ent, "left", False):
            title = getattr(ent, "title", "") or ""
            username = getattr(ent, "username", "") or ""
            if (username in EXCLUDE_USERNAMES) or (title in EXCLUDE_TITLES):
                continue
            if d.pinned:
                cid = int(ent.id)
                new_ids.add(cid)
                pinned_list.append((cid, title))
                # incluir también el grupo de comentarios enlazado, si existe
                linked_id = getattr(ent, "linked_chat_id", None)
                if linked_id:
                    lid = int(linked_id)
                    new_ids.add(lid)
                    pinned_list.append((lid, f"{title} [linked]"))
    PINNED_IDS = new_ids
    if pinned_list:
        log(f"[pinned] {len(pinned_list)} chats fijados activos:")
        for cid, title in pinned_list:
            log(f"    • {cid} → {title}")
    else:
        log("[pinned] Ningún chat fijado activo detectado.")

# ========= MAIN =========
async def main():
    r: Redis = Redis.from_url(REDIS_URL, decode_responses=True)
    await client.start(phone=phone)

    if WRITE_CSV:
        ensure_csv_header(CSV_PATH)

    await load_pinned_allowlist()
    log(f"Publicando {'TODOS los canales (CAPTURE_ALL)' if CAPTURE_ALL else 'SOLO canales fijados'} en Redis Stream: {PARSE_STREAM}. CSV={'ON' if WRITE_CSV else 'OFF'}. Ctrl+C para salir.")

    # ==== eventos ====
    @client.on(events.Raw)
    async def on_raw(update):
        if isinstance(update, (types.UpdatePinnedDialogs, types.UpdatePeerSettings,
                               types.UpdateDialogFilters, types.UpdateDialogFilter)):
            log("[pinned] Cambio detectado, recargando allowlist...")
            await load_pinned_allowlist()

    async def periodic_refresh():
        while True:
            await asyncio.sleep(300)  # cada 5 min
            await load_pinned_allowlist()
    asyncio.create_task(periodic_refresh())

    # ==== NEW MESSAGE ====
    @client.on(events.NewMessage())
    async def on_new(event: events.NewMessage.Event):
        chat = await event.get_chat()
        # id POSITIVO del canal
        ch_id = int(getattr(chat, "id", 0)) if isinstance(chat, Channel) else int(event.chat_id or 0)
        if not isinstance(chat, Channel) or getattr(chat, "left", False):
            return
        if not (chat.broadcast or chat.megagroup):
            return
        if (not CAPTURE_ALL) and (ch_id not in PINNED_IDS):
            return

        title    = getattr(chat, "title", "") or ""
        username = getattr(chat, "username", "") or ""
        if username in EXCLUDE_USERNAMES or title in EXCLUDE_TITLES:
            return

        msg  = event.message
        text = (msg.message or "").replace("\r", " ").strip()
        if not text:
            return

        rev = await get_or_set_rev_on_new(r, ch_id, msg.id)
        if not await dedup_once(r, ch_id, msg.id, rev):
            return

        fields = {
            "type": "new",
            "channel_id": ch_id,
            "channel_username": username,
            "channel_title": title,
            "msg_id": msg.id,
            "revision": rev,
            "ts_utc": utc_iso(msg.date),
            "sender_id": str(msg.sender_id or ""),
            "text/raw": text,
            "estado_operacion": "0"
        }
        await publish_to_stream(r, fields)
        pref = "NEW*" if CAPTURE_ALL and (ch_id not in PINNED_IDS) else "NEW "
        log(f"{pref} | ch_id={ch_id} ({title or username}) msg_id={msg.id} rev={rev} → {PARSE_STREAM}")
        if WRITE_CSV:
            append_csv(["new", ch_id, title, username, msg.id, rev, utc_iso(msg.date), str(msg.sender_id or ""), text])

    # ==== MESSAGE EDITED ====
    @client.on(events.MessageEdited())
    async def on_edit(event: events.MessageEdited.Event):
        chat = await event.get_chat()
        ch_id = int(getattr(chat, "id", 0)) if isinstance(chat, Channel) else int(event.chat_id or 0)
        if not isinstance(chat, Channel) or getattr(chat, "left", False):
            return
        if not (chat.broadcast or chat.megagroup):
            return
        if (not CAPTURE_ALL) and (ch_id not in PINNED_IDS):
            return

        title    = getattr(chat, "title", "") or ""
        username = getattr(chat, "username", "") or ""
        if username in EXCLUDE_USERNAMES or title in EXCLUDE_TITLES:
            return

        msg  = event.message
        text = (msg.message or "").replace("\r", " ").strip()
        if not text:
            return

        rev = await next_rev_on_edit(r, ch_id, msg.id)
        if not await dedup_once(r, ch_id, msg.id, rev):
            return

        fields = {
            "type": "edit",
            "channel_id": ch_id,
            "channel_username": username,
            "channel_title": title,
            "msg_id": msg.id,
            "revision": rev,
            "ts_utc": utc_iso(msg.edit_date or msg.date),
            "sender_id": str(msg.sender_id or ""),
            "text/raw": text,
            "estado_operacion": "0"
        }
        await publish_to_stream(r, fields)
        pref = "EDIT*" if CAPTURE_ALL and (ch_id not in PINNED_IDS) else "EDIT"
        log(f"{pref} | ch_id={ch_id} ({title or username}) msg_id={msg.id} rev={rev} → {PARSE_STREAM}")
        if WRITE_CSV:
            append_csv(["edit", ch_id, title, username, msg.id, rev,
                        utc_iso(msg.edit_date or msg.date), str(msg.sender_id or ""), text])

    await client.run_until_disconnected()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("listener stopped")

