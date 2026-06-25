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
    "TRIPLE=100%, DOBLE=suma de sus dos signos jugados, FIJO=probabilidad de su unico signo."
)


def ahora():
    return datetime.now(timezone.utc).isoformat()


def cargar_json(path, defecto=None):
    if defecto is None:
        defecto = {}
    path = Path(path)
    if not path.exists():
        return defecto
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return defecto


def guardar_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def numero_jornada(valor):
    if isinstance(valor, int):
        return valor
    m = re.search(r"\d+", str(valor or ""))
    return int(m.group(0)) if m else None


def detectar_jornada_activa():
    ultima = cargar_json(PREDICCIONES / "ultima_prediccion.json", {})
    jornada = numero_jornada(ultima.get("jornada"))
    if jornada and (PREDICCIONES / f"jornada_{jornada}.json").exists():
        return jornada
    jornadas = []
    for path in PREDICCIONES.glob("jornada_*.json"):
        n = numero_jornada(path.stem)
        if n:
            jornadas.append(n)
    return max(jornadas) if jornadas else None


def rutas_prediccion_actual():
    jornada = detectar_jornada_activa()
    rutas = []
    jornada_path = PREDICCIONES / f"jornada_{jornada}.json" if jornada else None
    ultima = PREDICCIONES / "ultima_prediccion.json"
    if jornada_path and jornada_path.exists():
        rutas.append(jornada_path)
    if ultima.exists():
        data = cargar_json(ultima, {})
        if not jornada or numero_jornada(data.get("jornada")) == jornada:
            rutas.append(ultima)
    return list(dict.fromkeys(rutas))


def ffloat(valor, defecto=0.0):
    try:
        return float(valor)
    except (TypeError, ValueError):
        return defecto


def signo_limpio(valor):
    texto = str(valor or "").upper()
    return "".join(signo for signo in SIGNOS if signo in texto)


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
    signos_elige8 = [p.get("signo_final") or p.get("signo_base") or "1" for p in partidos if p.get("en_elige8") or p.get("elige8")]
    apuestas = multiplicador(signos_totales)
    apuestas_elige8 = multiplicador(signos_elige8) if signos_elige8 else 0
    prediccion["coste"] = {
        "apuestas": apuestas,
        "apuestas_elige8": apuestas_elige8,
        "importe_quiniela": round(max(apuestas * PRECIO_APUESTA, PRECIO_APUESTA), 2),
        "importe_elige8": round(apuestas_elige8 * PRECIO_ELIGE8, 2),
        "importe_total": round(max(apuestas * PRECIO_APUESTA, PRECIO_APUESTA) + apuestas_elige8 * PRECIO_ELIGE8, 2),
    }


def prediccion_bloqueada(prediccion):
    if prediccion.get("prediccion_disponible") is False:
        return True
    estado = str(prediccion.get("estado") or "").lower()
    return "bloqueada" in estado or "aprendiendo" in estado or "pendiente_cierre" in estado


def limpiar_elige8_bloqueado(prediccion):
    for partido in prediccion.get("partidos", []) or []:
        partido["elige8"] = False
        partido["en_elige8"] = False
        partido["elige8_modo"] = "bloqueado"
        partido["probabilidad_acierto_elige8"] = 0.0
        partido["elige8_probabilidad_acierto"] = 0.0
        partido["elige8_probabilidad_cubierta"] = 0.0
        partido.pop("elige8_criterio", None)
        partido.pop("elige8_seguro_score", None)
        partido.pop("elige8_seguro_posicion", None)
        partido.pop("elige8_seguro_cumple_umbral", None)
    prediccion.pop("elige8_seguro", None)
    prediccion["prediccion_disponible"] = False
    prediccion["aprendizaje_pendiente"] = True
    prediccion["prediccion_permitida"] = False
    prediccion["publicar_solo_boleto"] = True
    prediccion["publicar_prediccion"] = False
    estado_actual = str(prediccion.get("estado") or "").lower()
    prediccion["estado"] = estado_actual if estado_actual in {"bloqueada", "aprendiendo"} else "bloqueada"
    config = prediccion.setdefault("configuracion", {})
    config["elige8"] = False
    config["elige8_modo"] = "bloqueado"
    config["elige8_recomendado"] = False
    resumen = prediccion.setdefault("resumen", {})
    resumen["elige8_seleccionados"] = 0
    return True


def evaluar_seguridad_elige8(partido):
    probs = probabilidades(partido)
    signos = signos_jugados(partido)
    tipo = tipo_cobertura(signos)
    prob_acierto = probabilidad_acierto_elige8(partido)
    return {
        "num": int(partido.get("num", 0) or 0),
        "partido": f"{partido.get('local', '')} - {partido.get('visitante', '')}",
        "signo_final": signos,
        "tipo_cobertura": tipo,
        "signo_mas_probable": signo_top(probs),
        "probabilidad_top": round(prob_top(probs), 2),
        "probabilidad_acierto": round(prob_acierto, 3),
        "probabilidad_cubierta": round(prob_acierto, 3),
        "margen": round(margen_top(probs), 2),
        "tercera_probabilidad": round(tercera_probabilidad(probs), 2),
        "incertidumbre": round(ffloat(partido.get("incertidumbre"), 0.0), 2),
        "probabilidad_sorpresa": round(ffloat(partido.get("probabilidad_sorpresa"), 0.0), 2),
        "indice_sorpresa_quinielistica": round(ffloat(partido.get("indice_sorpresa_quinielistica"), 0.0), 2),
        "calidad_datos": str(partido.get("calidad_datos") or "sin_dato").lower(),
        "score_seguridad": round(prob_acierto, 3),
        "confianza_real": round(prob_acierto, 3),
        "cumple_umbral_seguro": True,
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
    return {
        "selecciones_evaluadas": resumen.get("selecciones_elige8", 0),
        "aciertos": resumen.get("aciertos_elige8", 0),
        "precision": resumen.get("precision_elige8"),
        "fuente": "data/memoria_ia/aprendizaje_elige8.json",
    }


def construir_resumen(ranking, seleccionados_nums):
    ranking_con_flags = [dict(item, posicion=idx, seleccionado=item["num"] in seleccionados_nums) for idx, item in enumerate(ranking, start=1)]
    return {
        "version": "2.2",
        "generado_en": ahora(),
        "modo": "conservador",
        "modo_real": "probabilidad_real_de_acierto",
        "regla_activa": REGLA_ELIGE8,
        "recomendado": len(seleccionados_nums) == UMBRAL_PARTIDOS_SEGUROS,
        "seleccionados": sorted(seleccionados_nums),
        "ranking": ranking_con_flags,
        "rendimiento": metricas_historicas_modos(),
    }


def aplicar_elige8_seguro(prediccion):
    if prediccion_bloqueada(prediccion):
        return limpiar_elige8_bloqueado(prediccion)

    partidos = [p for p in prediccion.get("partidos", []) if int(p.get("num", 0) or 0) <= 14]
    if len(partidos) < UMBRAL_PARTIDOS_SEGUROS:
        return False

    ranking = sorted([evaluar_seguridad_elige8(p) for p in partidos], key=clave_ranking_elige8)
    seleccionados_nums = {item["num"] for item in ranking[:UMBRAL_PARTIDOS_SEGUROS]}
    posicion_por_num = {item["num"]: idx for idx, item in enumerate(ranking, start=1)}
    evaluacion_por_num = {item["num"]: item for item in ranking}

    for partido in partidos:
        num = int(partido.get("num", 0) or 0)
        evaluacion = evaluacion_por_num.get(num, {})
        elegido = num in seleccionados_nums
        prob_acierto = evaluacion.get("probabilidad_acierto", 0.0)
        partido["elige8"] = elegido
        partido["en_elige8"] = elegido
        partido["elige8_modo"] = "conservador"
        partido["elige8_modo_real"] = "probabilidad_real"
        partido["probabilidad_acierto_elige8"] = prob_acierto
        partido["elige8_probabilidad_acierto"] = prob_acierto
        partido["elige8_probabilidad_cubierta"] = evaluacion.get("probabilidad_cubierta", 0.0)
        partido["elige8_seguro_score"] = evaluacion.get("score_seguridad")
        partido["elige8_confianza_real"] = evaluacion.get("confianza_real")
        partido["elige8_tipo_cobertura"] = evaluacion.get("tipo_cobertura")
        partido["elige8_seguro_posicion"] = posicion_por_num.get(num)
        partido["elige8_seguro_cumple_umbral"] = True
        partido["elige8_seguro_probabilidad_top"] = evaluacion.get("probabilidad_top")
        partido["elige8_seguro_margen"] = evaluacion.get("margen")
        if elegido:
            partido["elige8_criterio"] = "Entra en Elige 8 por ranking de probabilidad real de acierto."
        else:
            partido.pop("elige8_criterio", None)

    resumen = construir_resumen(ranking, seleccionados_nums)
    prediccion["elige8_seguro"] = resumen
    prediccion["elige8_modos"] = {
        "version": "2.2",
        "generado_en": ahora(),
        "modo_activo": "conservador",
        "regla_activa": REGLA_ELIGE8,
        "modos": {
            "conservador": {"seleccionados": sorted(seleccionados_nums), "ranking": resumen["ranking"]},
            "rentable": {"seleccionados": sorted(seleccionados_nums), "ranking": resumen["ranking"]},
        },
        "rendimiento": resumen["rendimiento"],
    }
    config = prediccion.setdefault("configuracion", {})
    config["elige8"] = True
    config["elige8_modo"] = "conservador"
    config["elige8_modo_real"] = "probabilidad_real"
    config["elige8_modos_disponibles"] = ["conservador", "rentable"]
    config["elige8_recomendado"] = True
    resumen_pred = prediccion.setdefault("resumen", {})
    resumen_pred["elige8_seleccionados"] = UMBRAL_PARTIDOS_SEGUROS
    resumen_pred["elige8_seguro_recomendado"] = True
    resumen_pred["elige8_regla"] = "probabilidad_real_de_acierto"
    recalcular_coste(prediccion, partidos)
    return True


def main():
    actualizadas = []
    resumen_actual = {}
    for path in rutas_prediccion_actual():
        prediccion = cargar_json(path, {})
        if aplicar_elige8_seguro(prediccion):
            guardar_json(path, prediccion)
            actualizadas.append(str(path.relative_to(ROOT)))
            if path.name.startswith("jornada_"):
                resumen_actual = prediccion.get("elige8_seguro", resumen_actual)
            elif not resumen_actual:
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
