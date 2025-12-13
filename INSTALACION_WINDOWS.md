# Guía de Instalación para Windows

## Instalación Automática (Recomendado)

### Paso 1: Ejecutar el Script de Instalación

1. **Abrir PowerShell como Administrador:**
   - Presiona `Win + X`
   - Selecciona "Windows PowerShell (Administrador)" o "Terminal (Administrador)"
   - O busca "PowerShell" en el menú inicio, click derecho > "Ejecutar como administrador"

2. **Ejecutar el script:**
   ```powershell
   cd C:\ruta\al\proyecto
   .\instalar_windows.ps1
   ```

   O simplemente hacer doble-click en `instalar_windows.ps1` y seleccionar "Ejecutar con PowerShell"

### Paso 2: El Script Instalará Automáticamente:

- ✅ **Chocolatey** (gestor de paquetes para Windows)
- ✅ **Python 3.11** (con pip incluido)
- ✅ **Git** (control de versiones)
- ✅ **Redis** (servidor Redis para Windows)
- ✅ **Librerías Python:**
  - redis
  - telethon
  - python-dotenv

### Paso 3: Configurar Variables de Entorno

Después de la instalación, el script creará un archivo `.env.example`. 

1. Copia el archivo a `.env`:
   ```powershell
   Copy-Item .env.example .env
   ```

2. Edita `.env` con tus credenciales:
   ```powershell
   notepad .env
   ```

   Necesitarás:
   - `TELEGRAM_API_ID` - Obtener de https://my.telegram.org/apps
   - `TELEGRAM_API_HASH` - Obtener de https://my.telegram.org/apps
   - `TELEGRAM_PHONE` - Tu número de teléfono con código de país

---

## Instalación Manual (Alternativa)

Si prefieres instalar manualmente o el script falla:

### 1. Instalar Chocolatey

Abre PowerShell como Administrador y ejecuta:
```powershell
Set-ExecutionPolicy Bypass -Scope Process -Force
[System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072
iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))
```

### 2. Instalar Python 3.11

```powershell
choco install python311 -y
```

O descarga desde: https://www.python.org/downloads/

**IMPORTANTE:** Al instalar Python, marca la opción "Add Python to PATH"

### 3. Instalar Git

```powershell
choco install git -y
```

O descarga desde: https://git-scm.com/download/win

### 4. Instalar Redis

```powershell
choco install redis-64 -y
```

O descarga desde: https://github.com/microsoftarchive/redis/releases

**Iniciar Redis:**
```powershell
redis-server
```

O instalar como servicio Windows:
```powershell
redis-server --service-install
redis-server --service-start
```

### 5. Instalar Librerías Python

Abre una nueva terminal (PowerShell o CMD) y ejecuta:

```powershell
python -m pip install --upgrade pip
pip install redis telethon python-dotenv
```

---

## Verificación Post-Instalación

Ejecuta estos comandos para verificar que todo está instalado:

```powershell
# Verificar Python
python --version
# Debe mostrar: Python 3.11.x o superior

# Verificar pip
pip --version

# Verificar Git
git --version

# Verificar Redis (en otra terminal)
redis-cli ping
# Debe responder: PONG

# Verificar librerías Python
python -c "import redis; print('Redis OK')"
python -c "import telethon; print('Telethon OK')"
python -c "import dotenv; print('Dotenv OK')"
```

---

## Solución de Problemas

### Error: "No se puede ejecutar scripts en este sistema"

Ejecuta en PowerShell como Administrador:
```powershell
Set-ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### Redis no inicia

1. Verifica que el servicio esté instalado:
   ```powershell
   Get-Service Redis
   ```

2. Inicia el servicio manualmente:
   ```powershell
   Start-Service Redis
   ```

3. O ejecuta Redis en modo consola:
   ```powershell
   redis-server
   ```

### Python no se encuentra

1. Verifica que Python esté en el PATH:
   ```powershell
   $env:Path
   ```

2. Si no está, agrégalo manualmente:
   - Busca "Variables de entorno" en Windows
   - Agrega `C:\Python311` y `C:\Python311\Scripts` al PATH

### Chocolatey no funciona

Si Chocolatey falla, puedes instalar todo manualmente:
- Python: https://www.python.org/downloads/
- Git: https://git-scm.com/download/win
- Redis: https://github.com/microsoftarchive/redis/releases

---

## Estructura de Directorios Recomendada

```
C:\Pasarela\
├── services\
│   ├── src\
│   │   ├── listener\
│   │   ├── parser\
│   │   └── reglasnegocio\
│   └── config\
├── data\
├── .env
└── instalar_windows.ps1
```

---

## Próximos Pasos

1. ✅ Instalar software (usando el script automático)
2. ✅ Configurar archivo `.env` con credenciales
3. ✅ Clonar repositorio (si aplica)
4. ✅ Ejecutar listener: `python services\src\listener\listener.py`
5. ✅ Ejecutar parser: `python services\src\parser\parseador_local.py`

---

## Notas Importantes

- **Ejecutar como Administrador:** El script requiere permisos de administrador para instalar software
- **Reiniciar Terminal:** Después de instalar Python/Git, cierra y abre una nueva terminal
- **Redis como Servicio:** Redis puede ejecutarse como servicio Windows o en modo consola
- **Variables de Entorno:** El archivo `.env` debe estar en la raíz del proyecto
