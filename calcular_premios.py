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

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
PREDICCIONES = DATA / "predicciones"
JORNADAS = DATA / "jornadas"
QUINIELAS_JUGADAS = DATA / "quinielas_jugadas.json"
HISTORIAL_QUINIELAS = DATA / "historial_quinielas.json"
SALIDA = DATA / "premios" / "historial_premios.json"

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


def jugada_por_jornada(jornada):
    data = cargar_json(QUINIELAS_JUGADAS, {"jugadas": []})
    for jugada in data.get("jugadas", []) if isinstance(data, dict) else []:
        if jugada.get("jornada") == jornada:
            return jugada
    return {}


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
# Mas alto que antes porque el Pleno al 15 puede legitimamente ser grande;
# esto sigue protegiendo contra datos mal extraidos sin descartar un bote
# real ganado con varias columnas de triples.
PREMIO_TOTAL_MAXIMO_PLAUSIBLE = 500000.0


def limite_categoria(cat):
    return PREMIO_CATEGORIA_15_MAXIMO_PLAUSIBLE if int(cat) == 15 else PREMIO_CATEGORIA_MAXIMO_PLAUSIBLE


def buscar_tabla_premios_loteriaanta(jornada):
    """Obtiene la tabla completa de premios por categoría desde loteriaanta.com.

    La pagina tiene muchas filas de tabla que no son de premios (navegacion,
    otras loterias, fechas...). Para no coger un numero cualquiera que
    coincida por casualidad con el digito de una categoria, se exige que la
    fila mencione "acierto(s)" Y un simbolo de moneda (€/euro), y se descarta
    cualquier importe por columna que supere un limite realista -evita que
    un falso positivo dispare el calculo multicolumna a cifras absurdas.
    """
    import itertools
    urls = [
        "https://www.loteriaanta.com/resultados-quiniela",
        f"https://www.loteriaanta.com/resultados-quiniela?jornada={jornada}",
    ]
    for url in urls:
        try:
            r = requests.get(url, headers=HEADERS_WEB, timeout=12)
            if r.status_code != 200:
                continue
            soup = BeautifulSoup(r.text, "html.parser")
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
                    if re.search(rf'(^|\D){cat}(\D|$)', texto):
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
            if len(tabla) >= 3:
                print(f"J{jornada}: tabla premios obtenida de loteriaanta: {tabla}")
                return tabla
        except Exception as e:
            print(f"Error tabla loteriaanta J{jornada}: {e}")
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


def extraer_premio_html(html, aciertos):
    soup = BeautifulSoup(html, "html.parser")

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
                        raw = m.group(1).replace('.', '').replace(',', '.')
                        valor = float(raw)
                        if 0.50 < valor < 10_000_000:
                            premio_elige8 = 0.0
                            if gano_elige8:
                                m8 = re.search(r'elige\s*8[^\d]{0,60}(\d{1,3}(?:[\.,]\d{3})*[\.,]\d{2})\s*[€e]', texto, re.IGNORECASE)
                                if m8:
                                    try:
                                        premio_elige8 = float(m8.group(1).replace('.', '').replace(',', '.'))
                                    except Exception:
                                        pass
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


def registro_jornada(jornada):
    prediccion = leer_prediccion_jornada(jornada)
    resultados = leer_resultados_jornada(jornada)
    if not partidos_principales_cerrados(resultados):
        return None

    aciertos, fallos, detalle = calcular_aciertos(prediccion, resultados)
    gano_elige8, seleccion = elige8_acertado(prediccion, jornada, detalle)

    # Intentar calcular premio multi-columna (dobles/triples generan múltiples apuestas)
    # eduardolosilla.es primero (escrutinio oficial, mas fiable); loteriaanta.com de respaldo.
    tabla_premios = buscar_tabla_premios_losilla(jornada) or buscar_tabla_premios_loteriaanta(jornada)
    desglose_columnas = None
    if tabla_premios and aciertos >= 10:
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
        "aciertos_confirmados": True,
        "boleto": boleto,
        "elige8_jugado": bool(seleccion),
        "elige8_seleccion": list(seleccion),
        "elige8_acertado": gano_elige8,
        "detalle_partidos": detalle,
        "notas": "Premio calculado considerando todas las columnas del boleto (dobles/triples).",
    }
    if tabla_premios:
        reg["tabla_premios"] = tabla_premios
    if desglose_columnas:
        reg["desglose_columnas"] = desglose_columnas
    return reg


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


def pendiente_premio(entry):
    if premio_confirmado_usuario(entry):
        return False
    try:
        premio_cero = float(entry.get("premio_eur") or 0.0) == 0.0
    except (TypeError, ValueError):
        premio_cero = True
    return premio_cero or entry.get("fuente_premio") in ("pendiente", "estimado", "fallback") or premio_labruja_invalido(entry)


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


def refrescar_premio_real(entry):
    if premio_confirmado_usuario(entry):
        return False

    jornada = entry.get("jornada")
    aciertos = entry.get("aciertos")
    if not isinstance(jornada, int) or not isinstance(aciertos, int):
        return False
    if int(aciertos) < 10:
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
    registros = {
        entry["jornada"]: entry
        for entry in historial.get("jornadas") or []
        if isinstance(entry.get("jornada"), int)
    }

    actualizadas = []
    revertidas = revertir_estimados_y_labruja_invalidos(historial)

    for path in sorted(JORNADAS.glob("jornada_*.json")):
        data = cargar_json(path, {})
        jornada = data.get("jornada")
        if not isinstance(jornada, int):
            continue

        existente = registros.get(jornada)
        if existente and premio_confirmado_usuario(existente):
            continue
        mejorable = bool(existente) and puede_mejorarse_con_jugada_real(existente, jornada)
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

    if actualizadas or revertidas:
        historial["jornadas"] = sorted(registros.values(), key=lambda x: x["jornada"])
        guardar_json(SALIDA, historial)
        print(f"Historial de premios actualizado: {len(actualizadas)} jornada(s), {revertidas} revertida(s).")
    else:
        print("Sin premios reales nuevos ni premios invalidos que revertir.")


if __name__ == "__main__":
    main()
