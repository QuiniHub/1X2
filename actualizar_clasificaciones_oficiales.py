import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup


ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
OFICIALES = DATA / "clasificaciones_oficiales.json"

FUENTES = {
    "primera": "https://www.laliga.com/laliga-easports/clasificacion",
    "segunda": "https://www.laliga.com/laliga-hypermotion/clasificacion",
}

ALIAS = {
    "FC Barcelona": ["Barcelona", "FC Barcelona"],
    "Real Madrid CF": ["Real Madrid"],
    "Club Atlético de Madrid": ["Atlético de Madrid", "Atletico de Madrid", "Atlético"],
    "Villarreal CF": ["Villarreal"],
    "Real Betis Balompié": ["Betis", "Real Betis"],
    "RC Celta de Vigo": ["Celta", "Celta de Vigo"],
    "Rayo Vallecano de Madrid": ["Rayo", "Rayo Vallecano"],
    "Elche CF": ["Elche"],
    "RCD Espanyol de Barcelona": ["Espanyol"],
    "Athletic Club": ["Athletic"],
    "Getafe CF": ["Getafe"],
    "RCD Mallorca": ["Mallorca"],
    "CA Osasuna": ["Osasuna"],
    "Sevilla FC": ["Sevilla"],
    "Real Sociedad de Fútbol": ["Real Sociedad"],
    "Deportivo Alavés": ["Alavés", "Alaves"],
    "Levante UD": ["Levante"],
    "Valencia CF": ["Valencia"],
    "Girona FC": ["Girona"],
    "Real Oviedo": ["Oviedo", "Real Oviedo"],
    "Real Racing Club de Santander": ["Racing", "Racing Santander"],
    "RC Deportivo de La Coruña": ["Deportivo", "Deportivo La Coruña", "Deportivo La Coruna"],
    "UD Almería": ["Almería", "Almeria"],
    "UD Las Palmas": ["Las Palmas"],
    "CD Castellón": ["Castellón", "Castellon"],
    "SD Eibar": ["Eibar"],
    "Burgos CF": ["Burgos"],
    "AD Ceuta FC": ["Ceuta"],
    "Real Valladolid CF": ["Valladolid"],
    "Granada CF": ["Granada"],
    "FC Andorra": ["Andorra"],
    "Córdoba CF": ["Córdoba", "Cordoba"],
    "Real Sporting de Gijón": ["Sporting", "Sporting de Gijón", "Sporting de Gijon"],
    "Málaga CF": ["Málaga", "Malaga"],
    "Albacete Balompié": ["Albacete"],
    "CD Leganés": ["Leganés", "Leganes"],
    "Real Sociedad B": ["Real Sociedad B"],
    "Cádiz CF": ["Cádiz", "Cadiz"],
    "SD Huesca": ["Huesca"],
    "Cultural Leonesa": ["Cultural Leonesa", "Cultural"],
    "CD Mirandés": ["Mirandés", "Mirandes"],
    "Real Zaragoza": ["Zaragoza"],
}


def cargar_json(path, defecto=None):
    if defecto is None:
        defecto = {}
    if not path.exists():
        return defecto
    return json.loads(path.read_text(encoding="utf-8"))


def guardar_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def reparar_mojibake(texto):
    texto = str(texto or "")
    try:
        reparado = texto.encode("latin1").decode("utf-8")
        if "�" not in reparado:
            return reparado
    except (UnicodeEncodeError, UnicodeDecodeError):
        pass
    return texto


def normalizar(texto):
    texto = reparar_mojibake(texto).lower()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", texto).strip()


def normalizar_texto_tabla(texto):
    texto = reparar_mojibake(texto).lower()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9:+.\-]+", " ", texto).strip()


def descargar_texto(url):
    res = requests.get(
        url,
        timeout=20,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
            )
        },
    )
    res.raise_for_status()
    return BeautifulSoup(res.text, "lxml").get_text(" ", strip=True)


def patrones_alias(nombre):
    candidatos = ALIAS.get(nombre, []) + [nombre]
    vistos = set()
    for candidato in candidatos:
        clave = normalizar(candidato)
        if clave and clave not in vistos:
            vistos.add(clave)
            yield clave


def buscar_fila(texto, nombre):
    normalizado = normalizar_texto_tabla(texto)
    mejor = None
    for alias in patrones_alias(nombre):
        patron = re.compile(
            rf"(?:^|\s)(?:(\d{{1,2}})\.\s*)?{re.escape(alias)}\s+"
            r"(\d{1,2})\s+(\d{1,2})\s+(\d{1,2})\s+(\d{1,2})\s+"
            r"(\d{1,3})\s*:\s*(\d{1,3})\s+([+-]?\d{1,3})\s+(\d{1,3})(?=\s|$)",
            re.I,
        )
        match = patron.search(normalizado)
        if match and (mejor is None or match.start() < mejor.start()):
            mejor = match
    if not mejor:
        return None
    pos, pj, g, e, p, gf, gc, dg, puntos = mejor.groups()
    return {
        "match_pos": mejor.start(),
        "posicion": int(pos) if pos else None,
        "equipo": nombre,
        "pj": int(pj),
        "g": int(g),
        "e": int(e),
        "p": int(p),
        "gf": int(gf),
        "gc": int(gc),
        "dg": int(dg),
        "puntos": int(puntos),
    }


def actualizar_liga(liga, actuales):
    texto = descargar_texto(FUENTES[liga])
    filas = []
    for item in actuales:
        fila = buscar_fila(texto, item.get("equipo"))
        if fila:
            filas.append(fila)

    esperado = 20 if liga == "primera" else 22
    if len(filas) < esperado:
        print(f"Clasificacion {liga}: solo se encontraron {len(filas)}/{esperado}; se conserva la ultima valida.")
        return actuales

    filas.sort(key=lambda x: (x["posicion"] or 999, x["match_pos"]))
    for i, fila in enumerate(filas, 1):
        fila["posicion"] = fila["posicion"] or i
        fila.pop("match_pos", None)
    return filas


def main():
    data = cargar_json(OFICIALES, {})
    if not data:
        raise SystemExit("No existe data/clasificaciones_oficiales.json como base de equipos.")
    salida = dict(data)
    salida["fuentes"] = FUENTES
    for liga in ("primera", "segunda"):
        salida[liga] = actualizar_liga(liga, data.get(liga, []))
    salida["actualizado_en"] = datetime.now(timezone.utc).isoformat()
    guardar_json(OFICIALES, salida)
    print(OFICIALES)


if __name__ == "__main__":
    main()
