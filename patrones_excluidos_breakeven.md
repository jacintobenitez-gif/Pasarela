# Patrones Excluidos - Breakeven/Entrada

## Resumen
Estos patrones fueron **excluidos** porque están relacionados con mover el stop loss a **breakeven/entrada**, no a un valor numérico específico. El sistema actualmente excluye cualquier frase que contenga estas palabras clave.

## Palabras Clave de Exclusión Actuales
```python
EXCLUDE_WORDS = [
    'breakeven', 'break even', 'break-even', 
    'entry price', 'entry', 'back to entry',
    'to entry', 'to your entry'
]
```

## Patrones Excluidos por Categoría

### KW_MoverBE_A - "mover sl a entrada/breakeven"
```
- mover sl a entrada
- sl a be
- mover el sl a entrada
- mover sl a break even
- mover el sl a break even
```
**Razón de exclusión**: Contienen "entrada", "be", "break even"

---

### KW_MoverBE_B - "mover stop a entrada/breakeven"
```
- mover stop a entrada
- mover el stop a entrada
- mover stop a break even
- mover el stop a break even
```
**Razón de exclusión**: Contienen "entrada", "break even"

---

### KW_MoverBE_C - "sl a entrada"
```
- sl a
- sl a entrada
- sl al punto de entrada
- sl en entrada
- poner sl en entrada
- poner el sl en entrada
- pasa sl a entrada
```
**Razón de exclusión**: Contienen "entrada" o "a" sin número (solo "sl a" sin valor)

---

### KW_MoverBE_D - "subir/bajar sl a entrada"
```
- subir sl a entrada
- bajar sl a entrada
- ajustar sl a entrada
- ajusta sl a entrada
```
**Razón de exclusión**: Contienen "entrada"

**Nota**: Los patrones "subir sl a [número]" y "bajar sl a [número]" SÍ fueron añadidos (solo cuando hay número)

---

### KW_MoverBE_E - "stop a entrada"
```
- stop a entrada
- stop al punto de entrada
- stop en entrada
- stop loss a entrada
- stop loss al punto de entrada
```
**Razón de exclusión**: Contienen "entrada"

---

### KW_MoverBE_F - "stop-loss a entrada/be"
```
- stop-loss a entrada
- stop-loss al punto de entrada
- llevar sl a entrada
- llevar sl a be
- sl a be
- stop a be
```
**Razón de exclusión**: Contienen "entrada" o "be"

**Nota**: El patrón "llevar sl a [número]" SÍ fue añadido (solo cuando hay número)

---

### KW_MoverBE_G - "llevar/mover a be"
```
- llevar stop a be
- mover a be
- ir a be
- a be
- al be
- break even
- breakeven
```
**Razón de exclusión**: Contienen "be", "break even", "breakeven"

---

### KW_MoverBE_H - "sl a cero/0"
```
- sl a cero
- sl a 0
- stop a cero
- stop a 0
- move to breakeven
- move to break even
```
**Razón de exclusión**: Contienen "cero", "0", "breakeven", "break even"

**Nota**: El número "0" podría considerarse válido, pero se excluye porque generalmente indica breakeven

---

### KW_MoverBE_I - "go/set to breakeven"
```
- go breakeven
- go to breakeven
- set to breakeven
- set to break even
- be
- to be
- move to be
- set to be
```
**Razón de exclusión**: Contienen "be", "breakeven", "break even"

---

### KW_MoverBE_J - "sl to entry" (inglés)
```
- sl to entry
- set sl to entry
- move sl to entry
- put sl at entry
- adjust sl to entry
- stop to entry
- set stop to entry
- move stop to entry
```
**Razón de exclusión**: Contienen "entry" o "to entry"

---

### KW_MoverBE_K - "stoploss to entry/be/zero"
```
- stoploss to entry
- stop-loss to entry
- stop loss to entry
- sl to be
- stop to be
- move stop to be
- set stop to be
- move sl to be
- set sl to be
- sl to zero
- sl to 0
- stop to zero
- stop to 0
```
**Razón de exclusión**: Contienen "entry", "be", "zero", "0"

---

## Patrones que SÍ fueron añadidos (solo con números)

De las listas anteriores, estos verbos/estructuras SÍ se añadieron, pero **solo cuando van seguidos de un número**:

### ✅ Añadidos:
- `poner (el) SL a [número]` - ✅ Añadido
- `poner (el) SL en [número]` - ✅ Añadido
- `llevar (el) SL a [número]` - ✅ Añadido
- `subir (el) SL a [número]` - ✅ Añadido
- `bajar (el) SL a [número]` - ✅ Añadido
- `pasa (el) SL a [número]` - ✅ Añadido
- `mover (el) SL a [número]` - ✅ Añadido
- `ajustar (el) SL a [número]` - ✅ Añadido

### ❌ NO añadidos (porque son para breakeven):
- `poner SL a entrada` - ❌ Excluido
- `llevar SL a be` - ❌ Excluido
- `subir SL a entrada` - ❌ Excluido
- `sl a cero` - ❌ Excluido
- `sl to entry` - ❌ Excluido
- `move to breakeven` - ❌ Excluido

---

## Cómo funciona la exclusión

El sistema verifica primero si el texto contiene alguna palabra de `EXCLUDE_WORDS`. Si la contiene, retorna `None` inmediatamente, sin intentar buscar patrones numéricos.

```python
# Verificar exclusiones primero
texto_lower = texto.lower()
if any(ex in texto_lower for ex in EXCLUDE_WORDS):
    return None  # No procesa nada más
```

Esto significa que:
- ✅ "poner sl a 4170" → Se detecta (tiene número, no tiene palabras excluidas)
- ❌ "poner sl a entrada" → Se excluye (contiene "entrada")
- ✅ "llevar sl a 4200" → Se detecta (tiene número, no tiene palabras excluidas)
- ❌ "llevar sl a be" → Se excluye (contiene "be")

---

## Si quisieras añadir patrones de breakeven (NO recomendado)

Si en el futuro quisieras detectar estos patrones para breakeven, tendrías que:

1. **Crear una función separada** `_detect_move_sl_to_breakeven()` que:
   - Busque específicamente estos patrones
   - Retorne `'accion': 'BREAKEVEN'` (que ya existe en el sistema)
   - NO requiera número

2. **Modificar `clasificar_mensajes()`** para detectar breakeven ANTES de intentar detectar MOVETO

3. **NO modificar `_detect_move_sl()`** porque está diseñado específicamente para valores numéricos

Pero actualmente el sistema ya tiene detección de breakeven mediante `_has_breakeven_keyword()`, así que estos patrones adicionales no serían necesarios a menos que quieras mejorar la detección de breakeven.











