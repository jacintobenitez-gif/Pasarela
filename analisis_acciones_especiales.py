# -*- coding: utf-8 -*-
# analisis_acciones_especiales.py — Análisis de acciones BREAKEVEN, PARTIAL CLOSE, CLOSE en BBDD
# Analiza cómo se aplican estas acciones en la tabla Trazas_Unica

import os
import sys
import sqlite3
import re
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv, find_dotenv

# Cargar .env
ENV_PATH = find_dotenv(usecwd=True) or str(Path(__file__).resolve().parents[0] / ".env")
load_dotenv(ENV_PATH, override=True)

# Configuración de BBDD
DB_FILE = os.getenv("PASARELA_DB", r"C:\Pasarela\services\pasarela.db")
TABLE = os.getenv("PASARELA_TABLE", "Trazas_Unica")

# Importar funciones de reglas de negocio para detectar palabras clave
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SERVICES_DIR = os.path.join(BASE_DIR, "services", "src")
if SERVICES_DIR not in sys.path:
    sys.path.insert(0, SERVICES_DIR)

from reglasnegocio.reglasnegocio import _has_breakeven_keyword, _has_partial_close_keyword, _has_close_keyword

def buscar_mensajes_por_accion(db_path: str, table: str):
    """
    Busca mensajes en la BBDD que contengan palabras clave de BREAKEVEN, PARTIAL CLOSE, CLOSE.
    Retorna un diccionario con los mensajes clasificados por acción.
    """
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"No existe la BBDD: {db_path}")
    
    conn = sqlite3.connect(db_path, timeout=5.0)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    # Obtener todos los mensajes con texto
    sql = f"""
        SELECT oid, ts_utc, channel, channel_username, text, score, 
               order_type, symbol, entry_price, sl, tp, comment
        FROM {table}
        WHERE text IS NOT NULL AND text != ''
        ORDER BY ts_utc DESC
    """
    rows = cur.execute(sql).fetchall()
    conn.close()
    
    # Clasificar mensajes por acción detectada
    resultados = {
        'BREAKEVEN': [],
        'PARTIAL CLOSE': [],
        'CLOSE': [],
        'MULTIPLE': []  # Mensajes que detectan múltiples acciones
    }
    
    print(f"[INFO] Analizando {len(rows)} mensajes...")
    
    for row in rows:
        texto = row['text'] or ""
        if not texto:
            continue
        
        # Detectar acciones (en orden de prioridad: CLOSE > PARTIAL CLOSE > BREAKEVEN)
        es_close = _has_close_keyword(texto)
        es_partial_close = _has_partial_close_keyword(texto)
        es_breakeven = _has_breakeven_keyword(texto)
        
        # Contar cuántas acciones se detectan
        acciones_detectadas = []
        if es_close:
            acciones_detectadas.append('CLOSE')
        if es_partial_close:
            acciones_detectadas.append('PARTIAL CLOSE')
        if es_breakeven:
            acciones_detectadas.append('BREAKEVEN')
        
        # Clasificar según prioridad
        if len(acciones_detectadas) > 1:
            # Múltiples acciones detectadas
            resultados['MULTIPLE'].append({
                'row': row,
                'acciones': acciones_detectadas
            })
        elif es_close:
            resultados['CLOSE'].append(row)
        elif es_partial_close:
            resultados['PARTIAL CLOSE'].append(row)
        elif es_breakeven:
            resultados['BREAKEVEN'].append(row)
    
    return resultados

def analizar_order_type_en_bd(db_path: str, table: str):
    """
    Analiza qué valores de order_type existen en la BBDD relacionados con estas acciones.
    """
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"No existe la BBDD: {db_path}")
    
    conn = sqlite3.connect(db_path, timeout=5.0)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    # Buscar order_type relacionados con estas acciones
    sql = f"""
        SELECT order_type, COUNT(*) as count
        FROM {table}
        WHERE order_type IN ('BREAKEVEN', 'PARCIAL', 'CERRAR', 'PARTIAL CLOSE', 'CLOSE')
        GROUP BY order_type
        ORDER BY count DESC
    """
    rows = cur.execute(sql).fetchall()
    
    # También buscar por texto en order_type que pueda contener estas palabras
    sql2 = f"""
        SELECT order_type, COUNT(*) as count
        FROM {table}
        WHERE order_type LIKE '%BREAKEVEN%' 
           OR order_type LIKE '%PARCIAL%'
           OR order_type LIKE '%CERRAR%'
           OR order_type LIKE '%CLOSE%'
        GROUP BY order_type
        ORDER BY count DESC
    """
    rows2 = cur.execute(sql2).fetchall()
    
    conn.close()
    
    return rows, rows2

def mostrar_resumen(resultados: dict):
    """Muestra un resumen de los resultados encontrados."""
    print("\n" + "=" * 80)
    print("RESUMEN DE ANÁLISIS")
    print("=" * 80)
    
    total_breakeven = len(resultados['BREAKEVEN'])
    total_partial = len(resultados['PARTIAL CLOSE'])
    total_close = len(resultados['CLOSE'])
    total_multiple = len(resultados['MULTIPLE'])
    
    print(f"\nMensajes detectados por acción:")
    print(f"  BREAKEVEN:      {total_breakeven}")
    print(f"  PARTIAL CLOSE:  {total_partial}")
    print(f"  CLOSE:          {total_close}")
    print(f"  MÚLTIPLES:      {total_multiple}")
    print(f"  TOTAL:          {total_breakeven + total_partial + total_close + total_multiple}")
    
    return {
        'BREAKEVEN': total_breakeven,
        'PARTIAL CLOSE': total_partial,
        'CLOSE': total_close,
        'MULTIPLE': total_multiple
    }

def mostrar_ejemplos(resultados: dict, limite: int = 5):
    """Muestra ejemplos de cada tipo de acción."""
    print("\n" + "=" * 80)
    print("EJEMPLOS DE MENSAJES")
    print("=" * 80)
    
    # BREAKEVEN
    if resultados['BREAKEVEN']:
        print(f"\n[BREAKEVEN] - Mostrando primeros {min(limite, len(resultados['BREAKEVEN']))} ejemplos:")
        for i, row in enumerate(resultados['BREAKEVEN'][:limite], 1):
            print(f"\n  Ejemplo {i}:")
            print(f"    OID: {row['oid']}")
            print(f"    Fecha: {row['ts_utc']}")
            channel_username = row['channel_username'] if 'channel_username' in row.keys() else None
            channel = row['channel'] if 'channel' in row.keys() else None
            canal_display = channel_username or channel or 'N/A'
            print(f"    Canal: {canal_display}")
            texto_display = row['text'][:150] if row['text'] else ''
            # Limpiar caracteres problemáticos para la consola
            try:
                texto_display = texto_display.encode('ascii', 'ignore').decode('ascii')
            except:
                pass
            print(f"    Texto: {texto_display}...")
            print(f"    Score: {row['score'] if 'score' in row.keys() else 'N/A'}")
            order_type_val = row['order_type'] if 'order_type' in row.keys() else None
            symbol_val = row['symbol'] if 'symbol' in row.keys() else None
            print(f"    order_type (BBDD): {order_type_val or 'NULL'}")
            print(f"    symbol (BBDD): {symbol_val or 'NULL'}")
    
    # PARTIAL CLOSE
    if resultados['PARTIAL CLOSE']:
        print(f"\n[PARTIAL CLOSE] - Mostrando primeros {min(limite, len(resultados['PARTIAL CLOSE']))} ejemplos:")
        for i, row in enumerate(resultados['PARTIAL CLOSE'][:limite], 1):
            print(f"\n  Ejemplo {i}:")
            print(f"    OID: {row['oid']}")
            print(f"    Fecha: {row['ts_utc']}")
            channel_username = row['channel_username'] if 'channel_username' in row.keys() else None
            channel = row['channel'] if 'channel' in row.keys() else None
            canal_display = channel_username or channel or 'N/A'
            print(f"    Canal: {canal_display}")
            texto_display = row['text'][:150] if row['text'] else ''
            # Limpiar caracteres problemáticos para la consola
            try:
                texto_display = texto_display.encode('ascii', 'ignore').decode('ascii')
            except:
                pass
            print(f"    Texto: {texto_display}...")
            print(f"    Score: {row['score'] if 'score' in row.keys() else 'N/A'}")
            order_type_val = row['order_type'] if 'order_type' in row.keys() else None
            symbol_val = row['symbol'] if 'symbol' in row.keys() else None
            print(f"    order_type (BBDD): {order_type_val or 'NULL'}")
            print(f"    symbol (BBDD): {symbol_val or 'NULL'}")
    
    # CLOSE
    if resultados['CLOSE']:
        print(f"\n[CLOSE] - Mostrando primeros {min(limite, len(resultados['CLOSE']))} ejemplos:")
        for i, row in enumerate(resultados['CLOSE'][:limite], 1):
            print(f"\n  Ejemplo {i}:")
            print(f"    OID: {row['oid']}")
            print(f"    Fecha: {row['ts_utc']}")
            channel_username = row['channel_username'] if 'channel_username' in row.keys() else None
            channel = row['channel'] if 'channel' in row.keys() else None
            canal_display = channel_username or channel or 'N/A'
            print(f"    Canal: {canal_display}")
            texto_display = row['text'][:150] if row['text'] else ''
            # Limpiar caracteres problemáticos para la consola
            try:
                texto_display = texto_display.encode('ascii', 'ignore').decode('ascii')
            except:
                pass
            print(f"    Texto: {texto_display}...")
            print(f"    Score: {row['score'] if 'score' in row.keys() else 'N/A'}")
            order_type_val = row['order_type'] if 'order_type' in row.keys() else None
            symbol_val = row['symbol'] if 'symbol' in row.keys() else None
            print(f"    order_type (BBDD): {order_type_val or 'NULL'}")
            print(f"    symbol (BBDD): {symbol_val or 'NULL'}")
    
    # MÚLTIPLES
    if resultados['MULTIPLE']:
        print(f"\n[MÚLTIPLES] - Mostrando primeros {min(limite, len(resultados['MULTIPLE']))} ejemplos:")
        for i, item in enumerate(resultados['MULTIPLE'][:limite], 1):
            row = item['row']
            acciones = item['acciones']
            print(f"\n  Ejemplo {i}:")
            print(f"    OID: {row['oid']}")
            print(f"    Fecha: {row['ts_utc']}")
            print(f"    Acciones detectadas: {', '.join(acciones)}")
            texto_display = row['text'][:150] if row['text'] else ''
            # Limpiar caracteres problemáticos para la consola
            try:
                texto_display = texto_display.encode('ascii', 'ignore').decode('ascii')
            except:
                pass
            print(f"    Texto: {texto_display}...")
            print(f"    Score: {row['score'] if 'score' in row.keys() else 'N/A'}")
            order_type_val = row['order_type'] if 'order_type' in row.keys() else None
            print(f"    order_type (BBDD): {order_type_val or 'NULL'}")

def analizar_order_types():
    """Analiza los valores de order_type en la BBDD."""
    print("\n" + "=" * 80)
    print("ANÁLISIS DE ORDER_TYPE EN BBDD")
    print("=" * 80)
    
    rows_exactos, rows_like = analizar_order_type_en_bd(DB_FILE, TABLE)
    
    print("\nValores exactos encontrados:")
    if rows_exactos:
        for row in rows_exactos:
            print(f"  '{row['order_type']}': {row['count']} registros")
    else:
        print("  No se encontraron valores exactos")
    
    print("\nValores que contienen palabras clave (LIKE):")
    if rows_like:
        for row in rows_like:
            print(f"  '{row['order_type']}': {row['count']} registros")
    else:
        print("  No se encontraron valores con LIKE")

def analizar_scores(resultados: dict):
    """Analiza la distribución de scores para cada acción."""
    print("\n" + "=" * 80)
    print("ANÁLISIS DE SCORES")
    print("=" * 80)
    
    for accion in ['BREAKEVEN', 'PARTIAL CLOSE', 'CLOSE']:
        mensajes = resultados[accion]
        if not mensajes:
            continue
        
        scores = {}
        for row in mensajes:
            score = row['score'] if 'score' in row.keys() else None
            if score is not None:
                scores[score] = scores.get(score, 0) + 1
        
        print(f"\n[{accion}] Distribución de scores:")
        for score in sorted(scores.keys()):
            print(f"  Score {score}: {scores[score]} mensajes")
        
        score_10 = sum(1 for r in mensajes if ('score' in r.keys() and r['score'] == 10))
        total = len(mensajes)
        porcentaje = (100*score_10/total) if total > 0 else 0
        print(f"  Total con score=10: {score_10}/{total} ({porcentaje:.1f}%)")

def main():
    print("=" * 80)
    print("ANÁLISIS DE ACCIONES ESPECIALES EN BBDD")
    print("=" * 80)
    print(f"BBDD: {DB_FILE}")
    print(f"Tabla: {TABLE}")
    print("=" * 80)
    
    try:
        # 1. Buscar mensajes por acción
        print("\n[PASO 1] Buscando mensajes con palabras clave...")
        resultados = buscar_mensajes_por_accion(DB_FILE, TABLE)
        
        # 2. Mostrar resumen
        print("\n[PASO 2] Generando resumen...")
        resumen = mostrar_resumen(resultados)
        
        # 3. Analizar order_type en BBDD
        print("\n[PASO 3] Analizando order_type en BBDD...")
        analizar_order_types()
        
        # 4. Analizar scores
        print("\n[PASO 4] Analizando distribución de scores...")
        analizar_scores(resultados)
        
        # 5. Mostrar ejemplos
        print("\n[PASO 5] Mostrando ejemplos...")
        mostrar_ejemplos(resultados, limite=5)
        
        print("\n" + "=" * 80)
        print("ANÁLISIS COMPLETADO")
        print("=" * 80)
        
        # Sugerencia para usar testeador
        total_detectados = sum(resumen.values())
        if total_detectados > 0:
            print(f"\n[SUGERENCIA] Se encontraron {total_detectados} mensajes con estas acciones.")
            print("Para reprocesarlos con el testeador_mensajes.py, puedes:")
            print("  1. Filtrar manualmente los OIDs de interés")
            print("  2. O usar el testeador en modo 'todos' para reprocesar toda la BBDD")
            print("  3. Los resultados se guardarán en la tabla 'Mensajes_testados'")
        
    except Exception as e:
        print(f"\n[ERROR]: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())

