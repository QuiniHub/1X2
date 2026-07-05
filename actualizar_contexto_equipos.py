import json
import re
import unicodedata
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import quote_plus
from urllib.request import Request, urlopen

try:
    import requests
except ImportError:
    requests = None


ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
JORNADAS = DATA / "jornadas"
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


def debe_refrescar(objetivos=None):
    existente = cargar_json(SALIDA, {})
    if objetivos:
        cargados = {normalizar(nombre) for nombre in (existente.get("equipos") or {})}
        esperados = {normalizar(item.get("equipo")) for item in objetivos if item.get("equipo")}
        if esperados - cargados:
            return True
    generado = existente.get("generado_en")
    if not generado:
        return True
    try:
        fecha = datetime.fromisoformat(generado.replace("Z", "+00:00"))
    except ValueError:
        return True
    return datetime.now(timezone.utc) - fecha > timedelta(hours=TTL_HORAS)


def jornada_activa():
    jornadas = []
    for path in JORNADAS.glob("jornada_*.json"):
        data = cargar_json(path, {})
        try:
            numero = int(data.get("jornada") or path.stem.split("_")[-1])
        except Exception:
            continue
        if numero:
            jornadas.append((numero, data))
    if not jornadas:
        return None
    return max(jornadas, key=lambda item: item[0])[1]


def equipos_jornada_activa():
    data = jornada_activa() or {}
    jornada = data.get("jornada")
    equipos = []
    for partido in data.get("partidos", [])[:14]:
        for campo in ("local", "visitante"):
            nombre = partido.get(campo)
            if nombre:
                equipos.append({
                    "equipo": nombre,
                    "liga": f"jornada_{jornada}" if jornada else "jornada",
                    "origen": "boleto_activo",
                    "partido": partido.get("num"),
                })
    pleno = data.get("pleno15") or {}
    for campo in ("local", "visitante"):
        nombre = pleno.get(campo)
        if nombre:
            equipos.append({
                "equipo": nombre,
                "liga": f"jornada_{jornada}" if jornada else "jornada",
                "origen": "pleno15",
                "partido": 15,
            })
    return equipos


def equipos_objetivo():
    clasif = cargar_json(CLASIFICACIONES, {})
    equipos = []
    for liga in ("primera", "segunda"):
        for equipo in clasif.get(liga, []):
            nombre = equipo.get("equipo")
            if nombre:
                equipos.append({"equipo": nombre, "liga": liga, "origen": "clasificacion"})
    equipos.extend(equipos_jornada_activa())

    indice = {}
    for item in equipos:
        key = normalizar(item["equipo"])
        if not key:
            continue
        if key not in indice:
            item = dict(item)
            item["origenes"] = [item.get("origen", "desconocido")]
            indice[key] = item
            continue
        actual = indice[key]
        origen = item.get("origen", "desconocido")
        if origen not in actual["origenes"]:
            actual["origenes"].append(origen)
        if item.get("partido") and not actual.get("partido"):
            actual["partido"] = item["partido"]
        if str(actual.get("liga", "")).startswith("jornada_") and item.get("liga") in ("primera", "segunda"):
            actual["liga"] = item["liga"]
    return list(indice.values())


def leer_feed_noticias(url, equipo, fuente):
    try:
        if requests is not None:
            response = requests.get(url, headers=HEADERS, timeout=15)
            response.raise_for_status()
            contenido = response.content
        else:
            req = Request(url, headers=HEADERS)
            with urlopen(req, timeout=15) as response:
                contenido = response.read()
        root = ET.fromstring(contenido)
    except Exception as exc:
        print(f"No se pudo leer noticias de {equipo} via {fuente}: {exc}")
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
            noticias.append({"titulo": titulo, "url": enlace, "fecha": fecha, "fuente": fuente})
        if len(noticias) >= 8:
            break
    return noticias


def leer_google_news(equipo):
    consulta = quote_plus(f'"{nombre_corto(equipo)}" futbol lesion sancion baja alta noticias')
    url = f"https://news.google.com/rss/search?q={consulta}&hl=es&gl=ES&ceid=ES:es"
    return leer_feed_noticias(url, equipo, "google_news")


def leer_bing_news(equipo):
    consulta = quote_plus(f'"{nombre_corto(equipo)}" futbol lesion sancion baja alta noticias')
    url = f"https://www.bing.com/news/search?q={consulta}&format=RSS&setmkt=es-ES"
    return leer_feed_noticias(url, equipo, "bing_news")


def leer_noticias_equipo(equipo):
    """Google News como fuente principal; si no devuelve nada (fallo, bloqueo o
    sin resultados), se intenta Bing News como respaldo gratuito antes de darlo
    por vacio, para que la busqueda nunca dependa de una unica fuente."""
    noticias = leer_google_news(equipo)
    if noticias:
        return noticias
    return leer_bing_news(equipo)


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
    objetivos = equipos_objetivo()
    if not debe_refrescar(objetivos):
        print(f"Contexto de equipos reciente; se conserva {SALIDA}")
        return

    salida = {
        "version": "1.0",
        "generado_en": datetime.now(timezone.utc).isoformat(),
        "ttl_horas": TTL_HORAS,
        "ventana_noticias_dias": VENTANA_NOTICIAS_DIAS,
        "fuentes": ["Google News RSS (principal)", "Bing News RSS (respaldo si Google no da resultados)", "equipos de clasificacion", "equipos del boleto activo"],
        "equipos": {},
    }

    for item in objetivos:
        equipo = item["equipo"]
        noticias = leer_noticias_equipo(equipo)
        categorias, alertas = clasificar_noticias(noticias)
        fuente_usada = noticias[0]["fuente"] if noticias else "sin_resultados"
        salida["equipos"][equipo] = {
            "liga": item["liga"],
            "origenes": item.get("origenes", [item.get("origen", "desconocido")]),
            "partido_boleto": item.get("partido"),
            "noticias": noticias,
            "categorias": categorias,
            "alertas": alertas,
            "resumen": resumen_equipo(equipo, noticias, categorias, alertas),
        }
        print(f"{equipo}: {len(noticias)} noticias ({fuente_usada}), alertas={','.join(alertas) or 'sin_alertas'}")

    guardar_json(SALIDA, salida)
    print(f"Contexto de equipos guardado: {SALIDA}")


if __name__ == "__main__":
    main()
