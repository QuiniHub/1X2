"""Modulo de premios reales por jornada.

Calcula y persiste el registro de premios cobrados en cada jornada jugada.
Los importes solo se actualizan cuando se encuentra un premio real asociado
al numero de jornada correcto. Si no se encuentra dato real, el premio queda
como 0.0 EUR y fuente_premio = "pendiente". No usa premios estimados.

Salida: data/premios/historial_premios.json
"""

import json
import os
import re
import requests
from pathlib import Path
from bs4 import BeautifulSoup

import cronologia_jornadas as cronologia
from actualizar_porcentajes_lae import _numero_es as numero_importe
from modelo_reparto_quiniela import escrutinio_plausible

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
PREDICCIONES = DATA / "predicciones"
JORNADAS = DATA / "jornadas"
QUINIELAS_JUGADAS = DATA / "quinielas_jugadas.json"
HISTORIAL_QUINIELAS = DATA / "historial_quinielas.json"
SALIDA = DATA / "premios" / "historial_premios.json"
# Escrutinio capturado POR JORNADA Y TEMPORADA (actualizar_porcentajes_lae.py):
# es la fuente principal de la tabla de premios, porque las webs de respaldo
# se piden solo por numero de jornada y devuelven la de otra jornada/temporada.
PORCENTAJES_LAE = DATA / "memoria_ia" / "porcentajes_lae"

HEADERS_WEB = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-ES,es;q=0.9",
    "Referer": "https://www.loteriasyapuestas.es/",
}

FUENTE_LABRUJA = "https://www.labrujadeoro.es/quiniela-premios.htm"
FUENTE_LOSILLA = "https://www.eduardolosilla.es/quiniela/ayudas/escrutinio/jornada_{jornada}"
FUENTE_QUINIELA15 = "https://www.quiniela15.com/jornada-{jornada}"

CATEGORIAS_WEB = {
    15: ("pleno al 15", "pleno", "especial", "15"),
    14: ("14 aciertos", "14", "1ª", "1a", "primera"),
    13: ("13 aciertos", "13", "2ª", "2a", "segunda"),
    12: ("12 aciertos", "12", "3ª", "3a", "tercera"),
    11: ("11 aciertos", "11", "4ª", "4a", "cuarta"),
    10: ("10 aciertos", "10", "5ª", "5a", "quinta"),
}

JORNADAS_PREMIO_INVALIDO = {66, 67}


def cargar_json(path, defecto=None):
    if defecto is None:
        defecto = {}
    if not path.exists():
        return defecto
    return json.loads(path.read_text(encoding="utf-8-sig"))


def guardar_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def float_o_none(valor):
    if valor in (None, ""):
        return None
    try:
        return float(valor)
    except (TypeError, ValueError):
        texto = str(valor).replace("€", "").strip()
        texto = re.sub(r"[^0-9,.-]", "", texto)
        if not texto:
            return None
        if "," in texto:
            texto = texto.replace(".", "").replace(",", ".")
        try:
            return float(texto)
        except (TypeError, ValueError):
            return None


def tipo_por_signo(signo):
    signo = str(signo or "").strip().upper()
    if len(signo) == 3:
        return "TRIPLE"
    if len(signo) == 2:
        return "DOBLE"
    return "FIJO"


def temporada_de_jornada(jornada):
    """Temporada ('2026_2027') de la jornada que HOY ocupa
    data/jornadas/jornada_N.json, por la fecha real de sus partidos. None si
    el fichero no existe o no trae fechas."""
    try:
        datos = cargar_json(JORNADAS / f"jornada_{int(jornada)}.json", {})
    except Exception:
        return None
    if not isinstance(datos, dict) or not datos:
        return None
    fecha = cronologia.fecha_real_jornada(datos)
    return cronologia.temporada_de_fecha(fecha, jornada) if fecha else None


def temporada_de_jugada(jugada):
    """Temporada de una jugada de quinielas_jugadas.json: su campo
    'temporada' o, si falta, la que corresponde a la fecha de 'validado_en'."""
    declarada = str(jugada.get("temporada") or "").strip().replace("/", "_").replace("-", "_")
    if declarada:
        return declarada
    fecha = cronologia.parsear_fecha(jugada.get("validado_en"))
    return cronologia.temporada_de_fecha(fecha, jugada.get("jornada")) if fecha else None


def jugada_por_jornada(jornada, temporada=None):
    """Jugada real de esa jornada EN SU TEMPORADA.

    La numeracion se reinicia cada agosto: en quinielas_jugadas.json conviven
    la J59 de la 25/26 y (desde abril de 2027) la J59 de la 26/27. Antes se
    devolvia la PRIMERA con ese numero y los signos de una temporada se
    puntuaban contra los resultados de la otra. Ahora se elige la jugada de la
    temporada del fixture actual (data/jornadas/jornada_N.json) y, dentro de
    ella, la de 'validado_en' mas reciente. Una jugada de otra temporada nunca
    casa; si no se puede saber la temporada del fixture se usa la mas reciente.
    """
    data = cargar_json(QUINIELAS_JUGADAS, {"jugadas": []})
    candidatas = [
        jugada for jugada in (data.get("jugadas", []) if isinstance(data, dict) else [])
        if isinstance(jugada, dict) and jugada.get("jornada") == jornada
    ]
    if not candidatas:
        return {}
    temporada = temporada or temporada_de_jornada(jornada)
    if temporada:
        misma = [j for j in candidatas if temporada_de_jugada(j) == temporada]
        sin_fecha = [j for j in candidatas if temporada_de_jugada(j) is None]
        candidatas = misma or sin_fecha
        if not candidatas:
            return {}

    def orden(item):
        indice, jugada = item
        fecha = cronologia.parsear_fecha(jugada.get("validado_en"))
        return (fecha.toordinal() if fecha else 0, indice)

    return max(enumerate(candidatas), key=orden)[1]


def prediccion_desde_quinielas_jugadas(jornada):
    jugada = jugada_por_jornada(jornada)
    if not jugada:
        return {}

    signos = jugada.get("signos") or []
    if len(signos) < 14:
        return {}

    elige8 = {int(num) for num in (jugada.get("elige8") or []) if str(num).isdigit()}
    partidos = []
    dobles = 0
    triples = 0
    for idx, signo in enumerate(signos[:14], start=1):
        signo = str(signo or "").strip().upper()
        tipo = tipo_por_signo(signo)
        if tipo == "DOBLE":
            dobles += 1
        elif tipo == "TRIPLE":
            triples += 1
        partidos.append({
            "num": idx,
            "signo_base": signo,
            "signo_final": signo,
            "tipo": tipo,
            "elige8": idx in elige8,
            "en_elige8": idx in elige8,
        })
    return {
        "jornada": jornada,
        "partidos": partidos,
        "resumen": {
            "dobles": dobles,
            "triples": triples,
            "elige8_seleccionados": len(elige8),
        },
        "elige8": sorted(elige8),
        "origen_prediccion": "data/quinielas_jugadas.json",
    }


def prediccion_desde_historial_quinielas(jornada):
    """Lee nuestra_quiniela del historial y convierte a formato partidos."""
    h = cargar_json(HISTORIAL_QUINIELAS, {"jornadas": []})
    for entry in h.get("jornadas") or []:
        if entry.get("jornada") != jornada:
            continue
        nuestra = str(entry.get("nuestra_quiniela") or "").strip()
        if not nuestra or nuestra in ("No validada", ""):
            continue
        signos = nuestra.split()
        if len(signos) < 14:
            continue
        elige8 = {int(x) for x in (entry.get("elige8") or []) if str(x).isdigit()}
        partidos = []
        dobles = triples = 0
        for idx, signo in enumerate(signos[:14], start=1):
            signo = signo.strip().upper()
            tipo = tipo_por_signo(signo)
            if tipo == "DOBLE":
                dobles += 1
            elif tipo == "TRIPLE":
                triples += 1
            partidos.append({
                "num": idx,
                "signo_base": signo,
                "signo_final": signo,
                "tipo": tipo,
                "elige8": idx in elige8,
                "en_elige8": idx in elige8,
            })
        return {
            "jornada": jornada,
            "partidos": partidos,
            "resumen": {"dobles": dobles, "triples": triples},
            "elige8": sorted(elige8),
            "origen_prediccion": "data/historial_quinielas.json",
        }
    return {}


def leer_prediccion_jornada(jornada):
    # SIEMPRE priorizar los signos reales jugados sobre la predicción teórica.
    # quinielas_jugadas.json es la fuente de verdad para calcular aciertos y premios.
    jugada = prediccion_desde_quinielas_jugadas(jornada)
    if jugada and jugada.get("partidos"):
        return jugada
    # Segunda prioridad: nuestra_quiniela del historial de jornadas cerradas
    desde_historial = prediccion_desde_historial_quinielas(jornada)
    if desde_historial and desde_historial.get("partidos"):
        return desde_historial
    # Fallback si no hay quiniela jugada registrada
    candidatos = [
        PREDICCIONES / f"snapshot_jornada_{jornada}.json",
        PREDICCIONES / f"jornada_{jornada}.json",
        PREDICCIONES / "ultima_prediccion.json",
    ]
    for path in candidatos:
        data = cargar_json(path, {})
        if data and (data.get("jornada") == jornada or not data.get("jornada")):
            data.setdefault("origen_prediccion", f"data/predicciones/{path.name}")
            return data
    return {}


def leer_resultados_jornada(jornada):
    return cargar_json(JORNADAS / f"jornada_{jornada}.json", {})


PREMIO_CATEGORIA_MAXIMO_PLAUSIBLE = 5000.0
# El Pleno al 15 (categoria "especial") es un bote que puede acumularse
# semana a semana y crecer mucho mas que el resto de categorias -no se le
# puede aplicar el mismo limite bajo o se descartaria un premio real.
PREMIO_CATEGORIA_15_MAXIMO_PLAUSIBLE = 3_000_000.0
# La categoria 14 (1a) no acumula bote como la 15, pero su premio tambien es
# el fondo semanal repartido entre los acertantes de esa categoria -si una
# jornada tiene muy pocos (p.ej. la jornada 71 real: 13 acertantes de 14,
# 8.132,10e cada uno), el premio por acertante puede superar con creces el
# limite generico sin que el dato este mal extraido.
PREMIO_CATEGORIA_14_MAXIMO_PLAUSIBLE = 50_000.0
# Mas alto que antes porque el Pleno al 15 puede legitimamente ser grande;
# esto sigue protegiendo contra datos mal extraidos sin descartar un bote
# real ganado con varias columnas de triples.
PREMIO_TOTAL_MAXIMO_PLAUSIBLE = 500000.0

LIMITES_POR_CATEGORIA = {
    15: PREMIO_CATEGORIA_15_MAXIMO_PLAUSIBLE,
    14: PREMIO_CATEGORIA_14_MAXIMO_PLAUSIBLE,
}


def limite_categoria(cat):
    return LIMITES_POR_CATEGORIA.get(int(cat), PREMIO_CATEGORIA_MAXIMO_PLAUSIBLE)


def buscar_tabla_premios_loteriaanta(jornada):
    """Obtiene la tabla completa de premios por categoría desde loteriaanta.com.

    La pagina tiene muchas filas de tabla que no son de premios (navegacion,
    otras loterias, fechas...). Para no coger un numero cualquiera que
    coincida por casualidad con el digito de una categoria, se exige que la
    fila mencione "acierto(s)" Y un simbolo de moneda (€/euro), y se descarta
    cualquier importe por columna que supere un limite realista -evita que
    un falso positivo dispare el calculo multicolumna a cifras absurdas.
    """
    # Auditoria 26/11/2026: la URL generica (sin jornada) muestra SIEMPRE la
    # ultima jornada publicada y su tabla se asignaba a la jornada pedida (J8
    # recibio la de J13; J15 y J19 la de J20). Solo se usa la URL con jornada
    # y ademas la pagina debe nombrar "Jornada N".
    urls = [
        f"https://www.loteriaanta.com/resultados-quiniela?jornada={jornada}",
    ]
    for url in urls:
        try:
            r = requests.get(url, headers=HEADERS_WEB, timeout=12)
            if r.status_code != 200:
                continue
            tabla = tabla_premios_desde_html_loteriaanta(r.text, jornada)
            if tabla:
                print(f"J{jornada}: tabla premios obtenida de loteriaanta: {tabla}")
                return tabla
        except Exception as e:
            print(f"Error tabla loteriaanta J{jornada}: {e}")
    return {}


def pagina_es_de_jornada(texto, jornada):
    """True si el texto de la pagina nombra 'Jornada N' con el numero pedido
    (y no solo otro numero que lo contenga, como 'Jornada 13' para la 1)."""
    patron = r"jornada\s*(?:n[º°o.]*\s*|n[uú]mero\s*)?0*" + str(int(jornada)) + r"(?!\d)"
    return bool(re.search(patron, str(texto or ""), re.IGNORECASE))


def jornadas_nombradas(texto):
    """Conjunto de numeros N que aparecen como 'Jornada N' en el texto."""
    patron = r"jornada\s*(?:n[º°o.]*\s*|n[uú]mero\s*)?0*(\d{1,3})(?!\d)"
    return {int(n) for n in re.findall(patron, str(texto or ""), re.IGNORECASE)}


def html_es_de_jornada(soup, jornada):
    """True solo si la pagina es DE esa jornada, no si la nombra en un
    desplegable o listado con todas las jornadas (que haria pasar siempre la
    comprobacion y asignaria la tabla de la ultima jornada publicada).
    - Se ignoran select/option/datalist/nav.
    - Si los titulares (title, h1-h4, caption) nombran alguna jornada, debe
      ser unicamente la pedida.
    - Si ningun titular nombra jornada, la pedida debe ser la UNICA nombrada
      en el resto del texto."""
    jornada = int(jornada)
    for ruido in soup.find_all(["select", "option", "datalist", "nav"]):
        ruido.decompose()
    en_titulares = set()
    for cabecera in soup.find_all(["title", "h1", "h2", "h3", "h4", "caption"]):
        en_titulares |= jornadas_nombradas(cabecera.get_text(" ", strip=True))
    if en_titulares:
        return en_titulares == {jornada}
    return jornadas_nombradas(soup.get_text(" ", strip=True)) == {jornada}


def tabla_premios_desde_html_loteriaanta(html, jornada):
    """Tabla {categoria: premio} de una pagina de loteriaanta, o {} si la
    pagina no es de la jornada pedida o la tabla no es coherente."""
    soup = BeautifulSoup(html or "", "html.parser")
    if not html_es_de_jornada(soup, jornada):
        print(f"J{jornada}: la pagina de loteriaanta no nombra esa jornada; se descarta.")
        return {}
    tabla = {}
    for tr in soup.find_all("tr"):
        celdas = [c.get_text(" ", strip=True) for c in tr.find_all(["th", "td"])]
        texto = " ".join(celdas)
        texto_norm = texto.lower()
        if "acierto" not in texto_norm:
            continue
        if "€" not in texto and "euro" not in texto_norm:
            continue
        for cat in (15, 14, 13, 12, 11, 10):
            # La categoria debe ir pegada a "aciertos" ("14 aciertos"):
            # antes '14' casaba dentro de '14,48' y '10' en '8.132,10'.
            if re.search(rf'(^|\D){cat}\s*aciertos?', texto_norm) or (
                cat == 15 and "pleno" in texto_norm
            ):
                importes = [float_o_none(m) for m in re.findall(
                    r'(\d{1,3}(?:\.\d{3})*,\d{2}|\d+,\d{2}|\d+\.\d{2})', texto
                ) if float_o_none(m) is not None and 0 <= float_o_none(m) <= limite_categoria(cat)]
                if importes:
                    tabla[str(cat)] = importes[-1]
        if "elige" in texto_norm and "8" in texto:
            importes = [float_o_none(m) for m in re.findall(
                r'(\d{1,3}(?:\.\d{3})*,\d{2}|\d+,\d{2}|\d+\.\d{2})', texto
            ) if float_o_none(m) is not None and 0 <= float_o_none(m) <= PREMIO_CATEGORIA_MAXIMO_PLAUSIBLE]
            if importes:
                tabla["elige8"] = importes[-1]
    if len(tabla) >= 3 and tabla_premios_valida(tabla):
        return tabla
    return {}


def tabla_premios_valida(tabla):
    """False para una tabla de premios incoherente: menos de 3 categorias
    10-14, todo a cero, o importes que no decrecen al bajar de categoria.
    Forma valida de 14 a 10: ceros (sin acertantes), importes decrecientes y
    ceros (categorias que no llegan al minimo). Rechaza los placebos reales del
    historial ({14: 1.14, 13: 13.93, ...}, {14: 8132.1, 10: 8132.1, ...})."""
    if not isinstance(tabla, dict):
        return False
    valores = []
    for cat in (14, 13, 12, 11, 10):
        valor = tabla.get(str(cat))
        if valor is None:
            continue
        try:
            valores.append(float(valor))
        except (TypeError, ValueError):
            return False
    if len(valores) < 3 or not any(v > 0 for v in valores):
        return False
    positivos_cerrados = False
    anterior = None
    for valor in valores:
        if valor < 0:
            return False
        if valor == 0:
            if anterior is not None:
                positivos_cerrados = True
            continue
        if positivos_cerrados:
            return False        # un importe tras un cero intermedio
        if anterior is not None and valor > anterior:
            return False        # una categoria baja paga mas que una alta
        anterior = valor
    return True


def tablas_coinciden(tabla_a, tabla_b):
    """True si dos tablas dan el mismo premio (al centimo) en al menos 3
    categorias 10-14 comunes y en ninguna discrepan."""
    comunes = 0
    for cat in (14, 13, 12, 11, 10):
        a, b = tabla_a.get(str(cat)), tabla_b.get(str(cat))
        if a is None or b is None:
            continue
        if abs(float(a) - float(b)) > 0.011:
            return False
        comunes += 1
    return comunes >= 3


def tabla_premios_versionada(jornada):
    """Tabla de premios del escrutinio versionado de ESA jornada y temporada
    (data/memoria_ia/porcentajes_lae/<temporada>/jornada_N.json). {} si no
    existe, es un placebo o no es de la misma jornada real."""
    temporada = temporada_de_jornada(jornada)
    if not temporada:
        return {}
    registro = cargar_json(PORCENTAJES_LAE / temporada / f"jornada_{int(jornada)}.json", {})
    if not isinstance(registro, dict) or registro.get("jornada") != jornada:
        return {}
    escrutinio = registro.get("escrutinio") or {}
    if not escrutinio_plausible(escrutinio):
        return {}
    fixture = leer_resultados_jornada(jornada)
    coinciden, comparables = cronologia.coincidencia_equipos(
        [{"local": x.get("local"), "visitante": x.get("visitante")} for x in registro.get("partidos") or []],
        fixture,
    )
    if comparables >= 7 and coinciden * 2 < comparables:
        return {}
    tabla = {}
    for cat in (15, 14, 13, 12, 11, 10):
        premio = ((escrutinio.get("categorias") or {}).get(str(cat)) or {}).get("premio_eur")
        if isinstance(premio, (int, float)) and not isinstance(premio, bool) and premio >= 0:
            tabla[str(cat)] = float(premio)
    return tabla if tabla_premios_valida(tabla) else {}


_TEMPORADA_ACTUAL_CACHE = {}


def temporada_actual():
    """Temporada de la jornada mas reciente POR FECHA de data/jornadas."""
    clave = str(JORNADAS)
    if clave not in _TEMPORADA_ACTUAL_CACHE:
        temporada = None
        try:
            fechadas = [j for j in cronologia.indice_jornadas(dir_jornadas=JORNADAS) if j.get("fecha")]
            if fechadas:
                temporada = fechadas[-1].get("temporada")
        except Exception:
            temporada = None
        _TEMPORADA_ACTUAL_CACHE[clave] = temporada
    return _TEMPORADA_ACTUAL_CACHE[clave]


def fuentes_web_aplicables(jornada):
    """Las webs de premios se consultan solo por NUMERO de jornada, asi que
    siempre devuelven la de la temporada en curso. Para un fixture de una
    temporada anterior (J28-J76 de la 25/26 en data/jornadas) esa respuesta es
    de otra jornada: no se consulta. Sin fechas no se puede saber -> True."""
    temporada = temporada_de_jornada(jornada)
    actual = temporada_actual()
    return not temporada or not actual or temporada == actual


def tabla_premios_jornada(jornada):
    """Tabla de premios fiable de la jornada. Prioridad: escrutinio
    versionado de esa jornada/temporada; la web de Losilla se acepta si es
    coherente y, cuando hay versionado, solo si coincide con el (entonces
    aporta ademas el premio de Elige 8). loteriaanta, ultimo respaldo."""
    versionada = tabla_premios_versionada(jornada)
    web = {}
    consultar_web = fuentes_web_aplicables(jornada)
    if consultar_web:
        web = buscar_tabla_premios_losilla(jornada)
        if web and not tabla_premios_valida(web):
            print(f"J{jornada}: tabla de premios de la web incoherente, se descarta: {web}")
            web = {}
    if versionada:
        if web and tablas_coinciden(web, versionada):
            return web
        if web:
            print(f"J{jornada}: la tabla de la web no coincide con el escrutinio versionado; manda el versionado.")
        return versionada
    if web:
        return web
    if consultar_web:
        return buscar_tabla_premios_loteriaanta(jornada)
    return {}


def buscar_tabla_premios_losilla(jornada):
    """Obtiene la tabla completa de premios por categoria desde el escrutinio
    oficial de eduardolosilla.es (URL directa por jornada, con la tabla de
    aciertos/acertantes/euros limpia y bien estructurada). Se prueba antes
    que loteriaanta.com por ser una fuente mas fiable y bien anclada al
    escrutinio real de cada jornada.
    """
    url = FUENTE_LOSILLA.format(jornada=int(jornada))
    html = descargar_html(url)
    if not html:
        return {}
    tabla = {}
    for cat in (15, 14, 13, 12, 11, 10):
        premio = extraer_premio_html(html, cat)
        if premio is not None and 0 <= premio <= limite_categoria(cat):
            tabla[str(cat)] = premio
    premio_elige8 = extraer_premio_elige8_html(html)
    if premio_elige8 is not None and 0 <= premio_elige8 <= PREMIO_CATEGORIA_MAXIMO_PLAUSIBLE:
        tabla["elige8"] = premio_elige8
    if len(tabla) >= 3:
        print(f"J{jornada}: tabla premios obtenida de eduardolosilla.es: {tabla}")
        return tabla
    return {}


def calcular_premio_multicolumna(prediccion, resultados, tabla_premios, gano_elige8=False, seleccion_elige8=None):
    """Calcula el premio total real considerando TODAS las columnas (dobles/triples).

    Un boleto con N dobles y M triples genera 2^N * 3^M columnas.
    Cada columna se comprueba independientemente y sus premios se suman.
    """
    import itertools

    partidos_pred = {p["num"]: p for p in (prediccion.get("partidos") or []) if p.get("num") and int(p.get("num", 0)) <= 14}
    partidos_res = {p["num"]: p for p in (resultados.get("partidos") or []) if p.get("num") and int(p.get("num", 0)) <= 14}

    if not partidos_pred or not partidos_res or not tabla_premios:
        return None

    # Para cada partido: lista de opciones posibles y el signo oficial
    opciones_por_partido = {}
    oficiales = {}
    for num, pred in sorted(partidos_pred.items()):
        res = partidos_res.get(num)
        if not res:
            continue
        signo_oficial = str(res.get("signo_oficial") or "").upper()
        if signo_oficial not in ("1", "X", "2"):
            continue
        signo_pred = str(pred.get("signo_final") or pred.get("signo_base") or "").upper()
        tipo = str(pred.get("tipo") or "FIJO").upper()
        if tipo == "TRIPLE":
            opciones = ["1", "X", "2"]
        elif tipo == "DOBLE" and len(signo_pred) >= 2:
            opciones = list(signo_pred[:2])
        else:
            opciones = [signo_pred[:1]] if signo_pred else [signo_pred]
        opciones_por_partido[num] = opciones
        oficiales[num] = signo_oficial

    if not opciones_por_partido:
        return None

    nums = sorted(opciones_por_partido.keys())
    total_columnas = 1
    for num in nums:
        total_columnas *= len(opciones_por_partido[num])

    if total_columnas > 2000:
        print(f"Boleto muy grande ({total_columnas} columnas), calculando por distribución estadística.")
        # Calcular distribución directamente sin enumerar
        n_aciertos_posibles = {num: sum(1 for o in opciones if o == oficiales[num]) for num, opciones in opciones_por_partido.items()}
        # nº de columnas con exactamente k aciertos: producto de (ok_count si acertado, (total-ok) si no)
        # Simplificado: distribucion de aciertos
        from functools import reduce
        distribuciones = []
        for num in nums:
            ok = n_aciertos_posibles[num]
            total_op = len(opciones_por_partido[num])
            no_ok = total_op - ok
            distribuciones.append({1: ok, 0: no_ok})
        # Convolución de distribuciones
        dist_total = {0: 1}
        for dist in distribuciones:
            nueva = {}
            for k_prev, cnt_prev in dist_total.items():
                for acierto, cnt_acierto in dist.items():
                    k_nuevo = k_prev + acierto
                    nueva[k_nuevo] = nueva.get(k_nuevo, 0) + cnt_prev * cnt_acierto
            dist_total = nueva
    else:
        # Enumerar todas las columnas
        todas_opciones = [opciones_por_partido[num] for num in nums]
        dist_total = {}
        for combo in itertools.product(*todas_opciones):
            k = sum(1 for i, num in enumerate(nums) if combo[i] == oficiales[num])
            dist_total[k] = dist_total.get(k, 0) + 1

    # Calcular premio total
    prize_elige8_por_columna = float(tabla_premios.get("elige8", 0))
    total_premio = 0.0
    desglose = {}
    for k_aciertos, n_columnas in dist_total.items():
        premio_cat = float(tabla_premios.get(str(k_aciertos), 0) or 0)
        if premio_cat <= 0:
            continue
        # Comprobar elige8 para columnas ganadoras (si aplica)
        subtotal = premio_cat * n_columnas
        # Solo añadir elige8 si aplica (fuera del cálculo por columna, SELAE lo trata aparte)
        total_premio += subtotal
        desglose[str(k_aciertos)] = {"columnas": n_columnas, "premio_cat": premio_cat, "subtotal": round(subtotal, 2)}

    # Elige 8 se añade una sola vez si se ganó (es un premio independiente del nº de columnas)
    if gano_elige8 and prize_elige8_por_columna > 0:
        total_premio += prize_elige8_por_columna
        desglose["elige8"] = {"columnas": 1, "premio_cat": prize_elige8_por_columna, "subtotal": prize_elige8_por_columna}

    if total_premio <= 0:
        return None

    return {
        "total": round(total_premio, 2),
        "desglose": desglose,
        "columnas_totales": total_columnas,
        "distribucion_aciertos": {str(k): v for k, v in dist_total.items()},
    }


def calcular_aciertos(prediccion, resultados):
    partidos_pred = {p["num"]: p for p in (prediccion.get("partidos") or []) if p.get("num")}
    partidos_res = {p["num"]: p for p in (resultados.get("partidos") or []) if p.get("num")}

    aciertos = 0
    fallos = 0
    detalle = []

    for num, pred in partidos_pred.items():
        res = partidos_res.get(num)
        if not res:
            continue
        signo_oficial = str(res.get("signo_oficial") or "").upper()
        if signo_oficial not in ("1", "X", "2"):
            continue
        signo_pred = str(pred.get("signo_final") or pred.get("signo_base") or "").upper()
        tipo = str(pred.get("tipo") or "FIJO").upper()

        if tipo == "TRIPLE":
            acertado = True
        elif tipo == "DOBLE":
            acertado = signo_oficial in signo_pred
        else:
            acertado = signo_oficial == signo_pred

        aciertos += 1 if acertado else 0
        fallos += 0 if acertado else 1
        detalle.append({
            "num": num,
            "local": pred.get("local") or res.get("local"),
            "visitante": pred.get("visitante") or res.get("visitante"),
            "signo_predicho": signo_pred,
            "signo_nuestro": signo_pred,
            "tipo": tipo,
            "signo_oficial": signo_oficial,
            "acertado": acertado,
            "en_elige8": bool(pred.get("elige8") or pred.get("en_elige8")),
        })

    return aciertos, fallos, sorted(detalle, key=lambda x: x["num"])


def texto_normalizado(texto):
    return re.sub(r"\s+", " ", str(texto or "").strip().lower())


def fila_contiene_categoria(texto, aciertos):
    t = texto_normalizado(texto)
    aciertos = int(aciertos)
    etiquetas = CATEGORIAS_WEB.get(aciertos, (str(aciertos),))
    for etiqueta in etiquetas:
        etiqueta = etiqueta.lower()
        if etiqueta.isdigit():
            # Una etiqueta puramente numerica ("11", "15"...) necesita limites
            # de palabra: si no, "11" coincide dentro de un numero mas grande
            # que la contenga (p.ej. "17.119,56", el premio de otra categoria).
            if re.search(rf"(^|\D){re.escape(etiqueta)}(\D|$)", t):
                return True
        elif etiqueta in t:
            return True
    return bool(re.search(rf"(^|\D){aciertos}(\D|$)", t)) and "€" in t


def importes_en_texto(texto):
    patron = r"(\d{1,3}(?:\.\d{3})*,\d{2}|\d+(?:,\d{2})?)\s*€"
    return [valor for valor in (float_o_none(m) for m in re.findall(patron, str(texto or ""))) if valor is not None]


def primera_celda_es_categoria(celdas, aciertos):
    """Comprobacion estricta: la PRIMERA celda de la fila (la columna
    "Aciertos" de una tabla de escrutinio bien formada) debe ser justo la
    categoria buscada, ni mas ni menos. Evita que la parte decimal de OTRA
    fila (p.ej. el ",10" final de "8.132,10 €", el premio de la categoria 14)
    se confunda con la etiqueta "10" de una categoria distinta.
    """
    if not celdas:
        return False
    primera = texto_normalizado(celdas[0])
    etiquetas = {e.lower() for e in CATEGORIAS_WEB.get(int(aciertos), (str(aciertos),))}
    return primera in etiquetas or primera == str(int(aciertos))


def extraer_premio_html(html, aciertos):
    soup = BeautifulSoup(html, "html.parser")

    for tr in soup.find_all("tr"):
        celdas = [c.get_text(" ", strip=True) for c in tr.find_all(["th", "td"])]
        if primera_celda_es_categoria(celdas, aciertos):
            importes = importes_en_texto(" | ".join(celdas))
            if importes:
                return importes[-1]

    for tr in soup.find_all("tr"):
        celdas = [c.get_text(" ", strip=True) for c in tr.find_all(["th", "td"])]
        texto = " | ".join(celdas)
        if fila_contiene_categoria(texto, aciertos):
            importes = importes_en_texto(texto)
            if importes:
                return importes[-1]

    texto = soup.get_text("\n", strip=True)
    for linea in texto.splitlines():
        linea = re.sub(r"\s+", " ", linea).strip()
        if fila_contiene_categoria(linea, aciertos):
            importes = importes_en_texto(linea)
            if importes:
                return importes[-1]

    etiquetas = "|".join(re.escape(e) for e in CATEGORIAS_WEB.get(int(aciertos), (str(aciertos),)))
    patron = rf"(?:{etiquetas}).{{0,260}}?(\d{{1,3}}(?:\.\d{{3}})*,\d{{2}}|\d+(?:,\d{{2}})?)\s*€"
    m = re.search(patron, texto, flags=re.I | re.S)
    return float_o_none(m.group(1)) if m else None


def extraer_premio_elige8_html(html):
    soup = BeautifulSoup(html, "html.parser")
    for tr in soup.find_all("tr"):
        texto = " | ".join(c.get_text(" ", strip=True) for c in tr.find_all(["th", "td"]))
        if "elige" in texto_normalizado(texto) and "8" in texto:
            importes = importes_en_texto(texto)
            if importes:
                return importes[-1]
    texto = soup.get_text("\n", strip=True)
    patron = r"elige\s*8.{0,220}?(\d{1,3}(?:\.\d{3})*,\d{2}|\d+(?:,\d{2})?)\s*€"
    m = re.search(patron, texto, flags=re.I | re.S)
    return float_o_none(m.group(1)) if m else None


def descargar_html(url, params=None):
    try:
        r = requests.get(url, params=params or None, headers=HEADERS_WEB, timeout=25)
        if r.status_code == 200 and r.text:
            return r.text
        print(f"Premios: {url} devolvio {r.status_code}")
    except Exception as exc:
        print(f"Premios: error consultando {url}: {exc}")
    return None


def premio_desde_html(html, aciertos, gano_elige8, fuente):
    premio = extraer_premio_html(html, aciertos)
    if premio is None:
        return None
    total = premio
    if gano_elige8:
        total += extraer_premio_elige8_html(html) or 0.0
    return round(total, 2), fuente


def obtener_premio_desde_lae(numero_jornada, aciertos, elige8_acertado=False):
    """Obtiene el premio real de una jornada desde LAE oficial."""
    urls_a_probar = [
        f"https://www.loteriasyapuestas.es/es/la-quiniela/resultados/jornada-{numero_jornada}",
        f"https://www.loteriasyapuestas.es/f/loterias/resultados/quiniela.html?game_id=LAQU&numero_jornada={numero_jornada}",
        f"https://www.loteriasyapuestas.es/es/resultados/quiniela/jornada-{numero_jornada}",
        f"https://www.combinacionganadora.com/quiniela/jornada/{numero_jornada}/",
    ]

    for url in urls_a_probar:
        try:
            r = requests.get(url, headers=HEADERS_WEB, timeout=15)
            if r.status_code != 200:
                continue
            soup = BeautifulSoup(r.text, "html.parser")
            texto = soup.get_text(" ", strip=True)
            if len(texto) < 100:
                continue

            patrones = [
                rf'{aciertos}\s+aciertos[^\d]{{0,50}}(\d[\d\.]*,\d{{2}})\s*[€euros]',
                rf'{aciertos}\s+aciert[^\d]{{0,50}}(\d[\d\.]*,\d{{2}})',
                rf'categoría\s+\d+ª[^\d]{{0,100}}{aciertos}[^\d]{{0,100}}(\d[\d\.]*,\d{{2}})',
                rf'{aciertos}[^\d]{{0,30}}(\d{{1,3}}(?:\.\d{{3}})*,\d{{2}})\s*€',
            ]
            for patron in patrones:
                m = re.search(patron, texto, re.IGNORECASE)
                if not m:
                    continue
                try:
                    valor = float(m.group(1).replace('.', '').replace(',', '.'))
                    if 0 < valor < 10000000:
                        fuente = url.split('/')[2]
                        premio_elige8 = 0.0
                        if elige8_acertado:
                            m8 = re.search(r'elige\s*8[^\d]{0,50}(\d[\d\.]*,\d{2})\s*€', texto, re.IGNORECASE)
                            if m8:
                                premio_elige8 = float(m8.group(1).replace('.', '').replace(',', '.'))
                        print(f"J{numero_jornada}: {aciertos} aciertos -> {valor} EUR (desde {url})")
                        return round(valor + premio_elige8, 2), fuente
                except Exception:
                    continue
        except Exception as e:
            print(f"Error en {url}: {e}")
            continue
    return 0.0, "pendiente"


def buscar_premio_labruja(jornada, aciertos, gano_elige8):
    jornada = int(jornada)
    urls_a_probar = [
        f"https://www.labrujadeoro.es/quiniela-premios.htm?jornada={jornada}",
        f"https://www.labrujadeoro.es/quiniela-premios.htm?j={jornada}",
        f"https://www.labrujadeoro.es/quiniela-premios.htm?num={jornada}",
        f"https://www.labrujadeoro.es/quiniela-{jornada}.htm",
        f"https://www.labrujadeoro.es/jornada-{jornada}.htm",
    ]
    for url in urls_a_probar:
        html = descargar_html(url)
        if not html:
            continue
        if str(jornada) not in html:
            continue
        jornada_en_pagina = re.search(
            r'jornada\s+n?[uú]mero?\s*[:\s]*(\d+)',
            html, re.IGNORECASE
        )
        if jornada_en_pagina:
            if int(jornada_en_pagina.group(1)) != jornada:
                continue

        premio = premio_desde_html(html, aciertos, gano_elige8, "labrujadeoro")
        if premio is not None:
            return premio
    return None


def buscar_premio_quiniela15(jornada, aciertos, gano_elige8):
    jornada = int(jornada)
    url = FUENTE_QUINIELA15.format(jornada=jornada)
    html = descargar_html(url)
    if not html or str(jornada) not in html:
        return None
    return premio_desde_html(html, aciertos, gano_elige8, "quiniela15")


def buscar_premio_losilla(jornada, aciertos, gano_elige8):
    url = FUENTE_LOSILLA.format(jornada=int(jornada))
    html = descargar_html(url)
    if not html:
        return None
    return premio_desde_html(html, aciertos, gano_elige8, "eduardolosilla")


def buscar_premio_tavily(jornada, aciertos, gano_elige8):
    api_key = os.environ.get("TAVILY_API_KEY", "")
    if not api_key:
        return None

    # Multiple focused queries — World Cup quinielas may use different terminology
    queries = [
        f"La Quiniela jornada {jornada} escrutinio premios {aciertos} aciertos euros 2026",
        f"quiniela futbol jornada {jornada} 2026 resultado escrutinio premio categoría {aciertos} aciertos",
        f"loteriasyapuestas quiniela jornada {jornada} premios {aciertos}",
    ]
    if gano_elige8:
        queries.insert(0, f"La Quiniela jornada {jornada} 2026 Elige8 premio euros {aciertos} aciertos")

    for query in queries:
        try:
            r = requests.post(
                "https://api.tavily.com/search",
                headers={"Content-Type": "application/json"},
                json={
                    "api_key": api_key,
                    "query": query,
                    "search_depth": "advanced",
                    "max_results": 6,
                    "include_answer": True,
                },
                timeout=20
            )
            if r.status_code != 200:
                continue
            data = r.json()
            textos = [data.get("answer", "")]
            for res in data.get("results", []):
                textos.append(res.get("content", ""))
            for texto in textos:
                if not texto:
                    continue
                patrones = [
                    rf'{aciertos}\s+aciertos?[^\d]{{0,80}}(\d{{1,3}}(?:[\.,]\d{{3}})*[\.,]\d{{2}})\s*[€e]',
                    rf'(\d{{1,3}}(?:[\.,]\d{{3}})*[\.,]\d{{2}})\s*[€e][^\d]{{0,40}}{aciertos}\s+aciertos?',
                    rf'premio[^\d]{{0,40}}{aciertos}[^\d]{{0,40}}(\d{{1,3}}(?:[\.,]\d{{3}})*[\.,]\d{{2}})\s*[€e]',
                    rf'categor[ií]a\s*\w*[^\d]{{0,60}}{aciertos}[^\d]{{0,60}}(\d{{1,3}}(?:[\.,]\d{{3}})*[\.,]\d{{2}})\s*[€e]',
                ]
                for patron in patrones:
                    m = re.search(patron, texto, re.IGNORECASE)
                    if not m:
                        continue
                    try:
                        # "12.50" (punto decimal, habitual en buscadores) es
                        # 12,50 y no 1250: decide el ULTIMO separador.
                        valor = numero_importe(m.group(1))
                        if valor is not None and 0.50 < valor < 10_000_000:
                            premio_elige8 = 0.0
                            if gano_elige8:
                                m8 = re.search(r'elige\s*8[^\d]{0,60}(\d{1,3}(?:[\.,]\d{3})*[\.,]\d{2})\s*[€e]', texto, re.IGNORECASE)
                                if m8:
                                    premio_elige8 = numero_importe(m8.group(1)) or 0.0
                            print(f"J{jornada}: premio encontrado via Tavily: {valor} EUR (elige8: {premio_elige8})")
                            return round(valor + premio_elige8, 2), "tavily"
                    except Exception:
                        continue
        except Exception as e:
            print(f"Tavily error en query '{query}': {e}")
            continue
    return None


def obtener_premio_real(jornada, aciertos, gano_elige8):
    """Devuelve (premio_eur, fuente) solo si encuentra premio real por jornada."""
    try:
        aciertos = int(aciertos)
    except (TypeError, ValueError):
        return None
    if aciertos < 10:
        return None

    premio_lae, fuente_lae = obtener_premio_desde_lae(jornada, aciertos, gano_elige8)
    if premio_lae > 0 and fuente_lae != "pendiente":
        return premio_lae, fuente_lae

    # eduardolosilla.es (escrutinio oficial bien estructurado) antes que las
    # demas fuentes de respaldo, cuya fiabilidad no esta tan verificada.
    premio = buscar_premio_losilla(jornada, aciertos, gano_elige8)
    if premio:
        return premio

    premio = buscar_premio_labruja(jornada, aciertos, gano_elige8)
    if premio:
        return premio

    premio = buscar_premio_quiniela15(jornada, aciertos, gano_elige8)
    if premio:
        return premio

    # Último recurso: Tavily (bypasea bloqueos 403 de webs directas)
    premio = buscar_premio_tavily(jornada, aciertos, gano_elige8)
    if premio:
        return premio

    return None


def seleccion_elige8(prediccion, jornada):
    seleccion = set()
    for partido in prediccion.get("partidos") or []:
        if partido.get("elige8") or partido.get("en_elige8"):
            try:
                seleccion.add(int(partido.get("num")))
            except (TypeError, ValueError):
                pass
    if seleccion:
        return seleccion
    for valor in prediccion.get("elige8") or []:
        try:
            seleccion.add(int(valor))
        except (TypeError, ValueError):
            pass
    if seleccion:
        return seleccion
    jugada = jugada_por_jornada(jornada)
    for valor in jugada.get("elige8") or []:
        try:
            seleccion.add(int(valor))
        except (TypeError, ValueError):
            pass
    return seleccion


def elige8_acertado(prediccion, jornada, detalle):
    seleccion = seleccion_elige8(prediccion, jornada)
    if not seleccion:
        return False, []
    detalle_por_num = {int(item.get("num")): item for item in detalle if item.get("num")}
    acertados = [num for num in sorted(seleccion) if detalle_por_num.get(num, {}).get("acertado")]
    return len(seleccion) == 8 and len(acertados) == 8, sorted(seleccion)


def partidos_principales_cerrados(resultados):
    partidos = []
    for partido in resultados.get("partidos") or []:
        try:
            num = int(partido.get("num") or 0)
        except (TypeError, ValueError):
            continue
        if 1 <= num <= 14:
            partidos.append(partido)
    return len(partidos) == 14 and all(
        str(p.get("signo_oficial", "")).upper() in ("1", "X", "2")
        for p in partidos
    )


def premio_declarado_en_jugada(jornada):
    """Premio REAL cobrado que Marc dejo escrito en quinielas_jugadas.json
    (campo premio_eur). Es la fuente de verdad: un boleto reducido no se puede
    valorar desde fuera (el desarrollo de columnas lo conoce solo quien lo
    sello). None si no esta declarado."""
    jugada = jugada_por_jornada(jornada) or {}
    valor = jugada.get("premio_eur")
    if valor is None or isinstance(valor, bool):
        return None
    try:
        return float(valor)
    except (TypeError, ValueError):
        return None


def jugada_es_reducida(jornada):
    """True si la modalidad registrada en quinielas_jugadas.json es una
    reducida (LAE o Losilla/Super13): entonces las columnas jugadas NO son el
    desarrollo directo de dobles/triples y calcular_premio_multicolumna
    sobreestima el premio. Caso real (auditoria 16/11/2026): J16 285,70 EUR
    calculados vs 24,26 reales; J18 672,54 vs 0; J20 103,98 vs 6,82."""
    jugada = jugada_por_jornada(jornada) or {}
    modalidad = str(jugada.get("modalidad") or "").lower()
    return any(clave in modalidad for clave in ("reducid", "super13", "super_13", "condicionad"))


def premio_desalineado_con_jugada(entry, jornada):
    """True si el registro del historial contradice lo que dice la jugada real:
    hay premio declarado por Marc y el registro no lo usa, o la jugada es una
    reducida y el registro la valoro como desarrollo directo."""
    declarado = premio_declarado_en_jugada(jornada)
    if declarado is not None:
        if entry.get("fuente_premio") != "confirmado_usuario":
            return True
        try:
            return abs(float(entry.get("premio_eur") or 0.0) - declarado) > 0.005
        except (TypeError, ValueError):
            return True
    if jugada_es_reducida(jornada) and entry.get("fuente_premio") == "multicolumna_loteriaanta":
        return True
    return False


NOTA_REDUCIDA = (
    "Boleto REDUCIDO: las columnas jugadas no son el desarrollo directo de dobles/triples, "
    "asi que el premio no se calcula desde fuera. Pendiente de que Marc declare premio_eur "
    "en quinielas_jugadas.json (0 si no se cobro)."
)


NOTA_SIN_JUGADA = (
    "Sin jugada registrada en quinielas_jugadas.json para esta jornada: los aciertos son de la "
    "prediccion/historial y no se atribuye ningun premio."
)


def registro_jornada(jornada):
    prediccion = leer_prediccion_jornada(jornada)
    resultados = leer_resultados_jornada(jornada)
    if not partidos_principales_cerrados(resultados):
        return None

    aciertos, fallos, detalle = calcular_aciertos(prediccion, resultados)
    if not detalle:
        # Sin boleto que comparar (ni jugada, ni historial, ni prediccion de
        # ESTA jornada) no hay registro: antes se sembraba "0 aciertos
        # confirmados" (J22 y J25-J58) y quedaba protegido para siempre.
        return None
    gano_elige8, seleccion = elige8_acertado(prediccion, jornada, detalle)
    origen_jugada_real = prediccion.get("origen_prediccion") == "data/quinielas_jugadas.json"

    # Tabla de premios: escrutinio versionado de la jornada/temporada primero;
    # webs (Losilla, loteriaanta) validadas y solo para la temporada en curso.
    tabla_premios = tabla_premios_jornada(jornada)
    desglose_columnas = None
    declarado = premio_declarado_en_jugada(jornada)
    if declarado is not None:
        premio, fuente = declarado, "confirmado_usuario"
        print(f"J{jornada}: premio declarado por Marc en quinielas_jugadas = {premio} EUR")
    elif not origen_jugada_real:
        # No consta ninguna jugada real: no se atribuye premio a un boleto
        # que no esta registrado como jugado.
        premio, fuente = 0.0, "sin_jugada"
    elif jugada_es_reducida(jornada) and aciertos >= 10:
        premio, fuente = 0.0, "pendiente_reducida"
        print(f"J{jornada}: boleto reducido sin premio declarado -no se valora como desarrollo directo")
    elif tabla_premios and aciertos >= 10:
        resultado_multi = calcular_premio_multicolumna(prediccion, resultados, tabla_premios, gano_elige8, seleccion)
        if resultado_multi and resultado_multi.get("total", 0) > 0 and resultado_multi["total"] <= PREMIO_TOTAL_MAXIMO_PLAUSIBLE:
            premio = resultado_multi["total"]
            fuente = "multicolumna_loteriaanta"
            desglose_columnas = resultado_multi
            print(f"J{jornada}: premio multi-columna = {premio} EUR ({resultado_multi.get('columnas_totales')} columnas)")
        else:
            if resultado_multi and resultado_multi.get("total", 0) > PREMIO_TOTAL_MAXIMO_PLAUSIBLE:
                print(
                    f"AVISO: J{jornada} premio multi-columna implausible "
                    f"({resultado_multi['total']} EUR), se descarta y se usa la fuente alternativa."
                )
            premio_real = obtener_premio_real(jornada, aciertos, gano_elige8)
            premio, fuente = premio_real if premio_real is not None else (0.0, "pendiente")
    else:
        premio_real = obtener_premio_real(jornada, aciertos, gano_elige8)
        premio, fuente = premio_real if premio_real is not None else (0.0, "pendiente")

    boleto = "".join(
        str(p.get("signo_final") or p.get("signo_base") or "?")
        for p in sorted(prediccion.get("partidos") or [], key=lambda x: x.get("num") or 0)
    )
    origen_real = prediccion.get("origen_prediccion") or "desconocido"
    fuente_aciertos = (
        "quinielas_jugadas" if origen_real == "data/quinielas_jugadas.json"
        else "historial_quinielas" if origen_real == "data/historial_quinielas.json"
        else "prediccion_motor"
    )
    reg = {
        "jornada": jornada,
        "aciertos": aciertos,
        "fallos": fallos,
        "premio_eur": premio,
        "fuente_premio": fuente,
        "fuente_aciertos": fuente_aciertos,
        "origen_prediccion": origen_real,
        # Solo es un recuento CONFIRMADO si sale de la jugada real y se
        # compararon los 14 partidos.
        "aciertos_confirmados": bool(origen_jugada_real and len(detalle) == 14),
        "boleto": boleto,
        "elige8_jugado": bool(seleccion),
        "elige8_seleccion": list(seleccion),
        "elige8_acertado": gano_elige8,
        "detalle_partidos": detalle,
        "notas": (
            "Premio real declarado por Marc en quinielas_jugadas.json." if fuente == "confirmado_usuario"
            else NOTA_REDUCIDA if fuente == "pendiente_reducida"
            else NOTA_SIN_JUGADA if not origen_jugada_real
            else "Premio calculado considerando todas las columnas del boleto (dobles/triples)."
        ),
    }
    temporada = temporada_de_jornada(jornada)
    if temporada:
        reg["temporada"] = temporada
    if tabla_premios:
        reg["tabla_premios"] = tabla_premios
    if desglose_columnas:
        reg["desglose_columnas"] = desglose_columnas
    if fuente == "multicolumna_loteriaanta":
        marcar_elige8_pendiente(reg, elige8_sin_premio_en_tabla(gano_elige8, tabla_premios))
    return reg


def registro_sembrado_sin_boleto(entry):
    """True para un registro sin ningun partido comparado y sin premio
    confirmado: se creo sin boleto (prediccion vacia) y no dice nada real."""
    return (
        not (entry.get("detalle_partidos") or [])
        and not premio_confirmado_usuario(entry)
        and not float_o_none(entry.get("premio_eur"))
    )


def registro_completo(entry):
    return len(entry.get("detalle_partidos") or []) == 14


def aciertos_protegidos(entry):
    return bool(entry.get("aciertos_confirmados")) or str(entry.get("fuente_aciertos", "")) == "quinielas_jugadas"


def puede_mejorarse_con_jugada_real(entry, jornada):
    """True si ya existe una quiniela realmente jugada (confirmada por el
    usuario) en data/quinielas_jugadas.json para esta jornada, pero el
    registro guardado se calculo antes de que existiera ese dato -usando la
    prediccion cruda del motor como aproximacion- y nunca se recalculo.

    Sin esto, un registro con los 14 partidos ya rellenos (registro_completo)
    se queda protegido para siempre aunque su origen sea mas debil que el
    real disponible ahora, y los aciertos/premio quedan mal calculados de
    forma permanente en cuanto la jugada real llega despues de cerrarse la
    jornada.
    """
    if not jugada_por_jornada(jornada):
        return False
    return entry.get("origen_prediccion") != "data/quinielas_jugadas.json"


def resultados_oficiales_cambiados(entry, jornada):
    """True si algun signo oficial guardado ya no coincide con el que hay
    hoy en data/jornadas/jornada_N.json.

    Los aciertos se protegen para que una fuente peor no pise un recuento
    bueno, pero esa proteccion tambien congelaba recuentos calculados sobre
    resultados que DESPUES se corrigieron. Caso real (J1 de 26/27): el
    Celta-Osasuna estaba aplazado y se colo un 5-1 erroneo que daba signo
    "1"; al resolverse por sorteo el signo real fue "X", pero el historial
    se quedo con 10 aciertos en vez de los 9 reales, y ninguna ejecucion
    posterior lo recalculaba ("manteniendo 10 aciertos verificados").
    """
    detalle = entry.get("detalle_partidos") or []
    if not detalle:
        return False
    resultados = leer_resultados_jornada(jornada)
    partidos_res = {
        p["num"]: p
        for p in (resultados.get("partidos") or [])
        if p.get("num")
    }
    if not partidos_res:
        return False
    for partido in detalle:
        actual = partidos_res.get(partido.get("num"))
        if not actual:
            continue
        signo_actual = str(actual.get("signo_oficial") or "").upper()
        signo_guardado = str(partido.get("signo_oficial") or "").upper()
        if signo_actual not in ("1", "X", "2"):
            continue
        if signo_guardado and signo_guardado != signo_actual:
            return True
    return False


def premio_confirmado_usuario(entry):
    return str(entry.get("fuente_premio", "")) == "confirmado_usuario"


def premio_labruja_invalido(entry):
    return (
        entry.get("jornada") in JORNADAS_PREMIO_INVALIDO
        and entry.get("fuente_premio") == "labrujadeoro"
    )


def premio_multicolumna_implausible(entry):
    """Detecta un premio multicolumna ya guardado que sea irreal (p. ej. un
    scrapeo antiguo que cogio un numero equivocado de la tabla de premios).
    Se revierte a pendiente para que se recalcule con la tabla ya validada."""
    if entry.get("fuente_premio") != "multicolumna_loteriaanta":
        return False
    try:
        return float(entry.get("premio_eur") or 0.0) > PREMIO_TOTAL_MAXIMO_PLAUSIBLE
    except (TypeError, ValueError):
        return False


def boleto_tiene_multiples_columnas(entry):
    """True si el boleto jugado tenia al menos un doble o triple -genera mas
    de 1 columna/apuesta real, y por tanto el premio de una sola categoria
    no basta para saber cuanto se cobro de verdad."""
    return any(
        str(p.get("tipo") or "").upper() in ("DOBLE", "TRIPLE")
        for p in (entry.get("detalle_partidos") or [])
    )


def premio_multicolumna_pendiente(entry):
    """True si el boleto tenia varias columnas (dobles/triples), la
    categoria de aciertos ya da premio (>=10), pero el premio guardado NO
    viene de calcular_premio_multicolumna -normalmente porque la tabla de
    premios por categoria (eduardolosilla.es/loteriaanta.com) aun no estaba
    publicada cuando se calculo por primera vez, asi que se uso el valor de
    una sola columna (obtener_premio_real) como si el boleto no tuviera
    dobles/triples. Sin esto, un boleto con 48 columnas se queda cobrando el
    premio de 1 sola columna para siempre en cuanto ese valor deja de ser 0
    -caso real detectado por Marc: jornada 75, 4,60EUR guardado en vez de
    los 11,92EUR reales (1 columna a 12 aciertos + 6 columnas a 11)."""
    if premio_confirmado_usuario(entry):
        return False
    try:
        aciertos = int(entry.get("aciertos"))
    except (TypeError, ValueError):
        return False
    if aciertos < 10:
        return False
    if not boleto_tiene_multiples_columnas(entry):
        return False
    return entry.get("fuente_premio") != "multicolumna_loteriaanta"


NOTA_ELIGE8_PENDIENTE = (
    " Elige 8 acertado, pero la tabla de premios usada (escrutinio versionado) no trae su premio: "
    "falta sumarlo; pendiente de la web o de que Marc declare el premio."
)


def elige8_sin_premio_en_tabla(gano_elige8, tabla_premios):
    """True si se acerto el Elige 8 y la tabla no trae su premio (la tabla
    del escrutinio versionado solo lleva las categorias 10-15)."""
    return bool(gano_elige8) and "elige8" not in (tabla_premios or {})


def marcar_elige8_pendiente(entry, falta):
    if falta:
        entry["elige8_premio_pendiente"] = True
        if NOTA_ELIGE8_PENDIENTE not in str(entry.get("notas") or ""):
            entry["notas"] = str(entry.get("notas") or "") + NOTA_ELIGE8_PENDIENTE
    else:
        entry.pop("elige8_premio_pendiente", None)


def pendiente_premio(entry):
    if premio_confirmado_usuario(entry):
        return False
    if entry.get("elige8_premio_pendiente"):
        return True   # falta sumar el premio de Elige 8 (tabla sin 'elige8')
    # 0 EUR ya resuelto: lo dice el escrutinio versionado de la jornada, o no
    # hay jugada real. Si Marc declara despues un premio o registra la jugada,
    # main() rehace el registro (premio_desalineado / puede_mejorarse).
    if entry.get("fuente_premio") in ("escrutinio_versionado", "sin_jugada"):
        return False
    try:
        premio_cero = float(entry.get("premio_eur") or 0.0) == 0.0
    except (TypeError, ValueError):
        premio_cero = True
    return (
        premio_cero
        or entry.get("fuente_premio") in ("pendiente", "estimado", "fallback")
        or premio_labruja_invalido(entry)
        or premio_multicolumna_pendiente(entry)
    )


def resetear_premio_pendiente(entry, motivo):
    entry["premio_eur"] = 0.0
    entry["fuente_premio"] = "pendiente"
    entry["notas"] = motivo


def revertir_estimados_y_labruja_invalidos(historial):
    cambios = 0
    for entry in historial.get("jornadas") or []:
        if entry.get("fuente_premio") in ("estimado", "fallback"):
            resetear_premio_pendiente(entry, "Premio estimado/fallback revertido: pendiente de premio real.")
            cambios += 1
        elif premio_labruja_invalido(entry):
            resetear_premio_pendiente(entry, "Premio de Labruja revertido: no estaba verificado contra la jornada solicitada.")
            cambios += 1
        elif premio_multicolumna_implausible(entry):
            resetear_premio_pendiente(
                entry,
                f"Premio multicolumna revertido: {entry.get('premio_eur')} EUR superaba el limite plausible "
                f"({PREMIO_TOTAL_MAXIMO_PLAUSIBLE} EUR), probable dato mal extraido de la tabla de premios.",
            )
            cambios += 1
    return cambios


NOTA_ESCRUTINIO_SIN_PREMIO = (
    "Segun el escrutinio versionado de esta jornada (porcentajes_lae), ninguna columna del boleto "
    "alcanza una categoria con premio: 0,00 EUR."
)


def refrescar_premio_real(entry):
    if premio_confirmado_usuario(entry):
        return False

    jornada = entry.get("jornada")
    aciertos = entry.get("aciertos")
    if not isinstance(jornada, int) or not isinstance(aciertos, int):
        return False
    declarado = premio_declarado_en_jugada(jornada)
    if declarado is not None:
        entry["premio_eur"] = declarado
        entry["fuente_premio"] = "confirmado_usuario"
        entry.pop("desglose_columnas", None)
        entry["notas"] = "Premio real declarado por Marc en quinielas_jugadas.json."
        return True
    if int(aciertos) < 10:
        return False
    if entry.get("fuente_premio") == "sin_jugada" and not jugada_por_jornada(jornada):
        return False  # sin jugada real no se busca premio (ver NOTA_SIN_JUGADA)
    if jugada_es_reducida(jornada):
        if entry.get("fuente_premio") != "pendiente_reducida":
            entry["premio_eur"] = 0.0
            entry["fuente_premio"] = "pendiente_reducida"
            entry.pop("desglose_columnas", None)
            entry["notas"] = NOTA_REDUCIDA
            return True
        return False

    if entry.get("fuente_premio") in ("estimado", "fallback") or premio_labruja_invalido(entry):
        resetear_premio_pendiente(entry, "Premio revertido antes de buscar fuente real por jornada.")

    if entry.get("elige8_acertado") is None:
        prediccion = leer_prediccion_jornada(jornada)
        gano_elige8, seleccion = elige8_acertado(prediccion, jornada, entry.get("detalle_partidos") or [])
        entry["elige8_jugado"] = bool(seleccion)
        entry["elige8_seleccion"] = seleccion
        entry["elige8_acertado"] = gano_elige8
    else:
        gano_elige8 = bool(entry.get("elige8_acertado"))

    # Boleto con dobles/triples -> intentar SIEMPRE el calculo multicolumna
    # real primero (la tabla de premios por categoria puede no haber estado
    # publicada la primera vez que se calculo esta jornada). Sin esto, un
    # boleto de 48 columnas se quedaba cobrando el premio de una sola
    # columna en cuanto ese valor dejaba de ser 0 (ver premio_multicolumna_pendiente).
    if boleto_tiene_multiples_columnas(entry):
        prediccion = leer_prediccion_jornada(jornada)
        resultados = leer_resultados_jornada(jornada)
        tabla_premios = tabla_premios_jornada(jornada)
        if tabla_premios:
            resultado_multi = calcular_premio_multicolumna(
                prediccion, resultados, tabla_premios, gano_elige8, entry.get("elige8_seleccion") or []
            )
            falta_elige8 = elige8_sin_premio_en_tabla(gano_elige8, tabla_premios)
            if resultado_multi is None and tabla_premios_versionada(jornada) and not falta_elige8:
                # El escrutinio versionado de ESTA jornada dice que ninguna
                # columna cobra (p. ej. 10 aciertos con la categoria a 0,00):
                # es un 0 real, no un pendiente; no se pregunta a las webs.
                # (Si se acerto el Elige 8 y la tabla versionada no trae su
                # premio, NO se cierra a 0: sigue pendiente de la web.)
                cambia = entry.get("fuente_premio") != "escrutinio_versionado" or entry.get("premio_eur")
                entry["premio_eur"] = 0.0
                entry["fuente_premio"] = "escrutinio_versionado"
                entry["tabla_premios"] = tabla_premios
                entry.pop("desglose_columnas", None)
                entry["notas"] = NOTA_ESCRUTINIO_SIN_PREMIO
                return bool(cambia)
            if resultado_multi and resultado_multi.get("total", 0) > 0 and resultado_multi["total"] <= PREMIO_TOTAL_MAXIMO_PLAUSIBLE:
                antes = (entry.get("premio_eur"), entry.get("fuente_premio"), entry.get("elige8_premio_pendiente"))
                entry["premio_eur"] = resultado_multi["total"]
                entry["fuente_premio"] = "multicolumna_loteriaanta"
                entry["tabla_premios"] = tabla_premios
                entry["desglose_columnas"] = resultado_multi
                entry["notas"] = "Premio real actualizado con calculo multicolumna (boleto con dobles/triples)."
                marcar_elige8_pendiente(entry, falta_elige8)
                return antes != (entry["premio_eur"], entry["fuente_premio"], entry.get("elige8_premio_pendiente"))
            if falta_elige8 and entry.get("elige8_premio_pendiente"):
                # Ya consta como pendiente del premio de Elige 8 y la web
                # sigue sin darlo: no se toca el registro.
                return False

    premio_real = obtener_premio_real(jornada, aciertos, gano_elige8)
    if premio_real is None:
        resetear_premio_pendiente(entry, "Pendiente: no se encontro premio real validado para esta jornada.")
        return False

    premio, fuente = premio_real
    entry["premio_eur"] = premio
    entry["fuente_premio"] = fuente
    entry["notas"] = "Premio real actualizado desde fuente web validada por numero de jornada."
    return True


def main():
    historial = cargar_json(SALIDA, {"jornadas": []})
    # El historial puede traer DOS registros con el mismo numero (uno por
    # temporada). 'registros' solo lleva, por numero, el de la temporada que
    # HOY ocupa data/jornadas/jornada_N.json (o el que no dice temporada);
    # los demas van a 'otros' y se reescriben siempre tal cual. Indexar solo
    # por numero perdia el archivado en el segundo guardado.
    registros = {}
    otros = []
    for entry in historial.get("jornadas") or []:
        if not isinstance(entry, dict):
            continue
        numero = entry.get("jornada")
        if not isinstance(numero, int):
            otros.append(entry)   # no se entiende: se conserva, no se borra
            continue
        temporada_fixture = temporada_de_jornada(numero)
        es_actual = (
            not entry.get("temporada") or not temporada_fixture
            or entry["temporada"] == temporada_fixture
        )
        previo = registros.get(numero)
        if previo is None:
            registros[numero] = entry
        elif es_actual and previo.get("temporada") and temporada_fixture and previo["temporada"] != temporada_fixture:
            otros.append(previo)
            registros[numero] = entry
        else:
            otros.append(entry)

    actualizadas = []
    archivados = []   # registros de la misma numeracion en OTRA temporada
    purgados = 0
    revertidas = revertir_estimados_y_labruja_invalidos(historial)

    for path in sorted(JORNADAS.glob("jornada_*.json")):
        data = cargar_json(path, {})
        jornada = data.get("jornada")
        if not isinstance(jornada, int):
            continue

        existente = registros.get(jornada)
        temporada = temporada_de_jornada(jornada)
        if existente and temporada and existente.get("temporada") and existente["temporada"] != temporada:
            # El fichero jornada_N.json ya es de otra temporada: el registro
            # viejo se conserva aparte y NO protege ni se mezcla con el nuevo.
            archivados.append(registros.pop(jornada))
            existente = None
        if existente and registro_sembrado_sin_boleto(existente):
            # Registro "0 aciertos confirmados" sin ningun partido comparado
            # (J22 y J25-J58): no es un recuento, se rehace desde cero.
            registros.pop(jornada)
            existente = None
            purgados += 1
        if existente and premio_confirmado_usuario(existente) and not premio_desalineado_con_jugada(existente, jornada):
            continue
        mejorable = bool(existente) and puede_mejorarse_con_jugada_real(existente, jornada)
        # Un recuento protegido tambien debe rehacerse si los resultados
        # oficiales sobre los que se calculo han cambiado despues (partido
        # aplazado que se resuelve por sorteo, resultado mal scrapeado que
        # se corrige...). Sin esto el numero se congelaba para siempre.
        if existente and resultados_oficiales_cambiados(existente, jornada):
            mejorable = True
        # Marc ha declarado el premio real, o la jugada es una reducida que
        # se valoro como desarrollo directo: rehacer el registro.
        if existente and premio_desalineado_con_jugada(existente, jornada):
            mejorable = True
        # Si hay registro existente con aciertos protegidos, no recalcular
        # (salvo que ahora exista la jugada realmente jugada y el registro
        # guardado no viniera de ahi -entonces hay que actualizarlo-).
        if existente and aciertos_protegidos(existente) and not mejorable:
            if pendiente_premio(existente) and refrescar_premio_real(existente):
                actualizadas.append(existente)
                print(f"Jornada {jornada}: premio actualizado manteniendo {existente['aciertos']} aciertos verificados")
            continue
        if existente and registro_completo(existente) and not mejorable:
            if pendiente_premio(existente) and refrescar_premio_real(existente):
                actualizadas.append(existente)
                print(f"Jornada {jornada}: premio real actualizado a {existente['premio_eur']:.2f} EUR ({existente['fuente_premio']})")
            continue

        reg = registro_jornada(jornada)
        if reg:
            if mejorable:
                print(
                    f"Jornada {jornada}: recalculado con la quiniela realmente jugada "
                    f"(antes: {existente.get('aciertos')} aciertos desde {existente.get('origen_prediccion', 'desconocido')})"
                )
            registros[jornada] = reg
            actualizadas.append(reg)
            print(f"Jornada {jornada}: {reg['aciertos']} aciertos, {reg['fallos']} fallos, {reg['premio_eur']:.2f} EUR ({reg['fuente_premio']})")

    for entry in registros.values():
        if premio_confirmado_usuario(entry):
            continue
        if pendiente_premio(entry) and refrescar_premio_real(entry):
            if entry not in actualizadas:
                actualizadas.append(entry)
            print(f"Jornada {entry['jornada']}: premio real actualizado a {entry['premio_eur']:.2f} EUR ({entry['fuente_premio']})")

    if actualizadas or revertidas or purgados:
        historial["jornadas"] = sorted(
            list(registros.values()) + otros + archivados,
            key=lambda x: (
                x["jornada"] if isinstance(x.get("jornada"), int) else 10 ** 6,
                str(x.get("temporada") or ""),
            ),
        )
        guardar_json(SALIDA, historial)
        print(f"Historial de premios actualizado: {len(actualizadas)} jornada(s), {revertidas} revertida(s).")
    else:
        print("Sin premios reales nuevos ni premios invalidos que revertir.")


if __name__ == "__main__":
    main()
