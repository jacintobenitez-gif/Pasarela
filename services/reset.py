# reset_pipeline.py
# Borra (a elección) Redis (stream + dedup + rev), DB SQLite, cola MT4 y CSV.
# Seguro por defecto: pide confirmación; soporta --dry-run y --force.

import os
import sys
import glob
import json
import argparse
import sqlite3
from datetime import datetime, timezone

try:
    import redis
except ImportError:
    print("Falta la librería 'redis'. Instala con: pip install redis")
    sys.exit(1)

# ===== Config por entorno =====
REDIS_URL     = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
REDIS_STREAM  = os.getenv("REDIS_STREAM", "pasarela:parse")
REDIS_GROUP   = os.getenv("REDIS_GROUP", "parser")
DEDUP_PATTERNS = [
    "tg:dedup:*",
    "tg:rev:*",
]

APPDATA       = os.getenv("APPDATA") or ""
MT4_HASH      = os.getenv("MT4_TERMINAL_HASH", "BB190E062770E27C3E79391AB0D1A117")
QUEUE_ORDER   = os.path.join(APPDATA, "MetaQuotes", "Terminal", MT4_HASH, "MQL4", "Files", "queue_order")
QUEUE_SPOOL   = os.path.join(APPDATA, "MetaQuotes", "Terminal", MT4_HASH, "MQL4", "Files", "queue_spool")

DB_PATH       = os.getenv("PASARELA_DB", os.path.join(os.getcwd(), "pasarela.db"))
CSV_PATH      = os.getenv("CSV_PATH", r"C:\Pasarela\data\mensajes_raw.csv")

def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")

# ===== Helpers =====
def confirm_or_exit():
    ans = input("⚠️  Esto borrará datos. ¿Continuar? (escribe 'SI' en mayúsculas): ").strip()
    if ans != "SI":
        print("Cancelado.")
        sys.exit(0)

def human_del_list(items):
    if not items:
        return "0 elementos"
    if len(items) <= 5:
        return f"{len(items)} → " + ", ".join(items)
    return f"{len(items)} → {', '.join(items[:5])} ..."

# ===== Redis cleanup =====
def clear_redis(dry_run: bool = False):
    r = redis.Redis.from_url(REDIS_URL, decode_responses=True)
    report = {"stream_trimmed": False, "groups_destroyed": [], "keys_deleted": 0, "keys_list": []}

    # 1) Destruir consumer group (si existe)
    try:
        groups = r.xinfo_groups(REDIS_STREAM)
        gnames = [g.get("name") for g in groups]
    except Exception:
        gnames = []

    if REDIS_GROUP in gnames:
        if dry_run:
            report["groups_destroyed"].append(REDIS_GROUP + " (dry-run)")
        else:
            try:
                r.xgroup_destroy(REDIS_STREAM, REDIS_GROUP)
                report["groups_destroyed"].append(REDIS_GROUP)
            except Exception as e:
                report["groups_destroyed"].append(f"{REDIS_GROUP} (err: {e})")

    # 2) Vaciar el stream
    try:
        # XTRIM MAXLEN 0 borra todas las entradas
        if dry_run:
            report["stream_trimmed"] = "dry-run"
        else:
            r.xtrim(REDIS_STREAM, 0, approximate=False)
            report["stream_trimmed"] = True
    except Exception as e:
        report["stream_trimmed"] = f"err: {e}"

    # 3) Borrar claves auxiliares (dedup, rev)
    keys_to_del = []
    try:
        for pattern in DEDUP_PATTERNS:
            cursor = 0
            while True:
                cursor, keys = r.scan(cursor=cursor, match=pattern, count=1000)
                keys_to_del.extend(keys)
                if cursor == 0:
                    break
    except Exception:
        pass

    report["keys_list"] = keys_to_del
    if keys_to_del:
        if dry_run:
            report["keys_deleted"] = f"{len(keys_to_del)} (dry-run)"
        else:
            try:
                # Pipeline para borrar en lote
                pipe = r.pipeline()
                for k in keys_to_del:
                    pipe.delete(k)
                res = pipe.execute()
                report["keys_deleted"] = sum(1 for x in res if x)
            except Exception as e:
                report["keys_deleted"] = f"err: {e}"
    return report

# ===== DB cleanup =====
def clear_db(dry_run: bool = False):
    if not os.path.exists(DB_PATH):
        return {"removed": False, "path": DB_PATH, "note": "no existe"}
    if dry_run:
        return {"removed": "dry-run", "path": DB_PATH}
    try:
        os.remove(DB_PATH)
        return {"removed": True, "path": DB_PATH}
    except Exception as e:
        return {"removed": f"err: {e}", "path": DB_PATH}

# ===== MT4 queue cleanup =====
def clear_mt4(dry_run: bool = False):
    dirs = [QUEUE_ORDER, QUEUE_SPOOL]
    report = []
    for d in dirs:
        if not os.path.isdir(d):
            report.append({"dir": d, "removed": 0, "note": "no existe"})
            continue
        files = glob.glob(os.path.join(d, "*.json"))
        if dry_run:
            report.append({"dir": d, "removed": f"{len(files)} (dry-run)", "list": files[:5]})
        else:
            removed = 0
            for f in files:
                try:
                    os.remove(f)
                    removed += 1
                except Exception:
                    pass
            report.append({"dir": d, "removed": removed})
    return report

# ===== CSV cleanup =====
def clear_csv(dry_run: bool = False):
    if not os.path.exists(CSV_PATH):
        return {"removed": False, "path": CSV_PATH, "note": "no existe"}
    if dry_run:
        return {"removed": "dry-run", "path": CSV_PATH}
    try:
        os.remove(CSV_PATH)
        return {"removed": True, "path": CSV_PATH}
    except Exception as e:
        return {"removed": f"err: {e}", "path": CSV_PATH}

def main():
    ap = argparse.ArgumentParser(description="Reinicia el pipeline a estado limpio (Redis / DB / MT4 / CSV).")
    ap.add_argument("--all", action="store_true", help="Borrar TODO (Redis + DB + MT4 + CSV).")
    ap.add_argument("--redis", action="store_true", help="Borrar solo Redis (stream + dedup + rev).")
    ap.add_argument("--db", action="store_true", help="Borrar solo base de datos SQLite.")
    ap.add_argument("--mt4", action="store_true", help="Borrar solo archivos de la cola MT4 (queue_order/queue_spool).")
    ap.add_argument("--csv", action="store_true", help="Borrar solo CSV.")
    ap.add_argument("--dry-run", action="store_true", help="No borra nada; muestra lo que haría.")
    ap.add_argument("--force", action="store_true", help="No pedir confirmación.")
    args = ap.parse_args()

    if not any([args.all, args.redis, args.db, args.mt4, args.csv]):
        ap.print_help()
        sys.exit(0)

    print(f"[{now_iso()}] RESET — opciones: {args}")

    if not args.force and not args.dry_run:
        confirm_or_exit()

    if args.all or args.redis:
        print("\n— Redis —")
        rep = clear_redis(dry_run=args.dry_run)
        print(f"  stream='{REDIS_STREAM}' → trim={rep.get('stream_trimmed')}")
        if rep.get("groups_destroyed"):
            print(f"  groups destruidos: {rep['groups_destroyed']}")
        if rep.get("keys_list") is not None:
            print(f"  claves auxiliares (patrones {DEDUP_PATTERNS}): {human_del_list(rep['keys_list'])}")
            print(f"  total borrado: {rep.get('keys_deleted')}")

    if args.all or args.db:
        print("\n— DB —")
        rep = clear_db(dry_run=args.dry_run)
        print(f"  {rep}")

    if args.all or args.mt4:
        print("\n— MT4 queue —")
        rep = clear_mt4(dry_run=args.dry_run)
        for r in rep:
            print(f"  dir={r['dir']} → removed={r['removed']}" + (f" | ejemplos={r.get('list')}" if 'list' in r else ""))

    if args.all or args.csv:
        print("\n— CSV —")
        rep = clear_csv(dry_run=args.dry_run)
        print(f"  {rep}")

    print(f"\n[{now_iso()}] RESET — terminado.")

if __name__ == "__main__":
    main()
