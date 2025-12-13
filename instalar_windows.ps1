# Script de Instalación Automática para Windows
# Ejecutar como Administrador: Right-click > "Ejecutar con PowerShell como administrador"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  INSTALADOR AUTOMATICO - PASARELA" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Verificar si se ejecuta como administrador
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "ERROR: Este script debe ejecutarse como Administrador" -ForegroundColor Red
    Write-Host "Right-click en el archivo y selecciona 'Ejecutar con PowerShell como administrador'" -ForegroundColor Yellow
    pause
    exit 1
}

# Función para verificar si un comando existe
function Test-Command {
    param($command)
    $null = Get-Command $command -ErrorAction SilentlyContinue
    return $?
}

# Función para descargar e instalar Chocolatey si no está instalado
function Install-Chocolatey {
    if (Test-Command choco) {
        Write-Host "[OK] Chocolatey ya está instalado" -ForegroundColor Green
        return
    }
    
    Write-Host "[INSTALANDO] Chocolatey..." -ForegroundColor Yellow
    Set-ExecutionPolicy Bypass -Scope Process -Force
    [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072
    iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))
    
    # Refrescar variables de entorno
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
    
    if (Test-Command choco) {
        Write-Host "[OK] Chocolatey instalado correctamente" -ForegroundColor Green
    } else {
        Write-Host "[ERROR] No se pudo instalar Chocolatey. Instálalo manualmente desde: https://chocolatey.org/install" -ForegroundColor Red
        exit 1
    }
}

# Función para instalar Python
function Install-Python {
    if (Test-Command python) {
        $version = python --version 2>&1
        Write-Host "[OK] Python ya está instalado: $version" -ForegroundColor Green
        
        # Verificar versión mínima (3.10)
        $pythonVersion = python --version 2>&1 | Out-String
        if ($pythonVersion -match "Python (\d+)\.(\d+)") {
            $major = [int]$matches[1]
            $minor = [int]$matches[2]
            if ($major -lt 3 -or ($major -eq 3 -and $minor -lt 10)) {
                Write-Host "[ADVERTENCIA] Python 3.10+ es requerido. Versión actual: $version" -ForegroundColor Yellow
                Write-Host "[INSTALANDO] Python 3.11..." -ForegroundColor Yellow
                choco install python311 -y
            }
        }
        return
    }
    
    Write-Host "[INSTALANDO] Python 3.11..." -ForegroundColor Yellow
    choco install python311 -y
    
    # Refrescar variables de entorno
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
    
    if (Test-Command python) {
        Write-Host "[OK] Python instalado correctamente" -ForegroundColor Green
    } else {
        Write-Host "[ERROR] No se pudo instalar Python" -ForegroundColor Red
        exit 1
    }
}

# Función para instalar Git
function Install-Git {
    if (Test-Command git) {
        $version = git --version
        Write-Host "[OK] Git ya está instalado: $version" -ForegroundColor Green
        return
    }
    
    Write-Host "[INSTALANDO] Git..." -ForegroundColor Yellow
    choco install git -y
    
    # Refrescar variables de entorno
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
    
    if (Test-Command git) {
        Write-Host "[OK] Git instalado correctamente" -ForegroundColor Green
    } else {
        Write-Host "[ERROR] No se pudo instalar Git" -ForegroundColor Red
        exit 1
    }
}

# Función para instalar Redis
function Install-Redis {
    $redisService = Get-Service -Name "Redis" -ErrorAction SilentlyContinue
    if ($redisService) {
        Write-Host "[OK] Redis ya está instalado como servicio" -ForegroundColor Green
        if ($redisService.Status -ne "Running") {
            Write-Host "[INICIANDO] Servicio Redis..." -ForegroundColor Yellow
            Start-Service Redis
        }
        return
    }
    
    Write-Host "[INSTALANDO] Redis..." -ForegroundColor Yellow
    choco install redis-64 -y
    
    # Intentar iniciar el servicio
    Start-Sleep -Seconds 3
    $redisService = Get-Service -Name "Redis" -ErrorAction SilentlyContinue
    if ($redisService) {
        if ($redisService.Status -ne "Running") {
            Start-Service Redis
        }
        Write-Host "[OK] Redis instalado y corriendo" -ForegroundColor Green
    } else {
        Write-Host "[ADVERTENCIA] Redis instalado pero el servicio no se detectó automáticamente" -ForegroundColor Yellow
        Write-Host "  Puede que necesites iniciarlo manualmente o reiniciar el sistema" -ForegroundColor Yellow
    }
}

# Función para instalar librerías Python
function Install-PythonPackages {
    Write-Host "[INSTALANDO] Librerías Python..." -ForegroundColor Yellow
    
    # Verificar pip
    if (-not (Test-Command pip)) {
        Write-Host "[ERROR] pip no está disponible. Reinstala Python." -ForegroundColor Red
        return
    }
    
    # Actualizar pip
    Write-Host "  Actualizando pip..." -ForegroundColor Cyan
    python -m pip install --upgrade pip --quiet
    
    # Instalar librerías
    $packages = @("redis", "telethon", "python-dotenv")
    
    foreach ($package in $packages) {
        Write-Host "  Instalando $package..." -ForegroundColor Cyan
        python -m pip install $package --quiet
        if ($LASTEXITCODE -eq 0) {
            Write-Host "    [OK] $package instalado" -ForegroundColor Green
        } else {
            Write-Host "    [ERROR] No se pudo instalar $package" -ForegroundColor Red
        }
    }
}

# Función para verificar instalaciones
function Test-Installations {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "  VERIFICACION DE INSTALACIONES" -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host ""
    
    $allOK = $true
    
    # Verificar Python
    if (Test-Command python) {
        $version = python --version 2>&1
        Write-Host "[OK] Python: $version" -ForegroundColor Green
    } else {
        Write-Host "[ERROR] Python no encontrado" -ForegroundColor Red
        $allOK = $false
    }
    
    # Verificar pip
    if (Test-Command pip) {
        $version = pip --version
        Write-Host "[OK] pip: $version" -ForegroundColor Green
    } else {
        Write-Host "[ERROR] pip no encontrado" -ForegroundColor Red
        $allOK = $false
    }
    
    # Verificar Git
    if (Test-Command git) {
        $version = git --version
        Write-Host "[OK] Git: $version" -ForegroundColor Green
    } else {
        Write-Host "[ERROR] Git no encontrado" -ForegroundColor Red
        $allOK = $false
    }
    
    # Verificar Redis
    $redisService = Get-Service -Name "Redis" -ErrorAction SilentlyContinue
    if ($redisService) {
        Write-Host "[OK] Redis: Servicio instalado (Estado: $($redisService.Status))" -ForegroundColor Green
    } else {
        Write-Host "[ADVERTENCIA] Redis: Servicio no detectado (puede requerir reinicio)" -ForegroundColor Yellow
    }
    
    # Verificar librerías Python
    Write-Host ""
    Write-Host "Verificando librerías Python..." -ForegroundColor Cyan
    
    $packages = @("redis", "telethon", "dotenv")
    foreach ($package in $packages) {
        $result = python -c "import $package; print('OK')" 2>&1
        if ($result -eq "OK") {
            Write-Host "  [OK] $package" -ForegroundColor Green
        } else {
            Write-Host "  [ERROR] $package no instalado correctamente" -ForegroundColor Red
            $allOK = $false
        }
    }
    
    return $allOK
}

# Función para crear archivo .env de ejemplo
function Create-ExampleEnv {
    $envFile = ".env.example"
    if (Test-Path $envFile) {
        Write-Host "[INFO] Archivo .env.example ya existe" -ForegroundColor Cyan
        return
    }
    
    Write-Host "[CREANDO] Archivo .env.example..." -ForegroundColor Yellow
    $envContent = @"
# Configuración Telegram
TELEGRAM_API_ID=tu_api_id_aqui
TELEGRAM_API_HASH=tu_api_hash_aqui
TELEGRAM_PHONE=+34607190588
TELEGRAM_SESSION=telethon_session

# Configuración Redis
REDIS_URL=redis://localhost:6379/0
REDIS_STREAM=pasarela:parse
REDIS_GROUP=parser
REDIS_CONSUMER=local

# Configuración Base de Datos
PASARELA_DB=pasarela.db
PASARELA_TABLE=Trazas_Unica

# Configuración CSV
CSV_ENABLED=1
MT4_QUEUE_FILENAME=colaMT4.csv

# Configuración Socket
SOCKET_ENABLED=true
ACTIVAR_SOCKET=false
SOCKET_MODE=socket
SOCKET_HOST=127.0.0.1
SOCKET_PORT=8888

# Configuración Telegram Alertas
TELEGRAM_ALERT_ENABLED=1
TELEGRAM_DISCLAIMER_ENABLED=0
TELEGRAM_TARGETS=
"@
    
    Set-Content -Path $envFile -Value $envContent
    Write-Host "[OK] Archivo .env.example creado" -ForegroundColor Green
    Write-Host "  Copia este archivo a .env y completa tus credenciales" -ForegroundColor Yellow
}

# ========================================
# PROCESO PRINCIPAL DE INSTALACION
# ========================================

Write-Host "Iniciando instalación automática..." -ForegroundColor Cyan
Write-Host ""

# 1. Instalar Chocolatey
Write-Host "PASO 1/6: Chocolatey" -ForegroundColor Magenta
Install-Chocolatey
Write-Host ""

# 2. Instalar Python
Write-Host "PASO 2/6: Python" -ForegroundColor Magenta
Install-Python
Write-Host ""

# 3. Instalar Git
Write-Host "PASO 3/6: Git" -ForegroundColor Magenta
Install-Git
Write-Host ""

# 4. Instalar Redis
Write-Host "PASO 4/6: Redis" -ForegroundColor Magenta
Install-Redis
Write-Host ""

# 5. Instalar librerías Python
Write-Host "PASO 5/6: Librerías Python" -ForegroundColor Magenta
Install-PythonPackages
Write-Host ""

# 6. Verificar instalaciones
Write-Host "PASO 6/6: Verificación" -ForegroundColor Magenta
$allOK = Test-Installations

# Crear archivo .env de ejemplo
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  CONFIGURACION ADICIONAL" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Create-ExampleEnv

# Resumen final
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  INSTALACION COMPLETADA" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

if ($allOK) {
    Write-Host "[OK] Todas las instalaciones se completaron correctamente" -ForegroundColor Green
} else {
    Write-Host "[ADVERTENCIA] Algunas verificaciones fallaron. Revisa los mensajes anteriores." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "PRÓXIMOS PASOS:" -ForegroundColor Yellow
Write-Host "1. Copia .env.example a .env y completa tus credenciales de Telegram" -ForegroundColor White
Write-Host "2. Clona el repositorio (si aún no lo has hecho)" -ForegroundColor White
Write-Host "3. Ejecuta los scripts del proyecto" -ForegroundColor White
Write-Host ""
Write-Host "Para verificar Redis manualmente:" -ForegroundColor Cyan
Write-Host "  redis-cli ping" -ForegroundColor White
Write-Host ""

pause
