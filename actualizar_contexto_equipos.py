import json
import re
import unicodedata
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import quote_plus

import requests


ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
CLASIFICACIONES = ROOT / "clasificaciones.json"
SALIDA = DATA / "contexto_equipos.json"
TTL_HORAS = 6
VENTANA_NOTICIAS_DIAS = 60

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}

CATEGORIAS = {
    "lesiones": ["lesion", "lesionado", "lesionados", "molestias", "rotura", "baja medica", "parte medico"],
    "sanciones": ["sancion", "sancionado", "sancionados", "expulsion", "roja", "amarillas", "comite"],
    "dudas": ["duda", "dudas", "tocado", "entrenamiento al margen", "no entrena", "pendiente"],
    "altas": ["alta", "recuperado", "vuelve", "regresa", "convocatoria", "entrena con el grupo"],
    "mercado": ["fichaje", "traspaso", "cesion", "renovacion", "salida", "interes"],
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


def nombre_corto(nombre):
    limpio = re.sub(r"\b(FC|CF|CD|SD|UD|RCD|RC|Club|Real|de|del|la|el|Balompié|Fútbol)\b", " ", str(nombre), flags=re.I)
    limpio = " ".join(limpio.split())
    return limpio or str(nombre)


def debe_refrescar():
    existente = cargar_json(SALIDA, {})
    generado = existente.get("generado_en")
    if not generado:
        return True
    try:
        fecha = datetime.fromisoformat(generado.replace("Z", "+00:00"))
    except ValueError:
        return True
    return datetime.now(timezone.utc) - fecha > timedelta(hours=TTL_HORAS)


def equipos_objetivo():
    clasif = cargar_json(CLASIFICACIONES, {})
    equipos = []
    for liga in ("primera", "segunda"):
        for equipo in clasif.get(liga, []):
            nombre = equipo.get("equipo")
            if nombre:
                equipos.append({"equipo": nombre, "liga": liga})
    vistos = set()
    unicos = []
    for item in equipos:
        key = normalizar(item["equipo"])
        if key not in vistos:
            vistos.add(key)
            unicos.append(item)
    return unicos


def leer_google_news(equipo):
    consulta = quote_plus(f'"{nombre_corto(equipo)}" futbol lesion sancion baja alta noticias')
    url = f"https://news.google.com/rss/search?q={consulta}&hl=es&gl=ES&ceid=ES:es"
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()
        root = ET.fromstring(response.content)
    except Exception as exc:
        print(f"No se pudo leer noticias de {equipo}: {exc}")
        return []

    noticias = []
    limite = datetime.now(timezone.utc) - timedelta(days=VENTANA_NOTICIAS_DIAS)
    for item in root.findall(".//item"):
        titulo = item.findtext("title") or ""
        enlace = item.findtext("link") or ""
        fecha = item.findtext("pubDate") or ""
        try:
            fecha_dt = parsedate_to_datetime(fecha)
            if fecha_dt.tzinfo is None:
                fecha_dt = fecha_dt.replace(tzinfo=timezone.utc)
            if fecha_dt < limite:
                continue
        except Exception:
            pass
        if titulo:
            noticias.append({"titulo": titulo, "url": enlace, "fecha": fecha})
        if len(noticias) >= 8:
            break
    return noticias


def clasificar_noticias(noticias):
    categorias = {k: [] for k in CATEGORIAS}
    alertas = []
    for noticia in noticias:
        texto = normalizar(noticia.get("titulo", ""))
        for categoria, claves in CATEGORIAS.items():
            if any(clave in texto for clave in claves):
                categorias[categoria].append(noticia)
                alertas.append(categoria)
    return categorias, sorted(set(alertas))


def resumen_equipo(equipo, noticias, categorias, alertas):
    if not noticias:
        return "Sin noticias recientes detectadas en fuentes públicas durante esta actualización."
    partes = []
    if "lesiones" in alertas:
        partes.append("hay señales de posibles lesiones o partes médicos")
    if "sanciones" in alertas:
        partes.append("hay señales de sanciones o riesgo disciplinario")
    if "dudas" in alertas:
        partes.append("hay jugadores en duda o incidencias de entrenamiento")
    if "altas" in alertas:
        partes.append("hay posibles regresos o altas")
    if "mercado" in alertas:
        partes.append("aparecen noticias de mercado o movimientos de plantilla")
    if not partes:
        partes.append("noticias generales sin alerta deportiva clara")
    return f"{equipo}: " + "; ".join(partes) + "."


def main():
    if not debe_refrescar():
        print(f"Contexto de equipos reciente; se conserva {SALIDA}")
        return

    salida = {
        "version": "1.0",
        "generado_en": datetime.now(timezone.utc).isoformat(),
        "ttl_horas": TTL_HORAS,
        "ventana_noticias_dias": VENTANA_NOTICIAS_DIAS,
        "fuentes": ["Google News RSS"],
        "equipos": {},
    }

    for item in equipos_objetivo():
        equipo = item["equipo"]
        noticias = leer_google_news(equipo)
        categorias, alertas = clasificar_noticias(noticias)
        salida["equipos"][equipo] = {
            "liga": item["liga"],
            "noticias": noticias,
            "categorias": categorias,
            "alertas": alertas,
            "resumen": resumen_equipo(equipo, noticias, categorias, alertas),
        }
        print(f"{equipo}: {len(noticias)} noticias, alertas={','.join(alertas) or 'sin_alertas'}")

    guardar_json(SALIDA, salida)
    print(f"Contexto de equipos guardado: {SALIDA}")


if __name__ == "__main__":
    main()
