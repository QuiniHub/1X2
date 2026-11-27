"""
Busca resultados de partidos pendientes usando Flashscore directamente.

Para cada jornada activa, revisa partidos pendientes que ya deberian haber
terminado, consulta la pagina de resultados del Mundial en Flashscore y, si
existe una URL individual del partido en el JSON, tambien consulta esa pagina.
Actualiza jornada_XX.json y mundial_2026_resultados.json cuando encuentra un
marcador fiable cerca de los nombres de los equipos.

Auditoria 26/11 (hallazgos 6 y 126): la pagina que se consulta es la de
resultados del MUNDIAL 2026, asi que este script solo puede dar resultados de
partidos del Mundial. El 22/11/2026 publico un 2-0 falso en un partido de
clubes (R. Santander - Real Sociedad, real 3-2) porque:
  * 'R. Santander' generaba la variante 'r' (primera palabra) y se comparaba
    por subcadena, asi que casaba con cualquier texto;
  * se buscaban partidos de clubes en una pagina del Mundial;
  * el marcador se guardaba como 'confirmado' en mundial_2026_resultados.json.
Ahora: solo partidos dentro de las fechas del Mundial, nombres distintivos y
comparados por palabra completa, la URL individual debe nombrar a los dos
equipos, y si no hay ningun partido candidato no se hace ninguna peticion.
"""

import html
import json
import re
import time
import unicodedata
from datetime import date, datetime, time as dt_time, timedelta, timezone
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

# La pagina anterior solo contiene partidos del Mundial 2026 (11/06 - 19/07/2026).
# Fuera de esas fechas un partido de data/jornadas es de clubes y NO se busca aqui.
MUNDIAL_INICIO = date(2026, 6, 11)
MUNDIAL_FIN = date(2026, 7, 19)

# Palabras que no identifican a un equipo por si solas ('R. Santander' -> 'r',
# 'Real Sociedad' -> 'real', 'Club Atletico' -> 'club', 'RC Celta' -> 'rc'...).
PALABRAS_NO_DISTINTIVAS = {
    "real", "club", "atletico", "athletic", "deportivo", "sporting", "racing",
    "union", "sociedad", "sport", "futbol", "football", "city", "united",
    "nueva", "new", "san", "santa", "sur", "norte", "costa", "cabo", "arabia",
    "republica", "estados", "paises", "corea", "guinea", "south", "north",
    "saudi", "islas", "villa",
}
MIN_LETRAS_VARIANTE = 4

HEADERS = {
    # Cliente automatizado identificado como tal (no se suplanta un navegador).
    "User-Agent": "quiniela-resultados-bot/1.0 (cliente automatizado; python-requests)",
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


def variante_distintiva(variante):
    """True si la variante identifica a un equipo sin ambiguedad razonable.

    Se rechazan las de menos de 4 letras ('r', 'rc', 'ca', 'ud') y las que son
    una sola palabra generica ('real', 'club', 'sporting').
    """
    variante = str(variante or "").strip()
    if len(variante.replace(" ", "")) < MIN_LETRAS_VARIANTE:
        return False
    partes = variante.split()
    if len(partes) == 1 and partes[0] in PALABRAS_NO_DISTINTIVAS:
        return False
    return True


def variantes_equipo(nombre):
    """Nombre normalizado completo y sus alias. NUNCA la primera palabra suelta."""
    base = normalizar(nombre)
    variantes = {base}
    for alias, canonico in ALIAS.items():
        if canonico == base:
            variantes.add(normalizar(alias))
    return {v for v in variantes if v and variante_distintiva(v)}


def patron_variante(variante):
    """Regex de palabra completa: 'iran' no casa dentro de 'tirana'."""
    return r"(?<![a-z0-9])" + re.escape(variante) + r"(?![a-z0-9])"


def fecha_partido(fecha_txt):
    try:
        return datetime.fromisoformat(str(fecha_txt)).date()
    except Exception:
        return None


def es_partido_mundial(partido):
    """Solo los partidos jugados en las fechas del Mundial pueden estar en la
    pagina de resultados del Mundial. Sin fecha valida no se busca."""
    fecha = fecha_partido((partido or {}).get("fecha"))
    return fecha is not None and MUNDIAL_INICIO <= fecha <= MUNDIAL_FIN


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
    return any(re.search(patron_variante(v), fragmento_norm) for v in variantes_equipo(equipo))


def url_nombra_a_los_dos(url, local, visitante):
    """La URL individual de Flashscore lleva los dos equipos en el slug
    (/partido/futbol/atletico-madrid-xxx/getafe-cf-yyy/). Si no nombra a los dos
    equipos del partido buscado, es la pagina de OTRO partido."""
    slug = normalizar(str(url or "").split("?")[0])
    return contiene_equipo(slug, local) and contiene_equipo(slug, visitante)


def extraer_resultado_de_texto(texto, local, visitante):
    texto = limpiar_html(texto)
    texto_norm = normalizar(texto)
    local_vars = variantes_equipo(local)
    visitante_vars = variantes_equipo(visitante)
    if not local_vars or not visitante_vars:
        # Sin un nombre distintivo para cada equipo no hay forma segura de casar.
        return ""

    posiciones = []
    for variante in local_vars | visitante_vars:
        if not variante:
            continue
        for m in re.finditer(patron_variante(variante), texto_norm, re.I):
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
            # Una URL de Flashscore de otro partido no vale (hallazgo 6).
            if "flashscore" in url and "/partido/" in url and not url_nombra_a_los_dos(
                url, partido.get("local"), partido.get("visitante")
            ):
                continue
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
                # El enlace debe ser del propio partido, no de uno vecino en la pagina.
                if url_nombra_a_los_dos(href, partido.get("local"), partido.get("visitante")):
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
    if not es_partido_mundial(partido):
        # mundial_2026_resultados.json es solo del Mundial: nunca partidos de clubes.
        return False
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
    return True


def actualizar_partido(partido, resultado, fuente):
    partido["resultado"] = resultado
    partido["signo_oficial"] = signo_resultado(resultado)
    partido["fuente_resultado"] = fuente or FLASH_RESULTS_URL
    partido["actualizado_en"] = ahora_iso()


def partido_candidato(partido):
    """Partido pendiente, ya terminado, del Mundial y con equipos reales."""
    if normalizar_resultado(partido.get("resultado")):
        return False
    if str(partido.get("signo_oficial") or "").strip():
        # Signo ya fijado por otra fuente (LAE, sorteo, correccion): no se toca.
        return False
    if not es_partido_mundial(partido):
        return False
    if not partido_ya_terminado(partido.get("fecha"), partido.get("hora")):
        return False
    local = partido.get("local") or ""
    visitante = partido.get("visitante") or ""
    if not local or not visitante:
        return False
    if "grupo" in normalizar(local) or "grupo" in normalizar(visitante):
        return False
    return True


def actualizar_resultados_pendientes():
    cambios_totales = 0

    # Primero se decide SIN RED si hay algo que buscar. Fuera del Mundial no hay
    # candidatos y el script termina sin ninguna peticion.
    pendientes = []
    for path in sorted(JORNADAS.glob("jornada_*.json")):
        data = cargar_json(path, {})
        if not isinstance(data, dict) or not es_jornada_activa(data):
            continue
        if any(partido_candidato(x) for x in data.get("partidos", []) if isinstance(x, dict)):
            pendientes.append(path)

    if not pendientes:
        print("Flashscore Mundial: ningun partido del Mundial pendiente; no se consulta la red.")
        print("Total Flashscore: 0 resultado(s) actualizado(s).")
        return 0

    if RESULTADOS_MUNDIAL.exists():
        try:
            data_mundial = json.loads(RESULTADOS_MUNDIAL.read_text(encoding="utf-8"))
        except Exception as exc:
            # Fichero ilegible: no se sobrescribe el acumulado con uno vacio.
            print(f"AVISO: {RESULTADOS_MUNDIAL.name} no se puede leer ({exc}); no se toca.")
            return 0
    else:
        data_mundial = {"version": "1.0", "resultados": []}

    try:
        html_resultados = descargar(FLASH_RESULTS_URL)
        print(f"Flashscore OK: {FLASH_RESULTS_URL}")
    except Exception as exc:
        html_resultados = ""
        print(f"No se pudo consultar Flashscore resultados: {exc}")

    for path in pendientes:
        data = cargar_json(path, {})

        cambios_jornada = 0
        for partido in data.get("partidos", []):
            if not isinstance(partido, dict) or not partido_candidato(partido):
                continue
            local = partido.get("local") or ""
            visitante = partido.get("visitante") or ""

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
