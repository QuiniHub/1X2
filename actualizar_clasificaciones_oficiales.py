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

FUENTES_AS = {
    "primera": "https://as.com/resultados/futbol/primera/clasificacion/",
    "segunda": "https://as.com/resultados/futbol/segunda/clasificacion/",
}
FUENTE_QUINIELA = "https://www.quinielafutbol.info/clasificacion.html"
FUENTES = {
    "primera": FUENTES_AS["primera"],
    "segunda": FUENTES_AS["segunda"],
    "respaldo": FUENTE_QUINIELA,
}

CANONICOS = {
    "fc barcelona": "FC Barcelona",
    "barcelona": "FC Barcelona",
    "real madrid": "Real Madrid CF",
    "atletico": "Club Atletico de Madrid",
    "atletico madrid": "Club Atletico de Madrid",
    "club atletico de madrid": "Club Atletico de Madrid",
    "villareal cf": "Villarreal CF",
    "villarreal": "Villarreal CF",
    "villarreal cf": "Villarreal CF",
    "real betis": "Real Betis Balompie",
    "betis": "Real Betis Balompie",
    "celta": "RC Celta de Vigo",
    "rc celta de vigo": "RC Celta de Vigo",
    "getafe": "Getafe CF",
    "getafe cf": "Getafe CF",
    "rayo": "Rayo Vallecano de Madrid",
    "rayo vallecano": "Rayo Vallecano de Madrid",
    "valencia": "Valencia CF",
    "valencia cf": "Valencia CF",
    "r sociedad": "Real Sociedad de Futbol",
    "real sociedad": "Real Sociedad de Futbol",
    "real sociedad de futbol": "Real Sociedad de Futbol",
    "espanyol": "RCD Espanyol de Barcelona",
    "rcd espanyol de barcelona": "RCD Espanyol de Barcelona",
    "athletic": "Athletic Club",
    "athletic club": "Athletic Club",
    "sevilla": "Sevilla FC",
    "sevilla fc": "Sevilla FC",
    "alaves": "Deportivo Alaves",
    "deportivo alaves": "Deportivo Alaves",
    "levante": "Levante UD",
    "levante ud": "Levante UD",
    "osasuna": "CA Osasuna",
    "ca osasuna": "CA Osasuna",
    "elche": "Elche CF",
    "elche cf": "Elche CF",
    "girona": "Girona FC",
    "girona fc": "Girona FC",
    "mallorca": "RCD Mallorca",
    "rcd mallorca": "RCD Mallorca",
    "oviedo": "Real Oviedo",
    "real oviedo": "Real Oviedo",
    "racing": "Real Racing Club de Santander",
    "r racing club": "Real Racing Club de Santander",
    "real racing club de santander": "Real Racing Club de Santander",
    "deportivo": "RC Deportivo de La Coruna",
    "rc deportivo": "RC Deportivo de La Coruna",
    "rc deportivo de la coruna": "RC Deportivo de La Coruna",
    "almeria": "UD Almeria",
    "ud almeria": "UD Almeria",
    "malaga": "Malaga CF",
    "malaga cf": "Malaga CF",
    "las palmas": "UD Las Palmas",
    "ud las palmas": "UD Las Palmas",
    "castellon": "CD Castellon",
    "cd castellon": "CD Castellon",
    "burgos cf": "Burgos CF",
    "burgos": "Burgos CF",
    "eibar": "SD Eibar",
    "sd eibar": "SD Eibar",
    "cordoba": "Cordoba CF",
    "cordoba cf": "Cordoba CF",
    "andorra": "FC Andorra",
    "fc andorra": "FC Andorra",
    "albacete": "Albacete Balompie",
    "albacete bp": "Albacete Balompie",
    "albacete balompie": "Albacete Balompie",
    "sporting": "Real Sporting de Gijon",
    "real sporting": "Real Sporting de Gijon",
    "real sporting de gijon": "Real Sporting de Gijon",
    "a d ceuta": "AD Ceuta FC",
    "ad ceuta": "AD Ceuta FC",
    "ad ceuta fc": "AD Ceuta FC",
    "granada": "Granada CF",
    "granada cf": "Granada CF",
    "r sociedad b": "Real Sociedad B",
    "real sociedad b": "Real Sociedad B",
    "real valladolid": "Real Valladolid CF",
    "real valladolid cf": "Real Valladolid CF",
    "leganes": "CD Leganes",
    "cd leganes": "CD Leganes",
    "cadiz": "Cadiz CF",
    "cadiz cf": "Cadiz CF",
    "mirandes": "CD Mirandes",
    "cd mirandes": "CD Mirandes",
    "huesca": "SD Huesca",
    "sd huesca": "SD Huesca",
    "cultural": "Cultural Leonesa",
    "cultural y deportiva leonesa": "Cultural Leonesa",
    "cultural leonesa": "Cultural Leonesa",
    "real zaragoza": "Real Zaragoza",
    "zaragoza": "Real Zaragoza",
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
    limpio = normalizar(nombre)
    return CANONICOS.get(limpio, nombre.strip())


def descargar_soup(url):
    respuesta = requests.get(
        url,
        timeout=30,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
            ),
            "Accept-Language": "es-ES,es;q=0.9",
        },
    )
    respuesta.raise_for_status()
    return BeautifulSoup(respuesta.text, "html.parser")


def limpiar_nombre_as(linea):
    nombre = re.sub(r"\s+[A-Z]{2,4}$", "", linea).strip()
    nombre = nombre.replace("A. D.", "AD").replace("R.", "Real")
    return canonico(nombre)


def linea_equipo_as(linea):
    if not linea or linea.isdigit():
        return False
    if "Image" in linea or linea.startswith("#"):
        return False
    if linea in {"Total Casa Fuera", "Totales En casa Fuera"}:
        return False
    if linea.startswith("Posición") or linea.startswith("Actualizado"):
        return False
    return bool(re.search(r"\s[A-Z]{2,4}$", linea))


def parsear_estadisticas_as(linea):
    m = re.match(r"^(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(-?\d+)\b", linea)
    if not m:
        return None
    puntos, pj, g, e, p, gf, gc, dg = map(int, m.groups())
    return {
        "pj": pj,
        "g": g,
        "e": e,
        "p": p,
        "gf": gf,
        "gc": gc,
        "dg": dg,
        "puntos": puntos,
    }


def extraer_tabla_as(liga, esperado):
    soup = descargar_soup(FUENTES_AS[liga])
    lineas = [linea.strip() for linea in soup.get_text("\n", strip=True).splitlines() if linea.strip()]
    inicio = next((idx for idx, linea in enumerate(lineas) if linea.startswith("# Clasificación")), 0)
    fin = next((idx for idx, linea in enumerate(lineas[inicio:], start=inicio) if linea.startswith("Actualizado")), len(lineas))
    lineas = lineas[inicio:fin]

    filas = []
    esperado_pos = 1
    i = 0
    while i < len(lineas) and len(filas) < esperado:
        if lineas[i] != str(esperado_pos):
            i += 1
            continue

        i += 1
        while i < len(lineas) and (lineas[i].isdigit() or "Image" in lineas[i]):
            i += 1

        if i >= len(lineas) or not linea_equipo_as(lineas[i]):
            i += 1
            continue

        equipo = limpiar_nombre_as(lineas[i])
        i += 1

        stats = None
        while i < len(lineas):
            stats = parsear_estadisticas_as(lineas[i])
            i += 1
            if stats:
                break
        if not stats:
            continue

        filas.append({
            "posicion": esperado_pos,
            "equipo": equipo,
            **stats,
        })
        esperado_pos += 1

    if len(filas) != esperado:
        raise ValueError(f"AS {liga}: se esperaban {esperado} equipos y se encontraron {len(filas)}.")
    return filas


def parsear_fila_quiniela(linea):
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


def extraer_tablas_quiniela():
    soup = descargar_soup(FUENTE_QUINIELA)
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
            fila = parsear_fila_quiniela(linea)
            if fila:
                tablas[liga].append(fila)

    esperados = {"primera": 20, "segunda": 22}
    for nombre, esperado in esperados.items():
        if len(tablas[nombre]) != esperado:
            raise ValueError(
                f"Clasificacion {nombre}: se esperaban {esperado} equipos y se encontraron {len(tablas[nombre])}."
            )
    return tablas


def extraer_tablas():
    try:
        return {
            "primera": extraer_tabla_as("primera", 20),
            "segunda": extraer_tabla_as("segunda", 22),
        }
    except Exception as exc:
        print(f"No se pudo leer AS completo; se intenta respaldo quinielístico. Motivo: {exc}")
        return extraer_tablas_quiniela()


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
        print("Clasificacion descargada desde fuente externa vigente.")
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
