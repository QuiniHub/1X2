"""Scraper de lesionados/dudas de LaLiga desde futbolfantasy.com.

Llena el hueco real de "lesiones_sanciones" que API-Football (de pago) no
cubre en el plan Free -confirmado en vivo el 2026-07-18: 403 en
/fixtures con "Free plans do not have access to this season". FutbolFantasy
permite scraping segun su propio robots.txt (Disallow vacio) y responde
200 con el mismo patron de cabeceras que ya usamos para eduardolosilla.es.

Si la web falla o cambia su HTML, el script no detiene el flujo: conserva
el ultimo dato local valido en data/memoria_ia/fuente_lesiones_laliga.json
y deja avisos en la salida -mismo principio que actualizar_fuente_losilla.py.
"""

import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

import json

import requests
from bs4 import BeautifulSoup


ROOT = Path(__file__).resolve().parent
SALIDA = ROOT / "data" / "memoria_ia" / "fuente_lesiones_laliga.json"

URL_LESIONADOS = "https://www.futbolfantasy.com/laliga/lesionados"

TIMEOUT = 10
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
}

CATEGORIAS_VALIDAS = ("lesionado", "duda", "disponible")


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


def numero(valor):
    texto = re.sub(r"[^0-9,.\-]", "", str(valor or ""))
    if not texto:
        return None
    try:
        return float(texto.replace(",", "."))
    except ValueError:
        return None


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
    img = elemento.select_one("div.icono-wrapper span.lesion img")
    src = str(img.get("src", "")) if img else ""
    for candidato in CATEGORIAS_VALIDAS:
        if candidato in src:
            return candidato
    return None


def gravedad_desde_foto(elemento):
    foto = elemento.select_one("div.fotocontainer")
    if not foto:
        return None
    for clase in foto.get("class", []):
        m = re.match(r"gravedad-(\d+)", clase)
        if m:
            return int(m.group(1))
    return None


def datos_comentario(elemento):
    comentario = elemento.select_one("div.comentario")
    lesion_tipo, fecha_texto, estado_texto, dias = "", "", "", None
    if comentario:
        tipo_span = comentario.select_one("span.lesion")
        if tipo_span:
            lesion_tipo = normalizar_texto(tipo_span.get_text(" "))
        for span in comentario.find_all("span", recursive=False):
            texto = normalizar_texto(span.get_text(" "))
            clases = span.get("class") or []
            if texto.lower().startswith("desde"):
                fecha_texto = texto
                m = re.search(r"\((\d+)\s*d", texto)
                if m:
                    dias = int(m.group(1))
            elif any(str(c).startswith("gravedad-") for c in clases):
                estado_texto = texto
    return lesion_tipo, fecha_texto, estado_texto, dias


def enlace_referencia(elemento):
    link = elemento.select_one("div.links-c a.lesion.link")
    if not link:
        return None, None
    label = link.select_one("span.label")
    tipo = normalizar_texto(label.get_text(" ")) if label else None
    return tipo, link.get("href")


def extraer_jugador(elemento):
    jugador_link = elemento.select_one("a.jugador")
    if not jugador_link:
        return None
    lesion_tipo, fecha_texto, estado_texto, dias = datos_comentario(elemento)
    enlace_tipo, enlace_url = enlace_referencia(elemento)
    prob_span = elemento.select_one("span.probabilidad-widget span")
    return {
        "jugador": normalizar_texto(jugador_link.get_text(" ")),
        "jugador_url": jugador_link.get("href"),
        "categoria": categoria_desde_icono(elemento),
        "gravedad": gravedad_desde_foto(elemento),
        "probabilidad_disponibilidad": numero(prob_span.get_text("")) if prob_span else None,
        "lesion": lesion_tipo,
        "fecha_texto": fecha_texto,
        "dias": dias,
        "estado_texto": estado_texto,
        "enlace_tipo": enlace_tipo,
        "enlace_url": enlace_url,
    }


def extraer_lesionados(html):
    soup = soup_de(html)
    equipos = {}
    for seccion in soup.select("section.mod.lesionados"):
        header = seccion.select_one("header.title")
        if not header:
            continue
        nombre_equipo = normalizar_texto(header.get_text(" "))
        if not nombre_equipo:
            continue
        jugadores = [
            j for j in (extraer_jugador(el) for el in seccion.select("div.elemento.lesionado")) if j
        ]
        if jugadores:
            equipos[nombre_equipo] = jugadores
    return equipos


def fusionar_con_anterior(anterior, equipos_nuevos, avisos):
    equipos = equipos_nuevos if equipos_nuevos else (anterior.get("equipos") or {})
    return {
        "version": "1.0",
        "fuente": "futbolfantasy.com",
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
        avisos.append(f"Fallo al leer futbolfantasy.com: {type(exc).__name__}: {exc}. Se conserva el dato previo.")
        print(f"AVISO fuente_lesiones_laliga: {exc}")

    salida = fusionar_con_anterior(anterior, equipos_nuevos, avisos)
    guardar_json(SALIDA, salida)
    total_jugadores = sum(len(v) for v in salida["equipos"].values())
    print(f"Lesiones LaLiga actualizadas: {len(salida['equipos'])} equipos, {total_jugadores} jugadores en {SALIDA.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
