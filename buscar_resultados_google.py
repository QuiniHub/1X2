"""
Busca resultados de partidos pendientes usando Flashscore directamente.

Para cada jornada activa, revisa partidos pendientes que ya deberian haber
terminado, consulta la pagina de resultados del Mundial en Flashscore y, si
existe una URL individual del partido en el JSON, tambien consulta esa pagina.
Actualiza jornada_XX.json y mundial_2026_resultados.json cuando encuentra un
marcador fiable cerca de los nombres de los equipos.
"""

import html
import json
import re
import time
import unicodedata
from datetime import datetime, time as dt_time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
JORNADAS = DATA / "jornadas"
RESULTADOS_MUNDIAL = DATA / "mundial_2026_resultados.json"

TZ = ZoneInfo("Europe/Madrid")
MARGEN = timedelta(minutes=105)
FLASH_RESULTS_URL = "https://www.flashscore.es/futbol/mundial/campeonato-del-mundo/resultados/"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.7",
    "Referer": "https://www.flashscore.es/",
}

URL_KEYS = (
    "flashscore_url",
    "url_flashscore",
    "url_partido",
    "url_resultado",
    "fuente_resultado_url",
    "link_resultado",
)

ALIAS = {
    "eeuu": "estados unidos",
    "usa": "estados unidos",
    "united states": "estados unidos",
    "paises bajos": "paises bajos",
    "holanda": "paises bajos",
    "netherlands": "paises bajos",
    "japon": "japon",
    "japan": "japon",
    "belgica": "belgica",
    "belgium": "belgica",
    "n zelanda": "nueva zelanda",
    "n. zelanda": "nueva zelanda",
    "new zealand": "nueva zelanda",
    "irán": "iran",
    "iran": "iran",
    "egipto": "egipto",
    "egypt": "egipto",
    "espana": "espana",
    "spain": "espana",
    "arabia saudi": "arabia saudi",
    "saudi arabia": "arabia saudi",
    "cabo verde": "cabo verde",
    "cape verde": "cabo verde",
}


def cargar_json(path, defecto=None):
    if defecto is None:
        defecto = {}
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return defecto


def guardar_json(path, data):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def ahora_iso():
    return datetime.now(timezone.utc).isoformat()


def normalizar(texto):
    texto = html.unescape(str(texto or "")).lower().strip()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    texto = re.sub(r"[^a-z0-9]+", " ", texto)
    texto = " ".join(texto.split()).strip()
    return ALIAS.get(texto, texto)


def variantes_equipo(nombre):
    base = normalizar(nombre)
    variantes = {base}
    for alias, canonico in ALIAS.items():
        if canonico == base:
            variantes.add(normalizar(alias))
    if base:
        partes = base.split()
        if partes:
            variantes.add(partes[0])
    return {v for v in variantes if v}


def limpiar_html(html_text):
    texto = re.sub(r"(?is)<(script|style|noscript).*?</\1>", " ", html_text or "")
    texto = re.sub(r"(?s)<[^>]+>", " ", texto)
    texto = html.unescape(texto)
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto


def descargar(url):
    r = requests.get(url, headers=HEADERS, timeout=25)
    r.raise_for_status()
    return r.text


def partido_ya_terminado(fecha_txt, hora_txt):
    try:
        fecha = datetime.fromisoformat(str(fecha_txt)).date()
        m = re.match(r"^(\d{1,2}):(\d{2})$", str(hora_txt or ""))
        if not m:
            return fecha < datetime.now(TZ).date()
        hora = dt_time(int(m.group(1)), int(m.group(2)))
        inicio = datetime.combine(fecha, hora, TZ)
        return inicio + MARGEN <= datetime.now(TZ)
    except Exception:
        return False


def resultado_valido(resultado):
    return re.match(r"^\s*\d{1,2}\s*-\s*\d{1,2}\s*$", str(resultado or "")) is not None


def normalizar_resultado(resultado):
    m = re.match(r"^\s*(\d{1,2})\s*[-–]\s*(\d{1,2})\s*$", str(resultado or ""))
    if not m:
        return ""
    return f"{int(m.group(1))}-{int(m.group(2))}"


def signo_resultado(resultado):
    gl, gv = [int(x) for x in normalizar_resultado(resultado).split("-")]
    if gl > gv:
        return "1"
    if gl == gv:
        return "X"
    return "2"


def extraer_marcadores(fragmento):
    patrones = [
        r"\b(?P<a>\d{1,2})\s*[-–]\s*(?P<b>\d{1,2})\b",
        r"\b(?P<a>\d{1,2})\s+a\s+(?P<b>\d{1,2})\b",
    ]
    encontrados = []
    for patron in patrones:
        for m in re.finditer(patron, fragmento, re.I):
            a = int(m.group("a"))
            b = int(m.group("b"))
            if 0 <= a <= 20 and 0 <= b <= 20:
                encontrados.append((m.start(), f"{a}-{b}"))
    return [r for _, r in sorted(encontrados, key=lambda x: x[0])]


def contiene_equipo(fragmento_norm, equipo):
    return any(v in fragmento_norm for v in variantes_equipo(equipo))


def extraer_resultado_de_texto(texto, local, visitante):
    texto = limpiar_html(texto)
    texto_norm = normalizar(texto)
    local_vars = variantes_equipo(local)
    visitante_vars = variantes_equipo(visitante)

    posiciones = []
    for variante in local_vars | visitante_vars:
        if not variante:
            continue
        for m in re.finditer(re.escape(variante), texto_norm, re.I):
            posiciones.append(m.start())

    if not posiciones:
        return ""

    for pos in sorted(posiciones)[:80]:
        inicio = max(0, pos - 700)
        fin = min(len(texto), pos + 700)
        fragmento = texto[inicio:fin]
        frag_norm = normalizar(fragmento)
        if not (contiene_equipo(frag_norm, local) and contiene_equipo(frag_norm, visitante)):
            continue
        if re.search(r"\b(pron[oó]stico|previa|cu[aá]ndo|horario|canal|entradas|clasificaci[oó]n)\b", frag_norm, re.I):
            continue
        marcadores = extraer_marcadores(fragmento)
        if marcadores:
            return marcadores[0]
    return ""


def urls_individuales(partido, html_resultados):
    urls = []
    for key in URL_KEYS:
        url = partido.get(key)
        if isinstance(url, str) and url.startswith("http"):
            urls.append(url)

    local = normalizar(partido.get("local"))
    visitante = normalizar(partido.get("visitante"))
    if html_resultados and local and visitante:
        for m in re.finditer(r'href="([^"]+)"', html_resultados):
            href = html.unescape(m.group(1))
            if "/partido/" not in href:
                continue
            pos = max(0, m.start() - 500)
            frag = html_resultados[pos:m.end() + 500]
            frag_norm = normalizar(limpiar_html(frag))
            if contiene_equipo(frag_norm, partido.get("local")) and contiene_equipo(frag_norm, partido.get("visitante")):
                if href.startswith("/"):
                    href = "https://www.flashscore.es" + href
                urls.append(href)

    vistos = set()
    limpias = []
    for url in urls:
        if url not in vistos:
            vistos.add(url)
            limpias.append(url)
    return limpias


def buscar_resultado_flashscore(partido, html_resultados):
    local = partido.get("local", "")
    visitante = partido.get("visitante", "")

    resultado = extraer_resultado_de_texto(html_resultados, local, visitante)
    if resultado:
        return resultado, FLASH_RESULTS_URL

    for url in urls_individuales(partido, html_resultados):
        try:
            time.sleep(1)
            html_partido = descargar(url)
            resultado = extraer_resultado_de_texto(html_partido, local, visitante)
            if resultado:
                return resultado, url
        except Exception as exc:
            print(f"  No se pudo consultar URL individual {url}: {exc}")
    return "", ""


def es_jornada_activa(data):
    estado = str(data.get("estado") or "").lower()
    return estado in {"", "pendiente", "en_juego", "activa", "abierta"}


def upsert_mundial(data_mundial, partido, resultado, fuente):
    resultados = data_mundial.setdefault("resultados", [])
    local = partido.get("local", "")
    visitante = partido.get("visitante", "")
    fecha = partido.get("fecha", "")
    grupo = partido.get("grupo", "")
    actual = None
    for item in resultados:
        if normalizar(item.get("local")) == normalizar(local) and normalizar(item.get("visitante")) == normalizar(visitante):
            actual = item
            break
    if actual is None:
        actual = {
            "fecha": fecha,
            "grupo": grupo,
            "local": local,
            "visitante": visitante,
        }
        resultados.append(actual)
    actual["fecha"] = actual.get("fecha") or fecha
    actual["grupo"] = actual.get("grupo") or grupo
    actual["resultado"] = resultado
    actual["signo"] = signo_resultado(resultado)
    actual["fuente"] = fuente or FLASH_RESULTS_URL
    actual["confianza"] = "confirmado"
    actual["actualizado_en"] = ahora_iso()


def actualizar_partido(partido, resultado, fuente):
    partido["resultado"] = resultado
    partido["signo_oficial"] = signo_resultado(resultado)
    partido["fuente_resultado"] = fuente or FLASH_RESULTS_URL
    partido["actualizado_en"] = ahora_iso()


def actualizar_resultados_pendientes():
    data_mundial = cargar_json(RESULTADOS_MUNDIAL, {"version": "1.0", "resultados": []})
    cambios_totales = 0

    try:
        html_resultados = descargar(FLASH_RESULTS_URL)
        print(f"Flashscore OK: {FLASH_RESULTS_URL}")
    except Exception as exc:
        html_resultados = ""
        print(f"No se pudo consultar Flashscore resultados: {exc}")

    for path in sorted(JORNADAS.glob("jornada_*.json")):
        data = cargar_json(path, {})
        if not es_jornada_activa(data):
            continue

        cambios_jornada = 0
        for partido in data.get("partidos", []):
            resultado_actual = normalizar_resultado(partido.get("resultado"))
            if resultado_actual:
                continue
            if not partido_ya_terminado(partido.get("fecha"), partido.get("hora")):
                continue
            local = partido.get("local") or ""
            visitante = partido.get("visitante") or ""
            if not local or not visitante:
                continue
            if "grupo" in normalizar(local) or "grupo" in normalizar(visitante):
                continue

            print(f"  Buscando Flashscore: {local} vs {visitante}...")
            resultado, fuente = buscar_resultado_flashscore(partido, html_resultados)
            if not resultado:
                print(f"  Sin resultado fiable: {local} vs {visitante}")
                continue

            print(f"  OK {local} vs {visitante}: {resultado}")
            actualizar_partido(partido, resultado, fuente)
            upsert_mundial(data_mundial, partido, resultado, fuente)
            cambios_jornada += 1
            cambios_totales += 1
            time.sleep(1)

        if cambios_jornada:
            data["estado"] = "cerrada" if all(normalizar_resultado(p.get("resultado")) for p in data.get("partidos", [])) else "en_juego"
            data["actualizado_en"] = ahora_iso()
            guardar_json(path, data)
            print(f"Jornada {data.get('jornada')}: {cambios_jornada} cambio(s)")

    if cambios_totales:
        data_mundial["actualizado_en"] = ahora_iso()
        guardar_json(RESULTADOS_MUNDIAL, data_mundial)

    print(f"Total Flashscore: {cambios_totales} resultado(s) actualizado(s).")
    return cambios_totales


if __name__ == "__main__":
    actualizar_resultados_pendientes()
