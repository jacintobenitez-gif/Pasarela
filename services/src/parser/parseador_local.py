# -*- coding: utf-8 -*-
# parseador_local31.py — v3.3.4 (patch A+B)
# Mantiene: ruta fija MT4/Files, newline='' + flush(), trazas visuales,
# estados y política de atomicidad/rollback, score<10 -> estado=6 solo BBDD.
# Patch A: evitar duplicados (EDIT) por UNIQUE(oid) sin romper CSV.
# Patch B: SQLite WAL + busy_timeout + reintentos ante "database is locked".

import os, sys, csv, json, time, socket, threading, atexit
import sqlite3
import redis
from typing import Optional
from datetime import datetime, timezone
from time import sleep

# --- (NUEVO) Carga .env robusta ---
from pathlib import Path
from dotenv import load_dotenv, find_dotenv
ENV_PATH = find_dotenv(usecwd=True) or str(Path(__file__).resolve().parents[1].parent / ".env")
load_dotenv(ENV_PATH, override=True)

# --- Telegram (NUEVO, solo envío) ---
import asyncio
from telethon import TelegramClient, errors

# --- PATH robusto para imports locales (añade padre para paquetes hermanos) ---
BASE_DIR  = os.path.dirname(os.path.abspath(__file__))          # .../services/src/parser
PARENT_DIR = os.path.dirname(BASE_DIR)                           # .../services/src
if PARENT_DIR not in sys.path:
    sys.path.insert(0, PARENT_DIR)
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# === IMPORT CORRECTO DEL ANALIZADOR (SIN NOMBRES NUEVOS) ===
from reglasnegocio.reglasnegocio import clasificar_mensajes, formatear_senal, formatear_motivo_rechazo

# =================== CONFIG ===================
REDIS_URL    = os.getenv("REDIS_URL", "redis://localhost:6379/0")
REDIS_STREAM = os.getenv("REDIS_STREAM", "pasarela:parse")
REDIS_GROUP  = os.getenv("REDIS_GROUP", "parser")
CONSUMER     = os.getenv("REDIS_CONSUMER", "local")

# Usar misma ruta por defecto que visor.py para evitar inconsistencias
_DEFAULT_DB_PATH = r"C:\Pasarela\services\pasarela.db"
DB_FILE      = os.getenv("PASARELA_DB", _DEFAULT_DB_PATH)
TABLE        = os.getenv("PASARELA_TABLE", "Trazas_Unica")  # << PARCHE: tabla destino unificada

# === Ruta MT4/Files (lee de .env; fallback a tu ruta fija actual) ===
MT4_QUEUE_DIR = os.getenv(
    "MT4_FILES_ABS",
    r"C:\Users\Administrator\AppData\Roaming\MetaQuotes\Terminal\BB190E062770E27C3E79391AB0D1A117\MQL4\Files"
)
CSV_FILENAME  = os.getenv("MT4_QUEUE_FILENAME", "colaMT4.csv")
CSV_ENABLED   = os.getenv("CSV_ENABLED", "1").strip() in ("1", "true", "yes", "on")  # Por defecto activado

# === Socket para EA (archivo compartido) ===
SOCKET_ENABLED = os.getenv("SOCKET_ENABLED", "true").lower() == "true"
ACTIVAR_SOCKET = os.getenv("ACTIVAR_SOCKET", "false").lower() in ("1", "true", "yes", "on")  # Flag para activar/desactivar envío por socket
SOCKET_FILENAME = os.getenv("SOCKET_FILENAME", "socket_msg.txt")
SOCKET_MODE = os.getenv("SOCKET_MODE", "socket").lower()  # valores: socket | file
SOCKET_HOST = os.getenv("SOCKET_HOST", "127.0.0.1")
SOCKET_PORT = int(os.getenv("SOCKET_PORT", "8888"))
SOCKET_TIMEOUT = float(os.getenv("SOCKET_TIMEOUT", "1.0"))
SOCKET_FALLBACK_TO_FILE = os.getenv("SOCKET_FALLBACK_TO_FILE", "true").lower() == "true"

_BROADCAST_SERVER = None

CSV_FIELDS = [
    'oid','ts_mt4_queue','symbol','order_type',
    'entry_price','sl','tp1','tp2','tp3','tp4','comment','estado_operacion','channel'
]

def _should_run_broadcast() -> bool:
    return SOCKET_ENABLED and SOCKET_MODE == "socket"

class BroadcastWorker(threading.Thread):
    def __init__(self, host: str, port: int):
        super().__init__(daemon=True)
        self.host = host
        self.port = port
        self.sock = None
        self.clients = []
        self.clients_lock = threading.Lock()
        self.stop_event = threading.Event()

    def run(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self.sock.bind((self.host, self.port))
            self.sock.listen(8)
            print(f"[broadcast] escuchando en {self.host}:{self.port}")
            while not self.stop_event.is_set():
                try:
                    self.sock.settimeout(1.0)
                    conn, addr = self.sock.accept()
                except socket.timeout:
                    continue
                except OSError:
                    if self.stop_event.is_set():
                        break
                    else:
                        continue
                print(f"[broadcast] cliente conectado {addr}")
                with self.clients_lock:
                    self.clients.append(conn)
                threading.Thread(target=self._handle_client, args=(conn, addr), daemon=True).start()
        except Exception as e:
            print(f"[broadcast][ERROR] {e}")
        finally:
            self._close_all()
            if self.sock:
                try:
                    self.sock.close()
                except Exception:
                    pass

    def _handle_client(self, conn, addr):
        try:
            conn.settimeout(1.0)
            while not self.stop_event.is_set():
                try:
                    data = conn.recv(1024)
                    if not data:
                        break
                except socket.timeout:
                    continue
                except Exception:
                    break
        finally:
            print(f"[broadcast] cliente desconectado {addr}")
            with self.clients_lock:
                try:
                    self.clients.remove(conn)
                except ValueError:
                    pass
            try:
                conn.close()
            except Exception:
                pass

    def broadcast(self, message: str):
        payload = (message.rstrip("\r\n") + "\n").encode("utf-8")
        dead = []
        with self.clients_lock:
            for c in self.clients:
                try:
                    c.sendall(payload)
                except Exception as e:
                    dead.append(c)
                    print(f"[broadcast][WARN] error enviando a cliente: {e}")
            for c in dead:
                try:
                    self.clients.remove(c)
                except ValueError:
                    pass
                try:
                    c.close()
                except Exception:
                    pass

    def stop(self):
        self.stop_event.set()
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass

    def _close_all(self):
        with self.clients_lock:
            for c in self.clients:
                try:
                    c.close()
                except Exception:
                    pass
            self.clients.clear()


def _start_broadcast():
    global _BROADCAST_SERVER
    if not _should_run_broadcast():
        return
    if _BROADCAST_SERVER is not None:
        return
    server = BroadcastWorker(SOCKET_HOST, SOCKET_PORT)
    server.start()
    _BROADCAST_SERVER = server


def _stop_broadcast():
    global _BROADCAST_SERVER
    if _BROADCAST_SERVER is None:
        return
    _BROADCAST_SERVER.stop()
    _BROADCAST_SERVER = None


def _ensure_broadcast_alive():
    if not _should_run_broadcast():
        return
    global _BROADCAST_SERVER
    if _BROADCAST_SERVER is None:
        _start_broadcast()


atexit.register(_stop_broadcast)

# --- Telegram disclaimer ---
TELEGRAM_DISCLAIMER = (
    "Aviso: El contenido de este canal tiene carácter exclusivamente informativo y educativo; "
    "no constituye asesoramiento financiero ni una invitación a operar. Cada miembro es responsable "
    "de la ejecución de sus operaciones y de la gestión de su riesgo. El uso de la información se "
    "realiza bajo el criterio y la responsabilidad de cada trader. Aquí solo se comparten referencias "
    "de análisis, no instrucciones de inversión. En consecuencia, toda operación que usted ejecute será "
    "una decisión personal e independiente, y los beneficios o pérdidas que se deriven dependerán únicamente "
    "de su propia gestión."
)

# --- Telegram .env (NUEVO) ---
TG_API_ID   = os.getenv("TELEGRAM_API_ID", "").strip()
TG_API_HASH = os.getenv("TELEGRAM_API_HASH", "").strip()
TG_PHONE    = os.getenv("TELEGRAM_PHONE", "").strip()
TG_SESSION  = os.getenv("TELEGRAM_SESSION", "telethon_session").strip()
TG_TARGETS  = os.getenv("TELEGRAM_TARGETS", "").strip()  # ej: @JBMSignals|https://t.me/JBMSignals|JBMSignals
TELEGRAM_ALERT_ENABLED = os.getenv("TELEGRAM_ALERT_ENABLED", "1").strip().lower() in ("1", "true", "yes", "on")
TELEGRAM_DISCLAIMER_ENABLED = os.getenv("TELEGRAM_DISCLAIMER_ENABLED", "0").strip().lower() in ("1", "true", "yes", "on")

# ====== Telegram helpers (NUEVO) ======
_TG_CLIENT = None
_TG_ENTITY = None
_TG_LOOP = None

def _tg_loop():
    """
    Devuelve un event loop reutilizable evitando DeprecationWarning en Python 3.10+.
    """
    global _TG_LOOP
    try:
        return asyncio.get_running_loop()
    except RuntimeError:
        if _TG_LOOP is None or _TG_LOOP.is_closed():
            _TG_LOOP = asyncio.new_event_loop()
        asyncio.set_event_loop(_TG_LOOP)
        return _TG_LOOP

async def _tg_ensure_session():
    """Conecta/autoriza una vez. Pide código/2FA solo la primera ejecución."""
    global _TG_CLIENT
    if not (TG_API_ID and TG_API_HASH and TG_PHONE and TG_TARGETS):
        return None
    if _TG_CLIENT is None:
        _TG_CLIENT = TelegramClient(TG_SESSION, int(TG_API_ID), TG_API_HASH)
    await _TG_CLIENT.connect()
    if not await _TG_CLIENT.is_user_authorized():
        print("[TG] Autorizando sesión…")
        await _TG_CLIENT.send_code_request(TG_PHONE)
        code = input("[TG] Código (SMS/Telegram): ").strip().replace(" ", "")
        try:
            await _TG_CLIENT.sign_in(phone=TG_PHONE, code=code)
        except errors.SessionPasswordNeededError:
            pwd = input("[TG] Contraseña 2FA: ")
            await _TG_CLIENT.sign_in(password=pwd)
    return _TG_CLIENT

async def _tg_resolve_target():
    """Resuelve destino: link → @usuario → título exacto. Cachea en _TG_ENTITY."""
    global _TG_ENTITY
    if _TG_ENTITY is not None:
        return _TG_ENTITY
    client = await _tg_ensure_session()
    if client is None:
        return None
    cands = [c.strip() for c in TG_TARGETS.split("|") if c.strip()]

    # 1) enlaces t.me
    for c in cands:
        if c.startswith(("http://","https://")) or "t.me/" in c:
            try:
                _TG_ENTITY = await client.get_entity(c); return _TG_ENTITY
            except Exception: pass
    # 2) @username
    for c in cands:
        u = c.lstrip("@")
        if u:
            try:
                _TG_ENTITY = await client.get_entity(u); return _TG_ENTITY
            except Exception: pass
    # 3) título exacto
    async for d in client.iter_dialogs():
        if d.name in cands:
            _TG_ENTITY = d.entity; return _TG_ENTITY

    print("[TG] No se pudo resolver destino. Revisa TELEGRAM_TARGETS.")
    return None

async def _tg_send_async(texto: str):
    if not texto:
        return
    client = await _tg_ensure_session()
    if client is None:
        return
    entity = await _tg_resolve_target()
    if entity is None:
        return
    try:
        await client.send_message(entity=entity, message=texto)
        print("[TG] OK enviado.")
    except errors.FloodWaitError as fw:
        print(f"[TG] FloodWait: espera {fw.seconds}s")
    except errors.ChatWriteForbiddenError:
        print("[TG] Sin permiso para publicar.")
    except Exception as e:
        print(f"[TG] Error: {e}")

def tg_send(texto: str):
    """Envoltura síncrona mínima para llamar desde el flujo actual."""
    try:
        _tg_loop().run_until_complete(_tg_send_async(texto))
    except Exception as e:
        print(f"[TG] WARN: {e}")

def socket_send_to_mt5(message: str, filename: str = None) -> bool:
    """
    Envía un mensaje a broadcast.py para que lo distribuya al EA de MT5.
    Mantiene una conexión persistente al servidor. Fallback a archivo compartido si está configurado.
    Retorna True si se envió/escribió correctamente, False en caso contrario.
    """
    if not SOCKET_ENABLED:
        return False
    
    if not message or not message.strip():
        return False
    trimmed = message.strip()

    # --- Servidor integrado (preferido para MT5) ---
    send_success = False

    if SOCKET_MODE == "socket":
        _ensure_broadcast_alive()
        global _BROADCAST_SERVER
        if _BROADCAST_SERVER is not None:
            try:
                _BROADCAST_SERVER.broadcast(trimmed)
                print(f"[SOCKET] Mensaje enviado a clientes conectados ({SOCKET_HOST}:{SOCKET_PORT})")
                send_success = True
            except Exception as sock_err:
                print(f"[SOCKET][ERROR] Error en broadcast interno: {sock_err}")
        else:
            print("[SOCKET][WARN] Servidor interno no disponible.")

    if send_success:
        return True

    if not SOCKET_FALLBACK_TO_FILE:
        return False
    print("[SOCKET][WARN] Usando fallback a archivo compartido.")

    # --- Fallback: archivo compartido (compatibilidad MT4) ---
    if filename is None:
        filename = SOCKET_FILENAME

    try:
        common_files = os.path.join(os.getenv("APPDATA", ""), "MetaQuotes", "Terminal", "Common", "Files")
        os.makedirs(common_files, exist_ok=True)

        filepath = os.path.join(common_files, filename)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(trimmed)

        print(f"[SOCKET] Mensaje escrito en archivo: {filepath}")
        return True

    except Exception as e:
        print(f"[SOCKET][ERROR] Fallo al escribir archivo: {e}")
        return False

def _csv_path():
    os.makedirs(MT4_QUEUE_DIR, exist_ok=True)
    return os.path.abspath(os.path.join(MT4_QUEUE_DIR, CSV_FILENAME))

# =================== BBDD ===================
def _conn():
    # Patch B: tolerancia a locks
    conn = sqlite3.connect(DB_FILE, timeout=5.0, isolation_level=None)
    cur = conn.cursor()
    try:
        cur.execute("PRAGMA journal_mode=WAL;")
        cur.execute("PRAGMA busy_timeout=5000;")
    except Exception:
        pass
    return conn, cur

def db_connect():
    conn, cur = _conn()
    # PARCHE: crear si no existe la tabla unificada (campos extra opcionales -> NULL)
    cur.execute(f"""
    CREATE TABLE IF NOT EXISTS {TABLE}(
        oid TEXT PRIMARY KEY,
        ts_utc TEXT,
        ts_redis_ingest TEXT,
        ch_id TEXT,
        msg_id TEXT,
        channel TEXT,
        channel_username TEXT,
        sender_id TEXT,
        text TEXT,
        texto_formateado TEXT,
        score INTEGER,
        estado_operacion INTEGER,
        ts_mt4_queue TEXT,
        symbol TEXT,
        order_type TEXT,
        entry_price REAL,
        sl REAL,
        tp REAL,
        comment TEXT,
        PL REAL
    )
    """)
    # Si ya existía sin la columna PL, añadirla (ignorar si ya existe)
    try:
        cur.execute(f"ALTER TABLE {TABLE} ADD COLUMN PL REAL")
    except Exception:
        pass
    # Añadir texto_formateado si no existe
    try:
        cur.execute(f"ALTER TABLE {TABLE} ADD COLUMN texto_formateado TEXT")
    except Exception:
        pass
    conn.commit()
    conn.close()
    return sqlite3.connect(DB_FILE)

def db_exists_oid(oid: str) -> bool:
    conn, cur = _conn()
    try:
        cur.execute(f"SELECT 1 FROM {TABLE} WHERE oid = ? LIMIT 1", (oid,))
        return cur.fetchone() is not None
    finally:
        conn.close()

def db_upsert_basico(meta: dict) -> None:
    """
    Escribe SOLO los campos básicos en Trazas_Unica (no operativos).
    Usa UPSERT por oid.
    """
    SQL = f"""
      INSERT INTO {TABLE}
      (oid, ts_utc, ts_redis_ingest, ch_id, msg_id, channel, channel_username, sender_id, text, texto_formateado, score, estado_operacion)
      VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
      ON CONFLICT(oid) DO UPDATE SET
        ts_utc           = excluded.ts_utc,
        ts_redis_ingest  = excluded.ts_redis_ingest,
        ch_id            = excluded.ch_id,
        msg_id           = excluded.msg_id,
        channel          = excluded.channel,
        channel_username = excluded.channel_username,
        sender_id        = excluded.sender_id,
        text             = excluded.text,
        texto_formateado = excluded.texto_formateado,
        score            = excluded.score,
        estado_operacion = excluded.estado_operacion
    """
    params = (
        meta['oid'], meta.get('ts_utc'), meta.get('ts_redis_ingest'),
        meta.get('ch_id'), meta.get('msg_id'), meta.get('channel'),
        meta.get('channel_username'), meta.get('sender_id'), meta.get('text'),
        meta.get('texto_formateado'),
        int(meta.get('score', 0)), int(meta.get('estado_operacion', 0)),
    )

    backoff = 0.1
    for _ in range(5):
        conn, cur = _conn()
        try:
            cur.execute(SQL, params)
            conn.commit()
            return
        except sqlite3.OperationalError as e:
            # Patch B: reintentos ante lock
            if "locked" in str(e).lower():
                conn.close()
                sleep(backoff)
                backoff = min(backoff * 2, 1.6)
                continue
            conn.close()
            raise
        finally:
            try:
                conn.close()
            except Exception:
                pass
    # Si agota reintentos
    raise sqlite3.OperationalError("database is locked (retries exhausted)")

def db_delete_oid(oid):
    conn, cur = _conn()
    try:
        cur.execute(f"DELETE FROM {TABLE} WHERE oid = ?", (oid,))
        conn.commit()
    finally:
        conn.close()

def db_update_ts_mt4_queue(oid: str, tsq: str) -> None:
    """
    Parche: cuando score=10, grabar ts_mt4_queue en Trazas_Unica para ese oid.
    (El resto de campos operativos se rellenarán después por el ACK del EA.)
    """
    SQL = f"UPDATE {TABLE} SET ts_mt4_queue = ? WHERE oid = ?"
    backoff = 0.1
    for _ in range(5):
        conn, cur = _conn()
        try:
            cur.execute(SQL, (tsq, oid))
            conn.commit()
            return
        except sqlite3.OperationalError as e:
            if 'locked' in str(e).lower():
                conn.close()
                sleep(backoff)
                backoff = min(backoff*2, 1.6)
                continue
            conn.close()
            raise
        finally:
            try:
                conn.close()
            except Exception:
                pass
    raise sqlite3.OperationalError("database is locked (retries exhausted)")

def db_update_operativos(oid: str, fila: dict) -> None:
    """
    Actualiza los campos operativos en Trazas_Unica cuando score=10.
    Usa los datos de la fila construida para el CSV.
    """
    # Convertir tp1, tp2, tp3, tp4 a un solo campo tp concatenado con " / "
    tp_val = None
    tp_list = []
    for i in range(1, 5):
        tp_key = f'tp{i}'
        if fila.get(tp_key) is not None:
            tp_list.append(str(fila.get(tp_key)))
    
    # Si hay TPs, concatenarlos con " / "
    if tp_list:
        tp_val = " / ".join(tp_list)
    
    SQL = f"""
        UPDATE {TABLE} 
        SET ts_mt4_queue = ?,
            symbol = ?,
            order_type = ?,
            entry_price = ?,
            sl = ?,
            tp = ?,
            comment = ?
        WHERE oid = ?
    """
    params = (
        fila.get('ts_mt4_queue'),
        fila.get('symbol'),
        fila.get('order_type'),
        fila.get('entry_price'),
        fila.get('sl'),
        tp_val,
        fila.get('comment'),
        oid
    )
    
    backoff = 0.1
    for _ in range(5):
        conn, cur = _conn()
        try:
            cur.execute(SQL, params)
            conn.commit()
            return
        except sqlite3.OperationalError as e:
            if 'locked' in str(e).lower():
                conn.close()
                sleep(backoff)
                backoff = min(backoff*2, 1.6)
                continue
            conn.close()
            raise
        finally:
            try:
                conn.close()
            except Exception:
                pass
    raise sqlite3.OperationalError("database is locked (retries exhausted)")

# =================== CSV ===================
def csv_row_to_string(fila):
    """
    Convierte una fila dict a string CSV con el mismo formato que se escribe en el archivo.
    Retorna la línea CSV como string (sin newline final).
    """
    import io
    output = io.StringIO()
    w = csv.DictWriter(output, fieldnames=CSV_FIELDS)
    w.writerow({k: fila.get(k, "") for k in CSV_FIELDS})
    return output.getvalue().rstrip('\r\n')

def csv_write_row(fila):
    """
    Escribe asegurando cabecera y evitando duplicar por oid.
    Devuelve (path, wrote_bool)
    """
    path = _csv_path()
    file_exists = os.path.exists(path)
    # evitar duplicado por EDIT
    already = False
    if file_exists:
        try:
            with open(path, 'r', encoding='utf-8', newline='') as fr:
                r = csv.DictReader(fr)
                for row in r:
                    if row.get('oid') == fila.get('oid'):
                        already = True
                        break
        except Exception:
            pass
    if already:
        return path, False

    with open(path, 'a', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        if not file_exists:
            w.writeheader()
        w.writerow({k: fila.get(k, "") for k in CSV_FIELDS})
        f.flush()
    return path, True

def csv_remove_oid(oid):
    path = _csv_path()
    if not os.path.exists(path):
        return
    rows = []
    with open(path, 'r', encoding='utf-8', newline='') as f:
        r = csv.DictReader(f)
        for row in r:
            if row.get('oid') != oid:
                rows.append(row)
    with open(path, 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        w.writeheader()
        w.writerows(rows)
        f.flush()

# =================== UTIL: construir fila desde clasificar_mensajes ===================
def _best_result(resultados):
    """Prioriza score=10; si no hay, devuelve el primero."""
    for r in resultados:
        if int(r.get("score", 0)) == 10:
            return r
    return resultados[0]

def _build_fila_desde_resultado(resultados, evento):
    """
    Mapear salida de clasificar_mensajes(texto) -> fila estándar del parseador.
    """
    mejor = _best_result(resultados)
    symbol = (mejor.get("activo") or (evento.get("symbol") if isinstance(evento, dict) else "") or "").upper() or None
    accion = mejor.get("accion")
    # si no hay 'accion', derivar de 'direccion'
    if not accion:
        dir_ = (mejor.get("direccion") or "").upper()
        if dir_ in ("BUY", "SELL"):
            accion = dir_
    
    # Caso especial: PARTIAL CLOSE - solo rellenar order_type y channel
    es_partial_close = (accion == "PARTIAL CLOSE")
    
    # Caso especial: CLOSEALL - solo rellenar order_type y channel
    es_closeall = (accion == "CLOSEALL")
    
    # Caso especial: BREAKEVEN - solo rellenar symbol, order_type y channel
    es_breakeven = (accion == "BREAKEVEN")
    
    # Caso especial: MOVETO y STOPLOSSESTO
    es_moveto = (accion == "MOVETO")
    es_stoplossesto = (accion == "STOPLOSSESTO")
    
    if es_partial_close:
        # PARTIAL CLOSE: solo order_type y channel, resto vacío
        symbol = None
        entry_price = None
        sl = None
        tp1 = None
        tp2 = None
        tp3 = None
        tp4 = None
    elif es_closeall:
        # CLOSEALL: solo order_type y channel, resto vacío
        symbol = None
        entry_price = None
        sl = None
        tp1 = None
        tp2 = None
        tp3 = None
        tp4 = None
    elif es_breakeven:
        entry_price = None
        sl = None
        tp1 = None
        tp2 = None
        tp3 = None
        tp4 = None
    elif es_moveto or es_stoplossesto:
        # MOVETO/STOPLOSSESTO: solo necesita sl (el nuevo valor), no requiere entry_price ni TPs
        entry_price = None  # No se requiere entrada
        sl = mejor.get("sl")  # El nuevo valor del SL
        tp1 = None
        tp2 = None
        tp3 = None
        tp4 = None
    else:
        entry_price = mejor.get("entrada_resuelta")
        sl = mejor.get("sl")
        tp_list = mejor.get("tp") or []
        target_open = mejor.get("target_open", False)
        
        # Si target está abierto y no hay TPs, poner "OPEN" en tp1
        if target_open and len(tp_list) == 0:
            tp1 = "OPEN"
            tp2 = None
            tp3 = None
            tp4 = None
        else:
            # Extraer hasta 4 TPs y asignarlos a tp1, tp2, tp3, tp4
            tp1 = tp_list[0] if len(tp_list) > 0 else None
            tp2 = tp_list[1] if len(tp_list) > 1 else None
            tp3 = tp_list[2] if len(tp_list) > 2 else None
            tp4 = tp_list[3] if len(tp_list) > 3 else None
    
    score = int(mejor.get("score", 0))

    # OID basado en fecha y msg_id si viene
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    try:
        seq_raw = int(str((evento or {}).get("msg_id", "")) or 0) % 100000
    except Exception:
        hhmmss = datetime.now(timezone.utc).strftime("%H%M%S")
        seq_raw = int(hhmmss) % 100000
    oid = f"{today}-{str(seq_raw).zfill(5)}"

    # Extraer nombre del canal de Telegram (prioriza channel_username, luego channel)
    channel_name = None
    if isinstance(evento, dict):
        channel_name = evento.get('channel_username') or evento.get('channel') or None

    # Mapear acciones a los nuevos textos para order_type
    order_type_map = {
        'MOVETO': 'SL A',
        'STOPLOSSESTO': 'VARIOS SL A',
        'PARTIAL CLOSE': 'PARCIAL',
        'CLOSEALL': 'CERRAR'
    }
    order_type = order_type_map.get(accion, accion)
    
    fila = {
        'oid': oid,
        'ts_mt4_queue': datetime.now(timezone.utc).isoformat(),
        'symbol': symbol,
        'order_type': order_type,
        'entry_price': entry_price,
        'sl': sl,
        'tp1': tp1,
        'tp2': tp2,
        'tp3': tp3,
        'tp4': tp4,
        'comment': oid,
        'estado_operacion': 0,
        'score': score,
        'channel': channel_name
    }
    return fila

def _build_basico_desde_evento(evento, score: int, oid: str, texto_formateado: Optional[str] = None) -> dict:
    """Construye los campos básicos para Trazas_Unica a partir del mensaje Redis."""
    # Fallbacks para texto y ch_id (único cambio solicitado)
    txt = None
    ch_id_val = None
    if isinstance(evento, dict):
        txt = (evento.get('text')
               or evento.get('raw')
               or evento.get('text/raw'))
        ch_id_val = (evento.get('ch_id')
                     or evento.get('chat_id')
                     or evento.get('channel_id')
                     or evento.get('ch'))

    # Asegurar que ts_utc siempre tenga un valor (formato ISO UTC compatible con visor.py)
    # visor.py espera formato: "YYYY-MM-DDTHH:MM:SSZ" (sin microsegundos, sin timezone offset)
    ts_utc_val = None
    if isinstance(evento, dict):
        ts_utc_val = evento.get('ts_utc')
    
    # Normalizar formato: eliminar microsegundos y timezone offset
    if ts_utc_val:
        try:
            ts_str = str(ts_utc_val).strip()
            # Eliminar microsegundos si existen (.123456)
            if '.' in ts_str:
                ts_str = ts_str.split('.')[0]
            # Eliminar timezone offset si existe (+00:00 o -05:00)
            if '+' in ts_str:
                ts_str = ts_str.split('+')[0]
            elif len(ts_str) > 10 and ts_str[-6] in '+-':
                # Formato como "2025-12-14T10:38:02-05:00"
                ts_str = ts_str[:-6]
            # Asegurar formato Z al final
            if not ts_str.endswith('Z'):
                ts_str += 'Z'
            ts_utc_val = ts_str
        except Exception:
            # Si falla el parsing, usar timestamp actual
            ts_utc_val = None
    
    # Si no hay ts_utc del evento o el formato es incorrecto, usar timestamp actual
    if not ts_utc_val:
        ts_utc_val = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    
    return {
        'oid': oid,
        'ts_utc': ts_utc_val,
        'ts_redis_ingest': (evento.get('ts_redis_ingest') if isinstance(evento, dict) else None),
        'ch_id': ch_id_val,
        'msg_id': (evento.get('msg_id') if isinstance(evento, dict) else None),
        'channel': (evento.get('channel') if isinstance(evento, dict) else None),
        'channel_username': (evento.get('channel_username') if isinstance(evento, dict) else None),
        'sender_id': (evento.get('sender_id') if isinstance(evento, dict) else None),
        'text': txt,
        'texto_formateado': texto_formateado,
        'score': int(score),
        'estado_operacion': 0 if int(score) == 10 else 6,
    }

# =================== REDIS ===================
def ensure_group(r):
    try:
        r.xgroup_create(name=REDIS_STREAM, groupname=REDIS_GROUP, id="0", mkstream=True)
    except redis.exceptions.ResponseError:
        pass  # ya existe

# =================== MAIN LOOP ===================
def main():
    print("[parseador] v3.3.4 (patch A+B) arrancando…")
    print(f"[parseador] CSV destino = {_csv_path()}")
    print(f"[parseador] BBDD destino = {os.path.abspath(DB_FILE)} | Tabla={TABLE}")
    print(f"[parseador] Redis={REDIS_URL} Stream={REDIS_STREAM} Group={REDIS_GROUP} Consumer={CONSUMER}")
    print(f"[parseador] ACTIVAR_SOCKET = {ACTIVAR_SOCKET} (envío por socket {'ACTIVADO' if ACTIVAR_SOCKET else 'DESACTIVADO'})")

    _ensure_broadcast_alive()
    if not _should_run_broadcast():
        print("[parseador] broadcast interno desactivado (SOCKET_MODE != 'socket' o SOCKET_ENABLED=0).")

    # --- Telegram: pre-resolver sesión/target una vez (si hay credenciales) ---
    if TG_API_ID and TG_API_HASH and TG_PHONE and TG_TARGETS:
        try:
            _tg_loop().run_until_complete(_tg_ensure_session())
            _tg_loop().run_until_complete(_tg_resolve_target())
            print("[TG] Sesión/target listos.")
        except Exception as e:
            print(f"[TG] Aviso inicialización: {e}")
    else:
        print("[TG] Envío desactivado (faltan TELEGRAM_* en .env).")

    # asegurar tabla
    db_connect().close()

    r = redis.Redis.from_url(REDIS_URL)
    ensure_group(r)

    while True:
        try:
            _ensure_broadcast_alive()
            resp = r.xreadgroup(groupname=REDIS_GROUP, consumername=CONSUMER,
                                streams={REDIS_STREAM: ">"}, count=1, block=5000)
            if not resp:
                continue

            for stream, msgs in resp:
                for _msg_id, fields in msgs:
                    try:
                        data = {k.decode(): v.decode() for k, v in fields.items()}
                        mid   = data.get('msg_id')
                        ch_id = data.get('ch_id')
                        chusr = data.get('channel_username') or data.get('channel') or ""
                        preview = (data.get('text') or data.get('raw') or data.get('text/raw') or "")[:80].replace("\n"," ")
                        print(f"[parseador] <- Redis msg_id={mid} ch_id={ch_id} ch={chusr} txt='{preview}'")

                        # === USAR CLASIFICAR_MENSAJES DIRECTO ===
                        texto = data.get('text') or data.get('raw') or data.get('text/raw') or ""
                        resultados = clasificar_mensajes(texto)
                        if not resultados:
                            print(f"[parseador] análisis→ msg_id={mid} sin resultados. ACK")
                            r.xack(REDIS_STREAM, REDIS_GROUP, _msg_id)
                            continue
                        mejor_resultado = _best_result(resultados)
                        score = int(mejor_resultado.get("score", 0))
                        
                        # Formatear según el score
                        if score == 10:
                            texto_formateado = formatear_senal(mejor_resultado)
                        else:
                            texto_formateado = formatear_motivo_rechazo(mejor_resultado)

                        fila = _build_fila_desde_resultado(resultados, data)
                        oid   = fila['oid']

                        tps_str = ",".join([str(fila[f'tp{i}']) for i in range(1, 5) if fila.get(f'tp{i}') is not None])
                        print(f"[parseador] análisis→ msg_id={mid} score={score} sym={fila['symbol']} "
                              f"type={fila['order_type']} entry={fila['entry_price']} sl={fila['sl']} tp=[{tps_str}] oid={oid}")

                        # 0) Guardar SIEMPRE en Trazas_Unica los básicos (no operativos)
                        basico = _build_basico_desde_evento(data, score, oid, texto_formateado)
                        try:
                            db_upsert_basico(basico)
                            print(f"[parseador] BBDD OK → básicos guardados (oid={oid}, score={score})")
                        except Exception as e:
                            print(f"[parseador][ERROR] BBDD FAIL básicos (oid={oid}): {e}")
                            import traceback
                            traceback.print_exc()

                        if score == 10:
                            # 1) CSV (evita duplicado por oid) - Solo si CSV_ENABLED está activado
                            if CSV_ENABLED:
                                try:
                                    path, wrote = csv_write_row(fila)
                                    print(f"[parseador] CSV {'OK' if wrote else 'OK(dup-skip)'} → {path} (oid={oid})")
                                    csv_ok = True
                                except Exception as e:
                                    print(f"[parseador][ERROR] CSV FAIL (oid={oid}): {e}")
                                    csv_ok = False
                            else:
                                print(f"[parseador] CSV DESACTIVADO (CSV_ENABLED=0) → omitido (oid={oid})")

                            # 1b) Actualizar campos operativos en Trazas_Unica
                            try:
                                db_update_operativos(oid, fila)
                                print(f"[parseador] BBDD operativos OK → symbol={fila.get('symbol')} entry={fila.get('entry_price')} sl={fila.get('sl')} tp={fila.get('tp1')} (oid={oid})")
                            except Exception as e:
                                print(f"[parseador][ERROR] No se pudieron actualizar campos operativos (oid={oid}): {e}")
                                import traceback
                                traceback.print_exc()

                            csv_status = "CSV OK" if CSV_ENABLED else "CSV desactivado"
                            print(f"[parseador] ✅ score=10 → {csv_status} + campos operativos en BBDD.")

                            # --- NUEVO: enviar fila CSV al EA de socket (mismo formato que se escribe en CSV) ---
                            # Solo enviar si ACTIVAR_SOCKET está activado
                            if ACTIVAR_SOCKET:
                                try:
                                    csv_line = csv_row_to_string(fila)
                                    socket_send_to_mt5(csv_line)
                                    print(f"[parseador] SOCKET OK → fila CSV enviada a EA (oid={oid})")
                                except Exception as e:
                                    print(f"[parseador][SOCKET][WARN] No se pudo enviar al EA (oid={oid}): {e}")
                            else:
                                print(f"[parseador] SOCKET desactivado (ACTIVAR_SOCKET=false) → omitido (oid={oid})")

                            # --- NUEVO: enviar texto formateado a Telegram (SOLO si existe) ---
                            try:
                                if TG_API_ID and TG_API_HASH and TG_PHONE and TG_TARGETS:
                                    if TELEGRAM_ALERT_ENABLED:
                                        origen = data.get('channel_username')
                                        if origen:
                                            origen = origen.strip()
                                            if origen and not origen.startswith("@"):
                                                origen = f"@{origen.lstrip('@')}"
                                        else:
                                            alt = data.get('channel') or data.get('channel_title')
                                            if alt:
                                                alt_clean = alt.strip().replace(" ", "")
                                                origen = f"@{alt_clean}" if alt_clean else None
                                        
                                        # Caso especial: PARCIAL (PARTIAL CLOSE) - mensaje simple
                                        if fila.get('order_type') == 'PARCIAL':
                                            if origen:
                                                payload = f"{origen} PARCIAL"
                                            else:
                                                payload = "PARCIAL"
                                        # Caso especial: CERRAR (CLOSEALL) - mensaje simple
                                        elif fila.get('order_type') == 'CERRAR':
                                            if origen:
                                                payload = f"{origen} CERRAR"
                                            else:
                                                payload = "CERRAR"
                                        # Caso especial: BREAKEVEN - mensaje simple
                                        elif fila.get('order_type') == 'BREAKEVEN':
                                            if origen:
                                                payload = f"{origen} Breakeven"
                                            else:
                                                payload = "Breakeven"
                                        # Caso especial: VARIOS SL A (STOPLOSSESTO) - mensaje con valor numérico
                                        elif fila.get('order_type') == 'VARIOS SL A':
                                            sl_valor = fila.get('sl')
                                            if sl_valor is not None:
                                                if origen:
                                                    payload = f"{origen} VARIOS SL A {sl_valor}"
                                                else:
                                                    payload = f"VARIOS SL A {sl_valor}"
                                            else:
                                                payload = None
                                        # Caso especial: SL A (MOVETO) - mensaje con valor numérico
                                        elif fila.get('order_type') == 'SL A':
                                            sl_valor = fila.get('sl')
                                            if sl_valor is not None:
                                                if origen:
                                                    payload = f"{origen} SL A {sl_valor}"
                                                else:
                                                    payload = f"SL A {sl_valor}"
                                            else:
                                                payload = None
                                        else:
                                            # Caso normal: usar texto formateado
                                            if texto_formateado:
                                                lineas = []
                                                if origen:
                                                    lineas.append(origen)
                                                lineas.append(texto_formateado)
                                                if TELEGRAM_DISCLAIMER_ENABLED:
                                                    lineas.append("")
                                                    lineas.append(TELEGRAM_DISCLAIMER)
                                                payload = "\n".join(lineas)
                                            else:
                                                payload = None
                                        
                                        if payload:
                                            tg_send(payload)
                                    else:
                                        print("[TG] Envío omitido (TELEGRAM_ALERT_ENABLED=0).")
                            except Exception as e:
                                print(f"[TG] Aviso envío: {e}")

                        else:
                            # score < 10 → ya guardamos básicos con estado=6
                            print(f"[parseador] ℹ score<10 → SOLO básicos (estado=6) (oid={oid})")

                        r.xack(REDIS_STREAM, REDIS_GROUP, _msg_id)

                    except Exception as e:
                        print(f"[parseador][ERROR] Excepción procesando msg_id={data.get('msg_id')} : {e}")
                        r.xack(REDIS_STREAM, REDIS_GROUP, _msg_id)

        except KeyboardInterrupt:
            print("[parseador] Interrumpido por usuario.")
            break
        except Exception as loop_err:
            print(f"[parseador][ERROR] Loop: {loop_err}")
            time.sleep(1)  # backoff suave
    _stop_broadcast()

if __name__ == "__main__":
    main()
