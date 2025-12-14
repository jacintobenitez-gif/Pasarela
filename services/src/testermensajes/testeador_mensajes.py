# -*- coding: utf-8 -*-
# testeador_mensajes.py — Testeador de mensajes históricos
# Reprocesa mensajes de la BBDD para verificar que los cambios funcionan correctamente
# Solo guarda resultados en BBDD (sin publicar en Telegram ni escribir en CSV)
# Modos: semana pasada | toda la BBDD

import os
import sys
import sqlite3
import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path

# --- PATH robusto para imports locales ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))  # .../services/src/testermensajes
PARENT_DIR = os.path.dirname(BASE_DIR)  # .../services/src
if PARENT_DIR not in sys.path:
    sys.path.insert(0, PARENT_DIR)
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# Importar funciones del parseador y reglas de negocio
from reglasnegocio.reglasnegocio import clasificar_mensajes, formatear_senal, formatear_motivo_rechazo

# Importar funciones del parseador (necesitamos importar el módulo completo)
import importlib.util
parser_path = os.path.join(PARENT_DIR, "parser", "parseador_local.py")
spec = importlib.util.spec_from_file_location("parseador_local", parser_path)
parseador = importlib.util.module_from_spec(spec)
spec.loader.exec_module(parseador)

# Usar funciones del parseador
_best_result = parseador._best_result
_build_fila_desde_resultado = parseador._build_fila_desde_resultado
_build_basico_desde_evento = parseador._build_basico_desde_evento
db_upsert_basico = parseador.db_upsert_basico
db_update_operativos = parseador.db_update_operativos
DB_FILE = parseador.DB_FILE
TABLE = parseador.TABLE

# Cargar .env
from dotenv import load_dotenv, find_dotenv
ENV_PATH = find_dotenv(usecwd=True) or str(Path(__file__).resolve().parents[2] / ".env")
load_dotenv(ENV_PATH, override=True)

# Nombre de la tabla para resultados de testing
TEST_TABLE = "Mensajes_testados"

def crear_tabla_testados(db_path: str):
    """
    Crea o recrea la tabla Mensajes_testados con la misma estructura que la tabla principal.
    Si la tabla existe, la borra primero.
    """
    conn = sqlite3.connect(db_path, timeout=5.0)
    cur = conn.cursor()
    
    # Borrar tabla si existe
    cur.execute(f"DROP TABLE IF EXISTS {TEST_TABLE}")
    
    # Crear tabla con la misma estructura que Trazas_Unica
    # Basado en las columnas que se usan en el visor y en las consultas
    create_sql = f"""
    CREATE TABLE {TEST_TABLE} (
        oid TEXT PRIMARY KEY,
        ts_utc TEXT,
        ts_redis_ingest TEXT,
        ch_id INTEGER,
        msg_id INTEGER,
        channel TEXT,
        channel_username TEXT,
        sender_id INTEGER,
        text TEXT,
        texto_formateado TEXT,
        score INTEGER,
        estado_operacion TEXT,
        ts_mt4_queue TEXT,
        symbol TEXT,
        order_type TEXT,
        entry_price REAL,
        sl REAL,
        tp REAL,
        comment TEXT
    )
    """
    cur.execute(create_sql)
    conn.commit()
    conn.close()
    print(f"[OK] Tabla {TEST_TABLE} creada/recreada")

def guardar_resultado_testado(db_path: str, basico: dict, fila: dict = None):
    """
    Guarda un resultado procesado en la tabla Mensajes_testados.
    """
    conn = sqlite3.connect(db_path, timeout=5.0)
    cur = conn.cursor()
    
    # Preparar datos para insertar
    datos = {
        'oid': basico.get('oid'),
        'ts_utc': basico.get('ts_utc'),
        'ts_redis_ingest': basico.get('ts_redis_ingest'),
        'ch_id': basico.get('ch_id'),
        'msg_id': basico.get('msg_id'),
        'channel': basico.get('channel'),
        'channel_username': basico.get('channel_username'),
        'sender_id': basico.get('sender_id'),
        'text': basico.get('text'),
        'texto_formateado': basico.get('texto_formateado'),
        'score': basico.get('score'),
        'estado_operacion': basico.get('estado_operacion'),
        'ts_mt4_queue': basico.get('ts_mt4_queue'),
        'symbol': None,
        'order_type': None,
        'entry_price': None,
        'sl': None,
        'tp': None,
        'comment': None
    }
    
    # Si hay fila (score=10), añadir campos operativos
    if fila:
        datos['symbol'] = fila.get('symbol')
        datos['order_type'] = fila.get('order_type')
        datos['entry_price'] = fila.get('entry_price')
        datos['sl'] = fila.get('sl')
        datos['tp'] = fila.get('tp')
        datos['comment'] = fila.get('comment')
    
    # Insertar o reemplazar
    insert_sql = f"""
    INSERT OR REPLACE INTO {TEST_TABLE} (
        oid, ts_utc, ts_redis_ingest, ch_id, msg_id, channel, channel_username,
        sender_id, text, texto_formateado, score, estado_operacion, ts_mt4_queue,
        symbol, order_type, entry_price, sl, tp, comment
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    
    cur.execute(insert_sql, (
        datos['oid'], datos['ts_utc'], datos['ts_redis_ingest'], datos['ch_id'],
        datos['msg_id'], datos['channel'], datos['channel_username'],
        datos['sender_id'], datos['text'], datos['texto_formateado'],
        datos['score'], datos['estado_operacion'], datos['ts_mt4_queue'],
        datos['symbol'], datos['order_type'], datos['entry_price'],
        datos['sl'], datos['tp'], datos['comment']
    ))
    
    conn.commit()
    conn.close()

def day_bounds_utc_semana_pasada():
    """
    Devuelve (start_isoZ, end_isoZ) para la semana pasada en UTC.
    Semana pasada = hace 7 días hasta hace 1 día (para evitar procesar mensajes de hoy).
    """
    now = datetime.now(timezone.utc)
    end = datetime(now.year, now.month, now.day, tzinfo=timezone.utc) - timedelta(days=1)
    start = end - timedelta(days=7)
    fmt = "%Y-%m-%dT%H:%M:%SZ"
    return start.strftime(fmt), end.strftime(fmt)

def fetch_mensajes_semana_pasada(db_path: str, table: str):
    """Obtiene mensajes de la semana pasada desde la BBDD."""
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"No existe la BBDD: {db_path}")
    
    conn = sqlite3.connect(db_path, timeout=5.0)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    start_iso, end_iso = day_bounds_utc_semana_pasada()
    sql = f"""
        SELECT oid, ts_utc, ts_redis_ingest, ch_id, msg_id, channel, channel_username,
               sender_id, text, score, estado_operacion, ts_mt4_queue,
               symbol, order_type, entry_price, sl, tp, comment
        FROM {table}
        WHERE ts_utc >= ? AND ts_utc < ?
        ORDER BY ts_utc ASC, rowid ASC
    """
    rows = cur.execute(sql, (start_iso, end_iso)).fetchall()
    conn.close()
    return rows

def fetch_todos_mensajes(db_path: str, table: str):
    """Obtiene TODOS los mensajes desde la BBDD."""
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"No existe la BBDD: {db_path}")
    
    conn = sqlite3.connect(db_path, timeout=5.0)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    sql = f"""
        SELECT oid, ts_utc, ts_redis_ingest, ch_id, msg_id, channel, channel_username,
               sender_id, text, score, estado_operacion, ts_mt4_queue,
               symbol, order_type, entry_price, sl, tp, comment
        FROM {table}
        ORDER BY ts_utc ASC, rowid ASC
    """
    rows = cur.execute(sql).fetchall()
    conn.close()
    return rows

def procesar_mensaje(row, modo_test: str):
    """
    Procesa un mensaje histórico simulando el flujo normal del parseador.
    """
    # Reconstruir evento similar al que vendría de Redis
    # sqlite3.Row se accede con [] o con getattr, no tiene método .get()
    evento = {
        'msg_id': row['msg_id'] if 'msg_id' in row.keys() else None,
        'ch_id': row['ch_id'] if 'ch_id' in row.keys() else None,
        'channel': row['channel'] if 'channel' in row.keys() else None,
        'channel_username': row['channel_username'] if 'channel_username' in row.keys() else None,
        'sender_id': row['sender_id'] if 'sender_id' in row.keys() else None,
        'text': row['text'] if 'text' in row.keys() else None,
        'raw': row['text'] if 'text' in row.keys() else None,  # Fallback
        'text/raw': row['text'] if 'text' in row.keys() else None,  # Fallback
        'ts_utc': row['ts_utc'] if 'ts_utc' in row.keys() else None,
        'ts_redis_ingest': row['ts_redis_ingest'] if 'ts_redis_ingest' in row.keys() else None,
    }
    
    texto = evento.get('text') or ""
    oid_original = row['oid'] if 'oid' in row.keys() else None
    ts_utc_val = row['ts_utc'] if 'ts_utc' in row.keys() else None
    
    if not texto:
        print(f"[TEST] [WARN] OID={oid_original} sin texto, omitiendo...")
        return None
    
    print(f"\n[TEST] Procesando OID={oid_original} | ts_utc={ts_utc_val}")
    print(f"[TEST] Texto original: {texto[:100]}...")
    
    # 1) Clasificar mensaje
    resultados = clasificar_mensajes(texto)
    if not resultados:
        print(f"[TEST] [WARN] Sin resultados de clasificación")
        return None
    
    mejor_resultado = _best_result(resultados)
    score = int(mejor_resultado.get("score", 0))
    
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
    
    # 5) Guardar básicos en BBDD
    try:
        db_upsert_basico(basico)
        print(f"[TEST] [OK] BBDD básicos guardados (oid_nuevo={oid_nuevo}, score={score})")
    except Exception as e:
        print(f"[TEST] [ERROR] BBDD básicos (oid_nuevo={oid_nuevo}): {e}")
        import traceback
        traceback.print_exc()
        return None
    
    # 6) Si score=10, procesar operativos
    if score == 10:
        # Campos operativos en BBDD
        try:
            db_update_operativos(oid_nuevo, fila)
            tps_str = " / ".join([str(fila[f'tp{i}']) for i in range(1, 5) if fila.get(f'tp{i}') is not None])
            print(f"[TEST] [OK] BBDD operativos guardados -> symbol={fila.get('symbol')} entry={fila.get('entry_price')} sl={fila.get('sl')} tp=[{tps_str}]")
        except Exception as e:
            print(f"[TEST] [ERROR] BBDD operativos (oid={oid_nuevo}): {e}")
            import traceback
            traceback.print_exc()
        
        # Guardar en tabla de testing con datos operativos
        try:
            guardar_resultado_testado(DB_FILE, basico, fila)
        except Exception as e:
            print(f"[TEST] [WARN] Error guardando en {TEST_TABLE} (oid={oid_nuevo}): {e}")
    else:
        print(f"[TEST] [INFO] score<10 -> Solo básicos guardados (score={score})")
        if texto_formateado:
            print(f"[TEST] Motivo rechazo: {texto_formateado[:150]}...")
        
        # Guardar en tabla de testing sin datos operativos
        try:
            guardar_resultado_testado(DB_FILE, basico, None)
        except Exception as e:
            print(f"[TEST] [WARN] Error guardando en {TEST_TABLE} (oid={oid_nuevo}): {e}")
    
    score_original = row['score'] if 'score' in row.keys() else None
    
    return {
        'oid_original': oid_original,
        'oid_nuevo': oid_nuevo,
        'score': score,
        'score_original': score_original,
        'texto': texto[:80]
    }

def main():
    parser = argparse.ArgumentParser(description='Testeador de mensajes históricos')
    parser.add_argument('--modo', choices=['semana', 'todos'], default='semana',
                       help='Modo de ejecución: semana (semana pasada) o todos (toda la BBDD)')
    parser.add_argument('--auto', action='store_true',
                       help='Ejecutar automáticamente sin confirmación (útil para scripts)')
    args = parser.parse_args()
    
    print("=" * 80)
    print("TESTEADOR DE MENSAJES HISTÓRICOS")
    print("=" * 80)
    print(f"Modo: {'SEMANA PASADA' if args.modo == 'semana' else 'TODA LA BBDD'}")
    print(f"BBDD: {DB_FILE}")
    print(f"Tabla: {TABLE}")
    print(f"Tabla de resultados: {TEST_TABLE}")
    print("NOTA: Solo se guardan resultados en BBDD (sin Telegram ni CSV)")
    print("=" * 80)
    
    # Crear/borrar tabla de testing al inicio
    try:
        crear_tabla_testados(DB_FILE)
    except Exception as e:
        print(f"[ERROR] No se pudo crear/borrar tabla {TEST_TABLE}: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    # Obtener mensajes según el modo
    try:
        if args.modo == 'semana':
            start_iso, end_iso = day_bounds_utc_semana_pasada()
            print(f"\nBuscando mensajes entre {start_iso} y {end_iso}")
            mensajes = fetch_mensajes_semana_pasada(DB_FILE, TABLE)
        else:
            print(f"\nBuscando TODOS los mensajes")
            mensajes = fetch_todos_mensajes(DB_FILE, TABLE)
        
        total = len(mensajes)
        print(f"[OK] Encontrados {total} mensajes para procesar\n")
        
        if total == 0:
            print("[WARN] No hay mensajes para procesar. Saliendo...")
            return
        
        # Confirmar antes de procesar (solo si no está en modo auto)
        if not args.auto:
            try:
                respuesta = input(f"¿Procesar {total} mensajes? (s/n): ").strip().lower()
                if respuesta != 's':
                    print("Cancelado por el usuario.")
                    return
            except (EOFError, KeyboardInterrupt):
                print("\nCancelado por el usuario.")
                return
        else:
            print(f"[INFO] Modo automatico activado. Procesando {total} mensajes...")
        
        # Procesar cada mensaje
        procesados = 0
        errores = 0
        resultados = []
        
        for idx, row in enumerate(mensajes, 1):
            print(f"\n[{idx}/{total}] ", end="")
            try:
                resultado = procesar_mensaje(row, args.modo)
                if resultado:
                    procesados += 1
                    resultados.append(resultado)
                else:
                    errores += 1
            except Exception as e:
                errores += 1
                print(f"[TEST] [ERROR] procesando mensaje {idx}: {e}")
                import traceback
                traceback.print_exc()
        
        # Resumen final
        print("\n" + "=" * 80)
        print("RESUMEN FINAL")
        print("=" * 80)
        print(f"Total mensajes: {total}")
        print(f"Procesados exitosamente: {procesados}")
        print(f"Errores/omitidos: {errores}")
        
        if resultados:
            scores_10 = sum(1 for r in resultados if r['score'] == 10)
            scores_menor_10 = sum(1 for r in resultados if r['score'] < 10)
            print(f"\nDistribucion de scores:")
            print(f"  Score = 10: {scores_10}")
            print(f"  Score < 10: {scores_menor_10}")
        
        print("=" * 80)
        
    except Exception as e:
        print(f"\n[ERROR FATAL]: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())

