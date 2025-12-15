# DOCUMENTO FUNCIONAL: EA MQL4 - Gestión de Cola de Operaciones

## 1. OBJETIVO DEL PROYECTO

Crear un Expert Advisor (EA) en MQL4 que lea un archivo CSV (`colaMT4.csv`) cada 2 segundos y ejecute acciones de trading según los registros encontrados, con control de reintentos y persistencia de estado.

---

## 2. ARCHIVOS INVOLUCRADOS

### 2.1. Archivo de Entrada: `colaMT4.csv`

**Ubicación:**
- Carpeta "Common Files" de MetaTrader 4
- Ruta completa: `C:\Users\[Usuario]\AppData\Roaming\MetaQuotes\Terminal\[ID]\Common\Files\colaMT4.csv`

**Estructura del CSV:**
```
oid, ts_mt4_queue, symbol, order_type, entry_price, sl, tp1, tp2, tp3, tp4, comment, estado_operacion, channel
```

**Ejemplo de registros:**
```
20251213-00759,2025-12-13T21:52:50.275903+00:00,BTCUSD,SELL,106400.0,107400.0,105500.0,104800.0,,,20251213-00759,0,PRUEBASRUBENJACINTO
20251214-00760,2025-12-14T07:21:49.440454+00:00,,BREAKEVEN,,,,,,,20251214-00760,0,PRUEBASRUBENJACINTO
20251214-00761,2025-12-14T07:22:09.521652+00:00,BTCUSD,SELL,106400.0,107400.0,105500.0,104800.0,,,20251214-00761,0,PRUEBASRUBENJACINTO
```

**Nota importante:** El campo `estado_operacion` se **IGNORA**. El EA procesa **TODOS** los registros del CSV sin filtrar por este campo.

---

### 2.2. Archivo de Control: `colaMT4_control.txt`

**Ubicación:** Misma carpeta que el CSV (Common Files)

**Formato:** `oid|contador_reintentos`
```
20251213-00759|2
20251214-00760|3
20251214-00761|1
20251214-00771|3
```

**Propósito:**
- Persistir el estado de reintentos entre reinicios del EA
- Evitar procesar oids que ya fallaron 3 veces

**Significado del contador:**
- `contador = 0, 1, 2` → oid en proceso de reintento (aún puede intentarse)
- `contador >= 3` → oid fallido definitivamente (se ignora)

**Limpieza automática:**
- Al iniciar el EA (OnInit): compara fecha actual con fecha del archivo
- Si fecha archivo < fecha actual → **ELIMINAR** archivo `colaMT4_control.txt`
- El EA crea archivo nuevo si no existe

---

## 3. SISTEMA DE IDENTIFICACIÓN: COMMENT

### 3.1. Problema del Límite de Caracteres

- El campo `comment` en MQL4 tiene límite de **31 caracteres**
- `oid` (ej: "20251213-00759") = 14 caracteres
- `channel` (ej: "PRUEBAS RUBEN Y JACINTO") = ~25 caracteres
- Total excedería el límite

### 3.2. Solución: Mapeo de Channels a Códigos Numéricos

**Mapeo fijo en el EA:**
- `"JB UNITED"` → código `1`
- `"JB TORO"` → código `2`
- `"JB GOLD VIP IÑAKI"` → código `3`
- `"PRUEBAS RUBEN Y JACINTO"` → código `4`

**Formato del comment:**
- Comment = `oid + código_numerico`
- Ejemplo: `"20251213-00759-1"` o `"20251213-007591"`
- Longitud: ~15-16 caracteres (dentro del límite de 31 caracteres)

**Implementación:**
- Variables/constantes fijas en el EA que mapean cada channel a su código
- Al leer CSV: compara `channel` con variables → obtiene código numérico
- Construye comment como `oid + código`

---

## 4. PARÁMETROS CONFIGURABLES DEL EA

El EA tendrá los siguientes parámetros configurables (inputs):

### 4.1. Volume (Volumen)
- **Nombre del parámetro:** `Volume`
- **Tipo:** double
- **Valor por defecto:** `0.01`
- **Descripción:** Volumen en lotes para las órdenes BUY y SELL
- **Uso:** Se utiliza en `OrderSend()` para BUY y SELL

### 4.2. Slippage (Deslizamiento)
- **Nombre del parámetro:** `Slippage`
- **Tipo:** int
- **Valor por defecto:** `30`
- **Descripción:** Deslizamiento máximo permitido en puntos para ejecución de órdenes
- **Uso:** Se utiliza en `OrderSend()` y `OrderClose()`

### 4.3. Magic Number (Opcional)
- **Nombre del parámetro:** `MagicNumber`
- **Tipo:** int
- **Valor por defecto:** `0`
- **Descripción:** Número mágico para identificar órdenes del EA (opcional)
- **Uso:** Se utiliza en `OrderSend()` para identificar órdenes del EA

---

## 5. LAS 7 ACCIONES DEL EA

### 5.1. BUY

**Descripción:** Abre orden de compra a precio de mercado

**Datos requeridos del CSV:**
- `symbol`: símbolo a operar
- `entry_price`: precio de entrada (se usa precio de mercado actual)
- `sl`: stop loss
- `tp1`: take profit (solo se usa tp1, tp2-tp4 se ignoran)

**Ejecución:**
- Método: `OrderSend()` con `OP_BUY`
- Tipo: precio de mercado (precio actual)
- Parámetros:
  - Symbol: `symbol` del CSV
  - Cmd: `OP_BUY`
  - Volume: `Volume` (parámetro del EA, por defecto 0.01)
  - Price: `Ask` (precio de mercado actual)
  - Slippage: `Slippage` (parámetro del EA, por defecto 30)
  - StopLoss: `sl` del CSV
  - TakeProfit: `tp1` del CSV
  - Comment: `oid + código_canal`
  - Magic: `MagicNumber` (parámetro del EA, por defecto 0)
  - Expiration: 0

**Búsqueda previa:**
- Verificar en historial si ya existe orden con ese comment
- Si existe → ignorar registro (evitar duplicados)
- Si no existe → ejecutar orden

---

### 5.2. SELL

**Descripción:** Abre orden de venta a precio de mercado

**Datos requeridos del CSV:**
- `symbol`: símbolo a operar
- `entry_price`: precio de entrada (se usa precio de mercado actual)
- `sl`: stop loss
- `tp1`: take profit (solo se usa tp1, tp2-tp4 se ignoran)

**Ejecución:**
- Método: `OrderSend()` con `OP_SELL`
- Tipo: precio de mercado (precio actual)
- Parámetros:
  - Symbol: `symbol` del CSV
  - Cmd: `OP_SELL`
  - Volume: `Volume` (parámetro del EA, por defecto 0.01)
  - Price: `Bid` (precio de mercado actual)
  - Slippage: `Slippage` (parámetro del EA, por defecto 30)
  - StopLoss: `sl` del CSV
  - TakeProfit: `tp1` del CSV
  - Comment: `oid + código_canal`
  - Magic: `MagicNumber` (parámetro del EA, por defecto 0)
  - Expiration: 0

**Búsqueda previa:**
- Verificar en historial si ya existe orden con ese comment
- Si existe → ignorar registro (evitar duplicados)
- Si no existe → ejecutar orden

---

### 5.3. SL A

**Descripción:** Mueve stop loss a un precio específico (una posición)

**Datos requeridos del CSV:**
- `sl`: nuevo precio del stop loss
- `symbol`: opcional (puede venir vacío)

**Ejecución:**
- Método: `OrderModify()`
- Búsqueda: una posición abierta cuyo `OrderComment()` contenga el comment construido (oid + código_canal)
- Acción: modificar SL de la posición encontrada al nuevo precio

**Búsqueda:**
- Iterar sobre `OrdersTotal()` para posiciones abiertas
- Comparar `OrderComment()` con comment construido (oid + código_canal)
- Si `symbol` viene en CSV: también filtrar por `OrderSymbol()`
- Si encuentra posición → ejecutar `OrderModify()`
- Si no encuentra → registrar fallo y aplicar lógica de reintentos

---

### 5.4. VARIOS SL A

**Descripción:** Mueve stop loss a un precio específico (varias posiciones)

**Datos requeridos del CSV:**
- `sl`: nuevo precio del stop loss
- `symbol`: opcional (puede venir vacío)

**Ejecución:**
- Método: `OrderModify()` para cada posición encontrada
- Búsqueda: todas las posiciones abiertas cuyo `OrderComment()` contenga el comment construido (oid + código_canal)
- Acción: modificar SL de todas las posiciones encontradas al nuevo precio

**Búsqueda:**
- Iterar sobre `OrdersTotal()` para posiciones abiertas
- Comparar `OrderComment()` con comment construido (oid + código_canal)
- Si `symbol` viene en CSV: también filtrar por `OrderSymbol()`
- Para cada posición encontrada → ejecutar `OrderModify()`
- Si no encuentra ninguna → registrar fallo y aplicar lógica de reintentos

---

### 5.5. BREAKEVEN

**Descripción:** Mueve stop loss al precio de entrada de todas las operaciones que coincidan con el comment

**Datos requeridos del CSV:**
- `symbol`: opcional (puede venir vacío)
- No requiere `sl` del CSV (usa precio de entrada de cada orden)

**Ejecución:**
- Método: `OrderModify()` para cada posición encontrada
- Búsqueda: todas las posiciones abiertas cuyo `OrderComment()` contenga el comment construido (oid + código_canal)
- Acción: para cada posición encontrada:
  - Obtener `OrderOpenPrice()` (precio de entrada)
  - Ejecutar `OrderModify()` para poner SL = precio de entrada

**Búsqueda:**
- Iterar sobre `OrdersTotal()` para posiciones abiertas
- Comparar `OrderComment()` con comment construido (oid + código_canal)
- Si `symbol` viene en CSV: también filtrar por `OrderSymbol()`
- Para cada posición encontrada → obtener precio de entrada y modificar SL
- Si no encuentra ninguna → registrar fallo y aplicar lógica de reintentos

---

### 5.6. PARCIAL

**Descripción:** Reduce el volumen a la mitad de todas las operaciones que coincidan con el comment

**Datos requeridos del CSV:**
- `symbol`: opcional (puede venir vacío)
- No requiere datos adicionales (usa volumen actual de cada orden)

**Ejecución:**
- Método: `OrderClose()` parcial para cada posición encontrada
- Búsqueda: todas las posiciones abiertas cuyo `OrderComment()` contenga el comment construido (oid + código_canal)
- Acción: para cada posición encontrada:
  - Obtener `OrderLots()` (volumen actual)
  - Calcular nuevo volumen = `OrderLots() / 2`
  - Ejecutar `OrderClose()` parcial con el nuevo volumen

**Búsqueda:**
- Iterar sobre `OrdersTotal()` para posiciones abiertas
- Comparar `OrderComment()` con comment construido (oid + código_canal)
- Si `symbol` viene en CSV: también filtrar por `OrderSymbol()`
- Para cada posición encontrada → calcular volumen parcial y cerrar parcialmente
- Si no encuentra ninguna → registrar fallo y aplicar lógica de reintentos

**Parámetros de OrderClose():**
- Ticket: ticket de la posición encontrada
- Lots: volumen parcial calculado (`OrderLots() / 2`)
- Price: precio de cierre según tipo de orden (Bid para BUY, Ask para SELL)
- Slippage: `Slippage` (parámetro del EA, por defecto 30)

---

### 5.7. CERRAR

**Descripción:** Cierra todas las operaciones que coincidan con el comment

**Datos requeridos del CSV:**
- `symbol`: opcional (puede venir vacío)
- No requiere datos adicionales

**Ejecución:**
- Método: `OrderClose()` para cada posición encontrada
- Búsqueda: todas las posiciones abiertas cuyo `OrderComment()` contenga el comment construido (oid + código_canal)
- Acción: cerrar completamente todas las posiciones encontradas

**Búsqueda:**
- Iterar sobre `OrdersTotal()` para posiciones abiertas
- Comparar `OrderComment()` con comment construido (oid + código_canal)
- Si `symbol` viene en CSV: también filtrar por `OrderSymbol()`
- Para cada posición encontrada → ejecutar `OrderClose()` completo
- Si no encuentra ninguna → registrar fallo y aplicar lógica de reintentos

**Parámetros de OrderClose():**
- Ticket: ticket de la posición encontrada
- Lots: `OrderLots()` (cerrar todo el volumen)
- Price: precio de cierre según tipo de orden (Bid para BUY, Ask para SELL)
- Slippage: `Slippage` (parámetro del EA, por defecto 30)

---

## 6. ESTRUCTURA DE DATOS EN MEMORIA DEL EA

```mql4
// Arrays para gestión de reintentos y fallidos
string oids_fallidos[];           // oids con contador >= 3 (definitivos)
string oids_reintentando[];       // oids con contador 0, 1, 2
int contadores_reintentos[];      // contador paralelo a oids_reintentando[]

// Variables fijas de mapeo channel → código numérico
// (definidas como constantes o variables globales)
```

---

## 7. FLUJO DE FUNCIONAMIENTO COMPLETO

### 7.1. Inicialización del EA (OnInit)

```
PASO 1: Limpieza automática del archivo de control
   → Obtener fecha actual del sistema
   → Verificar si existe archivo colaMT4_control.txt
   → Si existe:
      - Obtener fecha de modificación del archivo
      - Comparar con fecha actual
      - Si fecha archivo < fecha actual → ELIMINAR archivo
   → Si no existe → continuar

PASO 2: Cargar archivo de control (si existe)
   → Abrir archivo colaMT4_control.txt en modo lectura
   → Por cada línea "oid|contador":
      - Parsear oid y contador
      - Si contador >= 3:
         * Añadir oid a array oids_fallidos[]
      - Si contador < 3:
         * Añadir oid a array oids_reintentando[]
         * Añadir contador a array contadores_reintentos[]
   → Cerrar archivo

PASO 3: Inicializar variables de mapeo channel → código
   → Definir constantes/variables para mapeo:
      - "JB UNITED" → 1
      - "JB TORO" → 2
      - "JB GOLD VIP IÑAKI" → 3
      - "PRUEBAS RUBEN Y JACINTO" → 4

PASO 4: Configurar ruta del archivo CSV
   → Construir ruta completa a colaMT4.csv en Common Files

PASO 5: Configurar timer para lectura periódica
   → EventSetTimer(2) para leer cada 2 segundos
```

---

### 7.2. Loop Principal (cada 2 segundos - OnTimer)

```
PASO 1: Leer archivo CSV
   → Abrir colaMT4.csv en modo lectura
   → Leer todas las filas (ignorar cabecera)
   → Cerrar archivo

PASO 2: Procesar cada registro del CSV
   
   Para cada fila del CSV:
   
   a) Extraer campos del registro:
      - oid
      - channel
      - order_type
      - symbol
      - entry_price
      - sl
      - tp1 (tp2, tp3, tp4 se ignoran)
   
   b) Convertir channel a código numérico:
      - Comparar channel con variables de mapeo
      - Obtener código numérico correspondiente
      - Si no coincide con ningún mapeo → usar código por defecto o ignorar
   
   c) Construir comment:
      - comment = oid + código_numerico
      - Ejemplo: "20251213-00759-1"
   
   d) Verificar si oid está en oids_fallidos[]:
      - Si SÍ → IGNORAR registro (ya falló 3 veces)
      - Si NO → continuar
   
   e) Verificar si oid está en oids_reintentando[]:
      - Si SÍ → leer su contador de reintentos actual
      - Si NO → contador = 0 (primera vez que se procesa)
   
   f) Verificar duplicados en historial MT4:
      - Buscar en OrdersTotal() y OrdersHistoryTotal()
      - Comparar OrderComment() con comment construido
      - Si encuentra orden con ese comment:
         * IGNORAR registro (ya fue procesado exitosamente)
         * Continuar siguiente registro
      - Si NO encuentra → continuar
   
   g) Identificar order_type y ejecutar acción:
      
      CASO: BUY
      → Ejecutar OrderSend():
         - Symbol: symbol del CSV
         - Cmd: OP_BUY
         - Volume: Volume (parámetro del EA, por defecto 0.01)
         - Price: Ask (precio de mercado actual)
         - Slippage: Slippage (parámetro del EA, por defecto 30)
         - StopLoss: sl del CSV
         - TakeProfit: tp1 del CSV
         - Comment: comment construido
         - Magic: MagicNumber (parámetro del EA, por defecto 0)
         - Expiration: 0
      → Verificar resultado:
         - Si éxito → ir a gestión de éxito
         - Si fallo → ir a gestión de fallo
      
      CASO: SELL
      → Ejecutar OrderSend():
         - Symbol: symbol del CSV
         - Cmd: OP_SELL
         - Volume: Volume (parámetro del EA, por defecto 0.01)
         - Price: Bid (precio de mercado actual)
         - Slippage: Slippage (parámetro del EA, por defecto 30)
         - StopLoss: sl del CSV
         - TakeProfit: tp1 del CSV
         - Comment: comment construido
         - Magic: MagicNumber (parámetro del EA, por defecto 0)
         - Expiration: 0
      → Verificar resultado:
         - Si éxito → ir a gestión de éxito
         - Si fallo → ir a gestión de fallo
      
      CASO: SL A
      → Buscar posición abierta:
         - Iterar OrdersTotal()
         - Para cada orden:
            * Verificar OrderComment() contiene comment construido
            * Si symbol viene en CSV: también verificar OrderSymbol()
            * Si coincide → guardar ticket
         - Si encuentra una posición:
            * Ejecutar OrderModify():
               - Ticket: ticket encontrado
               - Price: OrderOpenPrice() (mantener precio de entrada)
               - StopLoss: sl del CSV (nuevo precio)
               - TakeProfit: OrderTakeProfit() (mantener TP)
            * Verificar resultado:
               - Si éxito → ir a gestión de éxito
               - Si fallo → ir a gestión de fallo
         - Si NO encuentra:
            * Ir a gestión de fallo
      
      CASO: VARIOS SL A
      → Buscar posiciones abiertas:
         - Iterar OrdersTotal()
         - Para cada orden:
            * Verificar OrderComment() contiene comment construido
            * Si symbol viene en CSV: también verificar OrderSymbol()
            * Si coincide → añadir ticket a lista
         - Si encuentra posiciones:
            * Para cada ticket encontrado:
               - Ejecutar OrderModify():
                  - Ticket: ticket actual
                  - Price: OrderOpenPrice() (mantener precio de entrada)
                  - StopLoss: sl del CSV (nuevo precio)
                  - TakeProfit: OrderTakeProfit() (mantener TP)
            * Verificar resultado:
               - Si todas exitosas → ir a gestión de éxito
               - Si alguna falla → ir a gestión de fallo
         - Si NO encuentra ninguna:
            * Ir a gestión de fallo
      
      CASO: BREAKEVEN
      → Buscar posiciones abiertas:
         - Iterar OrdersTotal()
         - Para cada orden:
            * Verificar OrderComment() contiene comment construido
            * Si symbol viene en CSV: también verificar OrderSymbol()
            * Si coincide → añadir ticket a lista
         - Si encuentra posiciones:
            * Para cada ticket encontrado:
               - Obtener OrderOpenPrice() (precio de entrada)
               - Ejecutar OrderModify():
                  - Ticket: ticket actual
                  - Price: OrderOpenPrice() (mantener precio de entrada)
                  - StopLoss: OrderOpenPrice() (precio de entrada = breakeven)
                  - TakeProfit: OrderTakeProfit() (mantener TP)
            * Verificar resultado:
               - Si todas exitosas → ir a gestión de éxito
               - Si alguna falla → ir a gestión de fallo
         - Si NO encuentra ninguna:
            * Ir a gestión de fallo
      
      CASO: PARCIAL
      → Buscar posiciones abiertas:
         - Iterar OrdersTotal()
         - Para cada orden:
            * Verificar OrderComment() contiene comment construido
            * Si symbol viene en CSV: también verificar OrderSymbol()
            * Si coincide → añadir ticket a lista
         - Si encuentra posiciones:
            * Para cada ticket encontrado:
               - Obtener OrderLots() (volumen actual)
               - Calcular volumen_parcial = OrderLots() / 2
               - Determinar precio de cierre:
                  * Si OrderType() == OP_BUY → usar Bid
                  * Si OrderType() == OP_SELL → usar Ask
               - Ejecutar OrderClose():
                  - Ticket: ticket actual
                  - Lots: volumen_parcial
                  - Price: precio de cierre determinado
                  - Slippage: Slippage (parámetro del EA, por defecto 30)
            * Verificar resultado:
               - Si todas exitosas → ir a gestión de éxito
               - Si alguna falla → ir a gestión de fallo
         - Si NO encuentra ninguna:
            * Ir a gestión de fallo
      
      CASO: CERRAR
      → Buscar posiciones abiertas:
         - Iterar OrdersTotal()
         - Para cada orden:
            * Verificar OrderComment() contiene comment construido
            * Si symbol viene en CSV: también verificar OrderSymbol()
            * Si coincide → añadir ticket a lista
         - Si encuentra posiciones:
            * Para cada ticket encontrado:
               - Determinar precio de cierre:
                  * Si OrderType() == OP_BUY → usar Bid
                  * Si OrderType() == OP_SELL → usar Ask
               - Ejecutar OrderClose():
                  - Ticket: ticket actual
                  - Lots: OrderLots() (cerrar todo el volumen)
                  - Price: precio de cierre determinado
                  - Slippage: Slippage (parámetro del EA, por defecto 30)
            * Verificar resultado:
               - Si todas exitosas → ir a gestión de éxito
               - Si alguna falla → ir a gestión de fallo
         - Si NO encuentra ninguna:
            * Ir a gestión de fallo
   
   h) Gestión de resultado:
      
      Si ÉXITO:
      → Eliminar oid de oids_reintentando[] (si estaba)
      → Eliminar contador de contadores_reintentos[] (si existía)
      → Actualizar archivo colaMT4_control.txt:
         - Leer archivo completo
         - Eliminar línea que contiene el oid
         - Reescribir archivo completo
      → Continuar siguiente registro
      
      Si FALLA:
      → Incrementar contador de reintentos:
         - contador = contador + 1
      → Actualizar en memoria:
         - Si oid no estaba en oids_reintentando[]:
            * Añadir oid a oids_reintentando[]
            * Añadir contador a contadores_reintentos[]
         - Si oid ya estaba:
            * Actualizar contador en contadores_reintentos[]
      → Actualizar archivo colaMT4_control.txt:
         - Leer archivo completo
         - Si oid ya existía en archivo:
            * Actualizar línea "oid|contador_anterior" → "oid|contador_nuevo"
         - Si oid es nuevo:
            * Añadir nueva línea "oid|contador"
         - Reescribir archivo completo
      → Verificar si contador >= 3:
         - Si SÍ:
            * Mover oid de oids_reintentando[] a oids_fallidos[]
            * Eliminar de contadores_reintentos[]
            * (El archivo ya tiene contador=3, se ignorará en futuras lecturas)
         - Si NO:
            * Continuar (reintentará en siguiente lectura del CSV)
      → Continuar siguiente registro
```

---

## 8. DETALLES TÉCNICOS

### 8.1. Frecuencia de Lectura
- El EA lee el CSV **cada 2 segundos**
- Implementación: usar `EventSetTimer(2)` en OnInit y `OnTimer()` para el loop

### 8.2. Tipo de Orden para BUY/SELL
- **Precio de mercado** (Market Order)
- Para BUY: usar `Ask` (precio de compra actual)
- Para SELL: usar `Bid` (precio de venta actual)

### 8.3. TPs
- Solo se usa `tp1` del CSV
- `tp2`, `tp3`, `tp4` se ignoran

### 8.4. Reintentos
- Máximo **3 intentos** por oid
- Si falla → incrementar contador
- Si contador < 3 → reintentar en siguiente lectura del CSV
- Si contador >= 3 → marcar como fallido definitivamente

### 8.5. Persistencia
- Los reintentos **sobreviven a reinicios** del EA
- Se guardan en archivo `colaMT4_control.txt`
- Al reiniciar → se cargan y continúan desde donde estaban

### 8.6. Búsquedas en Historial
- Usar `comment` (oid + código_canal) para identificar posiciones
- Buscar en `OrdersTotal()` (posiciones abiertas)
- Buscar en `OrdersHistoryTotal()` (historial de órdenes cerradas)
- Comparar `OrderComment()` con comment construido

### 8.7. Manejo de Errores
- Si falla lectura del CSV → continuar (reintentará en siguiente ciclo)
- Si falla escritura del archivo de control → mantener en memoria (intentar escribir en siguiente ciclo)
- Si falla ejecución de orden → aplicar lógica de reintentos

---

## 9. MÉTODOS MQL4 UTILIZADOS

- `OrderSend()` — para BUY y SELL
- `OrderModify()` — para SL A, VARIOS SL A y BREAKEVEN
- `OrderClose()` — para PARCIAL (parcial) y CERRAR (total)
- `OrderOpenPrice()` — para BREAKEVEN (obtener precio de entrada)
- `OrderLots()` — para PARCIAL (obtener volumen actual)
- `OrderComment()` — para búsquedas por comment
- `OrderSymbol()` — para filtrar por símbolo (opcional)
- `OrderType()` — para determinar tipo de orden (BUY/SELL) en PARCIAL y CERRAR
- `OrdersTotal()` — para iterar posiciones abiertas
- `OrdersHistoryTotal()` — para iterar historial de órdenes cerradas
- `EventSetTimer()` — para configurar lectura periódica
- `OnTimer()` — para ejecutar loop cada 2 segundos

---

## 10. RESUMEN DE DECISIONES TOMADAS

✅ Campo `estado_operacion`: **ignorado** (se procesan todos los registros)  
✅ Comment: formato `oid + código_numerico_channel`  
✅ Tipo de orden: precio de mercado (Market Order)  
✅ TPs: solo `tp1` (tp2-tp4 ignorados)  
✅ Reintentos: máximo 3, persistentes en archivo  
✅ Limpieza: automática diaria del archivo de control  
✅ Persistencia: Opción B (reintentos sobreviven a reinicios)  
✅ Método PARCIAL: usar `OrderClose()` parcial  
✅ Acciones múltiples: BREAKEVEN, PARCIAL y CERRAR afectan todas las posiciones con el mismo comment  
✅ Volume: parámetro del EA, valor por defecto `0.01`  
✅ Slippage: parámetro del EA, valor por defecto `30`  
✅ Magic Number: parámetro del EA, valor por defecto `0` (opcional)

---

## 11. CONSIDERACIONES ADICIONALES

### 11.1. Volumen de Órdenes
- Volume es un **parámetro configurable** del EA
- Valor por defecto: `0.01` lotes
- Se utiliza para todas las órdenes BUY y SELL

### 11.2. Slippage
- Slippage es un **parámetro configurable** del EA
- Valor por defecto: `30` puntos
- Se utiliza en `OrderSend()` y `OrderClose()`

### 11.3. Magic Number
- Magic Number es un **parámetro configurable** del EA
- Valor por defecto: `0`
- Se utiliza en `OrderSend()` para identificar órdenes del EA (opcional)

### 11.4. Manejo de Símbolos
- Si `symbol` viene vacío en CSV → buscar en todas las posiciones (sin filtrar por símbolo)
- Si `symbol` viene en CSV → filtrar también por símbolo en búsquedas

### 11.5. Precios de Cierre para OrderClose()
- Para órdenes BUY: usar `Bid` (precio de venta)
- Para órdenes SELL: usar `Ask` (precio de compra)

---

**FIN DEL DOCUMENTO FUNCIONAL**

