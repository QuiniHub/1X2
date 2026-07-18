"""Scraper de RESPALDO de lesionados/dudas de LaLiga desde jornadaperfecta.com.

Fuente secundaria de fuente_lesiones_laliga.json (FutbolFantasy): mismo
tipo de dato (lesionados/dudas de LaLiga EA Sports), pero HTML totalmente
distinto y verificado por separado el 2026-07-18. Si FutbolFantasy cambia
su marcado o deja de responder, esta fuente puede seguir dando datos
reales -motor_prediccion_quiniela.py y el chat la consultan solo cuando
la fuente principal no tiene datos de un equipo concreto (ver
buscar_lesiones_equipo en motor_prediccion_quiniela.py, encadenado con
"or" contra esta fuente).

robots.txt de jornadaperfecta.com permite el scraping (solo bloquea
/pintar_alineacion, /wp-admin, /tag, /search y el bot GPTBot). Esta web
solo cubre LaLiga EA Sports (1a) -no se encontro una pagina equivalente
de Hypermotion (2a) en jornadaperfecta.com.
"""

import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

import json

import requests
from bs4 import BeautifulSoup


ROOT = Path(__file__).resolve().parent
SALIDA = ROOT / "data" / "memoria_ia" / "fuente_lesiones_jornadaperfecta.json"

URL_LESIONADOS = "https://www.jornadaperfecta.com/lesionados/"

TIMEOUT = 10
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
}

# Mapeo de nombre de icono (src) a la misma categoria que usa
# fuente_lesiones_laliga.json (FutbolFantasy) -mismo vocabulario para que
# ajustar_por_lesiones_laliga() cuente bajas igual sin importar la fuente.
ICONOS_CATEGORIA = {
    "lesion": "lesionado",
    "duda": "duda",
    "disponible": "disponible",
}


def ahora_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def cargar_json(path, defecto=None):
    if defecto is None:
        defecto = {}
    path = Path(path)
    if not path.exists():
        return defecto
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return defecto


def guardar_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def normalizar_texto(texto):
    texto = str(texto or "").replace("\xa0", " ")
    texto = unicodedata.normalize("NFKC", texto)
    return " ".join(texto.split())


def descargar(url):
    respuesta = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    respuesta.raise_for_status()
    if not respuesta.encoding or respuesta.encoding.lower() == "iso-8859-1":
        respuesta.encoding = respuesta.apparent_encoding or "utf-8"
    return respuesta.text


def soup_de(html):
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    return soup


def categoria_desde_icono(elemento):
    img = elemento.select_one("div.lesionados-jugador-iconos img")
    src = str(img.get("src", "")) if img else ""
    for clave, categoria in ICONOS_CATEGORIA.items():
        if clave in src:
            return categoria
    return None


def extraer_jugador(elemento):
    jugador_link = elemento.select_one("div.lesionados-jugador-nombre a")
    if not jugador_link:
        return None
    motivo_div = elemento.select_one("div.lesionados-jugador-motivo")
    return {
        "jugador": normalizar_texto(jugador_link.get_text(" ")),
        "jugador_url": jugador_link.get("href"),
        "categoria": categoria_desde_icono(elemento),
        "lesion": normalizar_texto(motivo_div.get_text(" ")) if motivo_div else "",
    }


def extraer_lesionados(html):
    soup = soup_de(html)
    equipos = {}
    for bloque in soup.select("div.lesionados"):
        nombre_link = bloque.select_one("div.lesionados-equipo-nombre a")
        if not nombre_link:
            continue
        nombre_equipo = normalizar_texto(nombre_link.get_text(" "))
        if not nombre_equipo:
            continue
        jugadores = [
            j for j in (extraer_jugador(el) for el in bloque.select("div.lesionados-jugador")) if j
        ]
        if jugadores:
            equipos[nombre_equipo] = jugadores
    return equipos


def fusionar_con_anterior(anterior, equipos_nuevos, avisos):
    equipos = equipos_nuevos if equipos_nuevos else (anterior.get("equipos") or {})
    return {
        "version": "1.0",
        "fuente": "jornadaperfecta.com",
        "url": URL_LESIONADOS,
        "actualizado_en": ahora_iso(),
        "avisos": avisos,
        "equipos": equipos,
        "conserva_datos_previos": not bool(equipos_nuevos),
    }


def main():
    anterior = cargar_json(SALIDA, {})
    avisos = []
    equipos_nuevos = {}
    try:
        html = descargar(URL_LESIONADOS)
        equipos_nuevos = extraer_lesionados(html)
        if not equipos_nuevos:
            avisos.append("Scrape sin datos de lesionados; se conserva el dato previo.")
    except Exception as exc:
        avisos.append(f"Fallo al leer jornadaperfecta.com: {type(exc).__name__}: {exc}. Se conserva el dato previo.")
        print(f"AVISO fuente_lesiones_jornadaperfecta: {exc}")

    salida = fusionar_con_anterior(anterior, equipos_nuevos, avisos)
    guardar_json(SALIDA, salida)
    total_jugadores = sum(len(v) for v in salida["equipos"].values())
    try:
        ruta_mostrada = SALIDA.relative_to(ROOT)
    except ValueError:
        ruta_mostrada = SALIDA
    print(f"Lesiones jornadaperfecta (respaldo) actualizadas: {len(salida['equipos'])} equipos, {total_jugadores} jugadores en {ruta_mostrada}")


if __name__ == "__main__":
    main()
