"""Modulo de premios reales por jornada.

Calcula y persiste el registro de premios cobrados en cada jornada jugada.
Los importes solo se actualizan cuando se encuentra un premio real en una
fuente web por numero de jornada. Si no se encuentra dato real, el premio
queda como 0.0 EUR y fuente_premio = "pendiente".

Salida: data/premios/historial_premios.json
"""

import json
import re
import requests
from pathlib import Path
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
PREDICCIONES = DATA / "predicciones"
JORNADAS = DATA / "jornadas"
QUINIELAS_JUGADAS = DATA / "quinielas_jugadas.json"
SALIDA = DATA / "premios" / "historial_premios.json"

HEADERS_WEB = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-ES,es;q=0.9",
    "Referer": "https://www.loteriasyapuestas.es/",
}

FUENTE_LABRUJA = "https://www.labrujadeoro.es/quiniela-premios.htm"
FUENTE_LOSILLA = "https://www.eduardolosilla.es/quiniela/escrutinio/"

CATEGORIAS_WEB = {
    15: ("pleno al 15", "pleno", "especial", "15"),
    14: ("14 aciertos", "14", "1ª", "1a", "primera"),
    13: ("13 aciertos", "13", "2ª", "2a", "segunda"),
    12: ("12 aciertos", "12", "3ª", "3a", "tercera"),
    11: ("11 aciertos", "11", "4ª", "4a", "cuarta"),
    10: ("10 aciertos", "10", "5ª", "5a", "quinta"),
}


def cargar_json(path, defecto=None):
    if defecto is None:
        defecto = {}
    if not path.exists():
        return defecto
    return json.loads(path.read_text(encoding="utf-8"))


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


def leer_prediccion_jornada(jornada):
    candidatos = [
        DATA / "predicciones" / f"snapshot_jornada_{jornada}.json",
        DATA / "predicciones" / f"jornada_{jornada}.json",
        DATA / "predicciones" / "ultima_prediccion.json",
    ]
    for path in candidatos:
        data = cargar_json(path, {})
        if not data:
            continue
        if data.get("jornada") == jornada or not data.get("jornada"):
            return data
    return prediccion_desde_quinielas_jugadas(jornada)


def leer_resultados_jornada(jornada):
    return cargar_json(JORNADAS / f"jornada_{jornada}.json", {})


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

        if acertado:
            aciertos += 1
        else:
            fallos += 1

        detalle.append({
            "num": num,
            "local": pred.get("local") or res.get("local"),
            "visitante": pred.get("visitante") or res.get("visitante"),
            "signo_predicho": signo_pred,
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
    if any(etiqueta.lower() in t for etiqueta in etiquetas):
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


def obtener_premio_desde_lae(numero_jornada, aciertos, elige8_acertado=False):
    """
    Obtiene el premio real de una jornada desde LAE oficial.
    Prueba multiples URLs hasta encontrar el escrutinio.
    """
    urls_a_probar = [
        f"https://www.loteriasyapuestas.es/es/la-quiniela/resultados/jornada-{numero_jornada}",
        f"https://www.loteriasyapuestas.es/f/loterias/resultados/quiniela.html?game_id=LAQU&numero_jornada={numero_jornada}",
        f"https://www.loteriasyapuestas.es/es/resultados/quiniela/jornada-{numero_jornada}",
        f"https://www.combinacionganadora.com/quiniela/jornada/{numero_jornada}/",
        f"https://www.quiniela15.com/jornada-{numero_jornada}",
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
                        print(f"J{numero_jornada}: {aciertos} aciertos -> {valor} EUR (desde {url})")
                        fuente = url.split('/')[2]

                        premio_elige8 = 0.0
                        if elige8_acertado:
                            m8 = re.search(
                                r'elige\s*8[^\d]{0,50}(\d[\d\.]*,\d{2})\s*€',
                                texto, re.IGNORECASE
                            )
                            if m8:
                                try:
                                    premio_elige8 = float(m8.group(1).replace('.', '').replace(',', '.'))
                                except Exception:
                                    pass

                        return round(valor + premio_elige8, 2), fuente
                except Exception:
                    continue
        except Exception as e:
            print(f"Error en {url}: {e}")
            continue

    return 0.0, "pendiente"


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


def buscar_premio_labruja(jornada, aciertos, gano_elige8):
    intentos = [
        (FUENTE_LABRUJA, {"jornada": int(jornada)}),
        (FUENTE_LABRUJA, {"jor": int(jornada)}),
        (FUENTE_LABRUJA, None),
    ]
    for url, params in intentos:
        html = descargar_html(url, params=params)
        if not html:
            continue
        premio = premio_desde_html(html, aciertos, gano_elige8, "labrujadeoro")
        if premio is not None:
            return premio
    return None


def buscar_premio_losilla(jornada, aciertos, gano_elige8):
    intentos = [
        (FUENTE_LOSILLA, {"jornada": int(jornada)}),
        (f"{FUENTE_LOSILLA.rstrip('/')}/jornada-{int(jornada)}/", None),
        (f"{FUENTE_LOSILLA.rstrip('/')}/{int(jornada)}/", None),
        (FUENTE_LOSILLA, None),
    ]
    for url, params in intentos:
        html = descargar_html(url, params=params)
        if not html:
            continue
        premio = premio_desde_html(html, aciertos, gano_elige8, "eduardolosilla")
        if premio is not None:
            return premio
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

    for buscador in (buscar_premio_labruja, buscar_premio_losilla):
        premio = buscador(jornada, aciertos, gano_elige8)
        if premio is not None:
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
    premio_real = obtener_premio_real(jornada, aciertos, gano_elige8)
    if premio_real is not None:
        premio, fuente = premio_real
    else:
        premio, fuente = 0.0, "pendiente"

    boleto = "".join(
        str(p.get("signo_final") or p.get("signo_base") or "?")
        for p in sorted(prediccion.get("partidos") or [], key=lambda x: x.get("num") or 0)
    )

    return {
        "jornada": jornada,
        "aciertos": aciertos,
        "fallos": fallos,
        "premio_eur": premio,
        "fuente_premio": fuente,
        "boleto": boleto,
        "elige8_jugado": bool(seleccion),
        "elige8_seleccion": seleccion,
        "elige8_acertado": gano_elige8,
        "detalle_partidos": detalle,
        "notas": "Premio real obtenido por numero de jornada; pendiente si no se encontro fuente valida.",
    }


def registro_completo(entry):
    return len(entry.get("detalle_partidos") or []) == 14


def pendiente_premio(entry):
    try:
        premio_cero = float(entry.get("premio_eur") or 0.0) == 0.0
    except (TypeError, ValueError):
        premio_cero = True
    return premio_cero or entry.get("fuente_premio") in ("pendiente", "estimado", "fallback")


def revertir_estimados(historial):
    cambios = 0
    for entry in historial.get("jornadas") or []:
        if entry.get("fuente_premio") in ("estimado", "fallback"):
            entry["premio_eur"] = 0.0
            entry["fuente_premio"] = "pendiente"
            entry["notas"] = "Premio estimado/fallback revertido: pendiente de premio real."
            cambios += 1
    return cambios


def refrescar_premio_real(entry):
    jornada = entry.get("jornada")
    aciertos = entry.get("aciertos")
    if not isinstance(jornada, int) or not isinstance(aciertos, int):
        return False

    if int(aciertos) < 10:
        return False

    if entry.get("fuente_premio") in ("estimado", "fallback"):
        entry["premio_eur"] = 0.0
        entry["fuente_premio"] = "pendiente"

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
        entry["premio_eur"] = 0.0
        entry["fuente_premio"] = "pendiente"
        return False

    premio, fuente = premio_real
    entry["premio_eur"] = premio
    entry["fuente_premio"] = fuente
    entry["notas"] = "Premio real actualizado desde LAE/fuente web por numero de jornada."
    return True


def main():
    historial = cargar_json(SALIDA, {"jornadas": []})
    registros = {
        entry["jornada"]: entry
        for entry in historial.get("jornadas") or []
        if isinstance(entry.get("jornada"), int)
    }

    actualizadas = []
    revertidas = revertir_estimados(historial)

    for path in sorted(JORNADAS.glob("jornada_*.json")):
        data = cargar_json(path, {})
        jornada = data.get("jornada")
        if not isinstance(jornada, int):
            continue

        existente = registros.get(jornada)
        if existente and registro_completo(existente):
            if pendiente_premio(existente) and refrescar_premio_real(existente):
                actualizadas.append(existente)
                print(f"Jornada {jornada}: premio real actualizado a {existente['premio_eur']:.2f} EUR ({existente['fuente_premio']})")
            continue

        reg = registro_jornada(jornada)
        if reg:
            registros[jornada] = reg
            actualizadas.append(reg)
            print(f"Jornada {jornada}: {reg['aciertos']} aciertos, {reg['fallos']} fallos, {reg['premio_eur']:.2f} EUR ({reg['fuente_premio']})")

    for entry in registros.values():
        if pendiente_premio(entry) and refrescar_premio_real(entry):
            if entry not in actualizadas:
                actualizadas.append(entry)
            print(f"Jornada {entry['jornada']}: premio real actualizado a {entry['premio_eur']:.2f} EUR ({entry['fuente_premio']})")

    if actualizadas or revertidas:
        historial["jornadas"] = sorted(registros.values(), key=lambda x: x["jornada"])
        guardar_json(SALIDA, historial)
        print(f"Historial de premios actualizado: {len(actualizadas)} jornada(s), {revertidas} revertida(s).")
    else:
        print("Sin premios reales nuevos ni estimados/fallback que revertir.")


if __name__ == "__main__":
    main()
