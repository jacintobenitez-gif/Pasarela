#!/usr/bin/env python3
# simple_broadcast.py — servidor TCP muy simple (broadcast por líneas)

import socket, threading

HOST = "127.0.0.1"
PORT = 8888

clients = []
lock = threading.Lock()

def broadcast(text, sender=None):
    if not text.endswith("\n"):
        text += "\n"
    data = text.encode("utf-8", "replace")
    dead = []
    with lock:
        for c in clients:
            if c is sender:
                continue
            try:
                c.sendall(data)
            except OSError:
                dead.append(c)
        for d in dead:
            try: clients.remove(d)
            except ValueError: pass
            try: d.close()
            except OSError: pass

def handle_client(conn, addr):
    print(f"[+] Conectado {addr}")
    buf = b""
    try:
        while True:
            data = conn.recv(4096)
            if not data:
                break
            buf += data
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                msg = line.decode("utf-8", "ignore")
                print(f"[{addr}] {msg}")
                broadcast(msg, sender=conn)
    except OSError:
        pass
    finally:
        with lock:
            try: clients.remove(conn)
            except ValueError: pass
        try: conn.close()
        except OSError: pass
        print(f"[-] Desconectado {addr}")

def accept_loop():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((HOST, PORT))
        s.listen(16)
        print(f"[SERVIDOR] Escuchando en {HOST}:{PORT}")
        while True:
            conn, addr = s.accept()
            with lock:
                clients.append(conn)
            t = threading.Thread(target=handle_client, args=(conn, addr), daemon=True)
            t.start()

def stdin_loop():
    # Permite escribir en consola y difundir a todos
    try:
        while True:
            line = input()
            if line.strip():
                broadcast(line, sender=None)
    except (EOFError, KeyboardInterrupt):
        pass

if __name__ == "__main__":
    threading.Thread(target=accept_loop, daemon=True).start()
    stdin_loop()


