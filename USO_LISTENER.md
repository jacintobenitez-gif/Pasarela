# Uso del Listener de Pasarela

## Comandos disponibles:

### 1. Solo canales fijados (por defecto)
```bash
python .\src\listener\listener.py
```
o
```bash
python .\src\listener\listener.py -pinned
```

### 2. Todos los canales
```bash
python .\src\listener\listener.py -all
```

### 3. Canales específicos
```bash
python .\src\listener\listener.py -specific 1727126726,3070669722,1839677922
```

## Scripts batch disponibles:

- `ejecutar_listener.bat` - Modo pinned (por defecto)
- `ejecutar_listener_all.bat` - Todos los canales
- `ejecutar_listener_specific.bat` - Canales específicos

## Ejemplos de uso:

```bash
# Ver ayuda
python .\src\listener\listener.py -h

# Solo canales fijados
python .\src\listener\listener.py -pinned

# Todos los canales
python .\src\listener\listener.py -all

# Canales específicos
python .\src\listener\listener.py -specific 1727126726,3070669722
```

## Notas:

- **Modo por defecto**: Solo canales fijados (pinned)
- **Modo -all**: Puede generar mucho tráfico
- **Modo -specific**: Necesitas conocer los IDs de los canales




