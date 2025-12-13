# Lista de Software para Instalación en VPS

## Requisitos del Sistema

### 1. Sistema Operativo
- **Ubuntu 20.04 LTS** o superior (recomendado)
- O **Debian 11+** / **CentOS 8+** / **RHEL 8+**

### 2. Python
- **Python 3.10** o superior (requerido por el código)
- Incluye `pip` (gestor de paquetes Python)

### 3. Redis (Servicio)
- **Redis Server 6.0+** (requerido para streams y mensajería)
- Debe estar corriendo como servicio

### 4. Git
- **Git** (para clonar el repositorio)

### 5. Librerías Python (instalar con pip)
- **redis** (cliente Python para Redis, versión 4.5+)
- **telethon** (cliente Telegram)
- **python-dotenv** (manejo de variables de entorno)

### 6. Herramientas Adicionales (Opcionales pero recomendadas)
- **screen** o **tmux** (para ejecutar procesos en background)
- **systemd** (ya viene en Ubuntu/Debian modernos) o **supervisor** (para gestionar servicios)
- **nano** o **vim** (editor de texto)

---

## Comandos de Instalación (Ubuntu/Debian)

### Actualizar sistema
```bash
sudo apt update
sudo apt upgrade -y
```

### Instalar Python 3.10+
```bash
sudo apt install python3 python3-pip python3-venv -y
python3 --version  # Verificar que sea 3.10+
```

### Instalar Redis
```bash
sudo apt install redis-server -y
sudo systemctl enable redis-server
sudo systemctl start redis-server
sudo systemctl status redis-server  # Verificar que esté corriendo
```

### Instalar Git
```bash
sudo apt install git -y
```

### Instalar herramientas adicionales
```bash
sudo apt install screen nano curl -y
```

### Instalar librerías Python (después de clonar el proyecto)
```bash
# Opción 1: Instalación global (no recomendado)
pip3 install redis telethon python-dotenv

# Opción 2: Usando entorno virtual (RECOMENDADO)
cd /ruta/al/proyecto
python3 -m venv venv
source venv/bin/activate
pip install redis telethon python-dotenv
```

---

## Comandos de Instalación (CentOS/RHEL)

### Actualizar sistema
```bash
sudo yum update -y
```

### Instalar Python 3.10+
```bash
sudo yum install python3 python3-pip -y
# O si no está disponible:
sudo yum install epel-release -y
sudo yum install python39 python39-pip -y
python3 --version
```

### Instalar Redis
```bash
sudo yum install redis -y
sudo systemctl enable redis
sudo systemctl start redis
sudo systemctl status redis
```

### Instalar Git
```bash
sudo yum install git -y
```

---

## Verificación Post-Instalación

### Verificar Python
```bash
python3 --version
# Debe mostrar: Python 3.10.x o superior
```

### Verificar Redis
```bash
redis-cli ping
# Debe responder: PONG
```

### Verificar Git
```bash
git --version
```

### Verificar librerías Python
```bash
python3 -c "import redis; print('Redis OK')"
python3 -c "import telethon; print('Telethon OK')"
python3 -c "import dotenv; print('Dotenv OK')"
```

---

## Configuración Adicional Necesaria

### 1. Variables de Entorno (.env)
Crear archivo `.env` en la raíz del proyecto con:
- `TELEGRAM_API_ID`
- `TELEGRAM_API_HASH`
- `TELEGRAM_PHONE`
- `REDIS_URL`
- `PASARELA_DB`
- Y otras variables según necesidad

### 2. Configuración de Redis
- Verificar que Redis esté escuchando en `127.0.0.1:6379` (por defecto)
- Si necesitas acceso remoto, configurar `bind` en `/etc/redis/redis.conf`

### 3. Permisos de Directorios
```bash
# Crear directorios necesarios
mkdir -p /ruta/al/proyecto/data
mkdir -p /ruta/al/proyecto/services/src/listener
mkdir -p /ruta/al/proyecto/services/src/parser
chmod 755 /ruta/al/proyecto/data
```

---

## Resumen Rápido (Copy-Paste para Ubuntu/Debian)

```bash
# 1. Actualizar sistema
sudo apt update && sudo apt upgrade -y

# 2. Instalar Python y herramientas
sudo apt install python3 python3-pip python3-venv git redis-server screen nano -y

# 3. Iniciar Redis
sudo systemctl enable redis-server
sudo systemctl start redis-server

# 4. Verificar instalaciones
python3 --version
redis-cli ping
git --version

# 5. Clonar proyecto (ajustar URL)
git clone <URL_DEL_REPOSITORIO> /ruta/al/proyecto

# 6. Crear entorno virtual e instalar dependencias
cd /ruta/al/proyecto
python3 -m venv venv
source venv/bin/activate
pip install redis telethon python-dotenv

# 7. Configurar .env (crear archivo con tus credenciales)
nano .env
```

---

## Notas Importantes

1. **Python 3.10+ es obligatorio** - El código usa características de Python 3.10+
2. **Redis debe estar corriendo** - Es crítico para el funcionamiento del sistema
3. **Variables de entorno** - El proyecto requiere archivo `.env` con credenciales de Telegram
4. **Entorno virtual recomendado** - Evita conflictos con otras aplicaciones Python
5. **Permisos** - Asegúrate de tener permisos de escritura en directorios de datos y logs

