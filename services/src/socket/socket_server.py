#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# socket_server.py — Servidor TCP que recibe mensajes por consola y los envía a MetaTrader
# Uso: python socket_server.py [mensaje]
#   - Si se pasa mensaje como argumento, lo envía y termina
#   - Si no hay argumentos, entra en modo interactivo (Ctrl+C para salir)

import socket
import sys
import time
from threading import Thread

# Configuración
HOST = "127.0.0.1"  # localhost
PORT = 8888         # Puerto para MT4

def send_message_to_mt4_file(message: str, filename: str = "socket_msg.txt") -> bool:
    """
    Envía un mensaje a MetaTrader vía archivo compartido (compatible con MQL4).
    Retorna True si se escribió correctamente, False en caso contrario.
    """
    if not message or not message.strip():
        print("[ERROR] Mensaje vacío")
        return False
    
    try:
        import os
        # Ruta común para MT4 (directorio compartido)
        # MT4 puede leer desde Terminal/Common/Files o desde un directorio específico
        common_files = os.path.join(os.getenv("APPDATA", ""), "MetaQuotes", "Terminal", "Common", "Files")
        os.makedirs(common_files, exist_ok=True)
        
        filepath = os.path.join(common_files, filename)
        
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(message.strip())
        
        print(f"[OK] Mensaje escrito en archivo: {filepath}")
        print(f"     Mensaje: {message}")
        return True
        
    except Exception as e:
        print(f"[ERROR] Fallo al escribir archivo: {e}")
        return False

def send_message_to_mt4(message: str, host: str = HOST, port: int = PORT, timeout: float = 2.0) -> bool:
    """
    Envía un mensaje a MetaTrader vía socket TCP (solo MQL5).
    Retorna True si se envió correctamente, False en caso contrario.
    """
    if not message or not message.strip():
        print("[ERROR] Mensaje vacío")
        return False
    
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((host, port))
        
        # Enviar mensaje con terminador de línea
        message_bytes = (message.strip() + "\n").encode("utf-8")
        sock.sendall(message_bytes)
        
        sock.close()
        print(f"[OK] Mensaje enviado a MT4 ({host}:{port}): {message}")
        return True
        
    except socket.timeout:
        print(f"[ERROR] Timeout: MT4 no está conectado en {host}:{port}")
        return False
    except ConnectionRefusedError:
        print(f"[ERROR] Conexión rechazada: ¿Está el EA ejecutándose en MT4?")
        return False
    except Exception as e:
        print(f"[ERROR] Fallo al enviar: {e}")
        return False

def server_mode():
    """
    Modo servidor: mantiene el socket abierto y espera conexiones de MT4.
    Útil si el EA se conecta periódicamente.
    """
    print(f"[SERVER] Iniciando servidor en {HOST}:{PORT}")
    print("[SERVER] Escribe mensajes y presiona Enter. Ctrl+C para salir.\n")
    
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    try:
        server_sock.bind((HOST, PORT))
        server_sock.listen(1)
        server_sock.settimeout(1.0)  # timeout para poder interrumpir con Ctrl+C
        
        connected_clients = []
        
        def accept_connections():
            while True:
                try:
                    client, addr = server_sock.accept()
                    print(f"[SERVER] Cliente conectado: {addr}")
                    connected_clients.append(client)
                except socket.timeout:
                    continue
                except Exception:
                    break
        
        accept_thread = Thread(target=accept_connections, daemon=True)
        accept_thread.start()
        
        while True:
            try:
                msg = input("> ")
                if not msg.strip():
                    continue
                
                # Enviar a todos los clientes conectados
                disconnected = []
                for client in connected_clients:
                    try:
                        client.sendall((msg.strip() + "\n").encode("utf-8"))
                        print(f"[OK] Enviado a {client.getpeername()}")
                    except Exception:
                        disconnected.append(client)
                
                # Limpiar clientes desconectados
                for client in disconnected:
                    connected_clients.remove(client)
                    client.close()
                    
            except KeyboardInterrupt:
                print("\n[SERVER] Cerrando servidor...")
                break
            except EOFError:
                break
        
    except Exception as e:
        print(f"[ERROR] Servidor: {e}")
    finally:
        for client in connected_clients:
            try:
                client.close()
            except:
                pass
        server_sock.close()

def main():
    # Usar modo archivo por defecto (compatible con MQL4)
    USE_FILE_MODE = True
    SOCKET_FILE = "socket_msg.txt"
    
    if len(sys.argv) > 1:
        # Modo directo: enviar mensaje pasado como argumento
        message = " ".join(sys.argv[1:])
        if USE_FILE_MODE:
            send_message_to_mt4_file(message, SOCKET_FILE)
        else:
            send_message_to_mt4(message)
    else:
        # Modo interactivo: enviar mensajes uno por uno
        mode_str = "archivo compartido" if USE_FILE_MODE else "socket TCP"
        print(f"Modo interactivo ({mode_str}). Escribe mensajes y presiona Enter.")
        print("Ctrl+C o línea vacía para salir.\n")
        try:
            while True:
                msg = input("Mensaje para MT4: ")
                if not msg.strip():
                    break
                if USE_FILE_MODE:
                    send_message_to_mt4_file(msg, SOCKET_FILE)
                else:
                    send_message_to_mt4(msg)
        except KeyboardInterrupt:
            print("\nSaliendo...")

if __name__ == "__main__":
    main()

