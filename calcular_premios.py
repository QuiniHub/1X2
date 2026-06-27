"""Modulo de premios por jornada.

Calcula y persiste el registro de premios cobrados en cada jornada
jugada. El premio se calcula automaticamente si hay datos fiables
(aciertos confirmados y tabla de premios oficial). Si no hay dato
oficial, se consulta historico web y finalmente se usa una estimacion.

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
MEMORIA = DATA / "memoria_ia"
QUINIELAS_JUGADAS = DATA / "quinielas_jugadas.json"
FUENTE_LOSILLA = MEMORIA / "fuente_losilla.json"
SALIDA = DATA / "premios" / "historial_premios.json"

HEADERS_WEB = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-ES,es;q=0.9",
}

# Tabla de premios aproximados pedida como ultimo fallback.
# Los valores reales dependen del bote y del numero de acertantes.
TABLA_PREMIOS_ESTIMADOS = {
    15: 0.0,       # categoria especial, variable
    14: 200000.0,
    13: 2000.0,
    12: 100.0,
    11: 20.0,
    10: 5.0,
}
PREMIO_ELIGE8_ESTIMADO = 5.0

CLAVES_PREMIO = {
    15: ("premio_pleno_al_15", "premio_15"),
    14: ("premio_14",),
    13: ("premio_13",),
    12: ("premio_12",),
    11: ("premio_11",),
    10: ("premio_10",),
}

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


def clave_jornada(jornada):
    try:
        return f"jornada_{int(jornada):02d}"
    except (TypeError, ValueError):
        return None


def float_o_none(valor):
    if valor in (None, ""):
        return None
    try:
        return float(valor)
    except (TypeError, ValueError):
        texto = str(valor).replace("€", "").strip()
        texto = re.sub(r"[^0-9,.-]", "", texto)
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
    """Construye una prediccion normalizada desde la quiniela jugada."""
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
    """Lee la prediccion pre-cierre de una jornada concreta."""
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
    """Lee los resultados oficiales de una jornada."""
    path = JORNADAS / f"jornada_{jornada}.json"
    return cargar_json(path, {})


def calcular_aciertos(prediccion, resultados):
    """Compara signos predichos con signos oficiales y cuenta aciertos."""
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


def historico_escrutinio():
    data = cargar_json(FUENTE_LOSILLA, {})
    escrutinio = data.get("escrutinio") if isinstance(data, dict) else {}
    if not isinstance(escrutinio, dict):
        return {}

    if any(str(k).startswith("jornada_") for k in escrutinio):
        return escrutinio

    jornada = escrutinio.get("jornada")
    clave = clave_jornada(jornada)
    return {clave: escrutinio} if clave else {}


def registro_escrutinio(jornada):
    clave = clave_jornada(jornada)
    if not clave:
        return None
    historico = historico_escrutinio()
    if clave in historico:
        return historico[clave]

    clave_sin_padding = f"jornada_{int(jornada)}"
    return historico.get(clave_sin_padding)


def premio_categoria(registro, aciertos):
    if not isinstance(registro, dict):
        return None

    for clave in CLAVES_PREMIO.get(int(aciertos), ()): 
        premio = float_o_none(registro.get(clave))
        if premio is not None:
            return premio

    categorias = registro.get("categorias") or {}
    datos = categorias.get(str(int(aciertos)))
    if isinstance(datos, dict):
        return float_o_none(datos.get("premio_euros"))

    return None


def premio_elige8(registro):
    if not isinstance(registro, dict):
        return 0.0

    premio = float_o_none(registro.get("premio_elige8"))
    if premio is not None:
        return premio

    datos = (registro.get("categorias") or {}).get("elige8")
    if isinstance(datos, dict):
        return float_o_none(datos.get("premio_euros")) or 0.0

    return 0.0


def importe_en_texto(texto):
    patron = r"(\d{1,3}(?:\.\d{3})*,\d{2}|\d+(?:,\d{2})?)\s*€"
    m = re.search(patron, texto)
    return float_o_none(m.group(1)) if m else None


def fila_contiene_categoria(texto, aciertos):
    t = re.sub(r"\s+", " ", str(texto or "").lower())
    for etiqueta in CATEGORIAS_WEB.get(int(aciertos), (str(aciertos),)):
        if etiqueta.lower() in t:
            return True
    return False


def extraer_premio_html(html, jornada, aciertos):
    soup = BeautifulSoup(html, "html.parser")

    for tr in soup.find_all("tr"):
        celdas = [c.get_text(" ", strip=True) for c in tr.find_all(["th", "td"])]
        texto = " | ".join(celdas)
        if fila_contiene_categoria(texto, aciertos):
            premio = importe_en_texto(texto)
            if premio is not None:
                return premio

    texto = soup.get_text("\n", strip=True)
    lineas = [re.sub(r"\s+", " ", linea).strip() for linea in texto.splitlines()]
    for linea in lineas:
        if fila_contiene_categoria(linea, aciertos):
            premio = importe_en_texto(linea)
            if premio is not None:
                return premio

    etiquetas = "|".join(re.escape(e) for e in CATEGORIAS_WEB.get(int(aciertos), (str(aciertos),)))
    patron = rf"(?:{etiquetas}).{{0,220}}?(\d{{1,3}}(?:\.\d{{3}})*,\d{{2}}|\d+(?:,\d{{2}})?)\s*€"
    m = re.search(patron, texto, flags=re.I | re.S)
    return float_o_none(m.group(1)) if m else None


def extraer_premio_elige8_html(html):
    soup = BeautifulSoup(html, "html.parser")
    for tr in soup.find_all("tr"):
        texto = " | ".join(c.get_text(" ", strip=True) for c in tr.find_all(["th", "td"]))
        if "elige" in texto.lower() and "8" in texto:
            premio = importe_en_texto(texto)
            if premio is not None:
                return premio
    texto = soup.get_text("\n", strip=True)
    patron = r"elige\s*8.{0,180}?(\d{1,3}(?:\.\d{3})*,\d{2}|\d+(?:,\d{2})?)\s*€"
    m = re.search(patron, texto, flags=re.I | re.S)
    return float_o_none(m.group(1)) if m else None


def urls_historicas_jornada(jornada):
    j = int(jornada)
    return [
        ("eduardolosilla", f"https://www.eduardolosilla.es/quiniela/escrutinio/?jornada={j}"),
        ("eduardolosilla", f"https://www.eduardolosilla.es/quiniela/escrutinio/jornada-{j}/"),
        ("eduardolosilla", f"https://www.eduardolosilla.es/quiniela/escrutinio/{j}/"),
        ("eduardolosilla", "https://www.eduardolosilla.es/quiniela/escrutinio/"),
        ("labrujadeoro", f"https://www.labrujadeoro.es/quiniela-premios.htm?jornada={j}"),
        ("labrujadeoro", f"https://www.labrujadeoro.es/quiniela-premios.htm?jor={j}"),
        ("labrujadeoro", "https://www.labrujadeoro.es/quiniela-premios.htm"),
    ]


def buscar_premio_historico_web(jornada, aciertos, jugo_elige8):
    """Busca escrutinio historico en Losilla y La Bruja antes del fallback."""
    if int(aciertos) < 10:
        return None

    for fuente, url in urls_historicas_jornada(jornada):
        try:
            r = requests.get(url, headers=HEADERS_WEB, timeout=20)
            if r.status_code != 200 or not r.text:
                continue
            premio = extraer_premio_html(r.text, jornada, aciertos)
            if premio is None:
                continue
            total = premio
            if jugo_elige8:
                total += extraer_premio_elige8_html(r.text) or 0.0
            return round(total, 2), f"historico_{fuente}"
        except Exception as exc:
            print(f"Aviso: no se pudo consultar {fuente} J{jornada}: {exc}")
    return None


def obtener_premio_oficial(jornada, aciertos, jugo_elige8):
    """Devuelve (importe, fuente) usando local, webs historicas o None."""
    registro = registro_escrutinio(jornada)
    if registro:
        total = 0.0
        encontrado = False
        if int(aciertos) in CLAVES_PREMIO:
            premio = premio_categoria(registro, int(aciertos))
            if premio is not None:
                total += premio
                encontrado = True
        if jugo_elige8:
            extra = premio_elige8(registro)
            if extra > 0:
                total += extra
                encontrado = True
        if encontrado:
            return round(total, 2), "oficial"

    return buscar_premio_historico_web(jornada, aciertos, jugo_elige8)


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


def estimar_premio(aciertos, gano_elige8=False):
    """Estimacion aproximada cuando no hay escrutinio exacto disponible."""
    try:
        aciertos = int(aciertos)
    except (TypeError, ValueError):
        return 0.0, "pendiente"

    premio = TABLA_PREMIOS_ESTIMADOS.get(aciertos, 0.0)
    if gano_elige8:
        premio += PREMIO_ELIGE8_ESTIMADO
    fuente = "estimado" if premio > 0 else "pendiente"
    return round(premio, 2), fuente


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
    """Genera el registro de premios para una jornada concreta."""
    prediccion = leer_prediccion_jornada(jornada)
    resultados = leer_resultados_jornada(jornada)

    if not partidos_principales_cerrados(resultados):
        return None

    aciertos, fallos, detalle = calcular_aciertos(prediccion, resultados)
    gano_elige8, seleccion = elige8_acertado(prediccion, jornada, detalle)
    premio_real = obtener_premio_oficial(jornada, aciertos, gano_elige8)
    if premio_real is not None:
        premio, fuente = premio_real
    else:
        premio, fuente = estimar_premio(aciertos, gano_elige8)

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
        "notas": "Premio exacto si se obtuvo de escrutinio; estimado si no hubo dato historico web.",
    }


def registro_completo(entry):
    return len(entry.get("detalle_partidos") or []) == 14


def pendiente_premio(entry):
    try:
        return float(entry.get("premio_eur") or 0.0) == 0.0 or entry.get("fuente_premio") == "pendiente"
    except (TypeError, ValueError):
        return True


def refrescar_premio_oficial(entry):
    jornada = entry.get("jornada")
    aciertos = entry.get("aciertos")
    if not isinstance(jornada, int) or not isinstance(aciertos, int):
        return False

    if entry.get("elige8_acertado") is None:
        prediccion = leer_prediccion_jornada(jornada)
        gano_elige8, seleccion = elige8_acertado(prediccion, jornada, entry.get("detalle_partidos") or [])
        entry["elige8_jugado"] = bool(seleccion)
        entry["elige8_seleccion"] = seleccion
        entry["elige8_acertado"] = gano_elige8
    else:
        gano_elige8 = bool(entry.get("elige8_acertado"))

    premio_real = obtener_premio_oficial(jornada, aciertos, gano_elige8)
    if premio_real is not None:
        premio, fuente = premio_real
    else:
        premio, fuente = estimar_premio(aciertos, gano_elige8)

    if premio <= 0:
        return False

    entry["premio_eur"] = premio
    entry["fuente_premio"] = fuente
    if fuente == "estimado":
        entry["notas"] = "Premio aproximado: no se encontro escrutinio exacto en fuentes historicas."
    return True


def main():
    """Actualiza el historial de premios con todas las jornadas cerradas."""
    historial = cargar_json(SALIDA, {"jornadas": []})
    registros = {
        entry["jornada"]: entry
        for entry in historial.get("jornadas") or []
        if isinstance(entry.get("jornada"), int)
    }

    actualizadas = []
    for path in sorted(JORNADAS.glob("jornada_*.json")):
        data = cargar_json(path, {})
        jornada = data.get("jornada")
        if not isinstance(jornada, int):
            continue

        existente = registros.get(jornada)
        if existente and registro_completo(existente):
            if pendiente_premio(existente) and refrescar_premio_oficial(existente):
                actualizadas.append(existente)
                print(f"Jornada {jornada}: premio actualizado a {existente['premio_eur']:.2f} EUR ({existente['fuente_premio']})")
            continue

        reg = registro_jornada(jornada)
        if reg:
            registros[jornada] = reg
            actualizadas.append(reg)
            print(f"Jornada {jornada}: {reg['aciertos']} aciertos, {reg['fallos']} fallos, "
                  f"{reg['premio_eur']:.2f} EUR ({reg['fuente_premio']})")

    for entry in registros.values():
        if pendiente_premio(entry) and refrescar_premio_oficial(entry):
            if entry not in actualizadas:
                actualizadas.append(entry)
            print(f"Jornada {entry['jornada']}: premio actualizado a {entry['premio_eur']:.2f} EUR ({entry['fuente_premio']})")

    if actualizadas:
        historial["jornadas"] = sorted(registros.values(), key=lambda x: x["jornada"])
        guardar_json(SALIDA, historial)
        print(f"Historial de premios actualizado: {len(actualizadas)} jornada(s).")
    else:
        print("Sin jornadas nuevas o incompletas cerradas para registrar premios.")


if __name__ == "__main__":
    main()
