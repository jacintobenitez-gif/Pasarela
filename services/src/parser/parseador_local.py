# -*- coding: utf-8 -*-
# parseador_local31.py — v3.3.4 (patch A+B)
# Mantiene: ruta fija MT4/Files, newline='' + flush(), trazas visuales,
# estados y política de atomicidad/rollback, score<10 -> estado=6 solo BBDD.
# Patch A: evitar duplicados (EDIT) por UNIQUE(oid) sin romper CSV.
# Patch B: SQLite WAL + busy_timeout + reintentos ante "database is locked".

import os, sys, csv, json, time
import sqlite3
import redis
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
from reglasnegocio.reglasnegocio import clasificar_mensajes

# =================== CONFIG ===================
REDIS_URL    = os.getenv("REDIS_URL", "redis://localhost:6379/0")
REDIS_STREAM = os.getenv("REDIS_STREAM", "pasarela:parse")
REDIS_GROUP  = os.getenv("REDIS_GROUP", "parser")
CONSUMER     = os.getenv("REDIS_CONSUMER", "local")

DB_FILE      = os.getenv("PASARELA_DB", "pasarela.db")
TABLE        = os.getenv("PASARELA_TABLE", "Trazas_Unica")  # << PARCHE: tabla destino unificada

# === Ruta MT4/Files (lee de .env; fallback a tu ruta fija actual) ===
MT4_QUEUE_DIR = os.getenv(
    "MT4_FILES_ABS",
    r"C:\Users\Administrator\AppData\Roaming\MetaQuotes\Terminal\BB190E062770E27C3E79391AB0D1A117\MQL4\Files"
)
CSV_FILENAME  = os.getenv("MT4_QUEUE_FILENAME", "colaMT4.csv")

CSV_FIELDS = [
    'oid','ts_mt4_queue','symbol','order_type',
    'entry_price','sl','tp','comment','estado_operacion'
]

# --- Telegram .env (NUEVO) ---
TG_API_ID   = os.getenv("TELEGRAM_API_ID", "").strip()
TG_API_HASH = os.getenv("TELEGRAM_API_HASH", "").strip()
TG_PHONE    = os.getenv("TELEGRAM_PHONE", "").strip()
TG_SESSION  = os.getenv("TELEGRAM_SESSION", "telethon_session").strip()
TG_TARGETS  = os.getenv("TELEGRAM_TARGETS", "").strip()  # ej: @JBMSignals|https://t.me/JBMSignals|JBMSignals

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
      (oid, ts_utc, ts_redis_ingest, ch_id, msg_id, channel, channel_username, sender_id, text, score, estado_operacion)
      VALUES (?,?,?,?,?,?,?,?,?,?,?)
      ON CONFLICT(oid) DO UPDATE SET
        ts_utc           = excluded.ts_utc,
        ts_redis_ingest  = excluded.ts_redis_ingest,
        ch_id            = excluded.ch_id,
        msg_id           = excluded.msg_id,
        channel          = excluded.channel,
        channel_username = excluded.channel_username,
        sender_id        = excluded.sender_id,
        text             = excluded.text,
        score            = excluded.score,
        estado_operacion = excluded.estado_operacion
    """
    params = (
        meta['oid'], meta.get('ts_utc'), meta.get('ts_redis_ingest'),
        meta.get('ch_id'), meta.get('msg_id'), meta.get('channel'),
        meta.get('channel_username'), meta.get('sender_id'), meta.get('text'),
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

# =================== CSV ===================
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
    entry_price = mejor.get("entrada_resuelta")
    sl = mejor.get("sl")
    tp_list = mejor.get("tp") or []
    tp = tp_list[0] if tp_list else None
    score = int(mejor.get("score", 0))

    # OID basado en fecha y msg_id si viene
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    try:
        seq_raw = int(str((evento or {}).get("msg_id", "")) or 0) % 100000
    except Exception:
        hhmmss = datetime.now(timezone.utc).strftime("%H%M%S")
        seq_raw = int(hhmmss) % 100000
    oid = f"{today}-{str(seq_raw).zfill(5)}"

    fila = {
        'oid': oid,
        'ts_mt4_queue': datetime.now(timezone.utc).isoformat(),
        'symbol': symbol,
        'order_type': accion,
        'entry_price': entry_price,
        'sl': sl,
        'tp': tp,
        'comment': oid,
        'estado_operacion': 0,
        'score': score
    }
    return fila

def _build_basico_desde_evento(evento, score: int, oid: str) -> dict:
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

    return {
        'oid': oid,
        'ts_utc': (evento.get('ts_utc') if isinstance(evento, dict) else None),
        'ts_redis_ingest': (evento.get('ts_redis_ingest') if isinstance(evento, dict) else None),
        'ch_id': ch_id_val,
        'msg_id': (evento.get('msg_id') if isinstance(evento, dict) else None),
        'channel': (evento.get('channel') if isinstance(evento, dict) else None),
        'channel_username': (evento.get('channel_username') if isinstance(evento, dict) else None),
        'sender_id': (evento.get('sender_id') if isinstance(evento, dict) else None),
        'text': txt,
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

                        fila = _build_fila_desde_resultado(resultados, data)
                        score = fila['score']
                        oid   = fila['oid']

                        print(f"[parseador] análisis→ msg_id={mid} score={score} sym={fila['symbol']} "
                              f"type={fila['order_type']} entry={fila['entry_price']} sl={fila['sl']} tp={fila['tp']} oid={oid}")

                        # 0) Guardar SIEMPRE en Trazas_Unica los básicos (no operativos)
                        basico = _build_basico_desde_evento(data, score, oid)
                        db_upsert_basico(basico)

                        if score == 10:
                            # 1) CSV (evita duplicado por oid)
                            try:
                                path, wrote = csv_write_row(fila)
                                print(f"[parseador] CSV {'OK' if wrote else 'OK(dup-skip)'} → {path} (oid={oid})")
                                csv_ok = True
                            except Exception as e:
                                print(f"[parseador][ERROR] CSV FAIL (oid={oid}): {e}")
                                csv_ok = False

                            # 1b) Parche: reflejar inmediatamente ts_mt4_queue en Trazas_Unica
                            try:
                                db_update_ts_mt4_queue(oid, fila['ts_mt4_queue'])
                                print(f"[parseador] TSQ OK → ts_mt4_queue={fila['ts_mt4_queue']} (oid={oid})")
                            except Exception as e:
                                print(f"[parseador][WARN] No se pudo actualizar ts_mt4_queue (oid={oid}): {e}")

                            print(f"[parseador] ✅ score=10 → CSV OK + ts_mt4_queue en BBDD. Campos operativos llegarán por ACK.")

                            # --- NUEVO: enviar el MISMO 'texto' a Telegram ---
                            try:
                                if TG_API_ID and TG_API_HASH and TG_PHONE and TG_TARGETS and texto:
                                    tg_send(texto)
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

if __name__ == "__main__":
    main()
