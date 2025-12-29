# -*- coding: utf-8 -*-
# listener.py — Listener de Telegram con configuración desde archivo JSON
# - Lee canales desde archivo de configuración (config/channels.json)
# - Captura mensajes nuevos y editados
# - Hot-reload: recarga configuración automáticamente
# - Publica mensajes en Redis Streams

import os, csv, json, asyncio, subprocess
from datetime import datetime, timezone
from telethon import TelegramClient, events, functions, types
from telethon.tl.types import Channel
from redis.asyncio import Redis
import redis.exceptions

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

# ========= REDIS WATCHDOG (auto-restart) =========
REDIS_SERVICE_NAME = os.getenv("REDIS_SERVICE_NAME", "Memurai")  # Nombre del servicio de Redis en Windows
REDIS_RESTART_MAX_RETRIES = int(os.getenv("REDIS_RESTART_MAX_RETRIES", "3"))  # Intentos máximos de reinicio
REDIS_RESTART_WAIT_SEC = int(os.getenv("REDIS_RESTART_WAIT_SEC", "2"))  # Segundos a esperar tras reiniciar

class RedisUnrecoverableError(Exception):
    """Excepción lanzada cuando Redis no se puede recuperar después de todos los intentos."""
    pass

async def check_and_restart_redis() -> bool:
    """
    Verifica si Redis responde y, si no, reinicia el servicio de Windows.
    Retorna True si Redis está disponible (o se recuperó), False si no se pudo recuperar.
    """
    log("[REDIS-WATCHDOG] Verificando estado de Redis...")
    
    # 1. Intentar ping rápido a Redis
    try:
        test_r = Redis.from_url(REDIS_URL, decode_responses=True, socket_connect_timeout=2)
        await test_r.ping()
        await test_r.aclose()
        log("[REDIS-WATCHDOG] ✅ Redis responde correctamente")
        return True
    except Exception as e:
        log(f"[REDIS-WATCHDOG] ⚠️  Redis NO responde: {e}")
    
    # 2. Redis no responde, verificar y reiniciar servicio
    log(f"[REDIS-WATCHDOG] Verificando servicio de Windows: {REDIS_SERVICE_NAME}")
    
    try:
        # Verificar estado del servicio
        check_cmd = f"Get-Service -Name '{REDIS_SERVICE_NAME}' | Select-Object -ExpandProperty Status"
        proc = await asyncio.create_subprocess_shell(
            f"powershell -Command \"{check_cmd}\"",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        status = stdout.decode().strip() if stdout else ""
        
        log(f"[REDIS-WATCHDOG] Estado del servicio: {status}")
        
        # Si el servicio está detenido o no está corriendo, iniciarlo/reiniciarlo
        if status.lower() not in ["running", "startpending"]:
            log(f"[REDIS-WATCHDOG] 🔄 Reiniciando servicio {REDIS_SERVICE_NAME}...")
            
            # Intentar iniciar/reiniciar el servicio
            restart_cmd = f"Start-Service -Name '{REDIS_SERVICE_NAME}'; if ($?) {{ Write-Output 'OK' }} else {{ Write-Output 'FAIL' }}"
            proc = await asyncio.create_subprocess_shell(
                f"powershell -Command \"{restart_cmd}\"",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            result = stdout.decode().strip() if stdout else ""
            
            if "OK" in result or proc.returncode == 0:
                log(f"[REDIS-WATCHDOG] ✅ Servicio {REDIS_SERVICE_NAME} iniciado")
            else:
                log(f"[REDIS-WATCHDOG] ❌ Error iniciando servicio: {stderr.decode() if stderr else 'Unknown error'}")
                return False
        else:
            log(f"[REDIS-WATCHDOG] ⚠️  Servicio está corriendo pero Redis no responde. Reiniciando...")
            restart_cmd = f"Restart-Service -Name '{REDIS_SERVICE_NAME}'; if ($?) {{ Write-Output 'OK' }} else {{ Write-Output 'FAIL' }}"
            proc = await asyncio.create_subprocess_shell(
                f"powershell -Command \"{restart_cmd}\"",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            result = stdout.decode().strip() if stdout else ""
            
            if "OK" not in result and proc.returncode != 0:
                log(f"[REDIS-WATCHDOG] ❌ Error reiniciando servicio: {stderr.decode() if stderr else 'Unknown error'}")
                return False
        
        # 3. Esperar a que Redis esté disponible
        log(f"[REDIS-WATCHDOG] ⏳ Esperando {REDIS_RESTART_WAIT_SEC}s a que Redis inicie...")
        await asyncio.sleep(REDIS_RESTART_WAIT_SEC)
        
        # 4. Verificar que Redis responde (con retry)
        for attempt in range(REDIS_RESTART_MAX_RETRIES):
            try:
                test_r = Redis.from_url(REDIS_URL, decode_responses=True, socket_connect_timeout=3)
                await test_r.ping()
                await test_r.aclose()
                log(f"[REDIS-WATCHDOG] ✅ Redis recuperado después de {attempt + 1} intento(s)")
                return True
            except Exception as e:
                if attempt < REDIS_RESTART_MAX_RETRIES - 1:
                    wait_time = 2 * (attempt + 1)  # Backoff exponencial: 2s, 4s, 6s
                    log(f"[REDIS-WATCHDOG] ⏳ Intento {attempt + 1}/{REDIS_RESTART_MAX_RETRIES} falló, esperando {wait_time}s...")
                    await asyncio.sleep(wait_time)
                else:
                    log(f"[REDIS-WATCHDOG] ❌ Redis NO se recuperó después de {REDIS_RESTART_MAX_RETRIES} intentos")
        
        return False
        
    except Exception as e:
        log(f"[REDIS-WATCHDOG] ❌ Error crítico verificando/reiniciando Redis: {e}")
        return False

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
    """
    Publica mensaje en Redis Stream con recuperación automática si Redis cae.
    Si falla la inserción, verifica y reinicia Redis automáticamente, luego reintenta.
    """
    max_retries = 2  # Intentos máximos de publicación (1 inicial + 1 después de reinicio)
    
    for attempt in range(max_retries):
        try:
            # Intentar obtener timestamp de Redis
            sec, micro = await r.time()
            sec = int(sec); micro = int(micro)
            dt = datetime.fromtimestamp(sec + micro / 1_000_000, tz=timezone.utc)
            ts_redis_ingest = dt.isoformat(timespec="milliseconds").replace("+00:00", "Z")
            to_send = dict(fields)
            to_send["ts_redis_ingest"] = ts_redis_ingest
            
            # Intentar insertar en stream
            await r.xadd(PARSE_STREAM, to_send, maxlen=STREAM_MAXLEN, approximate=True)
            return  # ✅ Éxito, salir
            
        except (ConnectionError, TimeoutError, redis.exceptions.ConnectionError, 
                redis.exceptions.TimeoutError, OSError) as e:
            # Error de conexión - Redis puede estar caído
            if attempt == 0:
                # Primer intento falló, verificar y reiniciar Redis
                log(f"[REDIS-WATCHDOG] ⚠️  Error publicando en Redis (intento {attempt + 1}): {e}")
                log(f"[REDIS-WATCHDOG] 🔄 Intentando recuperar Redis...")
                
                redis_recovered = await check_and_restart_redis()
                
                if redis_recovered:
                    log(f"[REDIS-WATCHDOG] ✅ Redis recuperado, reintentando publicación...")
                    # Continuar al siguiente intento (reintentar publicación)
                    continue
                else:
                    # Redis no se pudo recuperar después de todos los intentos
                    log(f"[REDIS-WATCHDOG] ❌ No se pudo recuperar Redis después de {REDIS_RESTART_MAX_RETRIES} intentos.")
                    raise RedisUnrecoverableError("Redis no se pudo recuperar. El listener se detendrá.")
            else:
                # Segundo intento también falló después de reiniciar
                log(f"[REDIS-WATCHDOG] ❌ Error persistente después de reiniciar Redis: {e}")
                raise RedisUnrecoverableError("Redis no responde después del reinicio. El listener se detendrá.")
                
        except Exception as e:
            # Otro tipo de error (no de conexión) - no intentar recuperar
            log(f"[REDIS-WATCHDOG] ❌ Error no relacionado con conexión: {e}")
            raise  # Re-lanzar excepción

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
        try:
            await publish_to_stream(r, fields)
            log(f"NEW | ch_id={ch_id} ({title or username}) msg_id={msg.id} rev={rev} → {PARSE_STREAM}")
            if WRITE_CSV:
                append_csv(["new", ch_id, title, username, msg.id, rev, utc_iso(msg.date), str(msg.sender_id or ""), text])
        except RedisUnrecoverableError:
            # Redis no se pudo recuperar - detener listener
            raise

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
        try:
            await publish_to_stream(r, fields)
            log(f"EDIT | ch_id={ch_id} ({title or username}) msg_id={msg.id} rev={rev} → {PARSE_STREAM}")
            if WRITE_CSV:
                append_csv(["edit", ch_id, title, username, msg.id, rev,
                            utc_iso(msg.edit_date or msg.date), str(msg.sender_id or ""), text])
        except RedisUnrecoverableError:
            # Redis no se pudo recuperar - detener listener
            raise

    try:
        await client.run_until_disconnected()
    except RedisUnrecoverableError as e:
        # Redis no se pudo recuperar - detener listener con mensaje claro
        log("")
        log("=" * 80)
        log("❌ ERROR CRÍTICO: REDIS NO SE PUEDE RECUPERAR")
        log("=" * 80)
        log("")
        log("El listener se ha detenido porque Redis no responde después de múltiples intentos.")
        log("")
        log("ACCIONES REQUERIDAS:")
        log(f"  1. Verifica que el servicio '{REDIS_SERVICE_NAME}' esté instalado y configurado correctamente")
        log(f"  2. Inicia el servicio manualmente: Start-Service -Name '{REDIS_SERVICE_NAME}'")
        log("  3. Verifica que Redis esté escuchando en el puerto 6379")
        log(f"  4. Verifica la configuración REDIS_URL: {REDIS_URL}")
        log("")
        log("Una vez que Redis esté funcionando, reinicia el listener.")
        log("=" * 80)
        log("")
        raise SystemExit(1)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("listener stopped")
    except RedisUnrecoverableError:
        # Ya se manejó arriba, solo salir
        pass

