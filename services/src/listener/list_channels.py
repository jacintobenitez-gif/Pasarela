# -*- coding: utf-8 -*-
# Script auxiliar para listar todos los canales disponibles y obtener sus IDs
# Uso: python list_channels.py

import os, json, asyncio
from pathlib import Path
from dotenv import load_dotenv, find_dotenv
from telethon import TelegramClient
from telethon.tl.types import Channel

# ========= Carga de .env =========
ENV_PATH = find_dotenv(usecwd=True) or str(Path(__file__).resolve().parents[1].parent / ".env")
load_dotenv(ENV_PATH, override=True)

def _must(varname: str) -> str:
    v = os.getenv(varname, "").strip()
    if not v:
        raise SystemExit(f"[ERROR] Falta {varname} en {ENV_PATH}")
    return v

api_id       = int(_must("TELEGRAM_API_ID"))
api_hash     = _must("TELEGRAM_API_HASH")
phone        = os.getenv("TELEGRAM_PHONE", "+34607190588")
session_name = os.getenv("TELEGRAM_SESSION", "telethon_session")

client = TelegramClient(session_name, api_id, api_hash)

async def list_all_channels():
    """Lista todos los canales disponibles con sus IDs para configuración."""
    channels = []
    
    print("\n=== LISTANDO CANALES DISPONIBLES ===\n")
    
    async for d in client.iter_dialogs():
        ent = d.entity
        if isinstance(ent, Channel) and not getattr(ent, "left", False):
            # Solo canales públicos o megagrupos
            if not (ent.broadcast or ent.megagroup):
                continue
                
            cid = int(ent.id)
            title = getattr(ent, "title", "") or ""
            username = getattr(ent, "username", "") or ""
            linked_id = getattr(ent, "linked_chat_id", None)
            
            channel_info = {
                "id": cid,
                "title": title,
                "username": username,
                "enabled": True,
                "include_linked": bool(linked_id)
            }
            
            channels.append(channel_info)
            
            # Mostrar información
            tipo = "CANAL" if ent.broadcast else "MEGAGRUPO"
            link_info = f" (linked: {linked_id})" if linked_id else ""
            print(f"[{tipo}] ID: {cid:12d} | @{username or 'N/A':20s} | {title}{link_info}")
    
    print(f"\n=== TOTAL: {len(channels)} canales encontrados ===\n")
    
    # Generar ejemplo de configuración JSON
    config_example = {
        "channels": channels,
        "metadata": {
            "last_updated": "2025-01-XX",
            "version": "1.0",
            "note": "IDs generados automáticamente. Edita 'enabled' para activar/desactivar canales."
        }
    }
    
    # Guardar en archivo de ejemplo
    config_path = Path(__file__).resolve().parents[1].parent / "config" / "channels.json"
    config_path.parent.mkdir(exist_ok=True)
    
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config_example, f, indent=2, ensure_ascii=False)
    
    print(f"✓ Configuración guardada en: {config_path}")
    print(f"\nPara usar solo algunos canales, edita el archivo y marca 'enabled': false en los que no quieras escuchar.\n")
    
    return channels

async def main():
    await client.start(phone=phone)
    await list_all_channels()
    await client.disconnect()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nOperación cancelada.")
    except Exception as e:
        print(f"\n[ERROR] {e}")



