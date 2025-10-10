# -*- coding: utf-8 -*-
# listener.py (v3) — Escucha TODOS los canales/supergrupos y publica en Redis Streams (campos planos)
# - Deduplicación y revisionado persistentes en Redis
# - CSV opcional (desactivado por defecto)
# - NUEVO v3: publica campos planos + ts_redis_ingest (UTC) en XADD (sin JSON encapsulado)

import os, csv, json, asyncio
from datetime import datetime, timezone
from telethon import TelegramClient, events
from telethon.tl.types import Channel
from redis.asyncio import Redis

# ========= CREDENCIALES TELEGRAM =========
api_id       = int(os.getenv("TELEGRAM_API_ID", "23185982"))
api_hash     = os.getenv("TELEGRAM_API_HASH", "c647020eccbc328284afbc940c06db81")
phone        = os.getenv("TELEGRAM_PHONE", "+34607190588")
session_name = os.getenv("TELEGRAM_SESSION", "telethon_session")

# ========= OPCIONES CSV =========
WRITE_CSV = False  # <--- por defecto OFF (pon True si quieres registro en CSV)
CSV_PATH  = os.getenv("CSV_PATH", r"C:\Pasarela\data\mensajes_raw.csv")

EXCLUDE_USERNAMES = set()  # ej: {"spamchannel"}
EXCLUDE_TITLES    = set()  # ej: {"Canal de Pruebas"}

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
    # ISO con milisegundos + 'Z'
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
    """En mensaje NUEVO: asegura rev=1 si no existe. Devuelve la revisión actual."""
    rev_key = f"tg:rev:{channel_id}:{msg_id}"
    await r.set(rev_key, 1, nx=True)
    val = await r.get(rev_key)
    try:
        return int(val or 1)
    except:
        return 1

async def next_rev_on_edit(r: Redis, channel_id: int, msg_id: int) -> int:
    """En EDICIÓN: incrementa rev. Si por carrera no existía, fuerza 2."""
    rev_key = f"tg:rev:{channel_id}:{msg_id}"
    new_val = await r.incr(rev_key)
    if new_val < 2:
        await r.set(rev_key, 2)
        return 2
    return new_val

async def dedup_once(r: Redis, channel_id: int, msg_id: int, revision: int) -> bool:
    """Devuelve True si es la PRIMERA vez que vemos (canal,msg,rev)."""
    dkey = f"tg:dedup:{channel_id}:{msg_id}:{revision}"
    ok = await r.set(dkey, "1", nx=True, ex=DEDUP_TTL_SEC)
    return bool(ok)

async def publish_to_stream(r: Redis, fields: dict):
    """
    v3: Publica CAMPOS PLANOS en el stream, sin JSON.
    Añade ts_redis_ingest (UTC) con la hora del servidor Redis para trazabilidad.
    """
    # Hora del servidor Redis
    sec, micro = await r.time()  # ['1730402962', '123456'] con decode_responses=True
    sec = int(sec); micro = int(micro)
    dt = datetime.fromtimestamp(sec + micro / 1_000_000, tz=timezone.utc)
    ts_redis_ingest = dt.isoformat(timespec="milliseconds").replace("+00:00", "Z")

    to_send = dict(fields)
    to_send["ts_redis_ingest"] = ts_redis_ingest

    await r.xadd(PARSE_STREAM, to_send, maxlen=STREAM_MAXLEN, approximate=True)

# ========= TELETHON CLIENT =========
client = TelegramClient(session_name, api_id, api_hash)

async def print_inventory():
    """Informativo: lista canales/supergrupos visibles en tu cuenta."""
    count = 0
    async for d in client.iter_dialogs():
        ent = d.entity
        if isinstance(ent, Channel) and not getattr(ent, "left", False):
            title = getattr(ent, "title", "") or ""
            usern = getattr(ent, "username", "") or ""
            if (usern in EXCLUDE_USERNAMES) or (title in EXCLUDE_TITLES):
                continue
            log(f"canal detectado: id={ent.id} title='{title}' username='{usern}'")
            count += 1
    log(f"Total canales/supergrupos detectados: {count}")

async def main():
    r: Redis = Redis.from_url(REDIS_URL, decode_responses=True)
    await client.start(phone=phone)

    if WRITE_CSV:
        ensure_csv_header(CSV_PATH)

    await print_inventory()
    log(f"Publicando en Redis Stream (campos planos): {PARSE_STREAM}. CSV={'ON' if WRITE_CSV else 'OFF'}. Ctrl+C para salir.")

    @client.on(events.NewMessage())
    async def on_new(event: events.NewMessage.Event):
        chat = await event.get_chat()
        if not isinstance(chat, Channel) or getattr(chat, "left", False):
            return

        title    = getattr(chat, "title", "") or ""
        username = getattr(chat, "username", "") or ""
        if username in EXCLUDE_USERNAMES or title in EXCLUDE_TITLES:
            return

        msg  = event.message
        text = (msg.message or "").replace("\r", " ").strip()
        if not text:
            return

        ch_id = int(event.chat_id)
        rev   = await get_or_set_rev_on_new(r, ch_id, msg.id)

        # Dedup exacto por (canal, msg, rev)
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
            # === CAMBIO 1: publicar como text/raw en Redis ===
            "text/raw": text,
            # === CAMBIO 2: estado_operacion inicial exigido por la línea base ===
            "estado_operacion": "0"
        }
        await publish_to_stream(r, fields)
        log(f"NEW  | ch_id={ch_id} ({title or username}) msg_id={msg.id} rev={rev} → enviado a {PARSE_STREAM}")

        if WRITE_CSV:
            # CSV se mantiene EXACTAMENTE igual (columna 'text'), sin cambios.
            append_csv(["new", ch_id, title, username, msg.id, rev, utc_iso(msg.date), str(msg.sender_id or ""), text])

    @client.on(events.MessageEdited())
    async def on_edit(event: events.MessageEdited.Event):
        chat = await event.get_chat()
        if not isinstance(chat, Channel) or getattr(chat, "left", False):
            return

        title    = getattr(chat, "title", "") or ""
        username = getattr(chat, "username", "") or ""
        if username in EXCLUDE_USERNAMES or title in EXCLUDE_TITLES:
            return

        msg  = event.message
        text = (msg.message or "").replace("\r", " ").strip()
        if not text:
            return

        ch_id = int(event.chat_id)
        rev   = await next_rev_on_edit(r, ch_id, msg.id)

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
            # === CAMBIO 1: publicar como text/raw en Redis ===
            "text/raw": text,
            # === CAMBIO 2: estado_operacion inicial exigido por la línea base ===
            "estado_operacion": "0"
        }
        await publish_to_stream(r, fields)
        log(f"EDIT | ch_id={ch_id} ({title or username}) msg_id={msg.id} rev={rev} → enviado a {PARSE_STREAM}")

        if WRITE_CSV:
            # CSV se mantiene EXACTAMENTE igual (columna 'text'), sin cambios.
            append_csv(["edit", ch_id, title, username, msg.id, rev,
                        utc_iso(msg.edit_date or msg.date), str(msg.sender_id or ""), text])

    await client.run_until_disconnected()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("listener stopped")
