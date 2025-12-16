# -*- coding: utf-8 -*-
# listener.py — Listener de Telegram con configuración desde archivo JSON
# - Lee canales desde archivo de configuración (config/channels.json)
# - Captura mensajes nuevos y editados
# - Hot-reload: recarga configuración automáticamente
# - Publica mensajes en Redis Streams

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

# ========= FILTRO DE MENSAJES ANTIGUOS =========
# Ignorar mensajes más antiguos que X minutos desde el inicio del listener
# Esto evita que el sistema se atasque procesando mensajes históricos
MESSAGE_AGE_LIMIT_MINUTES = int(os.getenv("MESSAGE_AGE_LIMIT_MINUTES", "5"))  # Por defecto: 5 minutos
_LISTENER_START_TIME = None

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

# ========= CHANNEL CONFIGURATION =========
CHANNEL_IDS = set()
CHANNEL_CONFIG = {}  # {channel_id: {title, username, include_linked}}
CONFIG_FILE = os.getenv("CHANNELS_CONFIG", str(Path(__file__).resolve().parents[1].parent / "config" / "channels.json"))
CONFIG_FILE_MTIME = 0

def load_channels_from_file():
    """Carga canales desde archivo JSON de configuración."""
    global CHANNEL_IDS, CHANNEL_CONFIG, CONFIG_FILE_MTIME
    
    config_path = Path(CONFIG_FILE)
    
    if not config_path.exists():
        log(f"[CONFIG] Archivo no encontrado: {CONFIG_FILE}")
        log(f"[CONFIG] Ejecuta 'python list_channels.py' para generar el archivo de configuración.")
        return False
    
    try:
        # Verificar si el archivo cambió
        current_mtime = config_path.stat().st_mtime
        if current_mtime == CONFIG_FILE_MTIME:
            return True  # Sin cambios, no recargar
        CONFIG_FILE_MTIME = current_mtime
        
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
        
        new_ids = set()
        new_config = {}
        enabled_count = 0
        
        for ch in config.get("channels", []):
            if not ch.get("enabled", True):
                continue
            
            cid = int(ch["id"])
            new_ids.add(cid)
            new_config[cid] = {
                "title": ch.get("title", ""),
                "username": ch.get("username", ""),
                "include_linked": ch.get("include_linked", False)
            }
            enabled_count += 1
            
            # Incluir linked_chat_id si está configurado
            if ch.get("include_linked", False):
                # Necesitamos obtener el linked_id del canal real
                # Lo haremos en validación async
                pass
        
        CHANNEL_IDS = new_ids
        CHANNEL_CONFIG = new_config
        
        log(f"[CONFIG] {enabled_count} canales cargados desde {CONFIG_FILE}")
        for cid, info in list(new_config.items())[:10]:  # Mostrar primeros 10
            log(f"    • {cid} → {info['title'] or info['username'] or 'N/A'}")
        if len(new_config) > 10:
            log(f"    ... y {len(new_config) - 10} más")
        
        return True
        
    except json.JSONDecodeError as e:
        log(f"[ERROR] JSON inválido en {CONFIG_FILE}: {e}")
        return False
    except Exception as e:
        log(f"[ERROR] Error cargando configuración: {e}")
        return False

async def validate_and_enrich_channels():
    """Valida que los canales existen y añade linked_chat_id si está configurado."""
    global CHANNEL_IDS, CHANNEL_CONFIG
    
    if not CHANNEL_IDS:
        return
    
    validated_ids = set()
    validated_config = {}
    
    async for d in client.iter_dialogs():
        ent = d.entity
        if not isinstance(ent, Channel) or getattr(ent, "left", False):
            continue
        
        cid = int(ent.id)
        if cid not in CHANNEL_IDS:
            continue
        
        # Canal encontrado y válido
        validated_ids.add(cid)
        config = CHANNEL_CONFIG.get(cid, {})
        validated_config[cid] = config.copy()
        
        # Si include_linked está activo, añadir el linked_chat_id
        if config.get("include_linked", False):
            linked_id = getattr(ent, "linked_chat_id", None)
            if linked_id:
                lid = int(linked_id)
                validated_ids.add(lid)
                validated_config[lid] = {
                    "title": f"{config.get('title', '')} [linked]",
                    "username": config.get("username", ""),
                    "include_linked": False
                }
    
    # Verificar canales no encontrados
    missing = CHANNEL_IDS - validated_ids
    if missing:
        log(f"[WARNING] {len(missing)} canales no encontrados o sin acceso:")
        for cid in missing:
            config = CHANNEL_CONFIG.get(cid, {})
            log(f"    • {cid} → {config.get('title', 'N/A')}")
    
    CHANNEL_IDS = validated_ids
    CHANNEL_CONFIG = validated_config
    
    if validated_ids:
        log(f"[CONFIG] {len(validated_ids)} canales validados y activos")

# ========= MAIN =========
async def main():
    r: Redis = Redis.from_url(REDIS_URL, decode_responses=True)
    await client.start(phone=phone)

    if WRITE_CSV:
        ensure_csv_header(CSV_PATH)

    # Cargar configuración inicial
    if not load_channels_from_file():
        log("[ERROR] No se pudo cargar configuración. Verifica el archivo channels.json")
        return
    
    await validate_and_enrich_channels()
    
    if not CHANNEL_IDS:
        log("[ERROR] Ningún canal válido encontrado. Verifica tu configuración.")
        return
    
    log(f"Publicando mensajes de {len(CHANNEL_IDS)} canales en Redis Stream: {PARSE_STREAM}")
    log(f"CSV={'ON' if WRITE_CSV else 'OFF'}. Ctrl+C para salir.")
    log(f"[FILTRO] Ignorando mensajes más antiguos de {MESSAGE_AGE_LIMIT_MINUTES} minutos para evitar atasco")

    # Hot-reload: recargar configuración periódicamente
    async def periodic_refresh():
        while True:
            await asyncio.sleep(600)  # cada 10 minutos verificar cambios
            if load_channels_from_file():
                await validate_and_enrich_channels()
                log(f"[CONFIG] Recarga automática completada. {len(CHANNEL_IDS)} canales activos.")
    
    asyncio.create_task(periodic_refresh())

    # ==== NEW MESSAGE ====
    @client.on(events.NewMessage())
    async def on_new(event: events.NewMessage.Event):
        # Filtrar mensajes antiguos para evitar atasco
        msg = event.message
        if msg.date:
            msg_time = msg.date.replace(tzinfo=timezone.utc) if msg.date.tzinfo is None else msg.date
            now = datetime.now(timezone.utc)
            age_minutes = (now - msg_time).total_seconds() / 60
            if age_minutes > MESSAGE_AGE_LIMIT_MINUTES:
                # Mensaje demasiado antiguo, ignorar silenciosamente
                return
        
        chat = await event.get_chat()
        # id POSITIVO del canal
        ch_id = int(getattr(chat, "id", 0)) if isinstance(chat, Channel) else int(event.chat_id or 0)
        if not isinstance(chat, Channel) or getattr(chat, "left", False):
            return
        if not (chat.broadcast or chat.megagroup):
            return
        if ch_id not in CHANNEL_IDS:
            return

        title    = getattr(chat, "title", "") or ""
        username = getattr(chat, "username", "") or ""
        # Fallback: usar username del archivo de configuración si el canal no tiene username en Telegram
        if not username:
            config_username = CHANNEL_CONFIG.get(ch_id, {}).get("username", "")
            if config_username:
                username = config_username
        if username in EXCLUDE_USERNAMES or title in EXCLUDE_TITLES:
            return

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
        log(f"NEW | ch_id={ch_id} ({title or username}) msg_id={msg.id} rev={rev} → {PARSE_STREAM}")
        if WRITE_CSV:
            append_csv(["new", ch_id, title, username, msg.id, rev, utc_iso(msg.date), str(msg.sender_id or ""), text])

    # ==== MESSAGE EDITED ====
    @client.on(events.MessageEdited())
    async def on_edit(event: events.MessageEdited.Event):
        # Filtrar mensajes antiguos para evitar atasco
        msg = event.message
        edit_time = msg.edit_date or msg.date
        if edit_time:
            msg_time = edit_time.replace(tzinfo=timezone.utc) if edit_time.tzinfo is None else edit_time
            now = datetime.now(timezone.utc)
            age_minutes = (now - msg_time).total_seconds() / 60
            if age_minutes > MESSAGE_AGE_LIMIT_MINUTES:
                # Mensaje demasiado antiguo, ignorar silenciosamente
                return
        
        chat = await event.get_chat()
        ch_id = int(getattr(chat, "id", 0)) if isinstance(chat, Channel) else int(event.chat_id or 0)
        if not isinstance(chat, Channel) or getattr(chat, "left", False):
            return
        if not (chat.broadcast or chat.megagroup):
            return
        if ch_id not in CHANNEL_IDS:
            return

        title    = getattr(chat, "title", "") or ""
        username = getattr(chat, "username", "") or ""
        # Fallback: usar username del archivo de configuración si el canal no tiene username en Telegram
        if not username:
            config_username = CHANNEL_CONFIG.get(ch_id, {}).get("username", "")
            if config_username:
                username = config_username
        if username in EXCLUDE_USERNAMES or title in EXCLUDE_TITLES:
            return

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
        log(f"EDIT | ch_id={ch_id} ({title or username}) msg_id={msg.id} rev={rev} → {PARSE_STREAM}")
        if WRITE_CSV:
            append_csv(["edit", ch_id, title, username, msg.id, rev,
                        utc_iso(msg.edit_date or msg.date), str(msg.sender_id or ""), text])

    await client.run_until_disconnected()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("listener stopped")

