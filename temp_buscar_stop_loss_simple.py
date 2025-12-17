#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Script temporal para buscar frases relacionadas con "mover stop loss"

import sqlite3
import re

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
]

# Conectar a la BD
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

print("Buscando textos relacionados con 'mover stop loss'...\n")

# Construir query optimizada
conditions = []
for kw in keywords:
    conditions.append(f"LOWER(text) LIKE '%{kw.lower()}%'")

query = f"""
SELECT DISTINCT text 
FROM {TABLE} 
WHERE text IS NOT NULL 
  AND text != ''
  AND ({' OR '.join(conditions)})
LIMIT 500
"""

cursor.execute(query)
results = cursor.fetchall()

print(f"Encontrados {len(results)} textos únicos.\n")
print("=" * 80)
print("TEXTOS COMPLETOS ENCONTRADOS:")
print("=" * 80)

# Mostrar textos completos
textos_unicos = []
for (text,) in results:
    if text and text.strip():
        textos_unicos.append(text.strip())

# Eliminar duplicados manteniendo orden
textos_unicos = list(dict.fromkeys(textos_unicos))

for i, texto in enumerate(textos_unicos[:100], 1):
    print(f"\n[{i}] {texto}")

if len(textos_unicos) > 100:
    print(f"\n... y {len(textos_unicos) - 100} textos más")

# Buscar patrones específicos
print("\n" + "=" * 80)
print("PATRONES ESPECÍFICOS DETECTADOS:")
print("=" * 80)

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
    (r'mover.*a.*breakeven', 'mover a breakeven'),
    (r'poner.*sl.*a', 'poner SL a'),
    (r'colocar.*sl.*a', 'colocar SL a'),
]

from collections import Counter
patrones_encontrados = Counter()

for texto in textos_unicos:
    texto_lower = texto.lower()
    for pattern, nombre in patrones:
        if re.search(pattern, texto_lower):
            patrones_encontrados[nombre] += 1

print("\nPatrones más frecuentes:")
for patron, count in patrones_encontrados.most_common(20):
    print(f"  - {patron}: {count} ocurrencias")

# Extraer frases cortas relevantes
print("\n" + "=" * 80)
print("FRASES CORTAS RELEVANTES (extractos):")
print("=" * 80)

frases_cortas = set()
for texto in textos_unicos[:200]:  # Limitar procesamiento
    texto_lower = texto.lower()
    # Buscar frases de hasta 100 caracteres que contengan palabras clave
    for kw in ['mover', 'ajustar', 'cambiar', 'modificar', 'subir', 'bajar']:
        if kw in texto_lower:
            idx = texto_lower.find(kw)
            start = max(0, idx - 30)
            end = min(len(texto), idx + 70)
            frase = texto[start:end].strip()
            if len(frase) > 15 and len(frase) < 150:
                # Limpiar frase
                frase = re.sub(r'\s+', ' ', frase)
                if any(k in frase.lower() for k in ['sl', 'stop', 'loss', 'breakeven']):
                    frases_cortas.add(frase)

for i, frase in enumerate(sorted(frases_cortas)[:50], 1):
    print(f"\n{i}. ...{frase}...")

conn.close()
print("\n\nAnálisis completado.")



























