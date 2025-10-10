# -*- coding: utf-8 -*-
"""
parseador_ia_local.py (v1.1 — coste cero, sin OpenAI)
- Lee eventos desde Redis Stream 'pasarela:parse' (consumer group)
- Clasifica y extrae campos según reglas (SL/TP/Activo/Dirección/Entrada)
- Calcula score de confianza [0..10] y lista de motivos (pros/carencias)
- Publica JSON en 'pasarela:parsed'  (AHORA: solo si score == 10)
- Persiste en SQLite: C:\Pasarela\data\pasarela.db (tabla parsed_signals)
  *Migración automática*: añade columnas 'score' (INTEGER) y 'motivos' (TEXT) si no existen.

Cambios solicitados:
- Tracking visual: imprimir fecha, ch_id, msg_id, revision, clasificacion y score tras procesar
- Guardar/publicar SOLO si score == 10 (ACK siempre)
"""

import os, re, json, time, sqlite3
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple
from redis import Redis

# ---------- Entorno ----------
REDIS_URL   = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
IN_STREAM   = os.getenv("REDIS_STREAM_IN",  "pasarela:parse")
OUT_STREAM  = os.getenv("REDIS_STREAM_OUT", "pasarela:parsed")
DLQ_STREAM  = os.getenv("REDIS_STREAM_DLQ", "pasarela:dead")
GROUP       = os.getenv("REDIS_GROUP", "g1")
CONSUMER    = os.getenv("REDIS_CONSUMER", "local1")
BLOCK_MS    = int(os.getenv("BLOCK_MS", "5000"))
COUNT       = int(os.getenv("COUNT", "64"))

DB_PATH     = os.getenv("SQLITE_DB", r"C:\Pasarela\data\pasarela.db")

# ---------- Utilidades ----------
def log(msg: str):
    print(f"[parseador-local] {datetime.now(timezone.utc).isoformat()} {msg}")

def ensure_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.execute("""
    CREATE TABLE IF NOT EXISTS parsed_signals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_utc TEXT NOT NULL,
        channel_id INTEGER,
        channel_username TEXT,
        channel_title TEXT,
        msg_id INTEGER,
        revision INTEGER,
        ts_utc TEXT,
        text TEXT,
        clasificacion TEXT,                -- 'Válido' / 'Ruido'
        activo TEXT,
        direccion TEXT,                    -- 'BUY' / 'SELL' / 'INDETERMINADA'
        entrada_tipo TEXT,                 -- 'precio' / 'rango' / 'multiple' / 'no_encontrada'
        entrada_valores TEXT,              -- JSON array
        sl REAL,
        tp TEXT,                           -- JSON array
        consistencia_direccion INTEGER,    -- 0/1
        observaciones TEXT
    )
    """)
    con.commit()
    # --- Migración: añadir columnas score/motivos si faltan ---
    cols = {row[1] for row in con.execute("PRAGMA table_info(parsed_signals)").fetchall()}
    if "score" not in cols:
        con.execute("ALTER TABLE parsed_signals ADD COLUMN score INTEGER")
    if "motivos" not in cols:
        con.execute("ALTER TABLE parsed_signals ADD COLUMN motivos TEXT")
    con.commit()
    return con

# ---------- Normalización numérica ----------
def parse_number(numstr: str) -> Optional[float]:
    """
    Convierte '3,814.5', '3814,5', '4k', '1 985,5' -> float
    Heurística: usa como decimal el separador (',' o '.') que aparece más a la derecha.
    """
    s = (numstr or "").lower().strip().replace(" ", "")
    if not s: return None

    mult = 1.0
    if s.endswith("k"):
        mult = 1000.0
        s = s[:-1]

    last_comma = s.rfind(",")
    last_dot   = s.rfind(".")
    dec = "," if last_comma > last_dot else "."
    cleaned = "".join(ch for ch in s if ch.isdigit() or ch in "-"+dec)
    if dec != ".":
        cleaned = cleaned.replace(dec, ".")
    try:
        return float(cleaned) * mult
    except:
        return None

# ---------- Detección de rasgos ----------
SL_WORDS = r"(?:\bsl\b|\bs/?l\b|\bstop\s*loss\b|\bstoploss\b)"
TP_WORDS = r"(?:\btp\d*\b|\btp\b|\btargets?\b|\btake\s*profit\b|\bobjetivo?s?\b|\bmeta\b|\btake\b|\balvo\b)"

BUY_WORDS  = r"(?:\bbuy\b|\blong\b|\bbullish\b|\bcomprar?\b|\bbuy\s+limit\b|\bbuy\s+stop\b)"
SELL_WORDS = r"(?:\bsell\b|\bshort\b|\bbearish\b|\bvender?\b|\bsell\s+limit\b|\bsell\s+stop\b)"

ASSET_PATTERNS = [
    r"\b[A-Z]{3}/[A-Z]{3}\b", r"\b[A-Z]{6}\b",
    r"\b(?:US30|DJ30|DJI|DOW|WS30|US100|NAS100|USTECH100|NDX|NASDAQ|SPX|SP500|S&P|US500|ES)\b",
    r"\b(?:GER40|DAX40|DAX|UK100|FTSE100|FTSE|FRA40|CAC40|CAC|ES35|IBEX35|IBEX)\b",
    r"\b(?:JP225|JPN225|NIKKEI225|NIKKEI|HK50|HANG\s*SENG)\b",
    r"\b(?:XAUUSD|XAGUSD|XAU|XAG|GOLD|ORO|SILVER|PLATA|COPPER|HG|CU)\b",
    r"\b(?:USOIL|WTI|CL|CRUDE\s*OIL|CRUDE|OIL|BRENT|UKOIL|NG|NATURAL\s*GAS|GAS)\b",
    r"\b(?:BTCUSD|BTCUSDT|BTC|BITCOIN|ETHUSD|ETHUSDT|ETH|LTCUSD|XRPUSD|BNBUSD|ADAUSD|SOLUSD)\b",
    r"(?:#gold|#btc|#xau|#xag|🥇|₿)"
]
ASSET_REGEX = re.compile("|".join(ASSET_PATTERNS), re.IGNORECASE)

def find_asset(text: str) -> Optional[str]:
    m = ASSET_REGEX.search(text)
    if not m: return None
    return m.group(0).upper()

def has_sl(text: str) -> bool:
    return re.search(SL_WORDS, text, re.IGNORECASE) is not None

def has_tp(text: str) -> bool:
    return re.search(TP_WORDS, text, re.IGNORECASE) is not None

def extract_sl(text: str) -> Optional[float]:
    m = re.search(rf"{SL_WORDS}\D{{0,12}}([+\-]?\d[\d\.,\s]*k?)", text, re.IGNORECASE)
    if not m:
        m = re.search(rf"([+\-]?\d[\d\.,\s]*k?)\D{{0,6}}{SL_WORDS}", text, re.IGNORECASE)
    return parse_number(m.group(1)) if m else None

def extract_tps(text: str) -> List[float]:
    results: List[float] = []
    for m in re.finditer(rf"{TP_WORDS}\D{{0,10}}((?:[+\-]?\d[\d\.,\s]*k?)(?:\s*[,;/\-–—]\s*[+\-]?\d[\d\.,\s]*k?)*)", text, re.IGNORECASE):
        block = m.group(1)
        for num in re.findall(r"[+\-]?\d[\d\.,\s]*k?", block):
            v = parse_number(num)
            if v is not None:
                results.append(v)
    for m in re.finditer(r"(?:\btp\d*\b)\D{0,6}([+\-]?\d[\d\.,\s]*k?)", text, re.IGNORECASE):
        v = parse_number(m.group(1))
        if v is not None:
            results.append(v)
    seen = set(); tps = []
    for x in results:
        if x not in seen:
            seen.add(x); tps.append(x)
    return tps

RANGE_SEP = r"(?:-|–|—|to|a|hasta|→)"
def extract_entry(text: str) -> Tuple[str, List[float]]:
    m = re.search(rf"([+\-]?\d[\d\.,\s]*k?)\s*{RANGE_SEP}\s*([+\-]?\d[\d\.,\s]*k?)", text, re.IGNORECASE)
    if m:
        a = parse_number(m.group(1)); b = parse_number(m.group(2))
        if a is not None and b is not None:
            lo, hi = (a, b) if a <= b else (b, a)
            return "rango", [lo, hi]

    m = re.search(r"(?:\bentry\b|\bentrada\b|\b(at|@)\b|\barea\b|\bzone\b|\bpoi\b|\bbuy\s+at\b|\bsell\s+at\b)\D{0,8}([+\-]?\d[\d\.,\s]*k?)", text, re.IGNORECASE)
    if m:
        v = parse_number(m.group(2))
        if v is not None:
            return "precio", [v]

    m = re.search(r"(?:\bentry\b|\bentrada\b)\D{0,10}((?:[+\-]?\d[\d\.,\s]*k?)(?:\D{0,5}(?:,|;|\s)\D{0,5}[+\-]?\d[\d\.,\s]*k?)*)", text, re.IGNORECASE)
    if m:
        vals = []
        for t in re.findall(r"[+\-]?\d[\d\.,\s]*k?", m.group(1)):
            v = parse_number(t)
            if v is not None:
                vals.append(v)
        if vals:
            return ("multiple" if len(vals) > 1 else "precio"), vals

    return "no_encontrada", []

def explicit_direction(text: str) -> Optional[str]:
    if re.search(BUY_WORDS, text, re.IGNORECASE): return "BUY"
    if re.search(SELL_WORDS, text, re.IGNORECASE): return "SELL"
    return None

def implicit_direction(sl: Optional[float], tps: List[float]) -> Optional[str]:
    if sl is None or not tps: return None
    if any(tp > sl for tp in tps) and not any(tp < sl for tp in tps): return "BUY"
    if any(tp < sl for tp in tps) and not any(tp > sl for tp in tps): return "SELL"
    return None

def check_consistency(direction: str, entry_vals: List[float], sl: Optional[float], tps: List[float]) -> Optional[bool]:
    if not direction or not entry_vals or sl is None or not tps:
        return None
    if direction == "BUY":
        return True if any(sl < e < tp for e in entry_vals for tp in tps) else False
    if direction == "SELL":
        return True if any(tp < e < sl for e in entry_vals for tp in tps) else False
    return None

def classify_and_extract(text: str) -> Dict[str, Any]:
    text_clean = re.sub(r"[ \t\r]+", " ", (text or "")).strip()

    activo = find_asset(text_clean)
    sl     = extract_sl(text_clean)
    tps    = extract_tps(text_clean)
    etipo, evalues = extract_entry(text_clean)

    dir_exp = explicit_direction(text_clean)
    dir_imp = implicit_direction(sl, tps)
    direccion = dir_exp or dir_imp or "INDETERMINADA"

    consist = check_consistency(direccion, evalues, sl, tps)

    valido = (activo is not None) and has_sl(text_clean) and has_tp(text_clean)
    clas = "Válido" if valido else "Ruido"

    # --- Score y motivos ---
    score = 0
    motivos: List[str] = []

    if has_sl(text_clean):
        score += 2; motivos.append("SL detectado")
    else:
        motivos.append("Falta SL")

    if has_tp(text_clean):
        score += 2; motivos.append("TP detectado")
    else:
        motivos.append("Falta TP")

    if activo:
        score += 2; motivos.append(f"Activo: {activo}")
    else:
        motivos.append("Falta activo")

    if direccion != "INDETERMINADA":
        score += 1; motivos.append(f"Dirección: {direccion} ({'explícita' if dir_exp else 'implícita'})")
    else:
        motivos.append("Dirección indeterminada")

    if sl is not None:
        score += 1; motivos.append(f"SL numérico: {sl}")
    else:
        motivos.append("No se extrajo SL numérico")

    if len(tps) >= 1:
        score += 1; motivos.append(f"TPs: {tps}")
        if len(tps) >= 2:
            score += 1; motivos.append("Múltiples TPs")
    else:
        motivos.append("No se extrajo TP numérico")

    if etipo != "no_encontrada":
        score += 1; motivos.append(f"Entrada: {etipo} {evalues}")
    else:
        motivos.append("Entrada no encontrada")

    if consist is True:
        score += 1; motivos.append("Consistencia dirección: OK")
    elif consist is False:
        score = max(0, score - 1); motivos.append("Consistencia dirección: NO")

    # Limitar a [0..10]
    score = max(0, min(10, score))

    return {
        "clasificacion": clas,
        "activo": activo,
        "direccion": direccion,
        "entrada": {
            "tipo": etipo,
            "valores": evalues
        },
        "sl": sl if sl is not None else None,
        "tp": tps,
        "consistencia_direccion": True if consist is True else (False if consist is False else None),
        "observaciones": None,
        "score": score,
        "motivos": motivos
    }

# ---------- Persistencia ----------
def save_row(con: sqlite3.Connection, src: Dict[str, Any], result: Dict[str, Any]):
    con.execute("""
        INSERT INTO parsed_signals
        (created_utc, channel_id, channel_username, channel_title, msg_id, revision, ts_utc, text,
         clasificacion, activo, direccion, entrada_tipo, entrada_valores, sl, tp,
         consistencia_direccion, observaciones, score, motivos)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        datetime.now(timezone.utc).isoformat(),
        src.get("channel_id"),
        src.get("channel_username"),
        src.get("channel_title"),
        src.get("msg_id"),
        src.get("revision"),
        src.get("ts_utc"),
        src.get("text"),
        result.get("clasificacion"),
        result.get("activo"),
        result.get("direccion"),
        result.get("entrada", {}).get("tipo"),
        json.dumps(result.get("entrada", {}).get("valores") or []),
        result.get("sl"),
        json.dumps(result.get("tp") or []),
        1 if result.get("consistencia_direccion") is True else (0 if result.get("consistencia_direccion") is False else None),
        result.get("observaciones"),
        result.get("score"),
        json.dumps(result.get("motivos") or [])
    ))
    con.commit()

# ---------- Main loop ----------
def main():
    ensure_db()
    con = sqlite3.connect(DB_PATH)

    r = Redis.from_url(REDIS_URL, decode_responses=True)
    try:
        r.xgroup_create(IN_STREAM, GROUP, id="$", mkstream=True)  # '$' = solo nuevos
        log(f"Grupo creado: stream={IN_STREAM} group={GROUP}")
    except Exception as e:
        if "BUSYGROUP" in str(e):
            log(f"Grupo ya existe: {GROUP}")
        else:
            raise

    log(f"Consumidor listo → group={GROUP} consumer={CONSUMER} in={IN_STREAM} out={OUT_STREAM}")
    while True:
        try:
            resp = r.xreadgroup(GROUP, CONSUMER, {IN_STREAM: ">"}, count=COUNT, block=BLOCK_MS)
            if not resp:
                continue

            for _stream, messages in resp:
                for msg_id, fields in messages:
                    try:
                        src = json.loads(fields.get("data", "{}"))
                    except Exception:
                        r.xadd(DLQ_STREAM, {"reason": "bad_payload", "fields": json.dumps(fields, ensure_ascii=False)})
                        r.xack(IN_STREAM, GROUP, msg_id)
                        continue

                    try:
                        result = classify_and_extract(src.get("text") or "")
                        out = {
                            "source": {
                                "stream": IN_STREAM,
                                "msg_id": msg_id,
                                "channel_id": src.get("channel_id"),
                                "channel_username": src.get("channel_username"),
                                "channel_title": src.get("channel_title"),
                                "revision": src.get("revision"),
                                "ts_utc": src.get("ts_utc"),
                            },
                            "classification": result,
                            "raw_text": src.get("text")
                        }

                        # --- Tracking visual (siempre) ---
                        ts = src.get("ts_utc") or datetime.now(timezone.utc).isoformat()
                        ch = src.get("channel_id")
                        mid = src.get("msg_id")
                        rev = src.get("revision")
                        log(f"PARSED {ts} | ch_id={ch} msg_id={mid} rev={rev} | clas={result['clasificacion']} score={result['score']}")

                        # --- Guardar/publicar SOLO si score == 10 ---
                        if result.get("score") == 10:
                            save_row(con, src, result)
                            r.xadd(OUT_STREAM, {"data": json.dumps(out, ensure_ascii=False)})
                            log(f"ACK {msg_id} → guardado en SQLite (score=10) y publicado en {OUT_STREAM}")
                        else:
                            log(f"ACK {msg_id} → SKIP persistencia/publicación (score={result.get('score')})")

                        # ACK SIEMPRE para no colas pendientes
                        r.xack(IN_STREAM, GROUP, msg_id)

                    except Exception as e:
                        log(f"ERROR procesando {msg_id}: {e}")
                        r.xadd(DLQ_STREAM, {"reason": f"process_error: {e}", "data": json.dumps(src, ensure_ascii=False)})
                        # sin ACK → quedará pendiente para reintento
        except KeyboardInterrupt:
            log("Interrumpido por usuario.")
            break
        except Exception as e:
            log(f"ERROR loop: {e}")
            time.sleep(1)

if __name__ == "__main__":
    main()

