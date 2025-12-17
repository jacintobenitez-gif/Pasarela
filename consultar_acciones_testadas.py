# -*- coding: utf-8 -*-
# consultar_acciones_testadas.py — Consulta resultados de acciones especiales en Mensajes_testados

import os
import sys
import sqlite3
from pathlib import Path
from dotenv import load_dotenv, find_dotenv

# Cargar .env
ENV_PATH = find_dotenv(usecwd=True) or str(Path(__file__).resolve().parents[0] / ".env")
load_dotenv(ENV_PATH, override=True)

DB_FILE = os.getenv("PASARELA_DB", r"C:\Pasarela\services\pasarela.db")
TEST_TABLE = "Mensajes_testados"

def consultar_acciones_especiales():
    """Consulta las acciones especiales en la tabla Mensajes_testados."""
    if not os.path.exists(DB_FILE):
        print(f"ERROR: No existe la BBDD: {DB_FILE}")
        return
    
    conn = sqlite3.connect(DB_FILE, timeout=5.0)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    # Consultar conteo por order_type
    print("=" * 80)
    print("ACCIONES ESPECIALES EN Mensajes_testados")
    print("=" * 80)
    
    sql = f"""
        SELECT order_type, COUNT(*) as count 
        FROM {TEST_TABLE} 
        WHERE order_type IN ('BREAKEVEN', 'PARCIAL', 'CERRAR', 'PARTIAL CLOSE', 'CLOSE')
        GROUP BY order_type 
        ORDER BY count DESC
    """
    rows = cur.execute(sql).fetchall()
    
    if rows:
        print("\nConteo por acción:")
        for row in rows:
            print(f"  {row['order_type']}: {row['count']} mensajes")
    else:
        print("\nNo se encontraron acciones especiales")
    
    # Consultar ejemplos de cada acción
    print("\n" + "=" * 80)
    print("EJEMPLOS DE CADA ACCIÓN")
    print("=" * 80)
    
    acciones = ['BREAKEVEN', 'PARCIAL', 'CERRAR', 'PARTIAL CLOSE', 'CLOSE']
    
    for accion in acciones:
        sql = f"""
            SELECT oid, text, score, symbol, entry_price, sl, tp, comment
            FROM {TEST_TABLE}
            WHERE order_type = ?
            LIMIT 3
        """
        ejemplos = cur.execute(sql, (accion,)).fetchall()
        
        if ejemplos:
            print(f"\n[{accion}] - {len(ejemplos)} ejemplos:")
            for i, ej in enumerate(ejemplos, 1):
                texto = ej['text'][:100] if ej['text'] else ''
                print(f"\n  Ejemplo {i}:")
                print(f"    OID: {ej['oid']}")
                print(f"    Score: {ej['score']}")
                print(f"    Texto: {texto}...")
                print(f"    Symbol: {ej['symbol'] or 'NULL'}")
                print(f"    Entry: {ej['entry_price'] or 'NULL'}")
                print(f"    SL: {ej['sl'] or 'NULL'}")
                print(f"    TP: {ej['tp'] or 'NULL'}")
    
    # Estadísticas generales
    print("\n" + "=" * 80)
    print("ESTADÍSTICAS GENERALES")
    print("=" * 80)
    
    total = cur.execute(f"SELECT COUNT(*) FROM {TEST_TABLE}").fetchone()[0]
    score_10 = cur.execute(f"SELECT COUNT(*) FROM {TEST_TABLE} WHERE score = 10").fetchone()[0]
    score_menor_10 = cur.execute(f"SELECT COUNT(*) FROM {TEST_TABLE} WHERE score < 10").fetchone()[0]
    
    print(f"\nTotal mensajes en Mensajes_testados: {total}")
    print(f"Con score=10: {score_10}")
    print(f"Con score<10: {score_menor_10}")
    
    conn.close()

if __name__ == "__main__":
    consultar_acciones_especiales()

