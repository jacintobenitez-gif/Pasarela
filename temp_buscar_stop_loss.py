#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Script temporal para buscar frases relacionadas con "mover stop loss"

import sqlite3
import re
from collections import Counter

DB_PATH = r"C:\Pasarela\services\pasarela.db"
TABLE = "Trazas_Unica"

# Palabras clave relacionadas con "mover stop loss"
keywords = [
    'mover', 'mov', 'mueve', 'muevo', 'movido', 'moviendo',
    'stop loss', 'stop-loss', 'stoploss', 'sl', 's.l.',
    'ajustar', 'ajuste', 'ajusta', 'ajustado',
    'modificar', 'modifica', 'modificado', 'modificando',
    'cambiar', 'cambio', 'cambia', 'cambiado',
    'subir', 'sube', 'subido', 'subiendo',
    'bajar', 'baja', 'bajado', 'bajando',
    'acercar', 'acerca', 'acercado',
    'alejar', 'aleja', 'alejado',
    'trailing', 'trail', 'arrastrar', 'arrastra',
    'breakeven', 'break even', 'break-even',
    'cero', 'ceros', '0',
    'punto', 'puntos',
    'pips'
]

# Conectar a la BD
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Obtener todos los textos que contengan alguna palabra clave
print("Buscando textos relacionados con 'mover stop loss'...\n")

# Crear patrón de búsqueda
pattern = '|'.join([re.escape(kw) for kw in keywords])
query = f"""
SELECT DISTINCT text 
FROM {TABLE} 
WHERE text IS NOT NULL 
  AND text != ''
  AND (
"""

# Construir condiciones OR para cada palabra clave
conditions = []
for kw in keywords:
    conditions.append(f"LOWER(text) LIKE '%{kw.lower()}%'")

query += " OR ".join(conditions) + ")"

cursor.execute(query)
results = cursor.fetchall()

print(f"Encontrados {len(results)} textos únicos con palabras clave relacionadas.\n")
print("=" * 80)
print("FRASES Y PATRONES ENCONTRADOS:")
print("=" * 80)

# Analizar y extraer frases relevantes (limitado a primeros 1000 resultados)
frases_encontradas = []
limit = min(1000, len(results))
for (text,) in results[:limit]:
    if text:
        text_lower = text.lower()
        # Buscar contexto alrededor de las palabras clave
        for kw in keywords:
            if kw.lower() in text_lower:
                # Extraer frase alrededor de la palabra clave (50 caracteres antes y después)
                idx = text_lower.find(kw.lower())
                start = max(0, idx - 50)
                end = min(len(text), idx + len(kw) + 50)
                contexto = text[start:end].strip()
                if contexto and len(contexto) > 10:
                    frases_encontradas.append(contexto)
                break  # Solo una vez por texto

# Mostrar frases únicas (limitado)
frases_unicas = list(set(frases_encontradas))
print(f"\nTotal de frases únicas encontradas: {len(frases_unicas)}")
print("\nPrimeras 50 frases más relevantes:")
for i, frase in enumerate(frases_unicas[:50], 1):
    print(f"\n{i}. {frase}")

if len(frases_unicas) > 50:
    print(f"\n... y {len(frases_unicas) - 50} frases más")

# Buscar patrones específicos
print("\n" + "=" * 80)
print("PATRONES ESPECÍFICOS DETECTADOS:")
print("=" * 80)

# Patrones comunes
patrones = [
    (r'mover.*sl', 'mover SL'),
    (r'mover.*stop', 'mover stop'),
    (r'ajustar.*sl', 'ajustar SL'),
    (r'ajustar.*stop', 'ajustar stop'),
    (r'cambiar.*sl', 'cambiar SL'),
    (r'modificar.*sl', 'modificar SL'),
    (r'subir.*sl', 'subir SL'),
    (r'bajar.*sl', 'bajar SL'),
    (r'trailing.*stop', 'trailing stop'),
    (r'breakeven', 'breakeven'),
    (r'sl.*a.*cero', 'SL a cero'),
    (r'sl.*a.*breakeven', 'SL a breakeven'),
]

patrones_encontrados = Counter()
for (text,) in results:
    if text:
        text_lower = text.lower()
        for pattern, nombre in patrones:
            if re.search(pattern, text_lower):
                patrones_encontrados[nombre] += 1

print("\nPatrones más frecuentes:")
for patron, count in patrones_encontrados.most_common(20):
    print(f"  - {patron}: {count} ocurrencias")

conn.close()

