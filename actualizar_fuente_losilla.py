"""Scraper principal de EduardoLosilla.es y La Bruja de Oro para alimentar la memoria IA.

Extrae, de forma defensiva, probabilidades, cuotas, escrutinio y
clasificaciones publicadas en fuentes externas. En probabilidades incluye los
14 partidos 1/X/2 y el Pleno al 15 con porcentajes de goles 0/1/2/M para cada
equipo. Si una web falla o cambia su HTML, el script no detiene el flujo:
conserva el ultimo dato local valido en data/memoria_ia/fuente_losilla.json y
deja avisos en la salida.

El escrutinio se guarda como historico acumulado bajo claves jornada_XX para
no perder jornadas anteriores.
"""

import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup


ROOT = Path(__file__).resolve().parent
SALIDA = ROOT / "data" / "memoria_ia" / "fuente_losilla.json"

BASE = "https://www.eduardolosilla.es"
URL_BOLETOS = f"{BASE}/quiniela/boletos"
URL_CUOTAS = f"{BASE}/quiniela/ayudas/cuotas"
URL_CLASIFICACION = f"{BASE}/quiniela/ayudas/clasificacion"
URL_ESCRUTINIO = f"{BASE}/quiniela/ayudas/escrutinio/jornada_{{jornada}}"
URL_BRUJA_PREMIOS = "https://www.labrujadeoro.es/quiniela-premios.htm"

TIMEOUT = 10
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
}

LABELS_NO_EQUIPO = {
    "0",
    "1",
    "x",
    "2",
    "m",
    "prob",
    "probabilidad",
    "probabilidades",
    "porcentaje",
    "porcentajes",
    "% prob",
    "local",
    "visitante",
    "equipo",
    "equipos",
    "partido",
    "pleno",
    "pleno al 15",
    "goles",
}

CATEGORIAS_ESCRUTINIO = ("15", "14", "13", "12", "11", "10", "elige8")
NOMBRES_CATEGORIA = {
    "15": "Pleno al 15",
    "14": "14 Aciertos",
    "13": "13 Aciertos",
    "12": "12 Aciertos",
    "11": "11 Aciertos",
    "10": "10 Aciertos",
    "elige8": "Elige 8 (8 Ac)",
}
CLAVES_PREMIO = {
    "15": "premio_pleno_al_15",
    "14": "premio_14",
    "13": "premio_13",
    "12": "premio_12",
    "11": "premio_11",
    "10": "premio_10",
    "elige8": "premio_elige8",
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


def normalizar_clave(texto):
    texto = normalizar_texto(texto).lower()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    texto = re.sub(r"[^a-z0-9%]+", " ", texto)
    return " ".join(texto.split()).strip()


def numero(valor):
    if valor is None:
        return None
    texto = normalizar_texto(valor)
    texto = texto.replace("%", "").replace("€", "")
    texto = re.sub(r"[^0-9,.-]", "", texto)
    if "," in texto:
        texto = texto.replace(".", "").replace(",", ".")
    elif texto.count(".") > 1:
        texto = texto.replace(".", "")
    texto = texto.strip()
    if not texto or texto in {"-", ".", "-."}:
        return None
    try:
        return float(texto)
    except ValueError:
        return None


def entero(valor):
    n = numero(valor)
    return int(n) if n is not None else None


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


def texto_soup(soup):
    return normalizar_texto(soup.get_text(" "))


def celdas_fila(fila):
    return [normalizar_texto(c.get_text(" ")) for c in fila.find_all(["th", "td"])]


def todas_las_filas(soup):
    filas = []
    for tr in soup.find_all("tr"):
        celdas = celdas_fila(tr)
        if celdas:
            filas.append(celdas)
    return filas


def porcentajes_en_texto(texto):
    valores = [numero(x) for x in re.findall(r"\d{1,3}(?:[,.]\d+)?\s*%", texto)]
    return [v for v in valores if v is not None and 0 <= v <= 100]


def separar_partido(texto):
    texto = normalizar_texto(texto)
    texto = re.sub(r"^\d{1,2}[.)ºª]?\s+", "", texto)
    texto = re.sub(r"^Pleno\s+al\s+15\s*[:.-]?\s*", "", texto, flags=re.I)
    partes = re.split(r"\s+(?:-|–|—|vs\.?|contra)\s+", texto, maxsplit=1, flags=re.I)
    if len(partes) != 2:
        return None, None
    local = normalizar_texto(partes[0])
    visitante = normalizar_texto(partes[1])
    visitante = re.sub(r"\s+\d+(?:[,.]\d+|%)?.*$", "", visitante).strip()
    if not local or not visitante:
        return None, None
    return local, visitante


def extraer_jornada(texto):
    patrones = (
        r"\bJORNADA\s*(?:N[ºO.]?\s*)?(\d{1,3})\b",
        r"\bJ\.\s*(\d{1,3})\b",
    )
    jornadas = []
    for patron in patrones:
        jornadas.extend(int(x) for x in re.findall(patron, texto or "", flags=re.I))
    return max(jornadas) if jornadas else None


def clave_jornada(jornada):
    try:
        return f"jornada_{int(jornada):02d}"
    except (TypeError, ValueError):
        return None


def numero_partido_en_fila(celdas):
    if not celdas:
        return None
    candidatos = celdas[:2]
    for celda in candidatos:
        m = re.match(r"^\s*(1[0-5]|[1-9])(?:[.)ºª]|\s|$)", celda)
        if m:
            return int(m.group(1))
    return None


def limpiar_candidato_equipo(texto):
    texto = normalizar_texto(texto)
    texto = re.sub(r"^\d{1,2}[.)ºª]?\s*", "", texto)
    texto = re.sub(r"^Pleno\s+al\s+15\s*[:.-]?\s*", "", texto, flags=re.I)
    texto = re.split(r"\d{1,3}(?:[,.]\d+)?\s*%", texto, maxsplit=1)[0]
    texto = normalizar_texto(texto)
    clave = normalizar_clave(texto)
    if not texto or clave in LABELS_NO_EQUIPO:
        return ""
    if re.fullmatch(r"[\d,.% €+\-/]+", texto):
        return ""
    if len(texto) > 60:
        return ""
    return texto


def extraer_equipos_de_celdas(celdas):
    for celda in celdas:
        local, visitante = separar_partido(celda)
        if local and visitante:
            return local, visitante

    candidatos = []
    for celda in celdas:
        candidato = limpiar_candidato_equipo(celda)
        if candidato and normalizar_clave(candidato) not in {normalizar_clave(c) for c in candidatos}:
            candidatos.append(candidato)
    if len(candidatos) >= 2:
        return candidatos[0], candidatos[1]
    return None, None


def extraer_partidos_desde_texto(texto):
    partidos = []
    patron = re.compile(
        r"(?:^|\s)(?P<num>\d{1,2})\s+"
        r"(?P<local>[A-ZÁÉÍÓÚÜÑ0-9 .]+?)\s*[-–—]\s*"
        r"(?P<visitante>[A-ZÁÉÍÓÚÜÑ0-9 .]+?)(?=\s+\d{1,2}\s+[A-ZÁÉÍÓÚÜÑ]|\s+15\s+|$)"
    )
    for m in patron.finditer(texto):
        num = int(m.group("num"))
        if 1 <= num <= 15:
            partidos.append(
                {
                    "numero": num,
                    "local": normalizar_texto(m.group("local")),
                    "visitante": normalizar_texto(m.group("visitante")),
                }
            )
    return partidos[:15]


def construir_partido_1x2(numero_partido, local, visitante, porcentajes):
    return {
        "numero": numero_partido,
        "tipo": "1X2",
        "local": local,
        "visitante": visitante,
        "probabilidad_1": porcentajes[0],
        "probabilidad_X": porcentajes[1],
        "probabilidad_2": porcentajes[2],
        "probabilidades_signo": {
            "1": porcentajes[0],
            "X": porcentajes[1],
            "2": porcentajes[2],
        },
    }


def construir_pleno_al_15(local, visitante, porcentajes, fuente):
    valores = list(porcentajes or [])[:8]
    while len(valores) < 8:
        valores.append(None)
    return {
        "numero": 15,
        "tipo": "pleno_al_15",
        "local": local,
        "visitante": visitante,
        "probabilidad_local_0": valores[0],
        "probabilidad_local_1": valores[1],
        "probabilidad_local_2": valores[2],
        "probabilidad_local_M": valores[3],
        "probabilidad_visitante_0": valores[4],
        "probabilidad_visitante_1": valores[5],
        "probabilidad_visitante_2": valores[6],
        "probabilidad_visitante_M": valores[7],
        "probabilidades_goles_local": {
            "0": valores[0],
            "1": valores[1],
            "2": valores[2],
            "M": valores[3],
        },
        "probabilidades_goles_visitante": {
            "0": valores[4],
            "1": valores[5],
            "2": valores[6],
            "M": valores[7],
        },
        "fuente_parseo": fuente,
    }


def partido_por_numero(partidos, numero_partido):
    for partido in partidos:
        if partido.get("numero") == numero_partido:
            return partido
    return None


def extraer_pleno_desde_texto(texto, partidos_texto):
    partido_15 = partido_por_numero(partidos_texto, 15) or {}
    local = partido_15.get("local")
    visitante = partido_15.get("visitante")

    marcadores = [m.start() for m in re.finditer(r"Pleno\s+al\s+15|Partido\s+15", texto, flags=re.I)]
    for inicio in marcadores:
        fragmento = texto[inicio : inicio + 1200]
        porcentajes = porcentajes_en_texto(fragmento)
        frag_local, frag_visitante = separar_partido(fragmento[:250])
        if frag_local and frag_visitante:
            local, visitante = frag_local, frag_visitante
        if local and visitante and len(porcentajes) >= 8:
            return construir_pleno_al_15(local, visitante, porcentajes[:8], "texto_pleno")

    porcentajes_todos = porcentajes_en_texto(texto)
    offset_pleno = 14 * 3
    if local and visitante and len(porcentajes_todos) >= offset_pleno + 8:
        return construir_pleno_al_15(
            local,
            visitante,
            porcentajes_todos[offset_pleno : offset_pleno + 8],
            "texto_offset_14x3",
        )
    if local and visitante:
        return construir_pleno_al_15(local, visitante, [], "solo_equipos_texto")
    return None


def extraer_probabilidades():
    html = descargar(URL_BOLETOS)
    soup = soup_de(html)
    texto = texto_soup(soup)
    jornada = extraer_jornada(texto)
    partidos_texto = extraer_partidos_desde_texto(texto)
    partidos_1x2 = []
    pleno_al_15 = None

    for celdas in todas_las_filas(soup):
        fila = " ".join(celdas)
        if "% PROB" in fila.upper():
            continue
        porcentajes = [numero(c) for c in celdas if "%" in c]
        porcentajes = [p for p in porcentajes if p is not None and 0 <= p <= 100]
        if len(porcentajes) < 3:
            porcentajes = porcentajes_en_texto(fila)
        if len(porcentajes) < 3:
            continue

        numero_fila = numero_partido_en_fila(celdas)
        local, visitante = extraer_equipos_de_celdas(celdas)
        if not (local and visitante):
            esperado = numero_fila or (len(partidos_1x2) + 1)
            partido_base = partido_por_numero(partidos_texto, esperado) or {}
            local = partido_base.get("local")
            visitante = partido_base.get("visitante")
        if not (local and visitante):
            continue

        es_pleno = (
            numero_fila == 15
            or "PLENO" in fila.upper()
            or (len(partidos_1x2) >= 14 and len(porcentajes) >= 8)
        )
        if es_pleno and len(porcentajes) >= 8:
            pleno_al_15 = construir_pleno_al_15(local, visitante, porcentajes[:8], "fila_html")
            continue

        if len(partidos_1x2) < 14:
            numero_partido = numero_fila or len(partidos_1x2) + 1
            if 1 <= numero_partido <= 14:
                partidos_1x2.append(construir_partido_1x2(numero_partido, local, visitante, porcentajes[:3]))

    if not partidos_1x2:
        porcentajes = porcentajes_en_texto(texto)
        for idx, partido in enumerate(partidos_texto[:14]):
            offs = idx * 3
            if len(porcentajes) >= offs + 3:
                partidos_1x2.append(
                    construir_partido_1x2(
                        partido.get("numero") or idx + 1,
                        partido.get("local"),
                        partido.get("visitante"),
                        porcentajes[offs : offs + 3],
                    )
                )

    if not pleno_al_15:
        pleno_al_15 = extraer_pleno_desde_texto(texto, partidos_texto)

    if not partidos_1x2 and not pleno_al_15:
        return None

    partidos = partidos_1x2[:14]
    if pleno_al_15:
        partidos = partidos + [pleno_al_15]

    return {
        "url": URL_BOLETOS,
        "jornada": jornada,
        "partidos": partidos,
        "partidos_1x2": partidos_1x2[:14],
        "pleno_al_15": pleno_al_15,
        "extraido_en": ahora_iso(),
    }


def extraer_cuotas():
    html = descargar(URL_CUOTAS)
    soup = soup_de(html)
    texto = texto_soup(soup)
    jornada = extraer_jornada(texto)
    partidos_texto = extraer_partidos_desde_texto(texto)
    partidos = []

    for celdas in todas_las_filas(soup):
        local, visitante = extraer_equipos_de_celdas(celdas)
        valores = [numero(c) for c in celdas]
        valores = [v for v in valores if v is not None and 1.0 <= v <= 99.0]
        if local and visitante and len(valores) >= 3:
            partidos.append(
                {
                    "numero": len(partidos) + 1,
                    "local": local,
                    "visitante": visitante,
                    "cuota_media_1": valores[-3],
                    "cuota_media_X": valores[-2],
                    "cuota_media_2": valores[-1],
                }
            )
        if len(partidos) >= 14:
            break

    if not partidos and partidos_texto:
        for partido in partidos_texto[:14]:
            partidos.append({**partido, "cuota_media_1": None, "cuota_media_X": None, "cuota_media_2": None})

    if not partidos:
        return None
    return {"url": URL_CUOTAS, "jornada": jornada, "partidos": partidos[:14], "extraido_en": ahora_iso()}


def candidatos_jornada_cerrada(*textos):
    max_jornada = None
    for texto in textos:
        jornada = extraer_jornada(texto or "")
        if jornada is not None:
            max_jornada = max(max_jornada or jornada, jornada)
    if max_jornada:
        inicio = max(max_jornada - 1, 1)
        return list(range(inicio, max(0, inicio - 15), -1))
    return list(range(90, 0, -1))


def categoria_desde_texto(texto):
    clave = normalizar_clave(texto)
    if "elige" in clave and "8" in clave:
        return "elige8"
    if "pleno" in clave and "15" in clave:
        return "15"
    if "especial" in clave and "15" in clave:
        return "15"
    for categoria in ("14", "13", "12", "11", "10"):
        if re.search(rf"\b{categoria}\b", clave) and (("acierto" in clave) or ("ac" in clave)):
            return categoria
    return None


def primer_importe(celdas):
    candidatos = []
    for celda in celdas:
        if "€" in celda or re.search(r"\d+\s*(?:euros?|eur)\b", celda, flags=re.I):
            valor = numero(celda)
            if valor is not None:
                candidatos.append(valor)
    if candidatos:
        return candidatos[-1]

    for celda in reversed(celdas):
        valor = numero(celda)
        if valor is not None and ("," in celda or "." in celda):
            return valor
    return None


def primer_acertantes(celdas):
    for celda in celdas:
        if "€" in celda:
            continue
        valor = entero(celda)
        if valor is not None:
            return valor
    return None


def construir_registro_escrutinio(jornada, categorias, url, fuente):
    clave = clave_jornada(jornada)
    if not clave or not categorias:
        return None

    normalizadas = {}
    for categoria in CATEGORIAS_ESCRUTINIO:
        datos = categorias.get(categoria) or {}
        premio = datos.get("premio_euros")
        normalizadas[categoria] = {
            "nombre": NOMBRES_CATEGORIA[categoria],
            "acertantes": datos.get("acertantes"),
            "premio_euros": float(premio) if premio is not None else 0.0,
        }

    registro = {
        "url": url,
        "fuente": fuente,
        "jornada": int(jornada),
        "clave": clave,
        "categorias": normalizadas,
        "extraido_en": ahora_iso(),
    }
    for categoria, nombre_clave in CLAVES_PREMIO.items():
        registro[nombre_clave] = normalizadas.get(categoria, {}).get("premio_euros", 0.0)
    return registro


def extraer_escrutinio_bruja():
    html = descargar(URL_BRUJA_PREMIOS)
    soup = soup_de(html)
    texto = texto_soup(soup)
    jornada = extraer_jornada(texto)
    categorias = {}

    for celdas in todas_las_filas(soup):
        fila = " ".join(celdas)
        categoria = categoria_desde_texto(fila)
        if not categoria:
            continue

        premio = primer_importe(celdas[1:]) if len(celdas) > 1 else primer_importe(celdas)
        acertantes = primer_acertantes(celdas[1:]) if len(celdas) > 1 else None
        if premio is None and "bote" in normalizar_clave(fila):
            premio = 0.0

        categorias[categoria] = {
            "acertantes": acertantes,
            "premio_euros": premio if premio is not None else 0.0,
        }

    if len(categorias) < 3:
        for categoria, etiqueta in NOMBRES_CATEGORIA.items():
            variantes = [etiqueta]
            if categoria == "15":
                variantes += ["Pleno al quince", "Categoria especial"]
            elif categoria == "elige8":
                variantes += ["Elige8", "8 Aciertos Elige 8", "8 Ac."]
            for variante in variantes:
                patron = re.compile(
                    rf"{re.escape(variante)}.{{0,120}}?(\d[\d.,]*)\s*(?:€|euros?|eur)",
                    flags=re.I,
                )
                m = patron.search(texto)
                if m:
                    categorias.setdefault(categoria, {"acertantes": None, "premio_euros": numero(m.group(1)) or 0.0})
                    break

    return construir_registro_escrutinio(jornada, categorias, URL_BRUJA_PREMIOS, "labrujadeoro.es")


def extraer_escrutinio_desde_texto(texto, jornada, url):
    limpio = normalizar_texto(texto)
    categorias = {}

    for categoria in ("15", "14", "13", "12", "11", "10"):
        etiqueta = "Pleno al 15" if categoria == "15" else f"{categoria} Aciertos"
        patrones = [
            rf"(?:{categoria}\s+aciertos|acertantes\s+de\s+{categoria}|premio\s+{categoria}|{re.escape(etiqueta)}).{{0,80}}?(\d[\d.]*)\D+(\d[\d.,]*)\s*€",
            rf"{categoria}\s+(\d[\d.]*)\s+(\d[\d.,]*)\s*€",
        ]
        for patron in patrones:
            m = re.search(patron, limpio, flags=re.I)
            if m:
                categorias[categoria] = {"acertantes": entero(m.group(1)), "premio_euros": numero(m.group(2))}
                break

    m_elige8 = re.search(r"(?:elige\s*8|8\s*ac\.?).{0,100}?(\d[\d.,]*)\s*€", limpio, flags=re.I)
    if m_elige8:
        categorias["elige8"] = {"acertantes": None, "premio_euros": numero(m_elige8.group(1)) or 0.0}

    if not categorias:
        return None
    return construir_registro_escrutinio(jornada, categorias, url, "eduardolosilla.es")


def extraer_escrutinio_losilla(textos_referencia):
    for jornada in candidatos_jornada_cerrada(*textos_referencia):
        url = URL_ESCRUTINIO.format(jornada=jornada)
        try:
            html = descargar(url)
            soup = soup_de(html)
            resultado = extraer_escrutinio_desde_texto(texto_soup(soup), jornada, url)
            if resultado:
                return resultado
        except Exception as exc:
            print(f"AVISO Losilla escrutinio jornada {jornada}: {exc}")
    return None


def extraer_escrutinio(textos_referencia):
    try:
        resultado = extraer_escrutinio_bruja()
        if resultado:
            return resultado
    except Exception as exc:
        print(f"AVISO Bruja de Oro escrutinio: {exc}")

    return extraer_escrutinio_losilla(textos_referencia)


def parsear_linea_clasificacion(linea):
    m = re.match(
        r"^\s*(?P<pos>\d{1,2})[ºª.]?\s+"
        r"(?P<equipo>.+?)\s+"
        r"(?P<pts>\d+)\s+(?P<pj>\d+)\s+(?P<g>\d+)\s+"
        r"(?P<e>\d+)\s+(?P<p>\d+)\s+(?P<gf>\d+)\s+(?P<gc>\d+)\s*$",
        linea,
        flags=re.I,
    )
    if not m:
        return None
    gf = int(m.group("gf"))
    gc = int(m.group("gc"))
    return {
        "posicion": int(m.group("pos")),
        "equipo": normalizar_texto(m.group("equipo")),
        "PJ": int(m.group("pj")),
        "G": int(m.group("g")),
        "E": int(m.group("e")),
        "P": int(m.group("p")),
        "GF": gf,
        "GC": gc,
        "DG": gf - gc,
        "Pts": int(m.group("pts")),
    }


def nombre_liga_desde_heading(texto):
    texto = normalizar_texto(texto)
    texto = re.sub(r"^Clasificaci[oó]n\s+(?:de\s+)?", "", texto, flags=re.I)
    return texto or "General"


def extraer_clasificaciones():
    html = descargar(URL_CLASIFICACION)
    soup = soup_de(html)
    clasificaciones = {}

    for tabla in soup.find_all("table"):
        anterior = tabla.find_previous(["h1", "h2", "h3", "h4"])
        titulo = nombre_liga_desde_heading(anterior.get_text(" ")) if anterior else f"Liga {len(clasificaciones) + 1}"
        filas = []
        for tr in tabla.find_all("tr"):
            fila = parsear_linea_clasificacion(normalizar_texto(" ".join(celdas_fila(tr))))
            if fila:
                filas.append(fila)
        if filas:
            clasificaciones[titulo] = filas

    if not clasificaciones:
        texto = texto_soup(soup)
        liga_actual = "1ª División"
        filas = []
        for linea in re.split(r"(?=(?:\d{1,2}[ºª.]\s+))", texto):
            if "Clasificación de" in linea:
                liga_actual = nombre_liga_desde_heading(linea.split("Clasificación de", 1)[-1].split(" TODAS", 1)[0])
            fila = parsear_linea_clasificacion(normalizar_texto(linea))
            if fila:
                filas.append(fila)
        if filas:
            clasificaciones[liga_actual] = filas

    if not clasificaciones:
        return None
    return {"url": URL_CLASIFICACION, "ligas": clasificaciones, "extraido_en": ahora_iso()}


def fusionar_probabilidades(anterior, nuevo):
    previas = anterior.get("probabilidades", {}) if isinstance(anterior, dict) else {}
    if not nuevo:
        return previas

    pleno = nuevo.get("pleno_al_15") or previas.get("pleno_al_15")
    partidos_1x2 = nuevo.get("partidos_1x2") or previas.get("partidos_1x2") or []
    if not partidos_1x2 and previas.get("partidos"):
        partidos_1x2 = [p for p in previas.get("partidos", []) if p.get("tipo") != "pleno_al_15"][:14]

    nuevo["partidos_1x2"] = partidos_1x2[:14]
    nuevo["pleno_al_15"] = pleno
    nuevo["partidos"] = nuevo["partidos_1x2"] + ([pleno] if pleno else [])
    return nuevo


def normalizar_registro_legacy(registro):
    if not isinstance(registro, dict):
        return None
    jornada = registro.get("jornada")
    clave = clave_jornada(jornada)
    if not clave:
        return None

    categorias = {}
    for categoria, datos in (registro.get("categorias") or {}).items():
        clave_categoria = "elige8" if str(categoria).lower() == "elige8" else str(categoria)
        if clave_categoria in CATEGORIAS_ESCRUTINIO and isinstance(datos, dict):
            categorias[clave_categoria] = {
                "acertantes": datos.get("acertantes"),
                "premio_euros": datos.get("premio_euros", datos.get("premio", 0.0)) or 0.0,
            }

    for categoria, nombre_clave in CLAVES_PREMIO.items():
        if nombre_clave in registro:
            categorias.setdefault(categoria, {"acertantes": None, "premio_euros": registro.get(nombre_clave) or 0.0})

    return construir_registro_escrutinio(
        jornada,
        categorias,
        registro.get("url") or "",
        registro.get("fuente") or "legacy",
    )


def historico_escrutinio(escrutinio):
    if not isinstance(escrutinio, dict) or not escrutinio:
        return {}

    if any(str(k).startswith("jornada_") for k in escrutinio):
        historico = {}
        for clave, registro in escrutinio.items():
            normalizado = normalizar_registro_legacy(registro)
            if normalizado:
                historico[clave_jornada(normalizado["jornada"]) or clave] = normalizado
            elif isinstance(registro, dict):
                historico[str(clave)] = registro
        return historico

    normalizado = normalizar_registro_legacy(escrutinio)
    if normalizado:
        return {clave_jornada(normalizado["jornada"]): normalizado}
    return {}


def categoria_con_dato(categoria):
    if not isinstance(categoria, dict):
        return False
    premio = categoria.get("premio_euros")
    acertantes = categoria.get("acertantes")
    return premio not in (None, "") or acertantes not in (None, "")


def fusionar_registros_escrutinio(previo, nuevo):
    if not isinstance(previo, dict):
        return nuevo
    if not isinstance(nuevo, dict):
        return previo

    fusionado = dict(previo)
    for campo in ("url", "fuente", "jornada", "clave", "extraido_en"):
        if not fusionado.get(campo) and nuevo.get(campo):
            fusionado[campo] = nuevo[campo]

    categorias = dict(fusionado.get("categorias") or {})
    for categoria, datos_nuevos in (nuevo.get("categorias") or {}).items():
        datos_previos = categorias.get(categoria)
        if not categoria_con_dato(datos_previos):
            categorias[categoria] = datos_nuevos
    fusionado["categorias"] = categorias

    for categoria, nombre_clave in CLAVES_PREMIO.items():
        previo_valor = fusionado.get(nombre_clave)
        nuevo_valor = nuevo.get(nombre_clave)
        if previo_valor in (None, "") or (float(previo_valor or 0.0) == 0.0 and float(nuevo_valor or 0.0) > 0.0):
            fusionado[nombre_clave] = nuevo_valor or 0.0

    return fusionado


def fusionar_escrutinio(anterior, nuevo):
    historico = historico_escrutinio(anterior.get("escrutinio", {}) if isinstance(anterior, dict) else {})
    nuevos = historico_escrutinio(nuevo)
    for clave, registro in nuevos.items():
        if clave in historico:
            historico[clave] = fusionar_registros_escrutinio(historico[clave], registro)
        else:
            historico[clave] = registro
    return dict(sorted(historico.items(), key=lambda item: int(re.search(r"\d+", item[0]).group(0)) if re.search(r"\d+", item[0]) else 0))


def fusionar_con_anterior(anterior, nuevo, avisos):
    probabilidades = fusionar_probabilidades(anterior, nuevo.get("probabilidades"))
    salida = {
        "version": "1.2",
        "fuente": "eduardolosilla.es + labrujadeoro.es",
        "actualizado_en": ahora_iso(),
        "avisos": avisos,
        "probabilidades": probabilidades,
        "cuotas": nuevo.get("cuotas") or anterior.get("cuotas", {}),
        "escrutinio": fusionar_escrutinio(anterior, nuevo.get("escrutinio")),
        "clasificaciones": nuevo.get("clasificaciones") or anterior.get("clasificaciones", {}),
    }
    salida["conserva_datos_previos"] = any(
        not nuevo.get(k) and anterior.get(k)
        for k in ("probabilidades", "cuotas", "escrutinio", "clasificaciones")
    ) or (bool(probabilidades.get("pleno_al_15")) and not (nuevo.get("probabilidades") or {}).get("pleno_al_15"))
    return salida


def main():
    anterior = cargar_json(SALIDA, {})
    nuevo = {}
    avisos = []
    textos_referencia = []

    for clave, funcion in (
        ("probabilidades", extraer_probabilidades),
        ("cuotas", extraer_cuotas),
        ("clasificaciones", extraer_clasificaciones),
    ):
        try:
            datos = funcion()
            if datos:
                nuevo[clave] = datos
                textos_referencia.append(json.dumps(datos, ensure_ascii=False))
                print(f"Losilla OK: {clave}")
            else:
                avisos.append(f"Sin datos nuevos para {clave}; se conserva el dato previo.")
        except Exception as exc:
            avisos.append(f"Fallo en {clave}: {type(exc).__name__}: {exc}. Se conserva el dato previo.")
            print(f"AVISO Losilla {clave}: {exc}")

    try:
        datos_escrutinio = extraer_escrutinio(textos_referencia)
        if datos_escrutinio:
            nuevo["escrutinio"] = datos_escrutinio
            print(f"Escrutinio OK: {datos_escrutinio.get('clave')}")
        else:
            avisos.append("Sin datos nuevos para escrutinio; se conserva el dato previo.")
    except Exception as exc:
        avisos.append(f"Fallo en escrutinio: {type(exc).__name__}: {exc}. Se conserva el dato previo.")
        print(f"AVISO escrutinio: {exc}")

    salida = fusionar_con_anterior(anterior, nuevo, avisos)
    guardar_json(SALIDA, salida)
    print(f"Fuente Losilla actualizada/conservada en {SALIDA.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
