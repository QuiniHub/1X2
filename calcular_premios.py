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
    "fuente_premio": "pendiente",   # o "calculado" / "manual"
    "boleto": "1X2X11X12X1X2X1X2",  # signos jugados (opcional)
    "notas": ""
}
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
PREDICCIONES = DATA / "predicciones"
JORNADAS = DATA / "jornadas"
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


def cargar_json(path, defecto=None):
    if defecto is None:
        defecto = {}
    if not path.exists():
        return defecto
    return json.loads(path.read_text(encoding="utf-8"))


def guardar_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def leer_prediccion_jornada(jornada):
    """Lee la prediccion pre-cierre de una jornada concreta."""
    candidatos = [
        DATA / "predicciones" / f"snapshot_jornada_{jornada}.json",
        DATA / "predicciones" / f"jornada_{jornada}.json",
        DATA / "predicciones" / "ultima_prediccion.json",
    ]
    for path in candidatos:
        data = cargar_json(path, {})
        if data.get("jornada") == jornada or not data.get("jornada"):
            return data
    return {}


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
        })

    return aciertos, fallos, sorted(detalle, key=lambda x: x["num"])


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


def registro_jornada(jornada):
    """Genera el registro de premios para una jornada concreta."""
    prediccion = leer_prediccion_jornada(jornada)
    resultados = leer_resultados_jornada(jornada)

    partidos_res = resultados.get("partidos") or []
    todos_cerrados = all(
        str(p.get("signo_oficial", "")).upper() in ("1", "X", "2")
        for p in partidos_res
    ) and len(partidos_res) > 0

    if not todos_cerrados:
        return None  # jornada aun no completamente cerrada

    aciertos, fallos, detalle = calcular_aciertos(prediccion, resultados)
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
        "detalle_partidos": detalle,
        "notas": "",
    }


def main():
    """Actualiza el historial de premios con todas las jornadas cerradas."""
    historial = cargar_json(SALIDA, {"jornadas": []})
    jornadas_conocidas = {entry["jornada"] for entry in historial.get("jornadas") or []}

    nuevas = []
    for path in sorted(JORNADAS.glob("jornada_*.json")):
        data = cargar_json(path, {})
        jornada = data.get("jornada")
        if not isinstance(jornada, int):
            continue
        if jornada in jornadas_conocidas:
            continue
        reg = registro_jornada(jornada)
        if reg:
            nuevas.append(reg)
            print(f"Jornada {jornada}: {reg['aciertos']} aciertos, {reg['fallos']} fallos, "
                  f"{reg['premio_eur']:.2f} EUR ({reg['fuente_premio']})")

    if nuevas:
        historial["jornadas"] = sorted(
            (historial.get("jornadas") or []) + nuevas,
            key=lambda x: x["jornada"]
        )
        guardar_json(SALIDA, historial)
        print(f"Historial de premios actualizado: {len(nuevas)} jornada(s) nueva(s).")
    else:
        print("Sin jornadas nuevas cerradas para registrar premios.")


if __name__ == "__main__":
    main()
