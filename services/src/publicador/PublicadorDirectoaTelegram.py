# publicador.py — v1.3 FINAL
# Publica mensajes en Telegram (canal/grupo/usuario) leyendo credenciales y destino de .env
# .env esperadas:
#   TELEGRAM_API_ID=...
#   TELEGRAM_API_HASH=...
#   TELEGRAM_PHONE=+34...
#   TELEGRAM_SESSION=telethon_session
#   TELEGRAM_TARGETS=@JBMSignals|https://t.me/JBMSignals|JBM Signals   (separar por '|')
#
# Uso:
#   python publicador.py -m "Hola mundo"
#   python publicador.py              # modo interactivo (/quit para salir)
#   python publicador.py -m "..." -t "@OtroCanal"   # override destino puntual

import os
import sys
import asyncio
import argparse
from getpass import getpass
from dotenv import load_dotenv, find_dotenv
from telethon import TelegramClient, errors

APP_NAME = "publicador_v1_3"

# ---------- Utilidades ----------
def load_env():
    """Carga .env desde cwd o árbol superior (no pisa variables ya exportadas)."""
    env_path = find_dotenv(usecwd=True)
    if env_path:
        load_dotenv(env_path, override=False)

def get_env_str(key: str, default: str = "") -> str:
    val = os.getenv(key)
    return val.strip() if isinstance(val, str) else default

def ensure_int(s: str, field: str) -> int:
    try:
        return int(s)
    except Exception:
        print(f"[ERROR] {field} debe ser numérico. Valor recibido: {s!r}")
        sys.exit(1)

# ---------- Credenciales ----------
def get_credentials():
    load_env()
    api_id   = get_env_str("TELEGRAM_API_ID")
    api_hash = get_env_str("TELEGRAM_API_HASH")
    phone    = get_env_str("TELEGRAM_PHONE")
    session  = get_env_str("TELEGRAM_SESSION", APP_NAME)

    if not api_id:
        api_id = input("TELEGRAM_API_ID (my.telegram.org): ").strip()
    if not api_hash:
        api_hash = getpass("TELEGRAM_API_HASH: ").strip()
    if not phone:
        phone = input("Teléfono con prefijo (p.ej. +34...): ").strip()

    api_id_int = ensure_int(api_id, "TELEGRAM_API_ID")
    return api_id_int, api_hash, phone, session

async def ensure_session(client: TelegramClient, phone: str):
    await client.connect()
    if not await client.is_user_authorized():
        print("[INFO] Autorizando sesión…")
        await client.send_code_request(phone)
        code = input("Código (SMS/Telegram): ").strip().replace(" ", "")
        try:
            await client.sign_in(phone=phone, code=code)
        except errors.SessionPasswordNeededError:
            pwd = getpass("Contraseña 2FA: ")
            await client.sign_in(password=pwd)

# ---------- Resolución de destino ----------
async def resolve_target(client: TelegramClient, override_target: str = ""):
    """
    Resuelve el destino probando:
    1) Link t.me (público o invitación)
    2) @username (con/sin @)
    3) Título EXACTO de un diálogo donde seas miembro
    """
    load_env()
    raw = override_target.strip() if override_target else get_env_str("TELEGRAM_TARGETS")
    if not raw:
        raise SystemExit(
            "[ERROR] No se ha definido el destino. Pon TELEGRAM_TARGETS en .env "
            "o usa -t/--target para forzar uno.\n"
            "Ejemplo: TELEGRAM_TARGETS=@JBMSignals|https://t.me/JBMSignals|JBM Signals"
        )
    candidates = [c.strip() for c in raw.split("|") if c.strip()]

    # 1) Links t.me
    for c in candidates:
        if c.startswith(("http://", "https://")) or "t.me/" in c:
            try:
                return await client.get_entity(c)
            except Exception:
                pass

    # 2) @username
    for c in candidates:
        u = c.lstrip("@")
        if not u or any(ch.isspace() for ch in u):
            continue
        try:
            return await client.get_entity(u)
        except Exception:
            pass

    # 3) Título exacto
    titles_seen = []
    async for d in client.iter_dialogs():
        titles_seen.append(d.name)
        if d.name in candidates:
            return d.entity

    # Nada funcionó
    raise SystemExit(
        "[ERROR] No se pudo resolver el destino.\n"
        f"- Probé: {candidates}\n"
        "- Causas típicas: el canal aún no propagó el @, el título no coincide exacto, "
        "o no eres miembro/admin.\n"
        "Soluciones:\n"
        "  • Usa el enlace completo https://t.me/<username> en TELEGRAM_TARGETS.\n"
        "  • Añade exactamente el título del canal como candidato.\n"
        f"  • Títulos detectados en tus diálogos: {titles_seen}"
    )

# ---------- Envío ----------
async def send_once(message: str, target_override: str = ""):
    api_id, api_hash, phone, session = get_credentials()
    client = TelegramClient(session, api_id, api_hash)
    try:
        await ensure_session(client, phone)
        entity = await resolve_target(client, target_override)
        await client.send_message(entity=entity, message=message)
        print("[OK] Mensaje enviado.")
    except errors.ChatWriteForbiddenError:
        print("[ERROR] No tienes permiso para escribir en el destino (¿owner/admin con publicar?)."); sys.exit(1)
    except errors.FloodWaitError as fw:
        print(f"[ERROR] FloodWait: espera {fw.seconds} s antes de reenviar."); sys.exit(1)
    except Exception as e:
        print(f"[ERROR] {e}"); sys.exit(1)
    finally:
        await client.disconnect()

async def interactive(target_override: str = ""):
    print("[INTERACTIVO] Escribe y Enter para enviar. /quit para salir.")
    while True:
        msg = input("> ").strip()
        if msg.lower() in ("/quit", "/exit"):
            print("Saliendo…")
            return
        if msg:
            await send_once(msg, target_override)

# ---------- CLI ----------
def parse_args():
    ap = argparse.ArgumentParser(description="Publicador de mensajes a Telegram (canal/grupo/usuario).")
    ap.add_argument("-m", "--message", help="Mensaje a enviar (modo una sola vez).")
    ap.add_argument("-t", "--target",  help="Destino puntual (sobrescribe TELEGRAM_TARGETS para esta ejecución).")
    return ap.parse_args()

def main():
    args = parse_args()
    if args.message:
        asyncio.run(send_once(args.message, args.target or ""))
    else:
        asyncio.run(interactive(args.target or ""))

if __name__ == "__main__":
    main()
