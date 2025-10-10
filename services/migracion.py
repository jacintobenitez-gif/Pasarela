#!/usr/bin/env python3
# migracion.py — Migración SQLite origen → destino sin dependencias externas.
# Hace dos pasos:
#   1) Migra TODAS las tablas de C:\Pasarela\services\pasarela.db → C:\Pasarela\pasarela.db
#   2) Asegura y migra Trazas_Unica (crea tabla si falta). Crea índice por oid.
#
# Uso:
#   python C:\Pasarela\services\migracion.py

import os, sqlite3, sys

BASE = r"C:\Pasarela"
SRC_DB = os.path.join(BASE, "services", "pasarela.db")
DST_DB = os.path.join(BASE, "pasarela.db")
FOCUS_TABLE = "Trazas_Unica"

def table_exists(con, schema, name):
    q = f"SELECT 1 FROM {schema}.sqlite_master WHERE type='table' AND name=?"
    return con.execute(q, (name,)).fetchone() is not None

def get_tables(con, schema):
    q = f"SELECT name FROM {schema}.sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    return [r[0] for r in con.execute(q)]

def get_columns(con, schema, table):
    q = f"PRAGMA {schema}.table_info('{table}')"
    return [r[1] for r in con.execute(q)]

def create_table_like(con, src_schema, table):
    ddl = con.execute(
        f"SELECT sql FROM {src_schema}.sqlite_master WHERE type='table' AND name=?",
        (table,)
    ).fetchone()
    if not ddl or not ddl[0]:
        raise RuntimeError(f"No se pudo obtener DDL de {table} en {src_schema}")
    con.execute(ddl[0])

def copy_common_columns(con, table):
    cols_src = get_columns(con, "src", table)
    cols_dst = get_columns(con, "main", table)
    cols = [c for c in cols_src if c in cols_dst]
    if not cols:
        print(f"[WARN] {table}: sin columnas comunes, se omite.")
        return
    collist = ", ".join([f'"{c}"' for c in cols])
    con.execute(f'INSERT OR IGNORE INTO "main"."{table}" ({collist}) SELECT {collist} FROM "src"."{table}"')

def migrate_all_tables(con):
    tabs = get_tables(con, "src")
    print(f"[INFO] Tablas en origen: {tabs}")
    for t in tabs:
        if not table_exists(con, "main", t):
            print(f"[INFO] Creando tabla en destino: {t}")
            create_table_like(con, "src", t)
        print(f"[INFO] Copiando datos: {t}")
        copy_common_columns(con, t)
    print("[OK] Paso 1 completado (todas las tablas).")

def ensure_and_migrate_focus(con, table):
    if not table_exists(con, "main", table):
        print(f"[INFO] {table} no existe en destino. Creando...")
        create_table_like(con, "src", table)
    print(f"[INFO] Copiando datos de {table}")
    copy_common_columns(con, table)
    # Índice útil:
    con.execute(f'CREATE INDEX IF NOT EXISTS ix_{table}_oid ON "{table}"(oid)')
    print(f"[OK] Paso 2 completado ({table}).")

def main():
    if not os.path.exists(SRC_DB):
        print(f"[ERROR] No existe DB origen: {SRC_DB}")
        return 1
    os.makedirs(os.path.dirname(DST_DB), exist_ok=True)

    con = sqlite3.connect(DST_DB, timeout=15.0, isolation_level=None)
    try:
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("PRAGMA synchronous=NORMAL")
        con.execute("PRAGMA busy_timeout=8000")
        con.execute("ATTACH DATABASE ? AS src", (SRC_DB,))

        con.execute("BEGIN")
        try:
            migrate_all_tables(con)
            ensure_and_migrate_focus(con, FOCUS_TABLE)
            con.commit()
        except Exception:
            con.rollback()
            raise
        print("\n[DONE] Migración finalizada sin errores.")
        return 0
    finally:
        con.close()

if __name__ == "__main__":
    sys.exit(main())

