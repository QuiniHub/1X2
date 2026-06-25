import json
import re
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
PREDICCIONES = DATA / "predicciones"
MEMORIA = DATA / "memoria_ia"
PRECIO_APUESTA = 1.50
PRECIO_ELIGE8 = 0.50
UMBRAL_PARTIDOS_SEGUROS = 8
SIGNOS = ("1", "X", "2")


REGLA_ELIGE8 = (
    "Elige 8 se selecciona por probabilidad real de acertar el signo jugado: "
    "TRIPLE=100%, DOBLE=suma de sus dos signos jugados, FIJO=probabilidad de su unico signo. "
    "El tipo no da prioridad salvo que el triple siempre vale 100%."
)


def ahora():
    return datetime.now(timezone.utc).isoformat()


def cargar_json(path, defecto=None):
    if defecto is None:
        defecto = {}
    if not path.exists():
        return defecto
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return defecto


def guardar_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def numero_jornada(valor):
    if isinstance(valor, int):
        return valor
    m = re.search(r"\d+", str(valor or ""))
    return int(m.group(0)) if m else None


def ffloat(valor, defecto=0.0):
    try:
        return float(valor)
    except (TypeError, ValueError):
        return defecto


def signo_limpio(valor):
    texto = str(valor or "").upper()
    return "".join(signo for signo in SIGNOS if signo in texto)


def prediccion_bloqueada(prediccion):
    if prediccion.get("prediccion_disponible") is False:
        return True
    estado = str(prediccion.get("estado") or "").lower()
    return "bloqueada" in estado or "aprendiendo" in estado or "pendiente_cierre" in estado


def limpiar_elige8_bloqueado(prediccion):
    """Si no puede haber prediccion real, no debe haber signos ni Elige 8 activo.

    Los 14 partidos se conservan visibles. El Pleno al 15 se conserva aparte.
    """
    for partido in prediccion.get("partidos", []) or []:
        partido["estado_prediccion"] = "bloqueada_por_aprendizaje_pendiente"
        partido["signo_base"] = ""
        partido["signo_final"] = ""
        partido["pronostico_ia"] = "SIN PREDICCION"
        partido["elige8"] = False
        partido["elige8_modo"] = "bloqueado"
        partido.pop("elige8_criterio", None)
        partido.pop("elige8_seguro_score", None)
        partido.pop("elige8_seguro_posicion", None)
        partido.pop("elige8_seguro_cumple_umbral", None)
        partido.pop("elige8_seguro_probabilidad_top", None)
        partido.pop("elige8_seguro_margen", None)
        partido.pop("elige8_probabilidad_acierto", None)
        partido.pop("elige8_probabilidad_cubierta", None)
        partido["lectura"] = "Partido cargado oficialmente. Prediccion retenida hasta cerrar y aprender la jornada anterior."

    prediccion.pop("elige8_seguro", None)
    prediccion["prediccion_disponible"] = False
    prediccion["aprendizaje_pendiente"] = True
    prediccion["prediccion_permitida"] = False
    estado_actual = str(prediccion.get("estado") or "").lower()
    prediccion["estado"] = estado_actual if estado_actual in {"bloqueada", "aprendiendo"} else "bloqueada"
    prediccion["publicar_solo_boleto"] = True
    prediccion["publicar_prediccion"] = False
    config = prediccion.setdefault("configuracion", {})
    config["elige8"] = False
    config["elige8_modo"] = "bloqueado"
    config["elige8_modos_disponibles"] = ["probabilidad_real"]
    config["elige8_recomendado"] = False
    prediccion["coste"] = {
        "apuestas": 0,
        "apuestas_elige8": 0,
        "importe_quiniela": 0,
        "importe_elige8": 0,
        "importe_total": 0.0,
    }
    resumen = prediccion.setdefault("resumen", {})
    resumen["fijos"] = 0
    resumen["dobles"] = 0
    resumen["triples"] = 0
    resumen["elige8_seleccionados"] = 0
    resumen["partidos_cargados"] = len(prediccion.get("partidos", []) or [])
    resumen["pleno15_cargado"] = bool(prediccion.get("pleno15"))
    resumen["total_casillas"] = len(prediccion.get("partidos", []) or []) + (1 if prediccion.get("pleno15") else 0)
    resumen["prediccion"] = "BLOQUEADA_POR_APRENDIZAJE_PENDIENTE"
    prediccion["mensaje"] = "Partidos de la jornada cargados. Prediccion bloqueada hasta cerrar y aprender la jornada anterior."
    return True


def probabilidades(partido):
    probs = partido.get("probabilidades") or {}
    salida = {signo: max(ffloat(probs.get(signo), 0.0), 0.0) for signo in SIGNOS}
    total = sum(salida.values())
    if 0 < total <= 1.5:
        salida = {signo: valor * 100.0 for signo, valor in salida.items()}
    return salida


def orden_probabilidades(probs):
    return sorted(probs.items(), key=lambda item: item[1], reverse=True)


def signo_top(probs):
    orden = orden_probabilidades(probs)
    return orden[0][0] if orden else "1"


def prob_top(probs):
    orden = orden_probabilidades(probs)
    return orden[0][1] if orden else 0.0


def margen_top(probs):
    orden = orden_probabilidades(probs)
    return orden[0][1] - orden[1][1] if len(orden) >= 2 else 0.0


def tercera_probabilidad(probs):
    orden = orden_probabilidades(probs)
    return orden[2][1] if len(orden) >= 3 else 0.0


def signos_jugados(partido):
    signos = signo_limpio(partido.get("signo_final") or partido.get("signo_base"))
    if signos:
        return signos
    return signo_top(probabilidades(partido))


def tipo_cobertura(signos):
    total = len(signo_limpio(signos))
    if total >= 3:
        return "TRIPLE"
    if total == 2:
        return "DOBLE"
    if total == 1:
        return "FIJO"
    return "SIN_SIGNO"


def probabilidad_acierto_elige8(partido):
    signos = signos_jugados(partido)
    if len(signos) >= 3:
        return 100.0
    probs = probabilidades(partido)
    return round(min(100.0, sum(probs.get(signo, 0.0) for signo in signos)), 3)


def multiplicador(signos):
    total = 1
    for valor in signos:
        total *= max(len(signo_limpio(valor)), 1)
    return total


def recalcular_coste(prediccion, partidos):
    signos_totales = [p.get("signo_final") or p.get("signo_base") or "1" for p in partidos]
    signos_elige8 = [p.get("signo_final") or p.get("signo_base") or "1" for p in partidos if p.get("elige8")]
    apuestas = multiplicador(signos_totales)
    apuestas_elige8 = multiplicador(signos_elige8) if signos_elige8 else 0
    prediccion["coste"] = {
        "apuestas": apuestas,
        "apuestas_elige8": apuestas_elige8,
        "importe_quiniela": round(max(apuestas * PRECIO_APUESTA, PRECIO_APUESTA), 2),
        "importe_elige8": round(apuestas_elige8 * PRECIO_ELIGE8, 2),
        "importe_total": round(max(apuestas * PRECIO_APUESTA, PRECIO_APUESTA) + apuestas_elige8 * PRECIO_ELIGE8, 2),
    }


def evaluar_seguridad_elige8(partido):
    probs = probabilidades(partido)
    signos = signos_jugados(partido)
    tipo = tipo_cobertura(signos)
    top = signo_top(probs)
    top_prob = prob_top(probs)
    margen = margen_top(probs)
    tercera = tercera_probabilidad(probs)
    prob_acierto = probabilidad_acierto_elige8(partido)
    incertidumbre = ffloat(partido.get("incertidumbre"), 0.0)
    sorpresa = ffloat(partido.get("probabilidad_sorpresa"), 0.0)
    indice = ffloat(partido.get("indice_sorpresa_quinielistica"), 0.0)
    calidad = str(partido.get("calidad_datos") or "").lower()
    cobertura_sugerida = str(partido.get("cobertura_sorpresa_sugerida") or "FIJO").upper()
    favorito_atacable = bool(partido.get("favorito_atacable"))
    riesgo_necesidad = bool(partido.get("riesgo_necesidad_real") or partido.get("riesgo_necesidad"))

    motivos = []
    if tipo == "TRIPLE":
        motivos.append("triple: probabilidad real de acierto 100%")
    elif tipo == "DOBLE":
        motivos.append(f"doble {signos}: probabilidad real por suma de signos jugados {prob_acierto:.1f}%")
    elif tipo == "FIJO":
        motivos.append(f"fijo {signos}: probabilidad real del signo jugado {prob_acierto:.1f}%")
    if favorito_atacable:
        motivos.append("favorito atacable: se informa como riesgo, pero no altera la prioridad principal")
    if cobertura_sugerida != "FIJO":
        motivos.append(f"cobertura sugerida {cobertura_sugerida}: la prioridad sigue siendo probabilidad real de acierto")
    if riesgo_necesidad:
        motivos.append("necesidad competitiva viva")

    return {
        "num": int(partido.get("num", 0) or 0),
        "partido": f"{partido.get('local', '')} - {partido.get('visitante', '')}",
        "signo_final": signos,
        "tipo_cobertura": tipo,
        "signo_mas_probable": top,
        "probabilidad_top": round(top_prob, 2),
        "probabilidad_acierto": round(prob_acierto, 3),
        "probabilidad_cubierta": round(prob_acierto, 3),
        "margen": round(margen, 2),
        "tercera_probabilidad": round(tercera, 2),
        "incertidumbre": round(incertidumbre, 2),
        "probabilidad_sorpresa": round(sorpresa, 2),
        "indice_sorpresa_quinielistica": round(indice, 2),
        "calidad_datos": calidad or "sin_dato",
        "favorito_atacable": favorito_atacable,
        "cobertura_sorpresa_sugerida": cobertura_sugerida,
        "score_seguridad": round(prob_acierto, 3),
        "confianza_real": round(prob_acierto, 3),
        "cumple_umbral_seguro": True,
        "motivos": motivos[:8],
        "bloqueos": [],
    }


def clave_ranking_elige8(item):
    return (
        -float(item.get("probabilidad_acierto") or 0.0),
        float(item.get("incertidumbre") or 0.0),
        float(item.get("probabilidad_sorpresa") or 0.0),
        float(item.get("indice_sorpresa_quinielistica") or 0.0),
        -float(item.get("margen") or 0.0),
        int(item.get("num") or 0),
    )


def metricas_historicas_modos():
    memoria = cargar_json(MEMORIA / "aprendizaje_elige8.json", {})
    resumen = memoria.get("resumen") or {}
    precision = resumen.get("precision_elige8")
    return {
        "probabilidad_real": {
            "selecciones_evaluadas": resumen.get("selecciones_elige8", 0),
            "aciertos": resumen.get("aciertos_elige8", 0),
            "precision": precision,
            "fuente": "data/memoria_ia/aprendizaje_elige8.json",
        }
    }


def construir_modos_elige8(ranking):
    seleccionados = {item["num"] for item in ranking[:UMBRAL_PARTIDOS_SEGUROS]}
    return {
        "version": "2.0",
        "generado_en": ahora(),
        "modo_activo": "probabilidad_real",
        "regla_activa": REGLA_ELIGE8,
        "modos": {
            "probabilidad_real": {
                "objetivo": "elegir los 8 partidos con mayor probabilidad real de acierto del signo jugado",
                "seleccionados": sorted(seleccionados),
                "ranking": [
                    dict(item, posicion=idx, seleccionado=item["num"] in seleccionados)
                    for idx, item in enumerate(ranking, start=1)
                ],
            }
        },
        "rendimiento": metricas_historicas_modos(),
    }


def aplicar_elige8_seguro(prediccion):
    if prediccion_bloqueada(prediccion):
        return limpiar_elige8_bloqueado(prediccion)

    partidos = [p for p in prediccion.get("partidos", []) if int(p.get("num", 0) or 0) <= 14]
    if len(partidos) < 8:
        return False

    ranking = sorted([evaluar_seguridad_elige8(p) for p in partidos], key=clave_ranking_elige8)
    seleccionados = ranking[:UMBRAL_PARTIDOS_SEGUROS]
    seleccionados_nums = {item["num"] for item in seleccionados}
    posicion_por_num = {item["num"]: idx for idx, item in enumerate(ranking, start=1)}
    evaluacion_por_num = {item["num"]: item for item in ranking}
    recomendado = len(seleccionados) == UMBRAL_PARTIDOS_SEGUROS

    for partido in partidos:
        num = int(partido.get("num", 0) or 0)
        evaluacion = evaluacion_por_num.get(num, {})
        elegido = num in seleccionados_nums
        partido["elige8"] = elegido
        partido["elige8_modo"] = "probabilidad_real"
        partido["elige8_seguro_score"] = evaluacion.get("score_seguridad")
        partido["elige8_confianza_real"] = evaluacion.get("confianza_real")
        partido["elige8_probabilidad_acierto"] = evaluacion.get("probabilidad_acierto")
        partido["elige8_probabilidad_cubierta"] = evaluacion.get("probabilidad_cubierta")
        partido["elige8_tipo_cobertura"] = evaluacion.get("tipo_cobertura")
        partido["elige8_seguro_posicion"] = posicion_por_num.get(num)
        partido["elige8_seguro_cumple_umbral"] = True
        partido["elige8_seguro_probabilidad_top"] = evaluacion.get("probabilidad_top")
        partido["elige8_seguro_margen"] = evaluacion.get("margen")
        if elegido:
            partido["elige8_criterio"] = (
                "Entra en Elige 8 por ranking de probabilidad real de acierto: "
                "TRIPLE=100%, DOBLE=suma de signos jugados, FIJO=probabilidad del signo jugado."
            )
        else:
            partido.pop("elige8_criterio", None)

    prediccion["elige8_seguro"] = {
        "version": "2.0",
        "generado_en": ahora(),
        "modo": "elige8_por_probabilidad_real_de_acierto",
        "regla_activa": REGLA_ELIGE8,
        "recomendado": recomendado,
        "lectura": "Elige 8 seleccionado por probabilidad real de acierto del signo jugado.",
        "seleccionados": sorted(seleccionados_nums),
        "ranking": [dict(item, posicion=idx, seleccionado=item["num"] in seleccionados_nums) for idx, item in enumerate(ranking, start=1)],
    }
    prediccion["elige8_modos"] = construir_modos_elige8(ranking)
    config = prediccion.setdefault("configuracion", {})
    config["elige8"] = True
    config["elige8_modo"] = "probabilidad_real"
    config["elige8_modos_disponibles"] = ["probabilidad_real"]
    config["elige8_recomendado"] = recomendado
    resumen = prediccion.setdefault("resumen", {})
    resumen["elige8_seleccionados"] = UMBRAL_PARTIDOS_SEGUROS
    resumen["elige8_seguro_recomendado"] = recomendado
    resumen["elige8_regla"] = "probabilidad_real_de_acierto"
    recalcular_coste(prediccion, partidos)
    return True


def rutas_prediccion_actual():
    rutas = []
    ultima = PREDICCIONES / "ultima_prediccion.json"
    if ultima.exists():
        rutas.append(ultima)
        data = cargar_json(ultima, {})
        jornada = numero_jornada(data.get("jornada"))
        if jornada:
            jornada_path = PREDICCIONES / f"jornada_{jornada}.json"
            if jornada_path.exists() and jornada_path not in rutas:
                rutas.append(jornada_path)
    return rutas


def main():
    actualizadas = []
    resumen_actual = {}
    for path in rutas_prediccion_actual():
        prediccion = cargar_json(path, {})
        if aplicar_elige8_seguro(prediccion):
            guardar_json(path, prediccion)
            actualizadas.append(str(path.relative_to(ROOT)))
            if path.name == "ultima_prediccion.json":
                resumen_actual = prediccion.get("elige8_seguro", {})

    if resumen_actual:
        guardar_json(MEMORIA / "elige8_seguro_actual.json", resumen_actual)

    print(json.dumps({
        "estado": "ok",
        "script": "aplicar_elige8_seguro.py",
        "archivos_actualizados": actualizadas,
        "prediccion_bloqueada": not bool(resumen_actual),
        "elige8_seguro": resumen_actual,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
