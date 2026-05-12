import json
import re
import unicodedata
from datetime import date, datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup


ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
TEMPORADA_URL = "2025-26"

COMPETICIONES = {
    "primera": {
        "archivo": DATA / "calendario_primera.json",
        "slug_laliga": "laliga-easports",
        "jornadas": range(1, 39),
    },
    "segunda": {
        "archivo": DATA / "calendario_segunda.json",
        "slug_laliga": "laliga-hypermotion",
        "jornadas": range(1, 43),
    },
}

FUENTES_NOTICIAS = [
    "https://cadenaser.com/search/{local}%20{visitante}%20resultado%20jornada%20{jornada}/",
    "https://as.com/buscador/?q={local}%20{visitante}%20resultado%20jornada%20{jornada}",
]

RESULTADOS_VERIFICADOS = {
    "primera": {
        35: {
            ("Levante UD", "CA Osasuna"): "3-2",
            ("Elche CF", "Deportivo Alaves"): "1-1",
            ("Sevilla FC", "RCD Espanyol de Barcelona"): "2-1",
            ("Club Atletico de Madrid", "RC Celta de Vigo"): "0-1",
            ("Real Sociedad de Futbol", "Real Betis Balompie"): "2-2",
            ("RCD Mallorca", "Villarreal CF"): "1-1",
            ("Athletic Club", "Valencia CF"): "0-1",
            ("Real Oviedo", "Getafe CF"): "0-0",
            ("FC Barcelona", "Real Madrid CF"): "2-0",
            ("Rayo Vallecano de Madrid", "Girona FC"): "1-1",
        },
        36: {
            ("RC Celta de Vigo", "Levante UD"): "2-3",
        },
    },
    "segunda": {
        39: {
            ("Albacete", "Cultural Leonesa"): "2-1",
            ("Cadiz CF", "Deportivo La Coruna"): "0-1",
            ("Cordoba CF", "Granada CF"): "1-0",
            ("SD Huesca", "Real Sociedad B"): "1-2",
            ("CD Leganes", "Racing Santander"): "1-2",
            ("Malaga CF", "Sporting Gijon"): "2-1",
            ("Real Valladolid", "Real Zaragoza"): "2-0",
            ("FC Andorra", "UD Las Palmas"): "5-1",
            ("AD Ceuta FC", "CD Castellon"): "1-1",
            ("CD Mirandes", "SD Eibar"): "0-1",
            ("Burgos CF", "UD Almeria"): "0-0",
        }
    },
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}


def normalizar(texto):
    texto = str(texto or "")
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    texto = texto.lower()
    texto = re.sub(r"\b(fc|cf|cd|sd|ud|rcd|rc|club|real|de|del|la|el|balompie|futbol)\b", " ", texto)
    texto = re.sub(r"[^a-z0-9]+", " ", texto)
    return " ".join(texto.split()).strip()


def cargar_json(path):
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def guardar_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def descargar_texto(url):
    try:
        response = requests.get(url, headers=HEADERS, timeout=20)
        if response.status_code >= 400:
            return ""
        soup = BeautifulSoup(response.text, "html.parser")
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        return " ".join(soup.get_text(" ").split())
    except Exception as exc:
        print(f"No se pudo consultar {url}: {exc}")
        return ""


def nombres_candidatos(nombre):
    limpio = normalizar(nombre)
    partes = [p for p in limpio.split() if len(p) > 2]
    candidatos = {limpio}
    if partes:
        candidatos.add(partes[-1])
        candidatos.add(partes[0])
    if "madrid" in limpio and "atletico" in limpio:
        candidatos.update({"atletico", "ath madrid"})
    if "bilbao" in limpio or "athletic" in limpio:
        candidatos.add("athletic")
    if "sociedad" in limpio:
        candidatos.add("sociedad")
    if "coruna" in limpio:
        candidatos.add("deportivo")
    if "santander" in limpio:
        candidatos.add("racing")
    if "gijon" in limpio:
        candidatos.add("sporting")
    return {c for c in candidatos if c}


def contiene_equipo(fragmento, equipo):
    texto = normalizar(fragmento)
    return any(candidato in texto for candidato in nombres_candidatos(equipo))


def marcador_en_texto(texto, local, visitante):
    if not texto:
        return None

    patrones = [
        r"(?P<a>\d{1,2})\s*[-:]\s*(?P<b>\d{1,2})",
        r"(?P<a>\d{1,2})\s+a\s+(?P<b>\d{1,2})",
    ]

    for patron in patrones:
        for match in re.finditer(patron, texto, re.IGNORECASE):
            inicio = max(match.start() - 90, 0)
            fin = min(match.end() + 90, len(texto))
            fragmento = texto[inicio:fin]
            if contiene_equipo(fragmento, local) and contiene_equipo(fragmento, visitante):
                return f"{int(match.group('a'))}-{int(match.group('b'))}"
    return None


def consultar_laliga(tipo, jornada):
    slug = COMPETICIONES[tipo]["slug_laliga"]
    urls = [
        f"https://www.laliga.com/{slug}/resultados/{TEMPORADA_URL}/jornada-{jornada}",
        f"https://iaas-public-front-pro.laliga.com/{slug}/resultados/{TEMPORADA_URL}/jornada-{jornada}",
    ]
    return " ".join(descargar_texto(url) for url in urls)


def consultar_noticias(partido, jornada):
    local = str(partido.get("local", "")).replace(" ", "%20")
    visitante = str(partido.get("visitante", "")).replace(" ", "%20")
    textos = []
    for plantilla in FUENTES_NOTICIAS:
        url = plantilla.format(local=local, visitante=visitante, jornada=jornada)
        textos.append(descargar_texto(url))
    return " ".join(textos)


def resultado_verificado(tipo, jornada, partido):
    resultados = RESULTADOS_VERIFICADOS.get(tipo, {}).get(jornada, {})
    clave_partido = (normalizar(partido.get("local")), normalizar(partido.get("visitante")))
    for (local, visitante), resultado in resultados.items():
        if clave_partido == (normalizar(local), normalizar(visitante)):
            return resultado
    return None


def jornada_debe_consultarse(jornada):
    fechas = []
    for partido in jornada.get("partidos", []):
        try:
            fechas.append(datetime.fromisoformat(str(partido.get("fecha"))).date())
        except ValueError:
            pass
    return bool(fechas and min(fechas) <= date.today())


def actualizar_calendario_liga(tipo):
    path = COMPETICIONES[tipo]["archivo"]
    data = cargar_json(path)
    actualizados = 0
    textos_laliga = {}

    for jornada in data.get("jornadas", []):
        numero_jornada = jornada.get("jornada")
        if not jornada_debe_consultarse(jornada):
            continue

        texto_laliga = textos_laliga.get(numero_jornada)
        if texto_laliga is None:
            texto_laliga = consultar_laliga(tipo, numero_jornada)
            textos_laliga[numero_jornada] = texto_laliga

        for partido in jornada.get("partidos", []):
            resultado_anterior = partido.get("resultado")
            resultado = marcador_en_texto(texto_laliga, partido.get("local"), partido.get("visitante"))

            if not resultado:
                resultado = marcador_en_texto(consultar_noticias(partido, numero_jornada), partido.get("local"), partido.get("visitante"))
            if not resultado:
                resultado = resultado_verificado(tipo, numero_jornada, partido)

            if resultado and resultado != resultado_anterior:
                partido["resultado"] = resultado
                partido["estado"] = "Jugado"
                partido["actualizado_en"] = datetime.utcnow().isoformat(timespec="seconds") + "Z"
                actualizados += 1
            elif resultado:
                partido["estado"] = "Jugado"

    guardar_json(path, data)
    return actualizados


def ejecutar_calendario():
    total = 0
    for tipo in ("primera", "segunda"):
        actualizados = actualizar_calendario_liga(tipo)
        total += actualizados
        print(f"{tipo}: {actualizados} marcadores nuevos o corregidos.")
    print(f"Calendarios actualizados automaticamente: {total} cambios.")


if __name__ == "__main__":
    ejecutar_calendario()
