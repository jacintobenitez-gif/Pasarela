#!/usr/bin/env python3
# traza_viewer.py — visor web básico de la tabla Trazas_Unica (SQLite)
# - Enlaces: /hoy, /ayer, /todo
# - HOY/AYER filtran por ts_utc (UTC). TODO muestra todo.
# - F5 recarga y vuelve a consultar.

import os, sqlite3, html
from datetime import datetime, timedelta, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler

DB_PATH = os.getenv("PASARELA_DB", r"C:\Pasarela\services\pasarela.db")
TABLE   = os.getenv("PASARELA_TABLE", "Trazas_Unica")
HOST, PORT = "127.0.0.1", 8080

# Columnas a mostrar (si alguna no existe en tu tabla, aparecerá vacía)
COLUMNS = [
    "oid","ts_utc","ts_redis_ingest","ch_id","msg_id","channel","channel_username",
    "sender_id","text","score","estado_operacion","ts_mt4_queue",
    "symbol","order_type","entry_price","sl","tp","comment"
]

HTML_HEAD = """<!doctype html><html lang="es"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Traza Única — Visor</title>
<style>
  body{font-family:system-ui,-apple-system,Segoe UI,Roboto,Arial,sans-serif;margin:20px;color:#222}
  h1{margin:0 0 10px}
  .meta{color:#555;margin:0 0 14px}
  .nav{margin:0 0 14px;display:flex;gap:8px;flex-wrap:wrap}
  .nav a{display:inline-block;padding:6px 10px;border:1px solid #ddd;border-radius:8px;text-decoration:none;color:#222}
  .nav a.active{background:#111;color:#fff;border-color:#111}
  table{border-collapse:collapse;width:100%}
  th,td{border:1px solid #ddd;padding:6px 8px;vertical-align:top}
  th{position:sticky;top:0;background:#f7f7f7}
  tr:nth-child(even){background:#fafafa}
  code{background:#f2f2f2;padding:1px 4px;border-radius:3px}
  .nowrap{white-space:nowrap}
  .mono{font-family:ui-monospace,Consolas,Monaco,monospace}
  .text{max-width:520px;white-space:pre-wrap}
</style>
</head><body>
"""

HTML_FOOT = """</body></html>"""

def day_bounds_utc(which: str):
    """
    Devuelve (start_isoZ, end_isoZ) para 'hoy' o 'ayer' en UTC, con formato 'YYYY-MM-DDTHH:MM:SSZ'.
    """
    now = datetime.now(timezone.utc)
    if which == "hoy":
        start = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
        end   = start + timedelta(days=1)
    elif which == "ayer":
        end   = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
        start = end - timedelta(days=1)
    else:
        return None, None
    fmt = "%Y-%m-%dT%H:%M:%SZ"
    return start.strftime(fmt), end.strftime(fmt)

def fetch_rows(range_key: str):
    if not os.path.exists(DB_PATH):
        raise FileNotFoundError(f"No existe la BBDD: {DB_PATH}")
    con = sqlite3.connect(DB_PATH, timeout=5.0)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    cols_csv = ", ".join(COLUMNS)

    if range_key in ("hoy", "ayer"):
        start_iso, end_iso = day_bounds_utc(range_key)
        sql = f"""
          SELECT {cols_csv}
          FROM {TABLE}
          WHERE ts_utc >= ? AND ts_utc < ?
          ORDER BY ts_utc DESC, rowid DESC
        """
        rows = cur.execute(sql, (start_iso, end_iso)).fetchall()
    else:  # 'todo'
        sql = f"""
          SELECT {cols_csv}
          FROM {TABLE}
          ORDER BY ts_utc DESC, rowid DESC
        """
        rows = cur.execute(sql).fetchall()

    con.close()
    return rows

def render_table(rows, range_key: str):
    html_parts = [HTML_HEAD]
    title = {"hoy":"HOY (UTC)","ayer":"AYER (UTC)","todo":"TODO"}[range_key]
    html_parts.append(f"<h1>Traza Única — {title}</h1>")
    html_parts.append(f"<p class='meta'>DB: <code>{html.escape(DB_PATH)}</code> — Tabla: <code>{html.escape(TABLE)}</code> — Filas: {len(rows)}</p>")

    # Navegación
    html_parts.append("<div class='nav'>")
    for key,label in (("hoy","HOY"),("ayer","AYER"),("todo","TODO")):
        cls = "active" if key == range_key else ""
        href = f"/{key}"
        html_parts.append(f"<a class='{cls}' href='{href}'>{label}</a>")
    html_parts.append("</div>")

    # Tabla
    html_parts.append("<table><thead><tr>")
    for c in COLUMNS:
        html_parts.append(f"<th class='nowrap'>{html.escape(c)}</th>")
    html_parts.append("</tr></thead><tbody>")
    for r in rows:
        html_parts.append("<tr>")
        for c in COLUMNS:
            v = r[c] if c in r.keys() else None
            if v is None:
                cell = ""
            else:
                s = str(v)
                cls = "text" if c == "text" else ("mono nowrap" if c in ("oid","ts_utc","ts_redis_ingest","ts_mt4_queue") else "")
                cell = f"<span class='{cls}'>{html.escape(s)}</span>"
            html_parts.append(f"<td>{cell}</td>")
        html_parts.append("</tr>")
    html_parts.append("</tbody></table>")
    html_parts.append(HTML_FOOT)
    return "".join(html_parts).encode("utf-8")

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # Rutas soportadas
        if self.path in ("/", "/index.html", "/hoy"):
            key = "hoy"
        elif self.path.startswith("/ayer"):
            key = "ayer"
        elif self.path.startswith("/todo"):
            key = "todo"
        else:
            self.send_error(404, "Not found")
            return
        try:
            rows = fetch_rows(key)
            body = render_table(rows, key)
            self.send_response(200)
            self.send_header("Content-Type","text/html; charset=utf-8")
            self.send_header("Cache-Control","no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except Exception as e:
            msg = f"<pre>{html.escape(repr(e))}</pre>".encode("utf-8")
            self.send_response(500)
            self.send_header("Content-Type","text/html; charset=utf-8")
            self.send_header("Cache-Control","no-store")
            self.send_header("Content-Length", str(len(msg)))
            self.end_headers()
            self.wfile.write(msg)

def main():
    print(f"DB: {DB_PATH} | Tabla: {TABLE} | http://{HOST}:{PORT}  (rutas: /hoy /ayer /todo)")
    HTTPServer((HOST, PORT), Handler).serve_forever()

if __name__ == "__main__":
    main()

