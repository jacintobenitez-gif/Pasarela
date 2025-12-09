# -*- coding: utf-8 -*-
# reglasnegocio.py — Clasificador y extractor de señales de trading (línea base 2025-10-03)
# - Clasificación: Válido / Ruido (requiere SL + TP + Activo)
# - Activos (forex, índices, materias primas, gas, cripto; acepta abreviaturas, emojis, hashtags)
# - Dirección (explícita por texto / implícita por SL vs TP)
# - Acción específica: BUY / SELL / BUY LIMIT / SELL LIMIT / BUY STOP / SELL STOP
# - Entrada: precio | rango | multiple | no_encontrada (resuelve rango→precio: min para BUY*, max para SELL*)
# - Normalización de números (., , miles, k)
# - Consistencia (BUY: SL < entrada < TP; SELL: TP < entrada < SL)
# - Score: 10 si Válido + acción definida + entrada utilizable (precio o rango resuelto) + SL + ≥1 TP; si no, 0.

from __future__ import annotations
import re
from typing import List, Tuple, Optional, Dict, Any

# =========================
# Utilidades de normalización
# =========================

_EN_DASH = u"\u2013"
_EM_DASH = u"\u2014"
_ARROW  = u"\u2192"

# >>> PARCHE: añadimos '/' como separador de rango
RANGE_SEPARATORS = r"(?:/|-|"+_EN_DASH+r"|"+_EM_DASH+r"|"+_ARROW+r"|(?:\s+a\s+)|(?:\s+hasta\s+)|(?:\s+to\s+)|(?:\s+and\s+))"

def _strip_emoji_tags(s: str) -> str:
    return re.sub(r"[:@•\*\|]", " ", s)

def _normalize_spaces(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()

def _normalize_text_for_search(s: str) -> str:
    s = s.replace("\t", " ")
    s = _strip_emoji_tags(s)
    s = s.replace(_EN_DASH, "-").replace(_EM_DASH, "-").replace("→", "-")
    for kw in (" a ", " hasta ", " to ", " and "):
        s = s.replace(kw, " - ")
    return _normalize_spaces(s)

def _normalize_number_str(raw: str) -> Optional[float]:
    raw = raw.lower().strip()
    k_match = re.match(r"^\s*([+-]?\d+(?:[.,]\d+)?)\s*k\s*$", raw)
    if k_match:
        base = _normalize_number_str(k_match.group(1))
        return None if base is None else base * 1000.0
    raw = raw.replace(" ", "")
    if not re.search(r"\d", raw):
        return None
    last_dot = raw.rfind(".")
    last_com = raw.rfind(",")
    if last_dot != -1 and last_com != -1:
        if last_dot > last_com:
            raw = raw.replace(",", "")
        else:
            raw = raw.replace(".", "").replace(",", ".")
    elif last_com != -1 and last_dot == -1:
        raw = raw.replace(",", ".")
    # limpia separadores sueltos tipo 1’234
    raw = re.sub(r"(?<=\d)[’']", "", raw)
    try:
        return float(raw)
    except ValueError:
        return None

def _find_all_numbers(s: str) -> List[float]:
    # PATCH: prioriza dígitos continuos (evita que 3886 se trocee en 388 y 6)
    # y deja como segunda alternativa los miles con separadores.
    pattern = (
        r"(?<![A-Za-z])"
        r"([+-]?\d+(?:[.,]\d+)?k?"                             # 1) cualquier cantidad de dígitos (preferente)
        r"|[+-]?\d{1,3}(?:[ \u00A0\.,]\d{3})+(?:[.,]\d+)?k?"   # 2) miles con separadores (>= un grupo de 3)
        r")"
        r"(?![A-Za-z])"
    )
    vals: List[float] = []
    for m in re.finditer(pattern, s, flags=re.IGNORECASE):
        num = _normalize_number_str(m.group(1))
        if num is not None:
            vals.append(num)
    return vals

# =========================
# Coincidencia segura de alias (evita falsos positivos tipo 'es' en 'latest')
# =========================
_ALNUM_ALIAS = re.compile(r"^[a-z0-9]+$", re.IGNORECASE)

def _alias_in_text(lowered: str, alias: str) -> bool:
    if _ALNUM_ALIAS.match(alias):
        return re.search(rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])", lowered) is not None
    else:
        return alias in lowered

# =========================
# Catálogo de activos
# =========================

ASSET_ALIASES: Dict[str, str] = {
    # Forex (muestrario; se pueden añadir)
    "eurusd":"EURUSD","eur/usd":"EURUSD","gbpjpy":"GBPJPY","gbp/jpy":"GBPJPY",
    "usdjpy":"USDJPY","usd/jpy":"USDJPY","audusd":"AUDUSD","aud/usd":"AUDUSD",
    "nzdusd":"NZDUSD","nzd/usd":"NZDUSD","usdcad":"USDCAD","usd/cad":"USDCAD",
    "chfjpy":"CHFJPY","chf/jpy":"CHFJPY","gbpusd":"GBPUSD","gbp/usd":"GBPUSD",
    "eurjpy":"EURJPY","eur/jpy":"EURJPY",

    # Índices USA
    "us30":"US30","dj30":"US30","dji":"US30","dow jones":"US30","ws30":"US30",
    "us100":"US100","nas100":"US100","ustech100":"US100","ndx":"US100","nasdaq":"US100",
    "spx":"US500","sp500":"US500","s&p":"US500","us500":"US500","es":"US500",

    # Europa
    "ger40":"DAX40","dax40":"DAX40","dax":"DAX40",
    "uk100":"FTSE100","ftse100":"FTSE100","ftse":"FTSE100",
    "fra40":"CAC40","cac40":"CAC40","cac":"CAC40",
    "es35":"IBEX35","ibex35":"IBEX35","ibex":"IBEX35",

    # Asia
    "jp225":"JP225","nikkei225":"JP225","nikkei":"JP225","jpn225":"JP225",
    "hk50":"HK50","hang seng":"HK50",

    # Materias primas - Metales
    "xauusd":"XAUUSD","xau/usd":"XAUUSD","gold":"XAUUSD","oro":"XAUUSD","🥇":"XAUUSD","#gold":"XAUUSD",
    "xagusd":"XAGUSD","xag/usd":"XAGUSD","silver":"XAGUSD","plata":"XAGUSD","🥈":"XAGUSD","#silver":"XAGUSD",
    "copper":"COPPER","hg":"COPPER","cu":"COPPER",

    # Energía
    "usoil":"USOIL","wti":"USOIL","cl":"USOIL","crude":"USOIL","crude oil":"USOIL","oil":"USOIL",
    "brent":"UKOIL","ukoil":"UKOIL",

    # Gas
    "ng":"NATGAS","natural gas":"NATGAS","gas":"NATGAS",

    # Cripto
    "btcusd":"BTCUSD","btc/usdt":"BTCUSDT","btc":"BTCUSD","bitcoin":"BTCUSD","₿":"BTCUSD","#btc":"BTCUSD",
    "ethusd":"ETHUSD","eth/usdt":"ETHUSDT","eth":"ETHUSD","ethereum":"ETHUSD",
    "ltcusd":"LTCUSD","xrpusd":"XRPUSD","bnbusd":"BNBUSD","adausd":"ADAUSD","solusd":"SOLUSD",
}

WEAK_TOKENS_TO_CANONICAL = {"xau":"XAUUSD","xag":"XAGUSD"}
EMOJI_HASHTAG_TO_CANONICAL = {"🥇":"XAUUSD","🥈":"XAGUSD","₿":"BTCUSD","#gold":"XAUUSD","#btc":"BTCUSD","#eth":"ETHUSD"}

ASSET_REGEXES = [
    re.compile(r"\b([A-Z]{3}/[A-Z]{3})\b", re.IGNORECASE),
    re.compile(r"\b([A-Z]{6})\b", re.IGNORECASE),
]

def _find_assets(text: str) -> List[str]:
    found: List[str] = []
    lowered = text.lower()
    for alias, canon in {**ASSET_ALIASES, **EMOJI_HASHTAG_TO_CANONICAL}.items():
        if _alias_in_text(lowered, alias):  # PATCH: coincidencia segura
            found.append(canon)
    for weak, canon in WEAK_TOKENS_TO_CANONICAL.items():
        if re.search(rf"\b{weak}\b", lowered):
            found.append(canon)
    for rx in ASSET_REGEXES:
        for m in rx.finditer(text):
            alias = m.group(1).lower()
            canon = ASSET_ALIASES.get(alias, alias.upper())
            found.append(canon)
    # dedup preservando orden
    uniq: List[str] = []
    for x in found:
        if x not in uniq:
            uniq.append(x)
    return uniq

# =========================
# Palabras clave
# =========================

SL_WORDS = r"(?:\bsl\b|\bs/l\b|\bstop\s*loss\b|\bstop\b)"
TP_WORDS = r"(?:\btp\d*\b|\btargets?\b|\btarget\b|\btake\s*profit\b|\bobjetivos?\b|\bmeta\b|\btake\b|\balvo\b)"

# Palabras clave para detectar breakeven
# Nota: BE solo en mayúsculas para evitar falsos positivos con el verbo "to be"
# El patrón (?<![a-z])(?:BE|B\.E\.)(?![a-z]) solo debe coincidir con BE en mayúsculas, no con "be" minúsculas
BREAKEVEN_WORDS = r"(?:\bbreakeven\b|\bbreak-even\b|\bbreak\s+even\b|(?<![a-z])(?:BE|B\.E\.)(?![a-z])|\bpunto\s+de\s+equilibrio\b|\bpunto\s+equilibrio\b|\bsin\s+pérdidas\b|\bsin\s+perdidas\b|\bcero\s+pérdidas\b|\bcero\s+perdidas\b)"

BUY_WORDS  = r"(?:\bbuy\b|\blong\b|\bgo\s*long\b|\bbullish\b|\bcomprar\b|\bcompra\b)"
SELL_WORDS = r"(?:\bsell\b|\bshort\b|\bgo\s*short\b|\bbearish\b|\bvender\b|\bventa\b)"

LIMIT_WORD = r"(?:\blimit\b)"
STOP_WORD  = r"(?:\bstop\b)"

# CHANGE 1: aceptar "entry price/precio"
ENTRY_HINTS = r"(?:\bentry\s*(?:price|precio)?\b|\bentrada\b|\bbuy\s*at\b|\bsell\s*at\b|\b@)"

def _has_sl_keyword(text: str) -> bool:
    return re.search(SL_WORDS, text, flags=re.IGNORECASE) is not None

def _has_tp_keyword(text: str) -> bool:
    return re.search(TP_WORDS, text, flags=re.IGNORECASE) is not None

def _has_closeall_keyword(text: str) -> bool:
    """
    Detecta si el texto contiene referencias a cerrar todas las posiciones.
    Nota: "close" y "cerrar" solas NO se detectan (necesitan contexto).
    "closed" en pasado SÍ se detecta como CLOSEALL.
    """
    text_lower = text.lower()
    
    # Patrones en inglés (excluyendo "close" sola)
    patterns_en = [
        r'\bclose\s+all\b',
        r'\bclose\s+everything\b',
        r'\bclose\s+now\b',
        r'\bclosed\b',  # Pasado - sí se detecta
        r'\bflatten\s+all\b',
        r'\bflatten\b',
    ]
    
    # Patrones en español (excluyendo "cerrar" sola)
    patterns_es = [
        r'\bcerrar\s+todo\b',
        r'\bcerrar\s+ya\b',
        r'\bcerrar\s+ahora\b',
        r'\banulamos\b',
        r'\banular\b',
        r'\banulen\b',
        r'\bcierra\s+todo\b',
        r'\bcierren\s+todo\b',
        r'\bcerrad\s+todo\b',
        r'\bcerrar\s+todas\b',
        r'\bcierra\s+todas\b',
        r'\bcerrar\s+posiciones\b',
        r'\bcierra\s+posiciones\b',
        r'\bcerrad\b',  # Imperativo plural
        r'\bcierren\b',  # Imperativo plural
        r'\bcerrar\s+todas\s+las\s+posiciones\b',
        r'\bcierra\s+todas\s+las\s+posiciones\b',
        r'\bcerrar\s+[oó]rdenes\b',
        r'\bcierra\s+[oó]rdenes\b',
        r'\bcerrar\s+todas\s+las\s+[oó]rdenes\b',
        r'\bcierra\s+todas\s+las\s+[oó]rdenes\b',
        r'\bcerrar\s+operaciones\b',
        r'\bcierra\s+operaciones\b',
        r'\bsalir\s+de\s+todo\b',
        r'\bsalida\s+total\b',
    ]
    
    # Verificar patrones en inglés
    for pattern in patterns_en:
        if re.search(pattern, text_lower, flags=re.IGNORECASE):
            return True
    
    # Verificar patrones en español
    for pattern in patterns_es:
        if re.search(pattern, text_lower, flags=re.IGNORECASE):
            return True
    
    return False

def _has_partial_close_keyword(text: str) -> bool:
    """
    Detecta si el texto contiene referencias a cierre parcial.
    """
    text_lower = text.lower()
    
    # Patrones en español
    patterns_es = [
        r'\basegurando\s+algo\s+de\s+profits\b',
        r'\basegurando\s+profits\b',
        r'\basegurando\b',
        r'\basegurar\b',
        r'\basegurad\b',
        r'\baseguren\s+partial\b',
        r'\bpartials\b',
        r'\bparcial\b',
        r'\bparciales\b',
        r'\bmitad\b',
        r'\bcerrad\s+parcial\b',
        r'\bcerrad\s+parciales\b',
        r'\bcerrad\s+mitad\b',
        r'\basegurar\s+parciales\b',
        r'\basegurando\s+parciales\b',
        r'\baseguren\s+parciales\b',
        r'\bcerrar\s+parcial\b',
        r'\bcerrar\s+parciales\b',
        r'\bcerrar\s+mitad\b',
        r'\breducir\s+posicion\b',
        r'\breducir\s+posici[oó]n\b',
        r'\breducid\b',
        r'\breducimos\b',
    ]
    
    # Patrones en inglés
    patterns_en = [
        r'\bpartial\s+close\b',
        r'\bpartial\s+tp\b',
        r'\bscale\s+out\b',
        r'\btrim\b',
        r'\breduce\s+position\b',
        r'\btake\s+partial\b',
        r'\btake\s+partials\b',
        r'\bpartial\b',  # Solo "partial" como palabra completa
    ]
    
    # Verificar patrones en español
    for pattern in patterns_es:
        if re.search(pattern, text_lower, flags=re.IGNORECASE):
            return True
    
    # Verificar patrones en inglés
    for pattern in patterns_en:
        if re.search(pattern, text_lower, flags=re.IGNORECASE):
            return True
    
    return False

def _has_breakeven_keyword(text: str) -> bool:
    """
    Detecta si el texto contiene referencias a breakeven.
    Incluye patrones de "mover SL a entrada/be/breakeven".
    Nota: "be" en minúsculas se descarta para evitar falsos positivos con el verbo "to be".
    Excluye falsos positivos: "TO BE", "BEEN", "BEING", "WILL BE".
    """
    # Primero verificar el regex básico de breakeven, pero con cuidado con "BE" vs "be"
    # Buscar primero "BE" en mayúsculas específicamente (sin IGNORECASE para esta parte)
    be_match = re.search(r'(?<![a-z])(?:BE|B\.E\.)(?![a-z])', text)
    if be_match:
        # Verificar que realmente sea "BE" en mayúsculas, no "be" minúsculas
        matched_text = text[be_match.start():be_match.end()]
        if matched_text.upper() == matched_text:  # Solo si está en mayúsculas
            # Verificar contexto para excluir falsos positivos del verbo "to be"
            start_pos = be_match.start()
            end_pos = be_match.end()
            
            # Contexto antes (hasta 10 caracteres antes)
            context_before = text[max(0, start_pos - 10):start_pos].lower()
            # Contexto después (hasta 10 caracteres después, incluyendo el texto inmediatamente después)
            context_after = text[end_pos:min(len(text), end_pos + 10)]
            
            # Excluir casos del verbo "to be"
            # "TO BE", "to be", "To Be" - verificar si antes hay "to"
            if re.search(r'\bto\s+be\b', context_before + matched_text.lower() + context_after.lower(), flags=re.IGNORECASE):
                return False
            
            # "BEEN", "been", "Been" - verificar si inmediatamente después de BE hay "EN"
            if len(context_after) >= 2 and context_after[:2].upper() == "EN":
                return False
            
            # "BEING", "being", "Being" - verificar si inmediatamente después de BE hay "ING"
            if len(context_after) >= 3 and context_after[:3].upper() == "ING":
                return False
            
            # "WILL BE", "will be", "Will Be" - verificar si antes hay "will"
            if re.search(r'\bwill\s+be\b', context_before + matched_text.lower() + context_after.lower(), flags=re.IGNORECASE):
                return False
            
            # Si pasó todas las exclusiones, es un BE válido de breakeven
            return True
    
    # Buscar otras palabras de breakeven con IGNORECASE (breakeven, break-even, etc.)
    other_patterns = r"(?:\bbreakeven\b|\bbreak-even\b|\bbreak\s+even\b|\bpunto\s+de\s+equilibrio\b|\bpunto\s+equilibrio\b|\bsin\s+pérdidas\b|\bsin\s+perdidas\b|\bcero\s+pérdidas\b|\bcero\s+perdidas\b)"
    if re.search(other_patterns, text, flags=re.IGNORECASE):
        return True
    
    # Patrones adicionales para detectar "mover SL a entrada/be/breakeven"
    # Español - "mover sl a entrada/be"
    patterns_es = [
        r'mover\s+(?:el\s+)?(?:SL|stop\s*loss|stoploss|stop-loss)(?:es)?\s+a\s+(?:entrada|be\b|breakeven|break\s+even)',
        r'mover\s+(?:el\s+)?(?:stop|stop\s*loss|stop-loss)\s+a\s+(?:entrada|be\b|breakeven|break\s+even)',
        r'(?:SL|stop\s*loss|stoploss|stop-loss)(?:es)?\s+a\s+(?:entrada|be\b|breakeven|break\s+even)',
        r'(?:SL|stop\s*loss|stoploss|stop-loss)(?:es)?\s+al\s+punto\s+de\s+entrada',
        r'(?:SL|stop\s*loss|stoploss|stop-loss)(?:es)?\s+en\s+entrada',
        r'poner\s+(?:el\s+)?(?:SL|stop\s*loss|stoploss|stop-loss)(?:es)?\s+(?:a|en)\s+(?:entrada|be\b|breakeven|break\s+even)',
        r'llevar\s+(?:el\s+)?(?:SL|stop\s*loss|stoploss|stop-loss)(?:es)?\s+a\s+(?:entrada|be\b|breakeven|break\s+even)',
        r'llevar\s+(?:el\s+)?(?:stop|stop\s*loss|stop-loss)\s+a\s+(?:entrada|be\b|breakeven|break\s+even)',
        r'subir\s+(?:el\s+)?(?:SL|stop\s*loss|stoploss|stop-loss)(?:es)?\s+a\s+(?:entrada|be\b|breakeven|break\s+even)',
        r'bajar\s+(?:el\s+)?(?:SL|stop\s*loss|stoploss|stop-loss)(?:es)?\s+a\s+(?:entrada|be\b|breakeven|break\s+even)',
        r'pasa\s+(?:el\s+)?(?:SL|stop\s*loss|stoploss|stop-loss)(?:es)?\s+a\s+(?:entrada|be\b|breakeven|break\s+even)',
        r'ajustar\s+(?:el\s+)?(?:SL|stop\s*loss|stoploss|stop-loss)(?:es)?\s+a\s+(?:entrada|be\b|breakeven|break\s+even)',
        r'ajusta\s+(?:el\s+)?(?:SL|stop\s*loss|stoploss|stop-loss)(?:es)?\s+a\s+(?:entrada|be\b|breakeven|break\s+even)',
        r'(?:SL|stop\s*loss|stoploss|stop-loss)(?:es)?\s+a\s+(?:cero|0)',
        r'(?:stop|stop\s*loss|stop-loss)\s+a\s+(?:cero|0)',
        r'mover\s+a\s+be\b',
        r'ir\s+a\s+be\b',
        r'al\s+be\b',
    ]
    
    # Inglés - "move sl to entry/be/breakeven"
    patterns_en = [
        r'move\s+(?:my\s+|our\s+|your\s+|all\s+)?(?:SL|stop\s*loss|stoploss|stop-loss)(?:es)?\s+to\s+(?:entry|be\b|breakeven|break\s+even)',
        r'moved\s+(?:my\s+|our\s+|your\s+|all\s+)?(?:SL|stop\s*loss|stoploss|stop-loss)(?:es)?\s+to\s+(?:entry|be\b|breakeven|break\s+even)',
        r'moving\s+(?:my\s+|our\s+|your\s+|all\s+)?(?:SL|stop\s*loss|stoploss|stop-loss)(?:es)?\s+to\s+(?:entry|be\b|breakeven|break\s+even)',
        r'set\s+(?:my\s+|our\s+|your\s+|all\s+)?(?:SL|stop\s*loss|stoploss)(?:es)?\s+to\s+(?:entry|be\b|breakeven|break\s+even)',
        r'put\s+(?:my\s+|our\s+|your\s+|all\s+)?(?:SL|stop\s*loss|stoploss)(?:es)?\s+(?:to|at)\s+(?:entry|be\b|breakeven|break\s+even)',
        r'adjust\s+(?:my\s+|our\s+|your\s+|all\s+)?(?:SL|stop\s*loss|stoploss)(?:es)?\s+to\s+(?:entry|be\b|breakeven|break\s+even)',
        r'(?:SL|stop\s*loss|stoploss|stop-loss)(?:es)?\s+to\s+(?:entry|be\b|breakeven|break\s+even)',
        r'(?:stop|stop\s*loss|stop-loss)\s+to\s+(?:entry|be\b|breakeven|break\s+even)',
        r'move\s+to\s+(?:breakeven|break\s+even|be\b)',
        r'go\s+(?:to\s+)?(?:breakeven|break\s+even|be\b)',
        r'set\s+to\s+(?:breakeven|break\s+even|be\b)',
        r'(?:SL|stop\s*loss|stoploss|stop-loss)(?:es)?\s+to\s+(?:zero|0)',
        r'(?:stop|stop\s*loss|stop-loss)\s+to\s+(?:zero|0)',
        r'to\s+be\b',
        r'move\s+to\s+be\b',
        r'set\s+to\s+be\b',
    ]
    
    # Verificar patrones en español e inglés
    all_patterns = patterns_es + patterns_en
    
    for pattern in all_patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            # Si el patrón contiene "be", verificar que no sea solo "be" en minúsculas sin contexto
            # Los patrones ya incluyen contexto ("a be", "to be", etc.), pero verificamos por seguridad
            if r'\bbe\b' in pattern:
                matched_text = match.group(0)
                # Buscar "be" en el texto original en la posición del match
                match_start = match.start()
                match_end = match.end()
                # Buscar "be" dentro del match
                be_in_match = re.search(r'\bbe\b', text[match_start:match_end], flags=re.IGNORECASE)
                if be_in_match:
                    be_pos_in_text = match_start + be_in_match.start()
                    be_text = text[be_pos_in_text:be_pos_in_text+2]
                    # Si es "be" en minúsculas, verificar que tenga contexto antes
                    if be_text == 'be':  # Solo minúsculas
                        context_start = max(0, be_pos_in_text - 15)
                        context = text[context_start:be_pos_in_text + 2].lower()
                        # Verificar que tenga contexto de movimiento (a be, to be, al be, etc.)
                        if any(ctx in context for ctx in ['a be', 'to be', 'al be', 'move to be', 'set to be', 'go to be', 'sl to be', 'stop to be']):
                            return True
                        # Si no tiene contexto, podría ser el verbo "to be", descartar
                        continue
                    else:
                        # Es "BE" en mayúsculas o tiene contexto, aceptar
                        return True
                else:
                    # No hay "be" en el match, aceptar
                    return True
            else:
                # Patrón sin "be", aceptar directamente
                return True
    
    return False

def _detect_move_sl(texto: str) -> Optional[Dict[str, Any]]:
    """
    Detecta frases que expresan "mover stop loss" y extrae el número.
    Retorna None si no encuentra, o dict con 'accion': 'MOVETO' o 'STOPLOSSESTO', 'sl': valor_numerico
    Si contiene "stoplosses" (plural), retorna 'STOPLOSSESTO', sino 'MOVETO'
    """
    # NOTA: Ya no excluimos breakeven/entrada aquí porque ahora se detectan como BREAKEVEN
    # antes de llegar a esta función. Solo verificamos exclusiones muy específicas.
    EXCLUDE_WORDS = [
        'back to entry',  # Caso muy específico que no queremos detectar
    ]
    
    # Verificar exclusiones específicas primero
    texto_lower = texto.lower()
    if any(ex in texto_lower for ex in EXCLUDE_WORDS):
        return None
    
    # Si contiene breakeven/entrada, no intentar detectar MOVETO (ya será detectado como BREAKEVEN antes)
    # Esto evita conflictos si llegara aquí por alguna razón
    if _has_breakeven_keyword(texto):
        return None
    
    # Detectar si contiene "stoplosses" (plural) - case insensitive
    contiene_stoplosses = re.search(r'\bstoplosses\b', texto_lower) is not None
    
    PATTERNS = [
        # Patrones en inglés
        r'move\s+(?:my\s+|our\s+|your\s+|all\s+)?(?:SL|stop\s*loss|stoploss|stop-loss)(?:es)?\s+to\s+([0-9]+(?:\.[0-9]+)?)',
        r'moved\s+(?:my\s+|our\s+|your\s+|all\s+)?(?:SL|stop\s*loss|stoploss|stop-loss)(?:es)?\s+to\s+([0-9]+(?:\.[0-9]+)?)',
        r'moving\s+(?:my\s+|our\s+|your\s+|all\s+)?(?:SL|stop\s*loss|stoploss|stop-loss)(?:es)?\s+to\s+([0-9]+(?:\.[0-9]+)?)',
        r'shift(?:ing)?\s+(?:my\s+|our\s+|your\s+|all\s+|the\s+)?(?:SL|stop\s*loss|stoploss|stop-loss)(?:es)?\s+to\s+([0-9]+(?:\.[0-9]+)?)',
        r'temporarily\s+shift(?:ing)?\s+(?:my\s+|our\s+|your\s+|all\s+|the\s+)?(?:SL|stop\s*loss|stoploss|stop-loss)(?:es)?\s+to\s+([0-9]+(?:\.[0-9]+)?)',
        r'(?:^|\s)(?:SL|stop\s*loss|stoploss|stop-loss)(?:es)?\s+to\s+([0-9]+(?:\.[0-9]+)?)',
        r'move\s+to\s+([0-9]+(?:\.[0-9]+)?)\s+(?:SL|stop\s*loss|stoploss)',
        r'set\s+(?:my\s+|our\s+|your\s+|all\s+)?(?:SL|stop\s*loss|stoploss)(?:es)?\s+to\s+([0-9]+(?:\.[0-9]+)?)',
        r'update\s+(?:my\s+|our\s+|your\s+|all\s+)?(?:SL|stop\s*loss|stoploss)(?:es)?\s+to\s+([0-9]+(?:\.[0-9]+)?)',
        r'change\s+(?:my\s+|our\s+|your\s+|all\s+)?(?:SL|stop\s*loss|stoploss)(?:es)?\s+to\s+([0-9]+(?:\.[0-9]+)?)',
        r'adjust\s+(?:my\s+|our\s+|your\s+|all\s+)?(?:SL|stop\s*loss|stoploss)(?:es)?\s+to\s+([0-9]+(?:\.[0-9]+)?)',
        r'put\s+(?:my\s+|our\s+|your\s+|all\s+)?(?:SL|stop\s*loss|stoploss)(?:es)?\s+to\s+([0-9]+(?:\.[0-9]+)?)',
        # Patrones en español - "poner" / "poner el"
        r'poner\s+(?:el\s+)?(?:SL|stop\s*loss|stoploss|stop-loss)(?:es)?\s+a\s+([0-9]+(?:\.[0-9]+)?)',
        r'poner\s+(?:el\s+)?(?:SL|stop\s*loss|stoploss|stop-loss)(?:es)?\s+en\s+([0-9]+(?:\.[0-9]+)?)',
        # Patrones en español - "llevar"
        r'llevar\s+(?:el\s+)?(?:SL|stop\s*loss|stoploss|stop-loss)(?:es)?\s+a\s+([0-9]+(?:\.[0-9]+)?)',
        r'llevar\s+(?:el\s+)?(?:stop|stop\s*loss|stop-loss)\s+a\s+([0-9]+(?:\.[0-9]+)?)',
        # Patrones en español - "subir" / "bajar"
        r'subir\s+(?:el\s+)?(?:SL|stop\s*loss|stoploss|stop-loss)(?:es)?\s+a\s+([0-9]+(?:\.[0-9]+)?)',
        r'bajar\s+(?:el\s+)?(?:SL|stop\s*loss|stoploss|stop-loss)(?:es)?\s+a\s+([0-9]+(?:\.[0-9]+)?)',
        # Patrones en español - "pasa"
        r'pasa\s+(?:el\s+)?(?:SL|stop\s*loss|stoploss|stop-loss)(?:es)?\s+a\s+([0-9]+(?:\.[0-9]+)?)',
        # Patrones en español - "mover" (ya tenemos en inglés, pero añadimos variantes en español)
        r'mover\s+(?:el\s+)?(?:SL|stop\s*loss|stoploss|stop-loss)(?:es)?\s+a\s+([0-9]+(?:\.[0-9]+)?)',
        r'mover\s+(?:el\s+)?(?:stop|stop\s*loss|stop-loss)\s+a\s+([0-9]+(?:\.[0-9]+)?)',
        # Patrones en español - "ajustar" (ya tenemos "adjust", pero añadimos variante en español)
        r'ajustar\s+(?:el\s+)?(?:SL|stop\s*loss|stoploss|stop-loss)(?:es)?\s+a\s+([0-9]+(?:\.[0-9]+)?)',
        r'ajusta\s+(?:el\s+)?(?:SL|stop\s*loss|stoploss|stop-loss)(?:es)?\s+a\s+([0-9]+(?:\.[0-9]+)?)',
    ]
    
    for pattern in PATTERNS:
        match = re.search(pattern, texto, re.IGNORECASE)
        if match:
            numero = float(match.group(1))
            # Determinar acción según si contiene "stoplosses"
            accion = 'STOPLOSSESTO' if contiene_stoplosses else 'MOVETO'
            return {
                'accion': accion,
                'sl': numero
            }
    return None

# =========================
# Extracción SL / TP / Entrada
# =========================

def _extract_numbers_after_keyword(text: str, keyword_regex: str, max_span: int = 120) -> List[float]:
    nums: List[float] = []
    for m in re.finditer(keyword_regex, text, flags=re.IGNORECASE):
        start = m.end()
        window = text[start:start+max_span]
        nums.extend(_find_all_numbers(window))
    return nums

def _extract_sl(text: str) -> Optional[float]:
    sls = _extract_numbers_after_keyword(text, SL_WORDS)
    return sls[0] if sls else None

def _extract_tps(text: str) -> List[float]:
    tps = _extract_numbers_after_keyword(text, TP_WORDS)
    if not tps:
        # Si se indica que el objetivo está abierto/libre, no hay TPs numéricos.
        if re.search(
            r"(tp\d*|targets?|take\s*profit|objetivos?|meta)\s*[:=\-]?\s*(open|abierto|libre|runner|pendiente|por\s+definir|sin\s+definir|none)",
            text,
            flags=re.IGNORECASE,
        ):
            return []
        tps = _find_all_numbers(text)  # fallback amplio
    if not _has_tp_keyword(text):
        return []
    # dedup preservando orden
    seen = set(); out=[]
    for v in tps:
        if v not in seen:
            seen.add(v); out.append(v)
    # PARCHE: eliminar ordinales (1,2,3,...) cuando existan precios "reales"
    out = _clean_tp_ordinals(out)
    return out

def _clean_tp_ordinals(tps: List[float]) -> List[float]:
    """
    Elimina enteros pequeños (1,2,3,...) usados como ordinales de TP
    cuando también hay valores que parecen precios (>=10 o con decimales).
    """
    if not tps:
        return tps
    def _is_price_like(x: float) -> bool:
        return (x >= 10.0) or (abs(x - int(x)) > 1e-9)
    has_price_like = any(_is_price_like(x) for x in tps)
    if not has_price_like:
        return tps
    return [x for x in tps if (abs(x - int(x)) > 1e-9) or (x >= 10.0)]

def _extract_entry_candidates(text: str) -> List[Tuple[str, List[float]]]:
    cands: List[Tuple[str, List[float]]] = []
    norm = _normalize_text_for_search(text).lower()

    # CHANGE 1 (parte 2): permitir separadores : = -
    for m in re.finditer(r"(?:@|"+ENTRY_HINTS+r")\s*[:=\-]?\s*([+-]?\d[\d .,k]*)", norm, flags=re.IGNORECASE):
        val = _normalize_number_str(m.group(1))
        if val is not None:
            cands.append(("precio", [val]))

    # Fallback: patrones "BUY 4125" / "SELL LIMIT 1.0850" sin palabra clave de entrada.
    fallback_dir_prices: List[Tuple[str, List[float]]] = []
    for m in re.finditer(r"\b(buy|sell)\b(?:\s+(?:limit|stop))?\s*@?\s*([+-]?\d[\d .,k]*)", norm, flags=re.IGNORECASE):
        raw_num = m.group(2)
        val = _normalize_number_str(raw_num)
        if val is None:
            continue
        tail = norm[m.end(): m.end() + 8]
        if re.match(r"\s*(lot|lots|lote|lotes)\b", tail, flags=re.IGNORECASE):
            continue
        fallback_dir_prices.append(("precio", [val]))

    # Rangos con separadores: 3815-3812, 3629 – 3632, etc.
    for m in re.finditer(r"([+-]?\d[\d .,k]*)\s*"+RANGE_SEPARATORS+r"\s*([+-]?\d[\d .,k]*)", norm, flags=re.IGNORECASE):
        a = _normalize_number_str(m.group(1))
        b = _normalize_number_str(m.group(2))
        if a is not None and b is not None and a != b:
            lo, hi = (a, b) if a < b else (b, a)
            cands.append(("rango", [lo, hi]))

    # Palabras zona/area/POI/supply/demand
    if re.search(r"\b(zone|zona|área|area|poi|supply|demand|entry\s*zone|buy\s*area|sell\s*area|range)\b", norm, flags=re.IGNORECASE):
        nums = _find_all_numbers(norm)
        if len(nums) >= 2:
            lo, hi = (min(nums), max(nums))
            cands.append(("rango", [lo, hi]))
        elif len(nums) == 1:
            cands.append(("precio", [nums[0]]))

    if not cands and fallback_dir_prices:
        cands.extend(fallback_dir_prices)

    return cands

# =========================
# Dirección y acción
# =========================

def _explicit_direction(text: str) -> Optional[str]:
    if re.search(BUY_WORDS, text, flags=re.IGNORECASE):
        return "BUY"
    if re.search(SELL_WORDS, text, flags=re.IGNORECASE):
        return "SELL"
    return None

def _implicit_direction(sl: Optional[float], tps: List[float]) -> Optional[str]:
    if sl is None or not tps:
        return None
    gt = sum(1 for tp in tps if tp > sl)
    lt = sum(1 for tp in tps if tp < sl)
    if gt > 0 and lt == 0:
        return "BUY"
    if lt > 0 and gt == 0:
        return "SELL"
    return None

def _detect_action(text: str, direction: Optional[str]) -> Optional[str]:
    """
    Acción específica:
      BUY LIMIT / SELL LIMIT / BUY STOP / SELL STOP
      Si no hay limit/stop explícito, BUY o SELL (si hay dirección).
    """
    low = text.lower()

    def _has(pattern: str) -> bool:
        return re.search(pattern, low, flags=re.IGNORECASE) is not None

    # Detectar expresiones explícitas aunque la dirección aún no esté resuelta
    if _has(r"\bbuy\s+limit\b") or _has(r"\blimit\s+buy\b"):
        return "BUY LIMIT"
    if _has(r"\bbuy\s+stop\b") or _has(r"\bstop\s+buy\b"):
        return "BUY STOP"
    if _has(r"\bsell\s+limit\b") or _has(r"\blimit\s+sell\b"):
        return "SELL LIMIT"
    if _has(r"\bsell\s+stop\b") or _has(r"\bstop\s+sell\b"):
        return "SELL STOP"

    # Si no hay palabras compuestas, usar la dirección genérica
    if direction == "BUY":
        return "BUY"
    if direction == "SELL":
        return "SELL"
    return None

# =========================
# Consistencia, normalización de escala y score
# =========================

def _entrada_utilizable(entrada_obj: Dict[str, Any],
                        accion: Optional[str]) -> Tuple[Optional[float], Optional[str]]:
    typ = entrada_obj.get("tipo")
    vals = entrada_obj.get("valores")
    if typ == "precio" and vals is not None:
        return float(vals), "precio"
    if typ == "rango" and isinstance(vals, list) and len(vals) == 2 and accion:
        lo, hi = float(vals[0]), float(vals[1])
        if accion.startswith("BUY"):
            return lo, "rango"
        if accion.startswith("SELL"):
            return hi, "rango"
    return None, None

def _check_consistency(direction: str,
                       usable_entry: Optional[float],
                       sl: Optional[float],
                       tps: List[float]) -> Optional[bool]:
    if direction not in ("BUY", "SELL") or usable_entry is None or sl is None or not tps:
        return None
    if direction == "BUY":
        return bool(sl < usable_entry and any(tp > usable_entry for tp in tps))
    else:
        return bool(any(tp < usable_entry for tp in tps) and usable_entry < sl)

# CHANGE 3: normalizador de escala (conservador)
def _normalizar_escala(direction: str,
                       entry: Optional[float],
                       sl: Optional[float],
                       tps: List[float]) -> Tuple[Optional[float], Optional[float], List[float], Optional[str]]:
    if direction not in ("BUY", "SELL") or entry is None or sl is None or not tps:
        return entry, sl, tps, None

    def _digits(x: float) -> int:
        try:
            return len(str(int(abs(float(x)))))
        except Exception:
            return 0

    nums = [entry, sl] + list(tps)
    lens = [_digits(v) for v in nums]
    # moda de longitudes
    from collections import Counter
    major = Counter(lens).most_common(1)[0][0]

    # desviaciones exactamente ±1
    dev = [i for i, L in enumerate(lens) if abs(L - major) == 1]
    if not dev:
        return entry, sl, tps, None

    entry_idx = 0
    others_idx = list(range(1, len(nums)))

    def _accept(e, s, T):
        c = _check_consistency(direction, e, s, T)
        return (c is True)

    # caso A: solo la entrada es minoría
    if dev == [entry_idx]:
        factor = 10.0 if lens[entry_idx] < major else 0.1
        e2 = entry * factor
        if _accept(e2, sl, tps):
            note = f"Autoajuste escala: entry {'×10' if factor==10.0 else '÷10'} ({lens[entry_idx]}→{major} dígitos)"
            return e2, sl, tps, note
        return entry, sl, tps, None

    # caso B: todos los demás (SL+TPs) son minoría
    if all(i in dev for i in others_idx):
        base_len = lens[1]  # longitud de SL
        factor = 10.0 if base_len < major else 0.1
        s2 = sl * factor
        T2 = [tp * factor for tp in tps]
        if _accept(entry, s2, T2):
            note = f"Autoajuste escala: SL/TP {'×10' if factor==10.0 else '÷10'} ({base_len}→{major} dígitos)"
            return entry, s2, T2, note
        return entry, sl, tps, None

    # otros casos: no tocamos
    return entry, sl, tps, None

# === PARCHE MÍNIMO: filtrar TPs por lado y exigir TP1 válido ===
def _filtrar_tps_y_validar_tp1(direction: str,
                               entry: Optional[float],
                               tps: List[float]) -> Tuple[List[float], Optional[bool]]:
    """
    PARCHE: descarta TPs del lado incorrecto y exige TP1 válido.
    Devuelve (tps_filtrados, tp1_ok).
      - BUY  => válidos si tp > entry
      - SELL => válidos si tp < entry
    Si entry es None o no hay dirección, devuelve (tps, None).
    """
    if entry is None or direction not in ("BUY", "SELL") or not tps:
        return tps, None

    def _ok(tp: float) -> bool:
        return (tp > entry) if direction == "BUY" else (tp < entry)

    tp1_ok = _ok(tps[0])
    filtrados = [tp for tp in tps if _ok(tp)]
    return filtrados, tp1_ok

def _decidir_score(data: Dict[str, Any]) -> int:
    """
    10 si: clasificacion=Válido AND accion definida AND entrada utilizable AND SL AND ≥1 TP
           AND la coherencia direccional no es False.
    Caso especial PARTIAL CLOSE: score=10 si accion=PARTIAL CLOSE (requisitos más flexibles).
    Caso especial CLOSEALL: score=10 si accion=CLOSEALL (requisitos más flexibles).
    Caso especial BREAKEVEN: score=10 si accion=BREAKEVEN (requisitos más flexibles).
    Caso especial MOVETO: score=10 si accion=MOVETO AND sl definido (requisitos más flexibles).
    Caso especial STOPLOSSESTO: score=10 si accion=STOPLOSSESTO AND sl definido (requisitos más flexibles).
    """
    es_valido = (data.get("clasificacion") == "Válido")
    accion = data.get("accion")
    
    # Caso especial: PARTIAL CLOSE (prioridad 1)
    if accion == "PARTIAL CLOSE" and es_valido:
        return 10  # PARTIAL CLOSE tiene score=10 sin requerir entrada, SL o TP explícitos
    
    # Caso especial: CLOSEALL (prioridad 2)
    if accion == "CLOSEALL" and es_valido:
        return 10  # CLOSEALL tiene score=10 sin requerir entrada, SL o TP explícitos
    
    # Caso especial: BREAKEVEN
    if accion == "BREAKEVEN" and es_valido:
        return 10  # Breakeven tiene score=10 sin requerir entrada, SL o TP explícitos
    
    # Caso especial: MOVETO
    if accion == "MOVETO" and es_valido:
        sl_ok = (data.get("sl") is not None)
        if sl_ok:
            return 10  # MOVETO tiene score=10 si tiene SL definido
    
    # Caso especial: STOPLOSSESTO
    if accion == "STOPLOSSESTO" and es_valido:
        sl_ok = (data.get("sl") is not None)
        if sl_ok:
            return 10  # STOPLOSSESTO tiene score=10 si tiene SL definido
    
    # Caso normal: requisitos estrictos
    entrada_resuelta = (data.get("entrada_resuelta"))
    sl_ok = (data.get("sl") is not None)
    tp_ok = bool(data.get("tp") or [])
    coherente = (data.get("consistencia_direccion") is not False)  # CHANGE 2
    if es_valido and accion and (entrada_resuelta is not None) and sl_ok and tp_ok and coherente:
        return 10
    return 0

# =========================
# Helpers de salida
# =========================

def _es_valido(texto: str, activos: List[str]) -> bool:
    # Caso especial: partial close (no requiere TP explícito, activo puede inferirse del canal)
    if _has_partial_close_keyword(texto):
        return True  # PARTIAL CLOSE es válido incluso sin activo explícito o TP
    # Caso especial: closeall (no requiere TP explícito, activo puede inferirse del canal)
    if _has_closeall_keyword(texto):
        return True  # CLOSEALL es válido incluso sin activo explícito o TP
    # Caso especial: breakeven (no requiere TP explícito, activo puede inferirse del canal)
    if _has_breakeven_keyword(texto):
        return True  # Breakeven es válido incluso sin activo explícito o TP
    # Caso normal: requiere activo + SL + TP
    return bool(activos) and _has_sl_keyword(texto) and _has_tp_keyword(texto)

# >>> ÚNICO CAMBIO DE ESTRUCTURA: devolver escalar para 'precio'
def _consolidar_entrada(cands: List[Tuple[str, List[float]]]) -> Dict[str, Any]:
    if not cands:
        return {"tipo": "no_encontrada", "valores": []}
    rangos = [v for t, v in cands if t == "rango"]
    precios_raw = [v for t, v in cands if t == "precio"]

    # Normaliza precios: si vienen como [valor], usa el escalar; acepta también valor directo
    precios: List[float] = []
    for p in precios_raw:
        if isinstance(p, list):
            if p:
                precios.append(p[0])
        else:
            precios.append(p)

    if rangos:
        if len(rangos) == 1:
            return {"tipo": "rango", "valores": rangos[0]}
        # múltiples rangos -> los aplanamos (no resolvemos a precio)
        flat: List[float] = []
        for lo, hi in rangos:
            flat.extend([lo, hi])
        return {"tipo": "multiple", "valores": flat}
    if precios:
        if len(precios) == 1:
            return {"tipo": "precio", "valores": precios[0]}
        return {"tipo": "multiple", "valores": precios}
    return {"tipo": "no_encontrada", "valores": []

}

def _build_output(clasificacion: str,
                  activo: Optional[str],
                  accion: Optional[str],
                  direccion: str,
                  entrada_obj: Dict[str, Any],
                  sl: Optional[float],
                  tps: List[float],
                  entrada_resuelta: Optional[float],
                  entrada_fuente: Optional[str],
                  consistencia: Optional[bool],
                  observaciones: Optional[str]) -> Dict[str, Any]:
    out = {
        "clasificacion": clasificacion,
        "activo": (activo or ""),
        "accion": accion if accion else None,
        "direccion": direccion if direccion else "INDETERMINADA",
        "entrada": entrada_obj,
        "entrada_resuelta": entrada_resuelta if entrada_resuelta is not None else None,
        "entrada_fuente": entrada_fuente if entrada_fuente else None,
        "sl": sl if sl is not None else None,   # <- FIX: 'is' en vez de 'es'
        "tp": tps if tps else [],
    }
    if consistencia is not None:
        out["consistencia_direccion"] = bool(consistencia)
    if observaciones:
        out["observaciones"] = observaciones
    return out


def _accion_a_etiqueta(accion: Optional[str]) -> Optional[str]:
    if not accion:
        return None
    upper = accion.upper()
    if upper.startswith("BUY"):
        return "COMPRAR"
    if upper.startswith("SELL"):
        return "VENDER"
    return None


def _fmt_num(valor: Optional[float]) -> Optional[str]:
    if valor is None:
        return None
    try:
        num = float(valor)
    except (TypeError, ValueError):
        return None
    texto = f"{num:.5f}".rstrip("0").rstrip(".")
    return texto if texto else str(int(num))


def formatear_senal(senal: Dict[str, Any]) -> Optional[str]:
    """
    Formatea una señal con score=10 al template:
    COMPRAR/VENDER - ACTIVO - PRECIO|(LO-HI)

    SL: X

    TP1: X
    TP2: X
    TP3: X
    (y todos los TPs adicionales disponibles)
    
    Para acciones especiales (BREAKEVEN, MOVETO, STOPLOSSESTO, PARTIAL CLOSE, CLOSEALL),
    devuelve solo el nombre de la acción detectada.
    """
    if not senal or int(senal.get("score", 0)) != 10:
        return None

    accion = senal.get("accion")
    
    # Casos especiales: devolver solo el nombre de la acción
    acciones_especiales = ["BREAKEVEN", "MOVETO", "STOPLOSSESTO", "PARTIAL CLOSE", "CLOSEALL"]
    if accion in acciones_especiales:
        return accion

    accion_txt = _accion_a_etiqueta(accion)
    if not accion_txt:
        return None

    activo = senal.get("activo") or "#Divisa#"

    entrada_obj = senal.get("entrada") or {}
    entrada_tipo = entrada_obj.get("tipo")
    entrada_valores = entrada_obj.get("valores")
    entrada_resuelta = senal.get("entrada_resuelta")

    if entrada_tipo == "rango" and isinstance(entrada_valores, list) and len(entrada_valores) == 2:
        lo, hi = entrada_valores
        lo_txt = _fmt_num(lo)
        hi_txt = _fmt_num(hi)
        entrada_txt = f"({lo_txt}-{hi_txt})" if lo_txt and hi_txt else None
    elif entrada_tipo == "precio":
        entrada_txt = _fmt_num(entrada_resuelta if entrada_resuelta is not None else entrada_valores)
    else:
        entrada_txt = _fmt_num(entrada_resuelta)

    if not entrada_txt:
        return None

    sl_txt = _fmt_num(senal.get("sl"))
    if not sl_txt:
        return None

    tps = senal.get("tp") or []
    tp_fmt = [_fmt_num(tp) for tp in tps]
    # Mostrar todos los TPs disponibles
    lineas = [
        f"{accion_txt} - {activo} - {entrada_txt}",
        "",
        f"SL: {sl_txt}",
        "",
    ]
    # Mostrar todos los TPs disponibles (sin límite)
    for idx, val in enumerate(tp_fmt, start=1):
        if val:
            lineas.append(f"TP{idx}: {val}")

    return "\n".join(lineas)

# =========================
# API principal
# =========================

def clasificar_mensajes(texto: str) -> List[Dict[str, Any]]:
    """
    Devuelve lista de operaciones (dict) — una por activo detectado.
    Cada operación incluye 'score' (0|10) y, si procede, 'entrada_resuelta' y 'entrada_fuente'.
    """
    # (typo arreglado) or en lugar de o
    if not texto or not texto.strip():
        base = _build_output(
            "Ruido", None, None, "INDETERMINADA",
            {"tipo": "no_encontrada", "valores": []},
            None, [], None, None, None, "Mensaje vacío"
        )
        base["score"] = _decidir_score(base)
        return [base]

    text_search = _normalize_text_for_search(texto)
    
    # PRIORIDAD 1: Detectar PARTIAL CLOSE antes que cualquier otro caso
    es_partial_close = _has_partial_close_keyword(text_search)
    if es_partial_close:
        # Construir resultado especial para PARTIAL CLOSE
        activos = _find_assets(text_search)
        activo = activos[0] if activos else None
        
        out = {
            "clasificacion": "Válido",
            "activo": activo or "",
            "accion": "PARTIAL CLOSE",
            "direccion": "INDETERMINADA",
            "entrada": {"tipo": "no_encontrada", "valores": []},
            "entrada_resuelta": None,  # No se requiere entrada
            "entrada_fuente": None,
            "sl": None,  # No se requiere SL
            "tp": [],  # No se requieren TPs
            "consistencia_direccion": None,  # No aplica
        }
        out["score"] = _decidir_score(out)
        return [out]
    
    # PRIORIDAD 2: Detectar CLOSEALL antes que MOVETO y BREAKEVEN
    es_closeall = _has_closeall_keyword(text_search)
    if es_closeall:
        # Construir resultado especial para CLOSEALL
        activos = _find_assets(text_search)
        activo = activos[0] if activos else None
        
        out = {
            "clasificacion": "Válido",
            "activo": activo or "",
            "accion": "CLOSEALL",
            "direccion": "INDETERMINADA",
            "entrada": {"tipo": "no_encontrada", "valores": []},
            "entrada_resuelta": None,  # No se requiere entrada
            "entrada_fuente": None,
            "sl": None,  # No se requiere SL
            "tp": [],  # No se requieren TPs
            "consistencia_direccion": None,  # No aplica
        }
        out["score"] = _decidir_score(out)
        return [out]
    
    # PRIORIDAD 3: Detectar MOVETO antes del procesamiento normal
    moveto_result = _detect_move_sl(texto)
    if moveto_result:
        # Construir resultado especial para MOVETO
        activos = _find_assets(text_search)
        activo = activos[0] if activos else None
        
        out = {
            "clasificacion": "Válido",
            "activo": activo or "",
            "accion": "MOVETO",
            "direccion": "INDETERMINADA",
            "entrada": {"tipo": "no_encontrada", "valores": []},
            "entrada_resuelta": None,  # No se requiere entrada
            "entrada_fuente": None,
            "sl": moveto_result['sl'],  # El nuevo valor del SL
            "tp": [],  # No se requieren TPs
            "consistencia_direccion": None,  # No aplica
        }
        out["score"] = _decidir_score(out)
        return [out]
    
    activos = _find_assets(text_search)
    
    # Detectar si es mensaje de breakeven
    es_breakeven = _has_breakeven_keyword(text_search)
    
    es_val = _es_valido(text_search, activos)

    sl = _extract_sl(text_search)
    tps = _extract_tps(text_search)

    dir_exp = _explicit_direction(text_search)
    dir_imp = _implicit_direction(sl, tps)
    direccion = dir_exp or dir_imp or "INDETERMINADA"

    entradas_cands = _extract_entry_candidates(text_search)
    entrada_obj = _consolidar_entrada(entradas_cands)

    # Acción específica: si es breakeven, establecer BREAKEVEN; si no, detectar normalmente
    if es_breakeven:
        accion = "BREAKEVEN"
    else:
        accion = _detect_action(text_search, dir_exp or dir_imp)

    # Resuelve entrada utilizable (precio o rango→precio según acción)
    entrada_resuelta, entrada_fuente = _entrada_utilizable(entrada_obj, accion)

    # CHANGE 3: normalizar escala si arregla coherencia (antes de evaluarla)
    entrada_resuelta, sl, tps, _nota_escala = _normalizar_escala(direccion, entrada_resuelta, sl, tps)

    # === PARCHE: filtrar TPs por lado y exigir TP1 correcto ===
    tps, _tp1_ok = _filtrar_tps_y_validar_tp1(direccion, entrada_resuelta, tps)

    # Consistencia con entrada utilizable (si se puede evaluar)
    consistencia = _check_consistency(direccion, entrada_resuelta, sl, tps)

    # Si TP1 no es válido, la señal no es válida (score=0)
    if _tp1_ok is False:
        consistencia = False

    # Observaciones (solo para el caso Ruido / avisos)
    obs_parts: List[str] = []
    if dir_exp and dir_imp and dir_exp != dir_imp:
        obs_parts.append(f"Dirección explícita ({dir_exp}) difiere de la implícita ({dir_imp}).")
    if not _has_sl_keyword(text_search):
        obs_parts.append("Falta palabra clave de SL.")
    if not _has_tp_keyword(text_search):
        obs_parts.append("Falta palabra clave de TP.")
    if not activos:
        obs_parts.append("No se detectó activo.")
    if _nota_escala:
        obs_parts.append(_nota_escala)
    observaciones = "; ".join(obs_parts) if obs_parts else None

    # Construcción de salidas
    salidas: List[Dict[str, Any]] = []
    if not es_val:
        base = _build_output("Ruido", activos[0] if activos else None, accion, direccion,
                             entrada_obj, sl, tps, entrada_resuelta, entrada_fuente, consistencia, observaciones)
        base["score"] = _decidir_score(base)
        return [base]

    # Es Válido: una salida por activo
    for act in (activos or [None]):
        base = _build_output("Válido", act, accion, direccion,
                             entrada_obj, sl, tps, entrada_resuelta, entrada_fuente, consistencia, observaciones)
        base["score"] = _decidir_score(base)
        salidas.append(base)

    return salidas

# =========================
# Ejecución manual
# =========================
if __name__ == "__main__":
    ejemplos = [
        "XAUUSD BUY @3814.5 SL 3809.5 TP 3820, 3825, 3830",
        "US100 sell area 18115 – 18090 SL 18240 TP1 18010 TP2 17960",
        "Bitcoin 🚀 TP 72000 SL 65500 #btc (sin dirección explícita)",
        "Oro long zone 2390-2384, TP 2405 / 2412, SL 2378",
        "EURUSD BUY LIMIT 1.0805-1.0795 SL 1.0780 TP 1.0840",
        "Mensaje random sin nada útil",
    ]
    for msg in ejemplos:
        print(">>", msg)
        for r in clasificar_mensajes(msg):
            print(r)
        print("-"*80)

