# -*- coding: utf-8 -*-
# parseador_local31.py — v3.3.3 FINAL (usar clasificar_mensajes)
# Mantiene: ruta fija MT4/Files, newline='' + flush(), trazas visuales,
# estados y política de atomicidad/rollback, score<10 -> estado=6 solo BBDD.

import os, sys, csv, json, time
import sqlite3
import redis
from datetime import datetime, timezone

# --- PATH robusto para imports locales ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# === IMPORT CORRECTO DEL ANALIZADOR (SIN NOMBRES NUEVOS) ===
from reglasnegocio31 import clasificar_mensajes

# =================== CONFIG ===================
REDIS_URL    = os.getenv("REDIS_URL", "redis://localhost:6379/0")
REDIS_STREAM = os.getenv("REDIS_STREAM", "pasarela:parse")
REDIS_GROUP  = os.getenv("REDIS_GROUP", "parser")
CONSUMER     = os.getenv("REDIS_CONSUMER", "local")

DB_FILE      = os.getenv("PASARELA_DB", "pasarela.db")

# === Ruta fija MT4/Files ===
MT4_QUEUE_DIR = r"C:\Users\Administrator\AppData\Roaming\MetaQuotes\Terminal\BB190E062770E27C3E79391AB0D1A117\MQL4\Files"
CSV_FILENAME  = "colaMT4.csv"

CSV_FIELDS = [
    'oid','ts_mt4_queue','symbol','order_type',
    'entry_price','sl','tp','comment','estado_operacion'
]

def _csv_path():
    os.makedirs(MT4_QUEUE_DIR, exist_ok=True)
    return os.path.abspath(os.path.join(MT4_QUEUE_DIR, CSV_FILENAME))

# =================== BBDD ===================
def db_connect():
    conn = sqlite3.connect(DB_FILE)
    conn.execute("""
    CREATE TABLE IF NOT EXISTS colaMT4(
        oid TEXT PRIMARY KEY,
        ts_mt4_queue TEXT,
        symbol TEXT,
        order_type TEXT,
        entry_price REAL,
        sl REAL,
        tp REAL,
        comment TEXT,
        estado_operacion INTEGER,
        score INTEGER
    )
    """)
    conn.commit()
    return conn

def db_insert(fila):
    conn = db_connect()
    conn.execute("""
        INSERT INTO colaMT4
        (oid, ts_mt4_queue, symbol, order_type, entry_price, sl, tp, comment, estado_operacion, score)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        fila['oid'], fila['ts_mt4_queue'], fila['symbol'], fila['order_type'],
        fila['entry_price'], fila['sl'], fila['tp'], fila['comment'],
        fila['estado_operacion'], fila.get('score',0)
    ))
    conn.commit()
    conn.close()

def db_delete_oid(oid):
    conn = sqlite3.connect(DB_FILE)
    conn.execute("DELETE FROM colaMT4 WHERE oid = ?", (oid,))
    conn.commit()
    conn.close()

# =================== CSV ===================
def csv_write_row(fila):
    path = _csv_path()
    file_exists = os.path.exists(path)
    with open(path, 'a', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        if not file_exists:
            w.writeheader()
        w.writerow({k: fila.get(k, "") for k in CSV_FIELDS})
        f.flush()
    return path

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

# =================== REDIS ===================
def ensure_group(r):
    try:
        r.xgroup_create(name=REDIS_STREAM, groupname=REDIS_GROUP, id="0", mkstream=True)
    except redis.exceptions.ResponseError:
        pass  # ya existe

# =================== MAIN LOOP ===================
def main():
    print("[parseador] v3.3.3 FINAL (clasificar_mensajes) arrancando…")
    print(f"[parseador] CSV destino = {_csv_path()}")
    print(f"[parseador] BBDD destino = {os.path.abspath(DB_FILE)}")
    print(f"[parseador] Redis={REDIS_URL} Stream={REDIS_STREAM} Group={REDIS_GROUP} Consumer={CONSUMER}")

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

                        if score == 10:
                            # 1) CSV
                            try:
                                path = csv_write_row(fila)
                                print(f"[parseador] CSV OK → {path} (oid={oid})")
                                csv_ok = True
                            except Exception as e:
                                print(f"[parseador][ERROR] CSV FAIL (oid={oid}): {e}")
                                csv_ok = False

                            # 2) BBDD
                            if csv_ok:
                                try:
                                    db_insert(fila)
                                    print(f"[parseador] BBDD OK → {DB_FILE} (oid={oid})")
                                    db_ok = True
                                except Exception as e:
                                    print(f"[parseador][ERROR] BBDD FAIL (oid={oid}): {e}")
                                    db_ok = False
                                    # rollback CSV
                                    try:
                                        csv_remove_oid(oid)
                                        print(f"[parseador] Rollback CSV hecho (oid={oid}) → estado=4")
                                    except Exception as ee:
                                        print(f"[parseador][ERROR] Rollback CSV falló (oid={oid}): {ee}")
                                    fila['estado_operacion'] = 4
                            else:
                                # CSV falló → registrar y rollback DB si hiciera falta
                                try:
                                    db_insert({**fila, 'estado_operacion': 3})
                                    db_delete_oid(oid)
                                    print(f"[parseador] Rollback BBDD hecho (oid={oid}) → estado=3")
                                except Exception as e:
                                    print(f"[parseador][ERROR] Rollback BBDD falló (oid={oid}): {e}")
                                fila['estado_operacion'] = 3
                                db_ok = False

                            if csv_ok and db_ok:
                                fila['estado_operacion'] = 1
                                print(f"[parseador] ✅ score=10 + CSV+BBDD OK (oid={oid}, {fila['symbol']} {fila['order_type']})")
                                print(f"[parseador][RESUMEN] msg_id={mid} score=10 CSV+BBDD (oid={oid})")
                            else:
                                print(f"[parseador][RESUMEN] msg_id={mid} score=10 con incidencias (estado={fila['estado_operacion']}) (oid={oid})")

                        else:
                            # score < 10 → solo BBDD, estado 6
                            fila['estado_operacion'] = 6
                            try:
                                db_insert(fila)
                                print(f"[parseador] ℹ score<10 solo BBDD (estado=6) (oid={oid})")
                                print(f"[parseador][RESUMEN] msg_id={mid} score={score} BBDD(estado=6) (oid={oid})")
                            except Exception as e:
                                print(f"[parseador][ERROR] BBDD FAIL score<10 (oid={oid}): {e}")
                                print(f"[parseador][RESUMEN] msg_id={mid} score={score} ERROR_BBDD (oid={oid})")

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
