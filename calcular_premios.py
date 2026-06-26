"""Modulo de premios por jornada.

Calcula y persiste el registro de premios cobrados en cada jornada
jugada. El premio se calcula automaticamente si hay datos fiables
(aciertos confirmados y tabla de premios oficial). Si no hay dato
fiable, el premio queda como 0.0 EUR y se marca como pendiente.

Salida: data/premios/historial_premios.json
Formato de cada entrada:
{
    "jornada": 62,
    "aciertos": 10,
    "fallos": 4,
    "premio_eur": 0.0,
    "fuente_premio": "pendiente",   # o "oficial" / "calculado" / "manual"
    "boleto": "1X2X11X12X1X2X1X2",  # signos jugados (opcional)
    "notas": ""
}
"""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
PREDICCIONES = DATA / "predicciones"
JORNADAS = DATA / "jornadas"
MEMORIA = DATA / "memoria_ia"
QUINIELAS_JUGADAS = DATA / "quinielas_jugadas.json"
FUENTE_LOSILLA = MEMORIA / "fuente_losilla.json"
SALIDA = DATA / "premios" / "historial_premios.json"

# Tabla de premios orientativa de La Quiniela (SELAE).
# Los valores reales cambian cada semana segun el bote acumulado
# y el numero de acertantes. Esta tabla solo se usa como estimacion
# cuando no hay dato oficial disponible.
# Fuente: https://www.loteriasyapuestas.es
TABLA_PREMIOS_ESTIMADOS = {
    15: 0.0,    # Pleno al 15 — bote variable, no estimable
    14: 0.0,    # Premio 14 — bote variable
    13: 25.0,   # Estimacion orientativa
    12: 8.0,    # Estimacion orientativa
    11: 4.0,    # Estimacion orientativa
    10: 0.0,    # Sin premio habitual
}

CLAVES_PREMIO = {
    15: ("premio_pleno_al_15", "premio_15"),
    14: ("premio_14",),
    13: ("premio_13",),
    12: ("premio_12",),
    11: ("premio_11",),
    10: ("premio_10",),
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
            continue  # partido sin resultado oficial todavia
        signo_pred = str(pred.get("signo_final") or pred.get("signo_base") or "").upper()
        tipo = str(pred.get("tipo") or "FIJO").upper()

        # Un TRIPLE cubre siempre los tres signos
        if tipo == "TRIPLE":
            acertado = True
        elif tipo == "DOBLE":
            acertado = signo_oficial in signo_pred  # signo_pred es p.ej. "1X" o "X2"
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

    # Compatibilidad por si alguna fuente guardo jornada_76 sin cero a la izquierda.
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


def obtener_premio_oficial(jornada, aciertos, jugo_elige8):
    """Devuelve el importe real del escrutinio oficial de una jornada.

    Lee data/memoria_ia/fuente_losilla.json -> escrutinio -> jornada_XX.
    Si no existe escrutinio para la jornada devuelve None. Si existe, devuelve
    el premio real de la categoria de aciertos y suma Elige 8 cuando corresponde
    y hay premio_elige8 mayor que cero.
    """
    registro = registro_escrutinio(jornada)
    if not registro:
        return None

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

    return round(total, 2) if encontrado else None


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


def estimar_premio(aciertos, prediccion):
    """Estima el premio basandose en la tabla orientativa.

    Devuelve (premio_eur, fuente) donde fuente es 'calculado' o 'pendiente'.
    Si el numero de aciertos no alcanza el minimo para prize, devuelve 0.0.
    """
    # Si la quiniela tiene triples/dobles, el coste es mayor y los
    # premios se reparten entre mas combinaciones. No se puede estimar
    # de forma fiable sin el bote oficial de esa semana.
    resumen = prediccion.get("resumen") or {}
    hay_coberturas = resumen.get("dobles", 0) > 0 or resumen.get("triples", 0) > 0
    if hay_coberturas:
        return 0.0, "pendiente"  # requiere dato oficial

    if aciertos in TABLA_PREMIOS_ESTIMADOS:
        premio = TABLA_PREMIOS_ESTIMADOS[aciertos]
        fuente = "calculado" if premio > 0 else "pendiente"
        return premio, fuente

    return 0.0, "pendiente"


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
        return None  # jornada aun no completamente cerrada

    aciertos, fallos, detalle = calcular_aciertos(prediccion, resultados)
    gano_elige8, seleccion = elige8_acertado(prediccion, jornada, detalle)
    premio_oficial = obtener_premio_oficial(jornada, aciertos, gano_elige8)
    if premio_oficial is not None:
        premio, fuente = premio_oficial, "oficial"
    else:
        premio, fuente = estimar_premio(aciertos, prediccion)

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
        "notas": "",
    }


def registro_completo(entry):
    return len(entry.get("detalle_partidos") or []) == 14


def pendiente_premio(entry):
    try:
        return float(entry.get("premio_eur") or 0.0) == 0.0
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

    premio = obtener_premio_oficial(jornada, aciertos, gano_elige8)
    if premio is None:
        return False

    entry["premio_eur"] = premio
    entry["fuente_premio"] = "oficial"
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
                print(f"Jornada {jornada}: premio oficial actualizado a "
                      f"{existente['premio_eur']:.2f} EUR")
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
            print(f"Jornada {entry['jornada']}: premio oficial actualizado a "
                  f"{entry['premio_eur']:.2f} EUR")

    if actualizadas:
        historial["jornadas"] = sorted(registros.values(), key=lambda x: x["jornada"])
        guardar_json(SALIDA, historial)
        print(f"Historial de premios actualizado: {len(actualizadas)} jornada(s).")
    else:
        print("Sin jornadas nuevas o incompletas cerradas para registrar premios.")


if __name__ == "__main__":
    main()
