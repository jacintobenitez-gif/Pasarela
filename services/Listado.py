#!/usr/bin/env python3
# ls_tables.py — Lista tablas (y columnas opcionalmente) en la BBDD SQLite de la pasarela.

import os
import sys
import sqlite3

DB_PATH = os.getenv("PASARELA_DB", r"C:\Pasarela\pasarela.db")

def main():
    if not os.path.exists(DB_PATH):
        print(f"[ERROR] No existe el fichero de BBDD: {DB_PATH}")
        return 1

    con = sqlite3.connect(DB_PATH, timeout=5.0)
    cur = con.cursor()

    tables = [
        r[0] for r in cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
    ]

    print(f"DB: {DB_PATH}")
    print(f"Tablas ({len(tables)}):")
    for t in tables:
        print(" -", t)

    if "--columns" in sys.argv and tables:
        for t in tables:
            cols = cur.execute(f"PRAGMA table_info({t})").fetchall()
            # PRAGMA table_info: (cid, name, type, notnull, dflt_value, pk)
            print(f"\n[{t}] columnas ({len(cols)}):")
            for cid, name, ctype, notnull, dflt, pk in cols:
                pk_tag = " PRIMARY KEY" if pk else ""
                nn_tag = " NOT NULL" if notnull else ""
                dflt_tag = f" DEFAULT {dflt}" if dflt is not None else ""
                print(f"  - {name} {ctype}{pk_tag}{nn_tag}{dflt_tag}")

    con.close()
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

