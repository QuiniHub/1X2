"""Scraper gratuito de la Liga F (futbol femenino espanol) a partir de Wikipedia.

Genera:
  data/liga_f/clasificacion.json  -> clasificacion + estadisticas por equipo
  data/liga_f/resultados.json     -> lista de partidos jugados

Los nombres de equipo se normalizan a los que usa La Quiniela, con sufijo " (F)".
Si la descarga falla se conservan los ficheros previos y se anota un aviso.

Uso: python -X utf8 actualizar_liga_f.py
"""

from __future__ import annotations

import json
import re
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data" / "liga_f"
FICHERO_CLASIFICACION = DATA_DIR / "clasificacion.json"
FICHERO_RESULTADOS = DATA_DIR / "resultados.json"

TEMPORADA = "2026/2027"
FUENTES = [
    "https://en.wikipedia.org/wiki/2026%E2%80%9327_Liga_F",
    "https://es.wikipedia.org/wiki/Liga_F_2026-27",
]
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
TIMEOUT = 30
MIN_EQUIPOS = 10

# ---------------------------------------------------------------------------
# Nombres: canonico (como en La Quiniela) -> alias que aparecen en Wikipedia,
# en LAE (mayusculas abreviadas) o en la prensa.
# ---------------------------------------------------------------------------
CANONICOS_LIGA_F: dict[str, list[str]] = {
    "Athletic Club (F)": ["Athletic", "ATH", "Athletic Bilbao", "Ath.Club", "Ath Club", "Athletic Club Femenino"],
    "Real Madrid (F)": ["Real Madrid", "R.Madrid", "R. Madrid", "Real Madrid Femenino", "RMA"],
    "Eibar (F)": ["SD Eibar", "Eibar", "EIB"],
    "Real Sociedad (F)": ["Real Sociedad", "R.Sociedad", "R. Sociedad", "Real Sociedad de Futbol", "RSO"],
    "Logroño (F)": ["Logroño United", "DUX Logroño", "Logrono United", "EDF Logroño", "Logroño", "LOG"],
    "Sevilla (F)": ["Sevilla FC", "Sevilla", "SEV"],
    "Tenerife (F)": ["Costa Adeje Tenerife", "UDG Tenerife", "Granadilla", "UD Granadilla Tenerife",
                     "Tenerife", "Granadilla Tenerife", "TEN"],
    "Alavés (F)": ["Deportivo Alavés", "Alavés Gloriosas", "Deportivo Alavés Gloriosas", "Alaves", "ALA"],
    "Valencia (F)": ["Valencia CF", "Valencia", "VAL"],
    "Granada (F)": ["Granada CF", "Granada", "GRA"],
    "At. Madrid (F)": ["Atlético Madrid", "Atlético de Madrid", "Atletico Madrid", "At. Madrid", "At.Madrid",
                       "Atl. Madrid", "Atlético", "Atletico", "Atlético de Madrid Femenino", "ATM"],
    "Barcelona (F)": ["FC Barcelona", "Barcelona", "FC Barcelona Femení", "Barça", "BAR"],
    "Levante (F)": ["Levante UD", "Levante", "LEV"],
    "Madrid CFF (F)": ["Madrid CFF", "Madrid Club de Fútbol Femenino", "MAD"],
    "Espanyol (F)": ["RCD Espanyol", "Espanyol", "Espanyol de Barcelona", "ESP"],
    "Deportivo (F)": ["Deportivo Abanca", "Deportivo de La Coruña", "Deportivo La Coruña", "Dépor Abanca",
                      "RC Deportivo", "Deportivo", "DEP"],
    "Badalona (F)": ["Badalona Women", "Levante Badalona", "Levante Las Planas", "Las Planas", "Badalona",
                     "CE Europa Badalona", "LBA"],
    "Villarreal (F)": ["Villarreal CF", "Villarreal", "VIL"],
    "Real Betis (F)": ["Real Betis", "Betis", "Real Betis Féminas", "BET"],
    "Sporting Huelva (F)": ["Sporting de Huelva", "Sporting Huelva", "Sporting Club de Huelva", "HUE"],
}

PALABRAS_VACIAS = {
    "club", "cf", "cd", "sd", "ud", "de", "del", "la", "el", "futbol", "femenino", "femeni",
    "women", "united", "fc", "rcd", "rc", "ca", "sad", "f",
}


def _sin_acentos(texto: str) -> str:
    descompuesto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in descompuesto if not unicodedata.combining(c))


def clave_liga_f(nombre: str) -> str:
    """Clave robusta para casar nombres: sin sufijo (F), sin acentos ni palabras vacias."""
    if not nombre:
        return ""
    texto = _sin_acentos(str(nombre)).lower()
    texto = re.sub(r"\(\s*f\s*\)", " ", texto)
    texto = re.sub(r"\[[^\]]*\]", " ", texto)  # notas tipo [a]
    texto = re.sub(r"[^a-z0-9]+", " ", texto)
    palabras = [p for p in texto.split() if p not in PALABRAS_VACIAS]
    return " ".join(palabras)


def _construir_indice_alias() -> dict[str, str]:
    indice: dict[str, str] = {}
    for canonico, alias in CANONICOS_LIGA_F.items():
        for nombre in [canonico, *alias]:
            clave = clave_liga_f(nombre)
            if clave:
                indice.setdefault(clave, canonico)
    return indice


INDICE_ALIAS = _construir_indice_alias()


def nombre_canonico_liga_f(nombre: str) -> str | None:
    """Devuelve el nombre con sufijo (F) que usa La Quiniela, o None si no se reconoce."""
    clave = clave_liga_f(nombre)
    if not clave:
        return None
    if clave in INDICE_ALIAS:
        return INDICE_ALIAS[clave]
    # Casado parcial: una clave contenida en la otra (p.ej. "costa adeje tenerife" vs "tenerife")
    candidatos = []
    for clave_alias, canonico in INDICE_ALIAS.items():
        if len(clave_alias) < 4:
            continue
        if f" {clave_alias} " in f" {clave} " or f" {clave} " in f" {clave_alias} ":
            candidatos.append((len(clave_alias), canonico))
    if candidatos:
        candidatos.sort(reverse=True)
        return candidatos[0][1]
    return None


def normalizar_equipo(nombre: str) -> str:
    """Nombre canonico si se reconoce; si no, el nombre limpio con sufijo (F)."""
    canonico = nombre_canonico_liga_f(nombre)
    if canonico:
        return canonico
    limpio = re.sub(r"\[[^\]]*\]", "", str(nombre)).strip()
    limpio = re.sub(r"\s*\(\s*F\s*\)\s*$", "", limpio, flags=re.IGNORECASE)
    return f"{limpio} (F)" if limpio else ""


# ---------------------------------------------------------------------------
# Descarga
# ---------------------------------------------------------------------------
def descargar(url: str) -> str:
    respuesta = requests.get(url, headers={"User-Agent": USER_AGENT, "Accept-Language": "en,es"}, timeout=TIMEOUT)
    respuesta.raise_for_status()
    return respuesta.text


# ---------------------------------------------------------------------------
# Utilidades de tablas
# ---------------------------------------------------------------------------
def _texto_celda(celda) -> str:
    for sup in celda.find_all("sup"):
        sup.decompose()
    texto = celda.get_text(" ", strip=True)
    texto = re.sub(r"\[[^\]]*\]", "", texto)
    texto = texto.replace("−", "-").replace("–", "-").replace("—", "-")
    return re.sub(r"\s+", " ", texto).strip()


def _expandir_tabla(tabla) -> list[list[str]]:
    """Convierte una <table> en una rejilla de textos respetando rowspan/colspan."""
    rejilla: list[list[str]] = []
    pendientes: dict[tuple[int, int], str] = {}
    for fila_idx, fila in enumerate(tabla.find_all("tr")):
        fila_textos: list[str] = []
        col = 0
        celdas = fila.find_all(["th", "td"], recursive=False)
        for celda in celdas:
            while (fila_idx, col) in pendientes:
                fila_textos.append(pendientes.pop((fila_idx, col)))
                col += 1
            texto = _texto_celda(celda)
            try:
                rowspan = int(celda.get("rowspan", 1) or 1)
            except ValueError:
                rowspan = 1
            try:
                colspan = int(celda.get("colspan", 1) or 1)
            except ValueError:
                colspan = 1
            for c in range(colspan):
                fila_textos.append(texto)
                for r in range(1, rowspan):
                    pendientes[(fila_idx + r, col + c)] = texto
            col += colspan
        while (fila_idx, col) in pendientes:
            fila_textos.append(pendientes.pop((fila_idx, col)))
            col += 1
        rejilla.append(fila_textos)
    return rejilla


def _entero(texto: str) -> int | None:
    texto = (texto or "").replace(" ", "").replace(",", "")
    coincidencia = re.search(r"[+-]?\d+", texto)
    return int(coincidencia.group(0)) if coincidencia else None


RE_MARCADOR = re.compile(r"^\s*(\d+)\s*[-–—:]\s*(\d+)\s*$")


def _marcador(texto: str) -> tuple[int, int] | None:
    coincidencia = RE_MARCADOR.match((texto or "").replace("–", "-"))
    if not coincidencia:
        return None
    return int(coincidencia.group(1)), int(coincidencia.group(2))


# ---------------------------------------------------------------------------
# Clasificacion
# ---------------------------------------------------------------------------
CABECERAS_CLASIFICACION = {
    "pj": {"pld", "pj", "p", "mp", "gp", "j"},
    "g": {"w", "pg", "g", "v"},
    "e": {"d", "pe", "e"},
    "p": {"l", "pp", "p"},
    "gf": {"gf"},
    "gc": {"ga", "gc"},
    "dg": {"gd", "dg", "dif", "+/-"},
    "pts": {"pts", "pt", "puntos", "points"},
}


def _mapear_cabecera_clasificacion(cabecera: list[str]) -> dict[str, int] | None:
    normalizada = [clave_liga_f(c).replace(" ", "") or c.strip().lower() for c in cabecera]
    mapa: dict[str, int] = {}
    # 'p' es ambiguo (Pld en ingles / PP en espanol): se resuelve por orden tras asignar el resto.
    for idx, col in enumerate(normalizada):
        for campo, nombres in CABECERAS_CLASIFICACION.items():
            if campo in mapa or col == "p":
                continue
            if col in nombres:
                mapa[campo] = idx
                break
    for idx, col in enumerate(normalizada):
        if col == "p" and "pj" in mapa and "p" not in mapa and idx > mapa["pj"]:
            mapa["p"] = idx
        elif col == "p" and "pj" not in mapa:
            mapa["pj"] = idx
    if {"pj", "g", "e", "p", "gf", "gc", "pts"} <= set(mapa):
        return mapa
    return None


def parsear_clasificacion(html: str) -> list[dict]:
    """Extrae la tabla de clasificacion (16 equipos) de la pagina de Wikipedia."""
    sopa = BeautifulSoup(html, "lxml")
    for tabla in sopa.find_all("table"):
        rejilla = _expandir_tabla(tabla)
        if len(rejilla) < 5:
            continue
        mapa = _mapear_cabecera_clasificacion(rejilla[0])
        if not mapa:
            continue
        idx_pos = 0
        idx_equipo = min(i for i in range(len(rejilla[0])) if i not in mapa.values() and i != idx_pos) \
            if len(rejilla[0]) > 2 else 1
        equipos = []
        for fila in rejilla[1:]:
            if len(fila) <= max(mapa.values()):
                continue
            posicion = _entero(fila[idx_pos])
            nombre_fuente = fila[idx_equipo].strip()
            pts = _entero(fila[mapa["pts"]])
            pj = _entero(fila[mapa["pj"]])
            if posicion is None or pts is None or pj is None or not nombre_fuente:
                continue
            equipos.append({
                "posicion": posicion,
                "equipo": normalizar_equipo(nombre_fuente),
                "equipo_fuente": nombre_fuente,
                "pj": pj,
                "g": _entero(fila[mapa["g"]]) or 0,
                "e": _entero(fila[mapa["e"]]) or 0,
                "p": _entero(fila[mapa["p"]]) or 0,
                "gf": _entero(fila[mapa["gf"]]) or 0,
                "gc": _entero(fila[mapa["gc"]]) or 0,
                "pts": pts,
            })
        if len(equipos) >= MIN_EQUIPOS:
            for eq in equipos:
                eq["dg"] = eq["gf"] - eq["gc"]
            return equipos
    return []


# ---------------------------------------------------------------------------
# Resultados: tablas por jornada ("Game day N" / "Jornada N") con fecha
# ---------------------------------------------------------------------------
MESES = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6, "july": 7,
    "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6, "julio": 7,
    "agosto": 8, "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
}


def _parsear_fecha(texto: str) -> str | None:
    texto = (texto or "").strip().lower()
    coincidencia = re.search(r"(\d{1,2})\s+(?:de\s+)?([a-z]+)\s+(?:de\s+)?(\d{4})", texto)
    if coincidencia and coincidencia.group(2) in MESES:
        dia, mes, anio = int(coincidencia.group(1)), MESES[coincidencia.group(2)], int(coincidencia.group(3))
        return f"{anio:04d}-{mes:02d}-{dia:02d}"
    coincidencia = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})", texto)
    if coincidencia:
        return f"{int(coincidencia.group(3)):04d}-{int(coincidencia.group(2)):02d}-{int(coincidencia.group(1)):02d}"
    coincidencia = re.search(r"(\d{4})-(\d{2})-(\d{2})", texto)
    if coincidencia:
        return coincidencia.group(0)
    return None


RE_JORNADA = re.compile(r"(?:game\s*day|matchday|round|jornada)\s*(\d+)", re.IGNORECASE)


def parsear_resultados_jornadas(html: str) -> list[dict]:
    """Extrae partidos con fecha de las tablas 'Game day N' (local, marcador, visitante, fecha)."""
    sopa = BeautifulSoup(html, "lxml")
    partidos: list[dict] = []
    vistos: set[tuple[str, str]] = set()
    for tabla in sopa.find_all("table"):
        rejilla = _expandir_tabla(tabla)
        if len(rejilla) < 3:
            continue
        jornada = None
        for celda in rejilla[0]:
            coincidencia = RE_JORNADA.search(celda)
            if coincidencia:
                jornada = int(coincidencia.group(1))
                break
        cabecera_idx = None
        for i, fila in enumerate(rejilla[:3]):
            claves = [clave_liga_f(c) for c in fila]
            if any(c in {"home team", "home", "local", "equipo local"} for c in claves) and \
               any(c in {"away team", "away", "visitante", "equipo visitante"} for c in claves):
                cabecera_idx = i
                break
        if cabecera_idx is None:
            continue
        claves = [clave_liga_f(c) for c in rejilla[cabecera_idx]]
        idx_local = next(i for i, c in enumerate(claves) if c in {"home team", "home", "local", "equipo local"})
        idx_visit = next(i for i, c in enumerate(claves) if c in {"away team", "away", "visitante", "equipo visitante"})
        idx_res = next((i for i, c in enumerate(claves) if c in {"results", "result", "score", "resultado", "marcador"}), None)
        idx_fecha = next((i for i, c in enumerate(claves) if c in {"date", "fecha"}), None)
        if idx_res is None:
            continue
        for fila in rejilla[cabecera_idx + 1:]:
            if len(fila) <= max(idx_local, idx_visit, idx_res):
                continue
            marcador = _marcador(fila[idx_res])
            if not marcador:
                continue
            local = normalizar_equipo(fila[idx_local])
            visitante = normalizar_equipo(fila[idx_visit])
            if not local or not visitante or (local, visitante) in vistos:
                continue
            vistos.add((local, visitante))
            fecha = _parsear_fecha(fila[idx_fecha]) if idx_fecha is not None and idx_fecha < len(fila) else None
            partidos.append({
                "jornada": jornada,
                "fecha": fecha,
                "local": local,
                "visitante": visitante,
                "goles_local": marcador[0],
                "goles_visitante": marcador[1],
                "signo": "1" if marcador[0] > marcador[1] else ("X" if marcador[0] == marcador[1] else "2"),
                "fuente": "jornadas",
            })
    return partidos


# ---------------------------------------------------------------------------
# Resultados: tabla cruzada local x visitante ("Home \\ Away")
# ---------------------------------------------------------------------------
def parsear_resultados_cruzados(html: str) -> list[dict]:
    """Extrae partidos de la tabla cruzada (filas = local, columnas = visitante, celda = marcador)."""
    sopa = BeautifulSoup(html, "lxml")
    for tabla in sopa.find_all("table"):
        rejilla = _expandir_tabla(tabla)
        if len(rejilla) < 5:
            continue
        esquina = clave_liga_f(rejilla[0][0]) if rejilla[0] else ""
        if not (("home" in esquina and "away" in esquina) or ("local" in esquina and "visitante" in esquina)):
            continue
        cabecera = rejilla[0]
        filas = [f for f in rejilla[1:] if f and f[0].strip()]
        locales = [normalizar_equipo(f[0]) for f in filas]
        # Las columnas suelen ser abreviaturas en el mismo orden que las filas; se intenta
        # casar por alias y, si no, se asume el mismo orden.
        visitantes: list[str | None] = []
        for j, abreviatura in enumerate(cabecera[1:]):
            canonico = nombre_canonico_liga_f(abreviatura) if abreviatura else None
            if canonico is None and j < len(locales) and len(cabecera) - 1 == len(locales):
                canonico = locales[j]
            visitantes.append(canonico)
        partidos: list[dict] = []
        for fila, local in zip(filas, locales):
            for j, celda in enumerate(fila[1:]):
                if j >= len(visitantes) or visitantes[j] is None:
                    continue
                marcador = _marcador(celda)
                if not marcador or visitantes[j] == local:
                    continue
                partidos.append({
                    "jornada": None,
                    "fecha": None,
                    "local": local,
                    "visitante": visitantes[j],
                    "goles_local": marcador[0],
                    "goles_visitante": marcador[1],
                    "signo": "1" if marcador[0] > marcador[1] else ("X" if marcador[0] == marcador[1] else "2"),
                    "fuente": "cruzada",
                })
        if partidos:
            return partidos
    return []


def parsear_resultados(html: str) -> list[dict]:
    """Union de resultados: primero las tablas por jornada (con fecha), luego la cruzada."""
    partidos = parsear_resultados_jornadas(html)
    vistos = {(p["local"], p["visitante"]) for p in partidos}
    for partido in parsear_resultados_cruzados(html):
        clave = (partido["local"], partido["visitante"])
        if clave not in vistos:
            vistos.add(clave)
            partidos.append(partido)
    return partidos


# ---------------------------------------------------------------------------
# Estadisticas por equipo
# ---------------------------------------------------------------------------
def _bloque_vacio() -> dict:
    return {"pj": 0, "g": 0, "e": 0, "p": 0, "gf": 0, "gc": 0}


def _sumar(bloque: dict, gf: int, gc: int) -> None:
    bloque["pj"] += 1
    bloque["gf"] += gf
    bloque["gc"] += gc
    if gf > gc:
        bloque["g"] += 1
    elif gf == gc:
        bloque["e"] += 1
    else:
        bloque["p"] += 1


def _orden_fiable(partidos: list[dict]) -> bool:
    if not partidos:
        return False
    return all(p.get("fecha") for p in partidos) or all(p.get("jornada") is not None for p in partidos)


def calcular_estadisticas(clasificacion: list[dict], resultados: list[dict]) -> list[dict]:
    """Combina clasificacion y resultados en la ficha por equipo que consume el motor."""
    fichas: dict[str, dict] = {}
    for fila in clasificacion:
        pj = fila["pj"]
        fichas[fila["equipo"]] = {
            "equipo": fila["equipo"],
            "equipo_fuente": fila.get("equipo_fuente", fila["equipo"]),
            "alias": CANONICOS_LIGA_F.get(fila["equipo"], []),
            "posicion": fila["posicion"],
            "pj": pj,
            "g": fila["g"],
            "e": fila["e"],
            "p": fila["p"],
            "gf": fila["gf"],
            "gc": fila["gc"],
            "dg": fila.get("dg", fila["gf"] - fila["gc"]),
            "puntos": fila["pts"],
            "ppg": round(fila["pts"] / pj, 3) if pj else 0.0,
            "empates_pct": round(100.0 * fila["e"] / pj, 1) if pj else 0.0,
            "casa": _bloque_vacio(),
            "fuera": _bloque_vacio(),
            "forma_5": None,
            "forma_5_puntos": None,
        }

    partidos_por_equipo: dict[str, list[dict]] = {}
    for partido in resultados:
        for lado, propio, rival in (("casa", "local", "visitante"), ("fuera", "visitante", "local")):
            equipo = partido[propio]
            ficha = fichas.get(equipo)
            if ficha is None:
                continue
            gf = partido["goles_local"] if lado == "casa" else partido["goles_visitante"]
            gc = partido["goles_visitante"] if lado == "casa" else partido["goles_local"]
            _sumar(ficha[lado], gf, gc)
            partidos_por_equipo.setdefault(equipo, []).append({
                "fecha": partido.get("fecha"), "jornada": partido.get("jornada"),
                "gf": gf, "gc": gc, "rival": partido[rival], "lado": lado,
            })

    for equipo, lista in partidos_por_equipo.items():
        if not _orden_fiable(lista):
            continue
        lista.sort(key=lambda p: ((p["fecha"] or ""), (p["jornada"] or 0)))
        ultimos = lista[-5:]
        forma = ["V" if p["gf"] > p["gc"] else ("E" if p["gf"] == p["gc"] else "D") for p in ultimos]
        fichas[equipo]["forma_5"] = "".join(forma)
        fichas[equipo]["forma_5_puntos"] = sum(3 if s == "V" else (1 if s == "E" else 0) for s in forma)

    return sorted(fichas.values(), key=lambda f: f["posicion"])


# ---------------------------------------------------------------------------
# Escritura / conservacion
# ---------------------------------------------------------------------------
def _ahora_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _leer_json(ruta: Path) -> dict | None:
    try:
        return json.loads(ruta.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _escribir_json(ruta: Path, contenido: dict) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(contenido, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def escribir_salidas(equipos: list[dict], resultados: list[dict], fuente: str, avisos: list[str],
                     dir_salida: Path = DATA_DIR) -> None:
    ahora = _ahora_iso()
    jornadas = [p["jornada"] for p in resultados if p.get("jornada") is not None]
    _escribir_json(dir_salida / "clasificacion.json", {
        "version": 1,
        "temporada": TEMPORADA,
        "fuente": fuente,
        "actualizado_en": ahora,
        "jornadas_jugadas": max(jornadas) if jornadas else None,
        "avisos": avisos,
        "equipos": equipos,
    })
    _escribir_json(dir_salida / "resultados.json", {
        "version": 1,
        "temporada": TEMPORADA,
        "fuente": fuente,
        "actualizado_en": ahora,
        "avisos": avisos,
        "total": len(resultados),
        "partidos": resultados,
    })


def conservar_previo_con_aviso(aviso: str, dir_salida: Path = DATA_DIR) -> None:
    """Si la descarga falla, no se borra nada: se anade el aviso a los ficheros existentes."""
    ahora = _ahora_iso()
    for nombre, clave_lista in (("clasificacion.json", "equipos"), ("resultados.json", "partidos")):
        ruta = dir_salida / nombre
        previo = _leer_json(ruta)
        if previo is None:
            previo = {"version": 1, "temporada": TEMPORADA, "fuente": None, "actualizado_en": None, clave_lista: []}
        avisos = [a for a in previo.get("avisos", []) if not str(a).startswith("Descarga fallida")]
        avisos.append(f"Descarga fallida {ahora}: {aviso}")
        previo["avisos"] = avisos
        previo["ultimo_intento"] = ahora
        _escribir_json(ruta, previo)


# ---------------------------------------------------------------------------
# Orquestacion
# ---------------------------------------------------------------------------
def procesar_html(html: str, fuente: str) -> tuple[list[dict], list[dict], list[str]]:
    avisos: list[str] = []
    clasificacion = parsear_clasificacion(html)
    if len(clasificacion) < MIN_EQUIPOS:
        raise ValueError(f"clasificacion incompleta ({len(clasificacion)} equipos) en {fuente}")
    resultados = parsear_resultados(html)
    if not resultados:
        avisos.append("Sin resultados por partido en la fuente: casa/fuera y forma_5 no disponibles")
    elif not any(p.get("fecha") for p in resultados):
        avisos.append("Resultados sin fecha ni orden fiable: forma_5 omitida")
    no_reconocidos = sorted({f["equipo_fuente"] for f in clasificacion
                             if nombre_canonico_liga_f(f["equipo_fuente"]) is None})
    if no_reconocidos:
        avisos.append("Equipos sin alias (F) conocido: " + ", ".join(no_reconocidos))
    equipos = calcular_estadisticas(clasificacion, resultados)
    return equipos, resultados, avisos


def main(argv: list[str] | None = None) -> int:
    errores: list[str] = []
    for url in FUENTES:
        try:
            html = descargar(url)
            equipos, resultados, avisos = procesar_html(html, url)
        except Exception as exc:  # noqa: BLE001 - se prueba la siguiente fuente
            errores.append(f"{url}: {exc}")
            print(f"[liga_f] fallo en {url}: {exc}", file=sys.stderr)
            continue
        escribir_salidas(equipos, resultados, url, avisos)
        lider = equipos[0] if equipos else None
        print(f"[liga_f] OK {len(equipos)} equipos, {len(resultados)} partidos desde {url}")
        if lider:
            print(f"[liga_f] lider: {lider['equipo']} {lider['puntos']} pts en {lider['pj']} PJ")
        for aviso in avisos:
            print(f"[liga_f] aviso: {aviso}")
        return 0
    conservar_previo_con_aviso(" | ".join(errores))
    print("[liga_f] todas las fuentes fallaron; se conservan los ficheros previos", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
