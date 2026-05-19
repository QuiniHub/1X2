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
PUBLICA = ROOT / "clasificaciones.json"

FUENTE_CLASIFICACION = "https://www.quinielafutbol.info/clasificacion.html"
FUENTES = {
    "primera": FUENTE_CLASIFICACION,
    "segunda": FUENTE_CLASIFICACION,
}

CANONICOS = {
    "fc barcelona": "FC Barcelona",
    "barcelona": "FC Barcelona",
    "real madrid": "Real Madrid CF",
    "atletico madrid": "Club Atletico de Madrid",
    "villareal cf": "Villarreal CF",
    "villarreal cf": "Villarreal CF",
    "real betis": "Real Betis Balompie",
    "celta": "RC Celta de Vigo",
    "getafe cf": "Getafe CF",
    "rayo vallecano": "Rayo Vallecano de Madrid",
    "valencia cf": "Valencia CF",
    "real sociedad": "Real Sociedad de Futbol",
    "rcd espanyol de barcelona": "RCD Espanyol de Barcelona",
    "athletic club": "Athletic Club",
    "sevilla fc": "Sevilla FC",
    "deportivo alaves": "Deportivo Alaves",
    "levante ud": "Levante UD",
    "ca osasuna": "CA Osasuna",
    "elche cf": "Elche CF",
    "girona fc": "Girona FC",
    "rcd mallorca": "RCD Mallorca",
    "real oviedo": "Real Oviedo",
    "r racing club": "Real Racing Club de Santander",
    "rc deportivo": "RC Deportivo de La Coruna",
    "ud almeria": "UD Almeria",
    "malaga cf": "Malaga CF",
    "ud las palmas": "UD Las Palmas",
    "cd castellon": "CD Castellon",
    "burgos cf": "Burgos CF",
    "sd eibar": "SD Eibar",
    "cordoba cf": "Cordoba CF",
    "fc andorra": "FC Andorra",
    "albacete bp": "Albacete Balompie",
    "real sporting": "Real Sporting de Gijon",
    "ad ceuta fc": "AD Ceuta FC",
    "granada cf": "Granada CF",
    "r sociedad b": "Real Sociedad B",
    "real valladolid cf": "Real Valladolid CF",
    "cd leganes": "CD Leganes",
    "cadiz cf": "Cadiz CF",
    "cd mirandes": "CD Mirandes",
    "sd huesca": "SD Huesca",
    "cultural y deportiva leonesa": "Cultural Leonesa",
    "real zaragoza": "Real Zaragoza",
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


def normalizar(texto):
    texto = str(texto or "").lower()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    texto = re.sub(r"[^a-z0-9]+", " ", texto)
    return " ".join(texto.split()).strip()


def canonico(nombre):
    return CANONICOS.get(normalizar(nombre), nombre.strip())


def descargar_soup():
    respuesta = requests.get(
        FUENTE_CLASIFICACION,
        timeout=30,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
            )
        },
    )
    respuesta.raise_for_status()
    return BeautifulSoup(respuesta.text, "html.parser")


def parsear_fila(linea):
    m = re.match(
        r"^(\d{1,2})\s+(.+?)\s+(\d{1,3})\s+(\d{1,2})\s+(\d{1,2})\s+(\d{1,2})\s+(\d{1,2})\s+(\d{1,3})\s+(\d{1,3})\s+[-+]?\d{1,3}$",
        linea,
    )
    if not m:
        return None
    posicion, equipo, puntos, pj, g, e, p, gf, gc = m.groups()
    gf_i = int(gf)
    gc_i = int(gc)
    return {
        "posicion": int(posicion),
        "equipo": canonico(equipo),
        "pj": int(pj),
        "g": int(g),
        "e": int(e),
        "p": int(p),
        "gf": gf_i,
        "gc": gc_i,
        "dg": gf_i - gc_i,
        "puntos": int(puntos),
    }


def extraer_tablas():
    soup = descargar_soup()
    texto = soup.get_text("\n", strip=True)
    lineas = [linea.strip() for linea in texto.splitlines() if linea.strip()]
    tablas = {"primera": [], "segunda": []}
    liga = None

    for linea in lineas:
        if "LaLiga EA Sports" in linea:
            liga = "primera"
            continue
        if "LaLiga Hypermotion" in linea:
            liga = "segunda"
            continue
        if linea.startswith("Liga F"):
            liga = None
            continue
        if liga and re.match(r"^\d{1,2}\s+", linea):
            fila = parsear_fila(linea)
            if fila:
                tablas[liga].append(fila)

    esperados = {"primera": 20, "segunda": 22}
    for nombre, esperado in esperados.items():
        if len(tablas[nombre]) != esperado:
            raise ValueError(
                f"Clasificacion {nombre}: se esperaban {esperado} equipos y se encontraron {len(tablas[nombre])}."
            )

    return tablas


def fusionar_clasificacion_publica(oficial, publica):
    salida = dict(publica) if isinstance(publica, dict) else {}
    for liga in ("primera", "segunda"):
        anteriores = {
            normalizar(e.get("equipo", "")): e
            for e in salida.get(liga, [])
            if isinstance(e, dict) and e.get("equipo")
        }
        nuevos = []
        for fila in oficial.get(liga, []):
            base = dict(anteriores.get(normalizar(fila.get("equipo", "")), {}))
            base.update(fila)
            base["pts"] = fila.get("puntos", fila.get("pts", 0))
            nuevos.append(base)
        if nuevos:
            salida[liga] = nuevos
    salida["actualizado_en"] = oficial.get("actualizado_en") or salida.get("actualizado_en")
    salida["fuentes"] = oficial.get("fuentes", salida.get("fuentes", {}))
    return salida


def validar_guardada(data):
    return (
        isinstance(data, dict)
        and len(data.get("primera", [])) == 20
        and len(data.get("segunda", [])) == 22
    )


def main():
    try:
        tablas = extraer_tablas()
        oficial = {
            "actualizado_en": datetime.now(timezone.utc).isoformat(),
            "fuentes": FUENTES,
            "primera": tablas["primera"],
            "segunda": tablas["segunda"],
        }
        guardar_json(OFICIALES, oficial)
        print("Clasificacion descargada desde fuente externa.")
    except Exception as exc:
        oficial = cargar_json(OFICIALES, {})
        if not validar_guardada(oficial):
            oficial = cargar_json(PUBLICA, {})
        if not validar_guardada(oficial):
            raise SystemExit(f"No hay clasificacion valida para conservar: {exc}")
        print(f"No se pudo refrescar clasificacion externa; se conserva la ultima valida. Motivo: {exc}")

    publica_actual = cargar_json(PUBLICA, {})
    publica = fusionar_clasificacion_publica(oficial, publica_actual)
    guardar_json(PUBLICA, publica)

    print(f"Clasificacion 1a disponible: {len(publica.get('primera', []))} equipos")
    print(f"Clasificacion 2a disponible: {len(publica.get('segunda', []))} equipos")
    print(OFICIALES)
    print(PUBLICA)


if __name__ == "__main__":
    main()
