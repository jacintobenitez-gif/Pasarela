# Guía: Clonar Repositorio en Nueva VPS

## Paso 1: Conectarse a la VPS

### Windows (PowerShell o CMD)
```powershell
ssh usuario@ip_de_la_vps
# Ejemplo: ssh root@192.168.1.100
```

### Linux/Mac (Terminal)
```bash
ssh usuario@ip_de_la_vps
# Ejemplo: ssh root@192.168.1.100
```

---

## Paso 2: Instalar Git (si no está instalado)

### Windows
```powershell
# Si tienes Chocolatey:
choco install git -y

# O descarga desde: https://git-scm.com/download/win
```

### Linux (Ubuntu/Debian)
```bash
sudo apt update
sudo apt install git -y
```

### Linux (CentOS/RHEL)
```bash
sudo yum install git -y
```

**Verificar instalación:**
```bash
git --version
```

---

## Paso 3: Clonar el Repositorio

### Opción A: Clonar con HTTPS (Más fácil, requiere credenciales)

```bash
# Navegar al directorio donde quieres clonar
cd /ruta/deseada
# Ejemplo: cd /home/usuario o cd C:\Proyectos

# Clonar el repositorio
git clone https://github.com/jacintobenitez-gif/Pasarela.git

# O si quieres especificar un nombre de carpeta diferente:
git clone https://github.com/jacintobenitez-gif/Pasarela.git mi-proyecto
```

**Si GitHub pide credenciales:**
- Usuario: tu nombre de usuario de GitHub
- Contraseña: **NO uses tu contraseña**, usa un **Personal Access Token**
  - Crea uno en: https://github.com/settings/tokens
  - Permisos necesarios: `repo` (acceso completo a repositorios privados)

### Opción B: Clonar con SSH (Recomendado para producción)

**Primero, configurar SSH:**

1. **Generar clave SSH (si no tienes una):**
```bash
ssh-keygen -t ed25519 -C "tu_email@ejemplo.com"
# Presiona Enter para aceptar ubicación por defecto
# Opcional: agrega una contraseña para mayor seguridad
```

2. **Copiar la clave pública:**
```bash
# Windows (PowerShell):
cat ~/.ssh/id_ed25519.pub

# Linux/Mac:
cat ~/.ssh/id_ed25519.pub
```

3. **Agregar la clave a GitHub:**
   - Ve a: https://github.com/settings/keys
   - Click en "New SSH key"
   - Pega el contenido de la clave pública
   - Guarda

4. **Clonar con SSH:**
```bash
git clone git@github.com:jacintobenitez-gif/Pasarela.git
```

---

## Paso 4: Navegar al Directorio Clonado

```bash
cd Pasarela
# O el nombre que hayas usado al clonar
```

---

## Paso 5: Verificar que Todo se Clonó Correctamente

```bash
# Ver estructura de directorios
ls -la
# Windows: dir

# Verificar que los archivos principales están presentes
ls services/src/
# Windows: dir services\src\
```

**Deberías ver:**
- `services/src/listener/`
- `services/src/parser/`
- `services/src/reglasnegocio/`
- `instalar_windows.ps1` (si es Windows)
- `INSTALACION_WINDOWS.md` o `INSTALACION_VPS.md`
- `.env.example` (si existe)

---

## Paso 6: Instalar Dependencias

### Si es Windows:
```powershell
# Ejecutar el script de instalación automática
.\instalar_windows.ps1
```

### Si es Linux:
```bash
# Seguir la guía INSTALACION_VPS.md
# O ejecutar manualmente:

# 1. Instalar Python 3.10+
sudo apt install python3 python3-pip python3-venv -y

# 2. Instalar Redis
sudo apt install redis-server -y
sudo systemctl enable redis-server
sudo systemctl start redis-server

# 3. Crear entorno virtual (recomendado)
python3 -m venv venv
source venv/bin/activate

# 4. Instalar librerías Python
pip install redis telethon python-dotenv
```

---

## Paso 7: Configurar Variables de Entorno

```bash
# Copiar archivo de ejemplo
cp .env.example .env
# Windows: Copy-Item .env.example .env

# Editar el archivo .env
nano .env
# Windows: notepad .env
# O: code .env (si tienes VS Code)
```

**Completar las siguientes variables:**
```env
TELEGRAM_API_ID=tu_api_id_aqui
TELEGRAM_API_HASH=tu_api_hash_aqui
TELEGRAM_PHONE=+34607190588
TELEGRAM_SESSION=telethon_session

REDIS_URL=redis://localhost:6379/0
REDIS_STREAM=pasarela:parse
REDIS_GROUP=parser
REDIS_CONSUMER=local

PASARELA_DB=pasarela.db
PASARELA_TABLE=Trazas_Unica
```

**Obtener credenciales de Telegram:**
- Ve a: https://my.telegram.org/apps
- Inicia sesión con tu número de teléfono
- Crea una nueva aplicación
- Copia `api_id` y `api_hash`

---

## Paso 8: Verificar Instalación

```bash
# Verificar Python
python --version
# Debe ser 3.10+

# Verificar Redis
redis-cli ping
# Debe responder: PONG

# Verificar librerías Python
python -c "import redis; print('Redis OK')"
python -c "import telethon; print('Telethon OK')"
python -c "import dotenv; print('Dotenv OK')"
```

---

## Paso 9: Iniciar los Servicios

### Iniciar Redis (si no está corriendo como servicio)
```bash
# Linux:
sudo systemctl start redis-server
# O manualmente:
redis-server

# Windows:
redis-server
# O como servicio:
redis-server --service-start
```

### Ejecutar Listener
```bash
cd services/src/listener
python listener.py
```

### Ejecutar Parser (en otra terminal)
```bash
cd services/src/parser
python parseador_local.py
```

---

## Resumen Rápido (Copy-Paste)

### Para Linux/Ubuntu:
```bash
# 1. Instalar Git
sudo apt update && sudo apt install git -y

# 2. Clonar repositorio
cd ~
git clone https://github.com/jacintobenitez-gif/Pasarela.git
cd Pasarela

# 3. Instalar dependencias
sudo apt install python3 python3-pip python3-venv redis-server -y
sudo systemctl enable redis-server
sudo systemctl start redis-server

# 4. Crear entorno virtual e instalar librerías
python3 -m venv venv
source venv/bin/activate
pip install redis telethon python-dotenv

# 5. Configurar .env
cp .env.example .env
nano .env  # Completar credenciales

# 6. Verificar
redis-cli ping
python -c "import redis, telethon, dotenv; print('OK')"
```

### Para Windows:
```powershell
# 1. Clonar repositorio
cd C:\
git clone https://github.com/jacintobenitez-gif/Pasarela.git
cd Pasarela

# 2. Ejecutar script de instalación
.\instalar_windows.ps1

# 3. Configurar .env
Copy-Item .env.example .env
notepad .env  # Completar credenciales

# 4. Iniciar Redis
redis-server

# 5. Ejecutar servicios
cd services\src\listener
python listener.py
```

---

## Solución de Problemas

### Error: "Permission denied (publickey)"
- Configura SSH keys en GitHub (ver Opción B arriba)
- O usa HTTPS con Personal Access Token

### Error: "Repository not found"
- Verifica que el repositorio sea público o tengas acceso
- Verifica la URL del repositorio
- Si es privado, asegúrate de estar autenticado

### Error: "git: command not found"
- Instala Git primero (ver Paso 2)

### Error: "Python not found"
- Instala Python 3.10+ (ver guías de instalación)

### Error: "Redis connection refused"
- Inicia Redis: `redis-server` o `sudo systemctl start redis-server`

---

## Próximos Pasos Después de Clonar

1. ✅ Clonar repositorio
2. ✅ Instalar dependencias
3. ✅ Configurar `.env`
4. ✅ Iniciar Redis
5. ✅ Ejecutar listener y parser
6. ✅ Verificar que todo funciona

---

## Notas Importantes

- **No compartas tu archivo `.env`** - Contiene credenciales sensibles
- **El archivo `.env` está en `.gitignore`** - No se subirá al repositorio
- **Cada VPS necesita su propio `.env`** con sus credenciales
- **La base de datos `pasarela.db`** se creará automáticamente al ejecutar el parser












