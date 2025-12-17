# -*- coding: utf-8 -*-
import sys
import os
sys.path.insert(0, 'services/src')

from reglasnegocio.reglasnegocio import clasificar_mensajes

# Importar _best_result desde parseador
import importlib.util
parser_path = os.path.join('services', 'src', 'parser', 'parseador_local.py')
spec = importlib.util.spec_from_file_location("parseador_local", parser_path)
parseador = importlib.util.module_from_spec(spec)
spec.loader.exec_module(parseador)
_best_result = parseador._best_result

textos = [
    'cerrar ya',
    'closed',
    'cerrar ahora',
    'close all',
    'cerrar todo',
    'cerrar',
    'close'
]

print("=" * 80)
print("PRUEBA DE DETECCIÓN DE CLOSE")
print("=" * 80)

for texto in textos:
    resultados = clasificar_mensajes(texto)
    mejor = _best_result(resultados)
    accion = mejor.get('accion', 'N/A')
    score = mejor.get('score', 'N/A')
    
    print(f"\nTexto: \"{texto}\"")
    print(f"  Acción detectada: {accion}")
    print(f"  Score: {score}")
    print(f"  Clasificación: {mejor.get('clasificacion', 'N/A')}")

