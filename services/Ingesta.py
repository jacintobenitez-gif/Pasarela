#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ack_ingest_sqlite v1.1.1 — colaMT4.ack.csv → SQLite (UPDATE mínimo, con diagnóstico)
#
# - Autodetecta la carpeta MT4 Data (...\MQL4\Files) y usa ahí:
#     * colaMT4.ack.csv   (lectura incremental)
#     * ack.pos           (offset persistido)
# - Actualiza **solo** en traza_unica: symbol, order_type, entry_price, sl, tp, comment (=oid)
# - NO inserta filas, NO toca ts_utc/ts_mt4_queue/text/score/estado_operacion
# - BBDD: usa la misma convención que el parseador:
#       DB_PATH = os.getenv("PASARELA_DB", r"C:\Pasarela\pasarela.db")

import os
import io
import re
import sys
import glob
import sqlite3

# ================== CONFIG ==================
DB_PATH  = os.getenv("PASARELA_DB", r"C:\Pasarela\pasarela.db")  # misma convención que el parseador
BATCH_MAX_LINES = 500
VERBOSE = True

ACK_NAME = "colaMT4.ack.csv"
POS_NAME = "ack.pos"
TABLE    = "Trazas_Unica"

# Campos que SÍ podemos tocar desde el ACK
UPDATE_CANDIDATES = ["symbol", "order_type", "entry_price", "sl", "tp", "comment"]
# ============================================

# --------- Regex de extracción desde 'msg' del ACK ---------
RX_TYPE   = re.compile(r"Tipo=(BUY|SELL(?:\s+LIMIT|\s+STOP)?)", re.IGNORECASE)
RX_SYM    = re.compile(r"Simbolo=([A-Z0-9]+)", re.IGNORECASE)
RX_ENTRY  = re.compile(r"Precio apertura=([0-9]+(?:\.[0-9]+)?)", re.IGNORECASE)
RX_SL     = re.compile(r"SL=([0-9]+(?:\.[0-9]+)?)", re.IGNORECASE)
RX_TP     = re.compile(r"TP=([0-9]+(?:\.[0-9]+)?)", re.IGNORECASE)

SQL_PRAGMAS = [
    "PRAGMA journal_mode=WAL",
    "PRAGMA synchronous=NORMAL",
    "PRAGMA busy_timeout=5000"
]

def log(*a):
    if VERBOSE:
        print(*a)

def find_mt4_files_dir() -> str:
    """
    Busca ...\\MQL4\\Files en ubicaciones típicas de MT4.
    Prioriza la carpeta que ya contiene colaMT4.ack.csv; si no, la más reciente.
    """
    candidates = []

    bases = [
        os.path.expandvars(r"%APPDATA%\MetaQuotes\Terminal"),
        os.path.expandvars(r"%LOCALAPPDATA%\MetaQuotes\Terminal"),
        os.path.expanduser(r"~\AppData\Roaming\MetaQuotes\Terminal"),
        r"C:\Program Files (x86)",
        r"C:\Program Files",
    ]
    patterns_rel = [
        os.path.join("*", "MQL4", "Files"),
        os.path.join("MetaTrader*", "MQL4", "Files"),
        os.path.join("*MetaTrader*", "MQL4", "Files"),
    ]

    for base in bases:
        if not os.path.isdir(base):
            continue
        for rel in patterns_rel:
            for path in glob.glob(os.path.join(base, rel)):
                if os.path.isdir(path):
                    score = 2 if os.path.isfile(os.path.join(path, ACK_NAME)) else 1
                    mtime = os.path.getmtime(path)
                    candidates.append((score, mtime, path))

    if not candidates:
        raise FileNotFoundError(
            "No se encontró ninguna carpeta MQL4\\Files. "
            "Abre MT4 y usa File → Open Data Folder."
        )

    candidates.sort(key=lambda t: (t[0], t[1]), reverse=True)
    return candidates[0][2]

def load_pos(pos_file: str) -> int:
    try:
        with open(pos_file, "r", encoding="utf-8") as f:
            return int(f.read().strip() or "0")
    except Exception:
        return 0

def save_pos(pos_file: str, p: int) -> None:
    tmp = pos_file + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(str(p))
    os.replace(tmp, pos_file)

def parse_msg(msg: str):
    """Devuelve dict con campos (o None) extraídos del mensaje del ACK."""
    def grab_float(rx):
        m = rx.search(msg);  return float(m.group(1)) if m else None
    def grab_str(rx):
        m = rx.search(msg);  return m.group(1).upper().strip() if m else None
    return {
        "order_type":  grab_str(RX_TYPE),
        "symbol":      grab_str(RX_SYM),
        "entry_price": grab_float(RX_ENTRY),
        "sl":          grab_float(RX_SL),
        "tp":          grab_float(RX_TP),
    }

def get_columns(conn, table: str):
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({table})")
    return [r[1] for r in cur.fetchall()]  # (cid,name,type,notnull,dflt,pk)

def build_update_sql(existing_cols):
    # Filtra actualizables que sí existan en la tabla
    cols = [c for c in UPDATE_CANDIDATES if c in existing_cols]
    if not cols or "oid" not in existing_cols:
        raise RuntimeError("La tabla no tiene las columnas requeridas (falta 'oid' o no hay ninguna actualizable).")

    set_parts = []
    for c in cols:
        if c == "comment":
            set_parts.append("comment = ?")                   # comment = oid
        else:
            set_parts.append(f"{c} = COALESCE(?, {c})")       # solo toca si tenemos valor

    sql = f"UPDATE {TABLE} SET " + ", ".join(set_parts) + " WHERE oid = ?"
    return sql, cols

def main():
    # --- Localizar ACK/POS en MQL4\Files ---
    mt4_files_dir = find_mt4_files_dir()
    ack_file = os.path.join(mt4_files_dir, ACK_NAME)
    pos_file = os.path.join(mt4_files_dir, POS_NAME)

    log("[ack_ingest_sqlite] MT4 Files dir:", mt4_files_dir)
    log("[ack_ingest_sqlite] ACK:", ack_file)
    log("[ack_ingest_sqlite] POS:", pos_file)
    log("[ack_ingest_sqlite] DB:", DB_PATH)

    # Abre ACK
    try:
        fh = open(ack_file, "r", encoding="utf-8", errors="replace", newline="")
    except FileNotFoundError:
        print("[ack_ingest_sqlite] ACK no encontrado:", ack_file)
        return 0

    with fh:
        size = os.path.getsize(ack_file)
        pos = load_pos(pos_file)
        if pos > size:   # archivo rotado/truncado
            pos = 0
        fh.seek(pos, io.SEEK_SET)

        updated = 0
        conn = sqlite3.connect(DB_PATH, timeout=5.0, isolation_level=None)  # autocommit
        try:
            cur = conn.cursor()
            for p in SQL_PRAGMAS:
                try:
                    cur.execute(p)
                except sqlite3.DatabaseError:
                    pass

            # Diagnóstico de esquema
            existing = get_columns(conn, TABLE)
            log(f"[ack_ingest_sqlite] Columnas de {TABLE}:", existing)
            SQL_UPDATE, cols_to_update = build_update_sql(existing)
            log("[ack_ingest_sqlite] UPDATE →", SQL_UPDATE)

            for _ in range(BATCH_MAX_LINES):
                line = fh.readline()
                if not line:
                    break
                if not line.endswith("\n"):
                    # línea incompleta (se procesará en el siguiente ciclo)
                    fh.seek(-len(line), io.SEEK_CUR)
                    break

                raw = line.strip("\r\n")
                # Formato ACK: oid, estado, ticket, ts_ack_utc, msg
                parts = raw.split(",", 4)
                if len(parts) != 5:
                    log(f"[ack_ingest_sqlite] línea inválida (cols={len(parts)}): {raw[:160]}")
                    continue

                oid, estado, ticket, ts_ack_utc, msg = [p.strip() for p in parts]
                if not oid:
                    log("[ack_ingest_sqlite] oid vacío; línea ignorada.")
                    continue

                f = parse_msg(msg)

                # Parámetros en el orden de cols_to_update
                params = []
                for c in cols_to_update:
                    if c == "comment":
                        params.append(oid)          # comment = oid
                    else:
                        params.append(f.get(c, None))
                params.append(oid)                  # WHERE oid = ?

                try:
                    cur.execute(SQL_UPDATE, params)
                    updated += cur.rowcount
                except sqlite3.OperationalError as e:
                    # Diagnóstico claro si hay problema de tabla/columnas/params
                    print("\n[ack_ingest_sqlite][ERROR] sqlite3.OperationalError:", str(e))
                    print("SQL:", SQL_UPDATE)
                    print("PARAMS:", params)
                    print("LÍNEA ACK:", raw, "\n")
                    continue
        finally:
            conn.close()

        new_pos = fh.tell()
        save_pos(pos_file, new_pos)
        print(f"[ack_ingest_sqlite] actualizados: {updated} | offset={new_pos}")
        return updated

if __name__ == "__main__":
    sys.exit(0 if main() is not None else 1)
