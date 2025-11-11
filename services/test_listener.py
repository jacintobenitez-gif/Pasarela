#!/usr/bin/env python3
import sys
import os

print("=== TEST LISTENER ===")
print(f"Python version: {sys.version}")
print(f"Current directory: {os.getcwd()}")
print(f"PYTHONPATH: {os.environ.get('PYTHONPATH', 'No definido')}")

try:
    print("Intentando importar dotenv...")
    from dotenv import load_dotenv, find_dotenv
    print("✅ dotenv importado correctamente")
except ImportError as e:
    print(f"❌ Error importando dotenv: {e}")
    sys.exit(1)

try:
    print("Intentando importar telethon...")
    from telethon import TelegramClient
    print("✅ telethon importado correctamente")
except ImportError as e:
    print(f"❌ Error importando telethon: {e}")
    sys.exit(1)

try:
    print("Intentando importar redis...")
    from redis.asyncio import Redis
    print("✅ redis importado correctamente")
except ImportError as e:
    print(f"❌ Error importando redis: {e}")
    sys.exit(1)

print("✅ Todos los módulos importados correctamente")
print("=== FIN TEST ===")





