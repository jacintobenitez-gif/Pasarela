# -*- coding: utf-8 -*-
# analisis_acciones_con_testeador.py — Análisis de acciones BREAKEVEN, PARTIAL CLOSE, CLOSE usando testeador
# Analiza cómo se aplican estas acciones en la tabla Trazas_Unica usando las funciones del testeador

import os
import sys
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv, find_dotenv

# Configurar codificación UTF-8 para Windows
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Cargar .env
ENV_PATH = find_dotenv(usecwd=True) or str(Path(__file__).resolve().parents[0] / ".env")
load_dotenv(ENV_PATH, override=True)

# Configuración de BBDD
DB_FILE = os.getenv("PASARELA_DB", r"C:\Pasarela\services\pasarela.db")
TABLE = os.getenv("PASARELA_TABLE", "Trazas_Unica")

# Importar funciones de reglas de negocio y del testeador
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SERVICES_DIR = os.path.join(BASE_DIR, "services", "src")
if SERVICES_DIR not in sys.path:
    sys.path.insert(0, SERVICES_DIR)

from reglasnegocio.reglasnegocio import (
    clasificar_mensajes, 
    formatear_senal, 
    formatear_motivo_rechazo,
    _has_breakeven_keyword, 
    _has_partial_close_keyword, 
    _has_close_keyword
)

# Importar funciones del parseador (como lo hace el testeador)
import importlib.util
parser_path = os.path.join(SERVICES_DIR, "parser", "parseador_local.py")
spec = importlib.util.spec_from_file_location("parseador_local", parser_path)
parseador = importlib.util.module_from_spec(spec)
spec.loader.exec_module(parseador)

_best_result = parseador._best_result
_build_fila_desde_resultado = parseador._build_fila_desde_resultado
_build_basico_desde_evento = parseador._build_basico_desde_evento

def buscar_mensajes_por_accion(db_path: str, table: str, limite: int = None):
    """
    Busca mensajes en la BBDD que contengan palabras clave de BREAKEVEN, PARTIAL CLOSE, CLOSE.
    Retorna un diccionario con los mensajes clasificados por acción.
    """
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"No existe la BBDD: {db_path}")
    
    conn = sqlite3.connect(db_path, timeout=5.0)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    # Obtener mensajes con texto
    sql = f"""
        SELECT oid, ts_utc, channel, channel_username, text, score, 
               order_type, symbol, entry_price, sl, tp, comment
        FROM {table}
        WHERE text IS NOT NULL AND text != ''
        ORDER BY ts_utc DESC
    """
    if limite:
        sql += f" LIMIT {limite}"
    
    rows = cur.execute(sql).fetchall()
    conn.close()
    
    # Clasificar mensajes por acción detectada
    resultados = {
        'BREAKEVEN': [],
        'PARTIAL CLOSE': [],
        'CLOSE': [],
        'MULTIPLE': []
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

def procesar_mensaje_con_testeador(row):
    """
    Procesa un mensaje usando las mismas funciones que el testeador.
    Retorna el resultado del procesamiento.
    """
    # Reconstruir evento similar al que vendría de Redis
    evento = {
        'msg_id': row['msg_id'] if 'msg_id' in row.keys() else None,
        'ch_id': row['ch_id'] if 'ch_id' in row.keys() else None,
        'channel': row['channel'] if 'channel' in row.keys() else None,
        'channel_username': row['channel_username'] if 'channel_username' in row.keys() else None,
        'sender_id': row['sender_id'] if 'sender_id' in row.keys() else None,
        'text': row['text'] if 'text' in row.keys() else None,
        'raw': row['text'] if 'text' in row.keys() else None,
        'text/raw': row['text'] if 'text' in row.keys() else None,
        'ts_utc': row['ts_utc'] if 'ts_utc' in row.keys() else None,
        'ts_redis_ingest': row['ts_redis_ingest'] if 'ts_redis_ingest' in row.keys() else None,
    }
    
    texto = evento.get('text') or ""
    if not texto:
        return None
    
    # 1) Clasificar mensaje
    resultados = clasificar_mensajes(texto)
    if not resultados:
        return None
    
    mejor_resultado = _best_result(resultados)
    score = int(mejor_resultado.get("score", 0))
    accion = mejor_resultado.get("accion", "")
    
    # 2) Formatear según el score
    if score == 10:
        texto_formateado = formatear_senal(mejor_resultado)
    else:
        texto_formateado = formatear_motivo_rechazo(mejor_resultado)
    
    # 3) Construir fila
    fila = _build_fila_desde_resultado(resultados, evento)
    oid_nuevo = fila['oid']
    
    # 4) Construir básicos
    basico = _build_basico_desde_evento(evento, score, oid_nuevo, texto_formateado)
    
    return {
        'oid_original': row['oid'] if 'oid' in row.keys() else None,
        'oid_nuevo': oid_nuevo,
        'score': score,
        'accion': accion,
        'fila': fila,
        'basico': basico,
        'texto_formateado': texto_formateado,
        'mejor_resultado': mejor_resultado
    }

def mostrar_comparacion(row, resultado_procesado):
    """
    Muestra una comparación entre el estado original en BBDD y el resultado del procesamiento.
    """
    print("\n" + "-" * 80)
    print(f"OID Original: {row['oid']}")
    print(f"Fecha: {row['ts_utc']}")
    
    # Mostrar texto original (manejar codificación)
    texto_original = row['text'][:200] if row['text'] else ''
    try:
        # Intentar limpiar caracteres problemáticos para la consola
        texto_original_clean = texto_original.encode('utf-8', errors='ignore').decode('utf-8', errors='ignore')
    except:
        texto_original_clean = texto_original
    print(f"Texto original: {texto_original_clean}...")
    
    # Estado en BBDD (original)
    print("\n[ESTADO EN BBDD (Original)]:")
    print(f"  Score: {row['score'] if 'score' in row.keys() else 'NULL'}")
    print(f"  order_type: {row['order_type'] if 'order_type' in row.keys() else 'NULL'}")
    print(f"  symbol: {row['symbol'] if 'symbol' in row.keys() else 'NULL'}")
    print(f"  entry_price: {row['entry_price'] if 'entry_price' in row.keys() else 'NULL'}")
    print(f"  sl: {row['sl'] if 'sl' in row.keys() else 'NULL'}")
    print(f"  tp: {row['tp'] if 'tp' in row.keys() else 'NULL'}")
    print(f"  comment: {row['comment'] if 'comment' in row.keys() else 'NULL'}")
    
    # Resultado del procesamiento (testeador)
    if resultado_procesado:
        print("\n[RESULTADO DEL PROCESAMIENTO (Testeador)]:")
        print(f"  Score: {resultado_procesado['score']}")
        print(f"  Acción detectada: {resultado_procesado['accion']}")
        print(f"  order_type: {resultado_procesado['fila'].get('order_type', 'NULL')}")
        print(f"  symbol: {resultado_procesado['fila'].get('symbol', 'NULL')}")
        print(f"  entry_price: {resultado_procesado['fila'].get('entry_price', 'NULL')}")
        print(f"  sl: {resultado_procesado['fila'].get('sl', 'NULL')}")
        tps_str = " / ".join([
            str(resultado_procesado['fila'][f'tp{i}']) 
            for i in range(1, 5) 
            if resultado_procesado['fila'].get(f'tp{i}') is not None
        ])
        print(f"  tp: {tps_str or 'NULL'}")
        print(f"  comment: {resultado_procesado['fila'].get('comment', 'NULL')}")
        
        if resultado_procesado['texto_formateado']:
            try:
                texto_formateado_clean = resultado_procesado['texto_formateado'][:200].encode('utf-8', errors='ignore').decode('utf-8', errors='ignore')
            except:
                texto_formateado_clean = resultado_procesado['texto_formateado'][:200]
            print(f"\n  Texto formateado: {texto_formateado_clean}...")
        
        # Detalles del mejor resultado
        mejor = resultado_procesado['mejor_resultado']
        print(f"\n  Detalles de clasificación:")
        print(f"    Clasificación: {mejor.get('clasificacion', 'N/A')}")
        print(f"    Activo: {mejor.get('activo', 'N/A')}")
        print(f"    Dirección: {mejor.get('direccion', 'N/A')}")
    else:
        print("\n[RESULTADO DEL PROCESAMIENTO]: No se pudo procesar")

def analizar_acciones_con_testeador(resultados: dict, limite_ejemplos: int = 10):
    """
    Analiza las acciones usando el testeador para ver cómo se procesan.
    """
    print("\n" + "=" * 80)
    print("ANÁLISIS CON TESTEADOR")
    print("=" * 80)
    
    for accion_nombre in ['BREAKEVEN', 'PARTIAL CLOSE', 'CLOSE']:
        mensajes = resultados[accion_nombre]
        if not mensajes:
            print(f"\n[{accion_nombre}]: No se encontraron mensajes")
            continue
        
        print(f"\n[{accion_nombre}]: {len(mensajes)} mensajes encontrados")
        print(f"Procesando primeros {min(limite_ejemplos, len(mensajes))} ejemplos...")
        
        ejemplos_procesados = 0
        ejemplos_con_score_10 = 0
        
        for i, row in enumerate(mensajes[:limite_ejemplos], 1):
            print(f"\n--- Ejemplo {i}/{min(limite_ejemplos, len(mensajes))} ---")
            
            resultado = procesar_mensaje_con_testeador(row)
            if resultado:
                mostrar_comparacion(row, resultado)
                
                ejemplos_procesados += 1
                if resultado['score'] == 10:
                    ejemplos_con_score_10 += 1
            else:
                print(f"[ERROR] No se pudo procesar el mensaje OID={row['oid']}")
        
        print(f"\n[{accion_nombre}] Resumen:")
        print(f"  Ejemplos procesados: {ejemplos_procesados}/{min(limite_ejemplos, len(mensajes))}")
        print(f"  Con score=10: {ejemplos_con_score_10}")
        print(f"  Con score<10: {ejemplos_procesados - ejemplos_con_score_10}")

def mostrar_resumen_general(resultados: dict):
    """Muestra un resumen general de los resultados encontrados."""
    print("\n" + "=" * 80)
    print("RESUMEN GENERAL")
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

def main():
    print("=" * 80)
    print("ANÁLISIS DE ACCIONES ESPECIALES CON TESTEADOR")
    print("=" * 80)
    print(f"BBDD: {DB_FILE}")
    print(f"Tabla: {TABLE}")
    print("=" * 80)
    
    try:
        # 1. Buscar mensajes por acción
        print("\n[PASO 1] Buscando mensajes con palabras clave...")
        print("(Limitando a 100 mensajes para análisis rápido)")
        resultados = buscar_mensajes_por_accion(DB_FILE, TABLE, limite=100)
        
        # 2. Mostrar resumen general
        print("\n[PASO 2] Generando resumen general...")
        mostrar_resumen_general(resultados)
        
        # 3. Analizar con testeador
        print("\n[PASO 3] Analizando con testeador (primeros 5 ejemplos de cada acción)...")
        analizar_acciones_con_testeador(resultados, limite_ejemplos=5)
        
        print("\n" + "=" * 80)
        print("ANÁLISIS COMPLETADO")
        print("=" * 80)
        print("\nNOTA: Este análisis muestra cómo el testeador procesa los mensajes.")
        print("Para reprocesar todos los mensajes y guardarlos en la tabla 'Mensajes_testados',")
        print("usa: python services/src/testermensajes/testeador_mensajes.py --modo todos --auto")
        
    except Exception as e:
        print(f"\n[ERROR]: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())

