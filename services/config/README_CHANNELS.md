# Configuración de Canales para Listener

## 📋 Introducción

El listener ahora lee los canales desde un archivo de configuración JSON en lugar de usar canales "pinned" de Telegram.

## 🚀 Cómo Configurar

### Paso 1: Obtener los IDs de tus canales

Ejecuta el script auxiliar para listar todos los canales disponibles:

```bash
# Windows
ejecutar_list_channels.bat

# O directamente con Python
cd services
set PYTHONPATH=%CD%\src
python src\listener\list_channels.py
```

Este script:
- ✅ Se conecta a Telegram usando tus credenciales
- ✅ Lista todos los canales/megagrupos disponibles
- ✅ Genera automáticamente el archivo `config/channels.json`

### Paso 2: Revisar y editar el archivo generado

El archivo se guardará en: `services/config/channels.json`

Estructura del archivo:
```json
{
  "channels": [
    {
      "id": 123456789,
      "title": "Nombre del Canal",
      "username": "nombrecanal",
      "enabled": true,
      "include_linked": false
    }
  ],
  "metadata": {
    "last_updated": "2025-01-XX",
    "version": "1.0"
  }
}
```

### Paso 3: Activar/Desactivar canales

Para escuchar solo ciertos canales, edita el archivo y marca `"enabled": false` en los que no quieras escuchar:

```json
{
  "id": 123456789,
  "title": "Canal No Deseado",
  "enabled": false  // ← Cambia esto a false
}
```

### Paso 4: Incluir grupos de comentarios enlazados

Si un canal tiene un grupo de comentarios enlazado y quieres escucharlo también:

```json
{
  "id": 123456789,
  "title": "Canal Principal",
  "enabled": true,
  "include_linked": true  // ← Esto incluirá el grupo de comentarios
}
```

## 📝 Campos del Archivo de Configuración

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `id` | integer | **REQUERIDO** - ID numérico del canal (se obtiene automáticamente) |
| `title` | string | Nombre del canal (información) |
| `username` | string | Username del canal, ej: `@nombrecanal` (información) |
| `enabled` | boolean | `true` = escuchar, `false` = ignorar (por defecto: `true`) |
| `include_linked` | boolean | `true` = incluir grupo de comentarios enlazado (por defecto: `false`) |

## 🔄 Hot-Reload

El listener recarga automáticamente la configuración cada **30 segundos**. Puedes:

- ✅ Editar el archivo `channels.json` mientras el listener está corriendo
- ✅ Los cambios se aplicarán automáticamente sin reiniciar
- ✅ Los canales nuevos se empezarán a escuchar automáticamente
- ✅ Los canales deshabilitados se dejarán de escuchar

## ⚙️ Configuración Avanzada

### Cambiar la ruta del archivo de configuración

Puedes cambiar la ubicación del archivo usando una variable de entorno:

```bash
# Windows
set CHANNELS_CONFIG=C:\MiRuta\mis_canales.json

# Linux/Mac
export CHANNELS_CONFIG=/home/user/mis_canales.json
```

Por defecto, el archivo se busca en: `services/config/channels.json`

## 🔍 Cómo Funciona

1. **Al iniciar**: El listener carga el archivo `channels.json`
2. **Validación**: Verifica que los canales existen y tienes acceso
3. **Enriquecimiento**: Si `include_linked: true`, añade automáticamente el grupo de comentarios
4. **Filtrado**: Solo escucha mensajes de los canales configurados
5. **Recarga**: Cada 30 segundos verifica cambios en el archivo

## ❓ Troubleshooting

### Error: "Archivo no encontrado"
- Verifica que el archivo existe en `services/config/channels.json`
- Ejecuta `list_channels.py` para generar el archivo

### Error: "Ningún canal válido encontrado"
- Verifica que los IDs en el archivo son correctos
- Asegúrate de tener acceso a los canales configurados
- Revisa los logs para ver qué canales no se encontraron

### Los canales no se recargan automáticamente
- Verifica que el archivo tiene permisos de lectura
- Asegúrate de guardar el archivo después de editarlo
- Revisa los logs para ver errores de parsing JSON

## 📊 Ejemplo de Salida del Script

```
=== LISTANDO CANALES DISPONIBLES ===

[CANAL] ID: 123456789 | @nombrecanal          | Trading Signals
[MEGAGRUPO] ID: 987654321 | @otrocanal       | Grupo de Trading
...

=== TOTAL: 5 canales encontrados ===

✓ Configuración guardada en: C:\Pasarela\services\config\channels.json
```



