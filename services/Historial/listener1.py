# -*- coding: utf-8 -*-
# listener.py (v1) — Escucha TODOS los canales/supergrupos de tu cuenta
import os, csv
from datetime import datetime, timezone
from telethon import TelegramClient, events
from telethon.tl.types import Channel

# === CREDENCIALES ===
api_id       = 23185982
api_hash     = "c647020eccbc328284afbc940c06db81"
phone        = "+34607190588"          # <-- tu número
session_name = "telethon_session"

# === OPCIONES ===
WRITE_CSV = True
CSV_PATH  = r"C:\Pasarela\data\mensajes_raw.csv"

EXCLUDE_USERNAMES = set()
EXCLUDE_TITLES    = set()

# === HELPERS ===
def utc_iso(dt):
    if dt is None:
        dt = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()

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
    # Versión sin warning: datetime con zona horaria (UTC)
    print(f"[listener] {datetime.now(timezone.utc).isoformat()} {msg}")

# === CLIENTE TELETHON ===
client = TelegramClient(session_name, api_id, api_hash)

# Mapa en memoria para versionar ediciones por (channel_id, msg_id)
revision_map: dict[tuple[int, int], int] = {}

async def main():
    await client.start(phone=phone)

    if WRITE_CSV:
        ensure_csv_header(CSV_PATH)

    log("Escuchando TODOS los canales/supergrupos. Ctrl+C para salir.")

    @client.on(events.NewMessage())
    async def on_new(event: events.NewMessage.Event):
        chat = await event.get_chat()
        if not isinstance(chat, Channel) or getattr(chat, "left", False):
            return

        title = getattr(chat, "title", "") or ""
        username = getattr(chat, "username", "") or ""
        if username in EXCLUDE_USERNAMES or title in EXCLUDE_TITLES:
            return

        msg = event.message
        text = (msg.message or "").replace("\r", " ").strip()
        if not text:
            return

        ch_id = int(event.chat_id)
        key = (ch_id, msg.id)
        rev = revision_map.get(key, 0) or 1
        revision_map[key] = rev

        log(f"NEW  | ch_id={ch_id} ({title or username}) msg_id={msg.id} rev={rev} "
            f"ts={utc_iso(msg.date)} → {text[:200].replace('\n',' ')}")

        if WRITE_CSV:
            append_csv(["new", ch_id, title, username, msg.id, rev, utc_iso(msg.date), str(msg.sender_id or ""), text])

    @client.on(events.MessageEdited())
    async def on_edit(event: events.MessageEdited.Event):
        chat = await event.get_chat()
        if not isinstance(chat, Channel) or getattr(chat, "left", False):
            return

        title = getattr(chat, "title", "") or ""
        username = getattr(chat, "username", "") or ""
        if username in EXCLUDE_USERNAMES or title in EXCLUDE_TITLES:
            return

        msg = event.message
        text = (msg.message or "").replace("\r", " ").strip()
        if not text:
            return

        ch_id = int(event.chat_id)
        key = (ch_id, msg.id)
        rev = (revision_map.get(key, 1) + 1)
        if rev < 2:
            rev = 2
        revision_map[key] = rev

        log(f"EDIT | ch_id={ch_id} ({title or username}) msg_id={msg.id} rev={rev} "
            f"ts={utc_iso(msg.edit_date or msg.date)} → {text[:200].replace('\n',' ')}")

        if WRITE_CSV:
            append_csv(["edit", ch_id, title, username, msg.id, rev, utc_iso(msg.edit_date or msg.date),
                        str(msg.sender_id or ""), text])

    await client.run_until_disconnected()

if __name__ == "__main__":
    try:
        with client:
            client.loop.run_until_complete(main())
    except KeyboardInterrupt:
        print("listener stopped")
