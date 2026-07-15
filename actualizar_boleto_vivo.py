import json
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from urllib.request import Request, urlopen

try:
    import requests
except Exception:
    requests = None

try:
    from bs4 import BeautifulSoup
except Exception:
    BeautifulSoup = None

try:
    from actualizar_jornadas_detalle import CANONICOS as CANONICOS_BASE
except Exception:
    CANONICOS_BASE = {}


ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
JORNADAS = DATA / "jornadas"
DIAGNOSTICO = DATA / "diagnostico_boleto_vivo.json"
RESULTADOS_LIBRES = DATA / "resultados_libres.json"

# Palabras genericas de nombre de club: si dos equipos solo comparten una de
# estas, no cuenta como coincidencia real (evita falsos positivos como
# "Real Madrid" vs "Real Sociedad", ambos con "real").
TOKENS_AMBIGUOS_EQUIPO = {
    "real", "athletic", "atletico", "atlético", "united", "city", "fc", "cf",
    "cd", "ud", "sd", "rc", "rcd", "club", "deportivo", "sporting", "afc",
}

FUENTES = [
    {
        "nombre": "quiniela15_resultados",
        "url": "https://www.quiniela15.com/resultados-quiniela",
        "tipo": "quiniela15",
    },
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "es-ES,es;q=0.9",
}

CANONICOS = {
    **CANONICOS_BASE,
    "ee uu": "EEUU",
    "eeuu": "EEUU",
    "estados unidos": "EEUU",
    "usa": "EEUU",
    "united states": "EEUU",
    "holanda": "Países Bajos",
    "paises bajos": "Países Bajos",
    "curaçao": "Curazao",
    "curacao": "Curazao",
    "curazao": "Curazao",
    "costa de marfil": "Costa Marfil",
    "costa marfil": "Costa Marfil",
    "malaga": "Malaga CF",
    "málaga": "Malaga CF",
    "almeria": "UD Almeria",
    "almería": "UD Almeria",
}


@dataclass
class CasillaViva:
    num: int
    local: str
    visitante: str
    resultado: str = ""
    fuente: str = ""


def ahora_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def cargar_json(path, defecto=None):
    if defecto is None:
        defecto = {}
    if not path.exists():
        return defecto
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return defecto


def guardar_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def descargar_html(url):
    if requests is not None:
        response = requests.get(url, headers=HEADERS, timeout=30)
        response.raise_for_status()
        return response.text

    req = Request(url, headers=HEADERS)
    with urlopen(req, timeout=30) as response:
        contenido = response.read()
        charset = response.headers.get_content_charset() or "utf-8"
    return contenido.decode(charset, errors="replace")


def reparar_mojibake(texto):
    texto = str(texto or "")
    try:
        reparado = texto.encode("latin1").decode("utf-8")
        if "\ufffd" not in reparado:
            return reparado
    except (UnicodeEncodeError, UnicodeDecodeError):
        pass
    return texto


def normalizar(texto):
    texto = reparar_mojibake(texto).lower()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    texto = re.sub(r"[^a-z0-9]+", " ", texto)
    texto = " ".join(texto.split()).strip()
    texto = texto.replace("ee uu", "eeuu")
    return texto


def canonico(nombre):
    texto = reparar_mojibake(nombre).strip()
    return CANONICOS.get(normalizar(texto), texto)


def limpiar_html(fragmento):
    texto = re.sub(r"(?is)<(script|style|noscript).*?</\1>", " ", fragmento)
    texto = re.sub(r"(?s)<[^>]+>", " ", texto)
    return " ".join(unescape(texto).split())


def parse_resultado(valor):
    match = re.match(r"^\s*(\d{1,2})\s*-\s*(\d{1,2})\s*$", str(valor or ""))
    if not match:
        return ""
    gl, gv = int(match.group(1)), int(match.group(2))
    if max(gl, gv) > 20:
        return ""
    return f"{gl}-{gv}"


def signo_resultado(resultado):
    gl, gv = [int(x) for x in resultado.split("-")]
    if gl > gv:
        return "1"
    if gl == gv:
        return "X"
    return "2"


def resultado_parece_final(row_html):
    texto = normalizar(limpiar_html(row_html))
    return not re.search(r"\b(descanso|1t|2t|min|minuto|en juego|live|jugando)\b", texto)


def resultado_columna_oficial(textos_td):
    if len(textos_td) < 3:
        return ""
    # En Quiniela15 la tercera columna es resultado real si el partido ha
    # terminado; si esta pendiente contiene fecha/hora y las columnas
    # siguientes son pronosticos del sistema/usuarios.
    return parse_resultado(textos_td[2])


def extraer_jornada(html):
    texto = limpiar_html(html)
    match = re.search(r"jornada\s+(\d{1,3})", texto, re.I)
    return int(match.group(1)) if match else None


def parsear_row_regex(row_html, fuente):
    num_match = re.search(r'class="[^"]*\btnum\b[^"]*"[^>]*>\s*(\d{1,2})\s*</td>', row_html, re.I)
    if not num_match:
        return None

    nombres = [
        canonico(limpiar_html(match.group(1)))
        for match in re.finditer(r'<span class="[^"]*\bfont-medium\b[^"]*"[^>]*>(.*?)</span>', row_html, re.I | re.S)
    ]
    if len(nombres) < 2:
        return None

    textos_td = [limpiar_html(td) for td in re.findall(r"(?is)<td\b[^>]*>(.*?)</td>", row_html)]
    resultado = resultado_columna_oficial(textos_td) if resultado_parece_final(row_html) else ""

    return CasillaViva(
        num=int(num_match.group(1)),
        local=nombres[0],
        visitante=nombres[1],
        resultado=resultado,
        fuente=fuente,
    )


def parsear_quiniela15_regex(html, fuente):
    items = []
    rows = re.findall(r'(?is)<tr[^>]*class="[^"]*hover:bg-gray-50[^"]*"[^>]*>(.*?)</tr>', html)
    for row in rows:
        casilla = parsear_row_regex(row, fuente)
        if casilla:
            items.append(casilla)
    return items


def clase_contiene(tag, fragmento):
    clases = tag.get("class") or []
    return any(fragmento in str(clase) for clase in clases)


def parsear_quiniela15_bs4(html, fuente):
    if BeautifulSoup is None:
        return []
    soup = BeautifulSoup(html, "html.parser")
    items = []
    for tr in soup.find_all("tr"):
        td_num = next((td for td in tr.find_all("td") if clase_contiene(td, "tnum")), None)
        if not td_num:
            continue
        try:
            num = int(td_num.get_text(" ", strip=True))
        except ValueError:
            continue

        spans = [
            span.get_text(" ", strip=True)
            for span in tr.find_all("span")
            if clase_contiene(span, "font-medium")
        ]
        if len(spans) < 2:
            continue

        textos_td = [td.get_text(" ", strip=True) for td in tr.find_all("td")]
        resultado = resultado_columna_oficial(textos_td) if resultado_parece_final(str(tr)) else ""

        items.append(CasillaViva(
            num=num,
            local=canonico(spans[0]),
            visitante=canonico(spans[1]),
            resultado=resultado,
            fuente=fuente,
        ))
    return items


def parsear_quiniela15(html, fuente):
    items = parsear_quiniela15_bs4(html, fuente)
    if len(items) >= 14:
        return items
    return parsear_quiniela15_regex(html, fuente)


def leer_boleto_vivo():
    errores = []
    for fuente in FUENTES:
        try:
            html = descargar_html(fuente["url"])
            if fuente["tipo"] == "quiniela15":
                items = parsear_quiniela15(html, fuente["nombre"])
            else:
                items = []
            jornada = extraer_jornada(html)
            normales = [item for item in items if 1 <= item.num <= 14]
            if jornada and len(normales) >= 14:
                return {
                    "jornada": jornada,
                    "items": sorted(items, key=lambda item: item.num),
                    "fuente": fuente["url"],
                    "nombre_fuente": fuente["nombre"],
                    "errores": errores,
                }
            errores.append(f"{fuente['nombre']}: lectura insuficiente ({len(normales)} casillas)")
        except Exception as exc:
            errores.append(f"{fuente['nombre']}: {exc}")
    return {"jornada": None, "items": [], "errores": errores}


def leer_resultados_libres():
    """Resultados ya descargados por actualizar_resultados_libres.py (ESPN +
    TheSportsDB + OpenFootball). No tienen numero de casilla de quiniela -se
    emparejan por nombre de equipo-, se usan solo como respaldo cuando
    quiniela15.com no ha resuelto una casilla.
    """
    data = cargar_json(RESULTADOS_LIBRES, {})
    return data.get("partidos") or []


def _tokens_equipo(nombre):
    return set(normalizar(canonico(nombre)).split())


def coincide_equipo(nombre_a, nombre_b):
    tokens_a = _tokens_equipo(nombre_a)
    tokens_b = _tokens_equipo(nombre_b)
    if not tokens_a or not tokens_b:
        return False
    if tokens_a == tokens_b:
        return True
    comunes = tokens_a & tokens_b
    if not comunes:
        return False
    if len(comunes) == 1 and next(iter(comunes)) in TOKENS_AMBIGUOS_EQUIPO:
        return False
    # Cobertura del nombre MAS CORTO: un sufijo generico de mas en uno de los
    # dos ("Villarreal" vs "Villarreal CF") no debe diluir la coincidencia,
    # mientras la palabra distintiva compartida no sea ambigua (ya filtrado
    # arriba).
    return len(comunes) / min(len(tokens_a), len(tokens_b)) >= 0.6


def buscar_resultado_libre(partidos_libres, local, visitante):
    for item in partidos_libres:
        if not item.get("resultado"):
            continue
        if coincide_equipo(item.get("local", ""), local) and coincide_equipo(item.get("visitante", ""), visitante):
            return item
    return None


def aplicar_resultados_libres_a_jornada(data, partidos_libres):
    """Segunda pasada, solo para casillas que quiniela15.com no resolvio:
    intenta completarlas con ESPN/TheSportsDB (ya descargados en
    data/resultados_libres.json) para que un fallo de la fuente principal no
    deje la jornada pendiente sin necesidad.
    """
    if not partidos_libres:
        return []
    cambios = []
    for partido in data.get("partidos", []):
        if signo_valido(partido.get("signo_oficial")):
            continue
        try:
            num = int(partido.get("num"))
        except (TypeError, ValueError):
            continue
        local = partido.get("local")
        visitante = partido.get("visitante")
        if es_placeholder(local) or es_placeholder(visitante):
            continue
        item = buscar_resultado_libre(partidos_libres, local, visitante)
        if not item:
            continue
        origen = CasillaViva(
            num=num,
            local=local,
            visitante=visitante,
            resultado=item.get("resultado", ""),
            fuente=f"resultados_libres_{item.get('fuente', 'espn')}",
        )
        cambios_casilla = aplicar_casilla(partido, origen, pleno=False)
        if cambios_casilla:
            cambios.append({"num": num, "cambios": cambios_casilla})
    if cambios:
        recalcular_estado(data)
    return cambios


def es_placeholder(nombre):
    texto = normalizar(nombre)
    return (
        not texto
        or texto == "pendiente"
        or "hypermotion" in texto
        or re.search(r"\bf[12]\b", texto) is not None
        or "por determinar" in texto
    )


def nombres_distintos(actual, nuevo):
    return normalizar(canonico(actual)) != normalizar(canonico(nuevo))


def aplicar_casilla(destino, origen, pleno=False):
    cambios = []
    nuevo_local = canonico(origen.local)
    nuevo_visitante = canonico(origen.visitante)

    if (
        es_placeholder(destino.get("local"))
        or es_placeholder(destino.get("visitante"))
        or nombres_distintos(destino.get("local"), nuevo_local)
        or nombres_distintos(destino.get("visitante"), nuevo_visitante)
    ):
        if destino.get("local") != nuevo_local or destino.get("visitante") != nuevo_visitante:
            destino["local"] = nuevo_local
            destino["visitante"] = nuevo_visitante
            destino["fuente_equipos"] = origen.fuente
            cambios.append("equipos")

    if origen.resultado:
        signo = origen.resultado if pleno else signo_resultado(origen.resultado)
        if (
            destino.get("resultado") != origen.resultado
            or destino.get("signo_oficial") != signo
            or destino.get("fuente_resultado") != origen.fuente
        ):
            mismos_valores = destino.get("resultado") == origen.resultado and destino.get("signo_oficial") == signo
            destino["resultado"] = origen.resultado
            destino["signo_oficial"] = signo
            destino["fuente_resultado"] = origen.fuente
            cambios.append("fuente_resultado" if mismos_valores else "resultado")
    elif pleno and destino.get("fuente_resultado") == origen.fuente:
        if destino.get("resultado") != "Pendiente" or destino.get("signo_oficial") != "Pendiente":
            destino["resultado"] = "Pendiente"
            destino["signo_oficial"] = "Pendiente"
            destino.pop("fuente_resultado", None)
            cambios.append("resultado_reabierto")

    if cambios:
        destino["actualizado_en"] = ahora_iso()
    return cambios


def signo_valido(valor):
    return str(valor or "").strip().upper() in {"1", "X", "2"}


def recalcular_estado(data):
    partidos = data.get("partidos", [])
    cerrados = sum(1 for p in partidos if signo_valido(p.get("signo_oficial")))
    if partidos and cerrados == len(partidos):
        data["estado"] = "cerrada"
    elif cerrados:
        data["estado"] = "en_juego"
    else:
        data["estado"] = "abierta"


def aplicar_boleto_a_jornada(data, boleto):
    por_num = {item.num: item for item in boleto.get("items", [])}
    cambios = []
    for partido in data.get("partidos", []):
        try:
            num = int(partido.get("num"))
        except Exception:
            continue
        origen = por_num.get(num)
        if not origen:
            continue
        cambios_casilla = aplicar_casilla(partido, origen, pleno=False)
        if cambios_casilla:
            cambios.append({"num": num, "cambios": cambios_casilla})

    pleno = data.get("pleno15") or {}
    origen_pleno = por_num.get(15)
    if pleno and origen_pleno:
        cambios_pleno = aplicar_casilla(pleno, origen_pleno, pleno=True)
        if cambios_pleno:
            cambios.append({"num": 15, "cambios": cambios_pleno})
        data["pleno15"] = pleno

    if cambios:
        data["fuente_boleto_vivo"] = boleto.get("fuente", "")
        data["boleto_vivo_actualizado_en"] = ahora_iso()
        recalcular_estado(data)
    return cambios


def jornada_objetivo(boleto):
    numero = boleto.get("jornada")
    if numero and (JORNADAS / f"jornada_{numero}.json").exists():
        return int(numero)
    nums = []
    for path in JORNADAS.glob("jornada_*.json"):
        match = re.search(r"(\d+)", path.stem)
        if match:
            nums.append(int(match.group(1)))
    return max(nums) if nums else None


def guardar_diagnostico(boleto, cambios, jornada=None, casillas_via_respaldo=0):
    guardar_json(DIAGNOSTICO, {
        "generado_en": ahora_iso(),
        "jornada": jornada or boleto.get("jornada"),
        "fuente": boleto.get("fuente", ""),
        "casillas_leidas": len(boleto.get("items", [])),
        "cambios": cambios,
        "casillas_via_respaldo_resultados_libres": casillas_via_respaldo,
        "errores": boleto.get("errores", []),
        "estado": "actualizado" if cambios else "sin_cambios",
    })


def main():
    boleto = leer_boleto_vivo()
    jornada = jornada_objetivo(boleto)
    if not jornada:
        guardar_diagnostico(boleto, [], None)
        print("No se pudo determinar jornada para boleto vivo.")
        return

    path = JORNADAS / f"jornada_{jornada}.json"
    data = cargar_json(path, {})
    if not data:
        guardar_diagnostico(boleto, [], jornada)
        print(f"No existe jornada local {jornada}.")
        return

    cambios = aplicar_boleto_a_jornada(data, boleto)

    partidos_libres = leer_resultados_libres()
    cambios_libres = aplicar_resultados_libres_a_jornada(data, partidos_libres)
    if cambios_libres:
        cambios.extend(cambios_libres)
        print(f"Boleto vivo jornada {jornada}: {len(cambios_libres)} casilla(s) completadas de respaldo (ESPN/TheSportsDB).")

    if cambios:
        guardar_json(path, data)
    guardar_diagnostico(boleto, cambios, jornada, casillas_via_respaldo=len(cambios_libres))
    print(f"Boleto vivo jornada {jornada}: {len(cambios)} casillas actualizadas.")


if __name__ == "__main__":
    main()
