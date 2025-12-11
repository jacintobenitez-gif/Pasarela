#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para buscar referencias al concepto "breakeven" en la tabla Trazas_Unica
Busca variaciones en inglés y español del término breakeven
"""

import os
import sqlite3
import re
from pathlib import Path

# Buscar la base de datos en posibles ubicaciones
DB_PATHS = [
    r"C:\Pasarela\services\pasarela.db",  # Prioridad: ubicación más común
    os.getenv("PASARELA_DB", "pasarela.db"),
    r"C:\Pasarela\pasarela.db",
    os.path.join(os.getcwd(), "pasarela.db"),
]

def find_db():
    """Encuentra la base de datos en las posibles ubicaciones"""
    for db_path in DB_PATHS:
        if os.path.exists(db_path):
            return db_path
    return None

def search_breakeven(db_path):
    """Busca todas las variaciones de breakeven en el campo text"""
    
    # Patrones de búsqueda (case-insensitive)
    patterns = [
        # Variaciones directas de breakeven
        r'breakeven',
        r'break-even',
        r'break even',
        r'break\s*even',
        r'break-even',
        
        # BE en mayúsculas o minúsculas (standalone o con contexto)
        r'\bBE\b',  # BE como palabra completa
        r'\bbe\b',  # be como palabra completa
        r'\bB\.E\.\b',  # B.E.
        r'\bb\.e\.\b',  # b.e.
        
        # BE con contexto (mover a BE, set BE, etc.)
        r'mover\s+a\s+BE',
        r'mover\s+al\s+BE',
        r'set\s+BE',
        r'set\s+to\s+BE',
        r'ajustar\s+a\s+BE',
        r'ajustar\s+al\s+BE',
        r'sl\s+a\s+BE',
        r'sl\s+en\s+BE',
        r'stop\s+a\s+BE',
        r'stop\s+en\s+BE',
        r'poner\s+BE',
        r'poner\s+a\s+BE',
        
        # BE con paréntesis o explicaciones
        r'be\s*\(breakeven\)',
        r'be\s*\(break\s*even\)',
        r'BE\s*\(breakeven\)',
        r'BE\s*\(break\s*even\)',
        
        # Variaciones en español
        r'punto\s*de\s*equilibrio',
        r'punto\s*equilibrio',
        r'sin\s*pérdidas',
        r'sin\s*perdidas',
        r'cero\s*pérdidas',
        r'cero\s*perdidas',
        r'sin\s*pérdida',
        r'sin\s*perdida',
        r'cero\s*pérdida',
        r'cero\s*perdida',
        
        # Expresiones comunes con breakeven
        r'mover\s+a\s+breakeven',
        r'mover\s+al\s+breakeven',
        r'mover\s+a\s+be',
        r'mover\s*sl\s*a\s+breakeven',
        r'sl\s+a\s+breakeven',
        r'sl\s+en\s+breakeven',
        r'stop\s+en\s+breakeven',
        r'stop\s+a\s+breakeven',
        r'set\s+breakeven',
        r'set\s+to\s+breakeven',
        r'ajustar\s+a\s+breakeven',
        r'ajustar\s+al\s+breakeven',
        r'poner\s+breakeven',
        r'poner\s+a\s+breakeven',
        r'lock\s+in.*breakeven',
        r'lock.*breakeven',
        r'close.*breakeven',
        r'cerrar.*breakeven',
        r'salir.*breakeven',
        
        # Otras variaciones
        r'breakeven\s+point',
        r'breakeven\s+price',
        r'precio\s+de\s+entrada',  # a veces se refiere a breakeven como precio de entrada
        r'entrada\s+original',
    ]
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    # Construir la consulta SQL con múltiples condiciones LIKE
    conditions = []
    params = []
    
    for pattern in patterns:
        # Convertir regex pattern a SQL LIKE pattern aproximado
        # Para búsquedas más flexibles, usamos LIKE con wildcards
        sql_pattern = pattern.replace(r'\s+', '%').replace(r'\s*', '%').replace('(', '').replace(')', '').replace('\\', '')
        conditions.append(f"LOWER(text) LIKE ?")
        params.append(f"%{sql_pattern.lower()}%")
    
    # También buscar con regex directamente en Python para mayor precisión
    query = f"""
        SELECT 
            oid,
            ts_utc,
            channel,
            channel_username,
            text,
            score,
            estado_operacion
        FROM Trazas_Unica
        WHERE text IS NOT NULL
        ORDER BY ts_utc DESC
    """
    
    cur.execute(query)
    rows = cur.fetchall()
    
    # Filtrar con regex en Python para mayor precisión
    matches = []
    seen_oids = set()  # Evitar duplicados
    
    for row in rows:
        text = row['text'] or ''
        text_lower = text.lower()
        text_original = text  # Mantener original para mostrar BE en mayúsculas
        
        # Buscar con cada patrón
        matched_patterns = []
        for pattern in patterns:
            # Para BE, buscar tanto en minúsculas como en mayúsculas en el texto original
            if r'\bBE\b' in pattern or r'\bB\.E\.\b' in pattern:
                if re.search(pattern, text, re.IGNORECASE):
                    matched_patterns.append(pattern)
            else:
                if re.search(pattern, text_lower, re.IGNORECASE):
                    matched_patterns.append(pattern)
        
        if matched_patterns and row['oid'] not in seen_oids:
            seen_oids.add(row['oid'])
            # Encontrar la posición del match para resaltar
            match_text = ""
            for pattern in matched_patterns[:1]:  # Solo mostrar el primer patrón encontrado
                if r'\bBE\b' in pattern or r'\bB\.E\.\b' in pattern:
                    match_obj = re.search(pattern, text, re.IGNORECASE)
                else:
                    match_obj = re.search(pattern, text_lower, re.IGNORECASE)
                if match_obj:
                    start = max(0, match_obj.start() - 30)
                    end = min(len(text), match_obj.end() + 30)
                    match_text = text[start:end]
                    break
            
            matches.append({
                'oid': row['oid'],
                'ts_utc': row['ts_utc'],
                'channel': row['channel'] or row['channel_username'] or 'N/A',
                'text': text[:300] + '...' if len(text) > 300 else text,
                'match_snippet': match_text,
                'score': row['score'],
                'estado_operacion': row['estado_operacion'],
                'matched_patterns': matched_patterns
            })
    
    conn.close()
    return matches

def main():
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    
    db_path = find_db()
    
    if not db_path:
        print("ERROR: No se encontro la base de datos pasarela.db")
        print("Buscadas en:")
        for path in DB_PATHS:
            print(f"  - {path}")
        return
    
    print(f"OK: Base de datos encontrada: {db_path}")
    
    # Verificar que la tabla existe
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='Trazas_Unica'")
    if not cur.fetchone():
        print("ERROR: La tabla Trazas_Unica no existe")
        conn.close()
        return
    
    # Contar registros totales
    cur.execute("SELECT COUNT(*) FROM Trazas_Unica WHERE text IS NOT NULL")
    total = cur.fetchone()[0]
    print(f"Total de registros con texto: {total}")
    conn.close()
    
    print("\nBuscando referencias a 'breakeven'...\n")
    
    matches = search_breakeven(db_path)
    
    if not matches:
        print("No se encontraron referencias a 'breakeven'")
        return
    
    print(f"OK: Se encontraron {len(matches)} referencias a 'breakeven':\n")
    print("=" * 100)
    
    for i, match in enumerate(matches, 1):
        print(f"\n[{i}] OID: {match['oid']}")
        print(f"    Fecha: {match['ts_utc']}")
        print(f"    Canal: {match['channel']}")
        print(f"    Score: {match['score']} | Estado: {match['estado_operacion']}")
        print(f"    Patrones encontrados: {', '.join(match['matched_patterns'][:3])}")
        if match.get('match_snippet'):
            print(f"    Fragmento: ...{match['match_snippet']}...")
        print(f"    Texto completo:")
        print(f"    {match['text']}")
        print("-" * 100)
    
    print(f"\nResumen: {len(matches)} registros encontrados")
    
    # Guardar resultados en archivo
    output_file = "breakeven_results.txt"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(f"BÚSQUEDA DE REFERENCIAS A BREAKEVEN\n")
        f.write(f"{'='*100}\n")
        f.write(f"Total de registros encontrados: {len(matches)}\n")
        f.write(f"Base de datos: {db_path}\n")
        f.write(f"{'='*100}\n\n")
        
        for i, match in enumerate(matches, 1):
            f.write(f"\n[{i}] OID: {match['oid']}\n")
            f.write(f"    Fecha: {match['ts_utc']}\n")
            f.write(f"    Canal: {match['channel']}\n")
            f.write(f"    Score: {match['score']} | Estado: {match['estado_operacion']}\n")
            f.write(f"    Patrones encontrados: {', '.join(match['matched_patterns'][:5])}\n")
            if match.get('match_snippet'):
                f.write(f"    Fragmento: ...{match['match_snippet']}...\n")
            f.write(f"    Texto completo:\n")
            f.write(f"    {match['text']}\n")
            f.write("-" * 100 + "\n")
    
    print(f"\nResultados guardados en: {output_file}")

if __name__ == "__main__":
    main()

