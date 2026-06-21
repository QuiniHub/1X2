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


def probabilidades(partido):
    probs = partido.get("probabilidades") or {}
    return {signo: ffloat(probs.get(signo), 0.0) for signo in SIGNOS}


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
    if len(orden) < 2:
        return 0.0
    return orden[0][1] - orden[1][1]


def tercera_probabilidad(probs):
    orden = orden_probabilidades(probs)
    return orden[2][1] if len(orden) >= 3 else 0.0


def signos_jugados(partido):
    signos = signo_limpio(partido.get("signo_final") or partido.get("signo_base"))
    if signos:
        return signos
    probs = probabilidades(partido)
    return signo_top(probs)


def probabilidad_cubierta(partido):
    probs = probabilidades(partido)
    signos = signos_jugados(partido)
    return min(100.0, sum(probs.get(signo, 0.0) for signo in signos))


def valor_indice_sorpresa(partido):
    return ffloat(partido.get("indice_sorpresa_quinielistica"), 0.0)


def datos_memoria_completos(partido):
    memoria = ((partido.get("trazabilidad_datos") or {}).get("memoria_estadistica") or {})
    return bool(memoria.get("local")) and bool(memoria.get("visitante"))


def evaluar_seguridad_elige8(partido):
    probs = probabilidades(partido)
    signos = signos_jugados(partido)
    top = signo_top(probs)
    top_prob = prob_top(probs)
    margen = margen_top(probs)
    tercera = tercera_probabilidad(probs)
    cubierta = probabilidad_cubierta(partido)
    incertidumbre = ffloat(partido.get("incertidumbre"), 0.0)
    sorpresa = ffloat(partido.get("probabilidad_sorpresa"), 0.0)
    indice = valor_indice_sorpresa(partido)
    calidad = str(partido.get("calidad_datos") or "").lower()
    cobertura_sugerida = str(partido.get("cobertura_sorpresa_sugerida") or "FIJO").upper()
    favorito_atacable = bool(partido.get("favorito_atacable"))
    riesgo_necesidad = bool(partido.get("riesgo_necesidad_real") or partido.get("riesgo_necesidad"))
    tiene_memoria = datos_memoria_completos(partido)

    # Elige 8 seguro busca partidos fiables, no simplemente partidos muy cubiertos.
    # Un doble ayuda, pero no debe ganar automaticamente a un fijo fuerte.
    if len(signos) == 1:
        base = probs.get(signos, top_prob)
    elif len(signos) == 2:
        base = min(cubierta, top_prob + 8.0)
    else:
        base = min(cubierta, top_prob + 3.0)

    score = base * 1.45 + margen * 1.10
    score -= sorpresa * 0.70
    score -= indice * 0.75
    score -= max(0.0, incertidumbre - 70.0) * 0.22
    score -= max(0.0, tercera - 18.0) * 0.60

    motivos = []
    bloqueos = []

    if top not in signos:
        score -= 30
        bloqueos.append("el signo jugado no incluye el signo mas probable")
    if len(signos) == 2:
        score -= 8
        motivos.append("doble: buena cobertura, pero no se trata como fijo seguro")
    if len(signos) == 3:
        score -= 42
        bloqueos.append("triple: cubre mucho, pero no es un resultado seguro para Elige 8")
    if calidad == "baja":
        score -= 28
        bloqueos.append("calidad de datos baja")
    elif calidad == "media_baja":
        score -= 16
        motivos.append("calidad de datos media-baja")
    elif calidad == "alta":
        score += 5
        motivos.append("datos estadisticos completos")
    if not tiene_memoria:
        score -= 12
        motivos.append("falta memoria estadistica completa de equipos")
    if favorito_atacable:
        score -= 26
        bloqueos.append("favorito atacable por indice de sorpresa")
    if cobertura_sugerida != "FIJO":
        score -= 20 if cobertura_sugerida == "DOBLE" else 30
        bloqueos.append(f"la propia IA sugiere cobertura {cobertura_sugerida}")
    if riesgo_necesidad:
        score -= 12
        motivos.append("hay necesidad competitiva viva")
    if top_prob < 50:
        score -= 25
        bloqueos.append("probabilidad top por debajo del 50%")
    if margen < 10:
        score -= 18
        bloqueos.append("margen entre signos demasiado corto")
    if sorpresa > 50:
        score -= 18
        bloqueos.append("riesgo de sorpresa alto")
    if indice >= 55:
        score -= 16
        bloqueos.append("indice de sorpresa alto")
    if tercera >= 22:
        score -= 10
        motivos.append("tercer signo demasiado vivo")

    cumple_umbral = not bloqueos
    if cumple_umbral:
        motivos.append("apto para Elige 8 seguro")

    return {
        "num": int(partido.get("num", 0) or 0),
        "partido": f"{partido.get('local', '')} - {partido.get('visitante', '')}",
        "local": partido.get("local"),
        "visitante": partido.get("visitante"),
        "signo_final": signos,
        "signo_mas_probable": top,
        "probabilidad_top": round(top_prob, 2),
        "probabilidad_cubierta": round(cubierta, 2),
        "margen": round(margen, 2),
        "tercera_probabilidad": round(tercera, 2),
        "incertidumbre": round(incertidumbre, 2),
        "probabilidad_sorpresa": round(sorpresa, 2),
        "indice_sorpresa_quinielistica": round(indice, 2),
        "calidad_datos": calidad or "sin_dato",
        "favorito_atacable": favorito_atacable,
        "cobertura_sorpresa_sugerida": cobertura_sugerida,
        "riesgo_necesidad_real": riesgo_necesidad,
        "score_seguridad": round(score, 3),
        "cumple_umbral_seguro": cumple_umbral,
        "motivos": motivos[:6],
        "bloqueos": bloqueos[:8],
    }


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
    importe_quiniela = max(apuestas * PRECIO_APUESTA, PRECIO_APUESTA)
    importe_elige8 = apuestas_elige8 * PRECIO_ELIGE8
    prediccion["coste"] = {
        "apuestas": apuestas,
        "apuestas_elige8": apuestas_elige8,
        "importe_quiniela": round(importe_quiniela, 2),
        "importe_elige8": round(importe_elige8, 2),
        "importe_total": round(importe_quiniela + importe_elige8, 2),
    }


def aplicar_elige8_seguro(prediccion):
    partidos = [p for p in prediccion.get("partidos", []) if int(p.get("num", 0) or 0) <= 14]
    if len(partidos) < 8:
        return False

    evaluaciones = [evaluar_seguridad_elige8(p) for p in partidos]
    ranking = sorted(
        evaluaciones,
        key=lambda item: (
            item["cumple_umbral_seguro"],
            item["score_seguridad"],
            item["probabilidad_top"],
            item["margen"],
        ),
        reverse=True,
    )

    fuertes = [item for item in ranking if item["cumple_umbral_seguro"]]
    if len(fuertes) >= UMBRAL_PARTIDOS_SEGUROS:
        seleccionados = fuertes[:UMBRAL_PARTIDOS_SEGUROS]
        recomendado = True
        lectura = "Elige 8 seguro recomendado: hay al menos 8 partidos que pasan los filtros de seguridad."
    else:
        seleccionados = ranking[:UMBRAL_PARTIDOS_SEGUROS]
        recomendado = False
        lectura = (
            f"Elige 8 forzado con los 8 mejores disponibles, pero solo {len(fuertes)} pasan filtros fuertes. "
            "La jornada no tiene 8 partidos realmente seguros."
        )

    seleccionados_nums = {item["num"] for item in seleccionados}
    posicion_por_num = {item["num"]: idx for idx, item in enumerate(ranking, start=1)}
    evaluacion_por_num = {item["num"]: item for item in ranking}

    for partido in partidos:
        num = int(partido.get("num", 0) or 0)
        evaluacion = evaluacion_por_num.get(num, {})
        elegido = num in seleccionados_nums
        partido["elige8"] = elegido
        partido["elige8_modo"] = "seguro"
        partido["elige8_seguro_score"] = evaluacion.get("score_seguridad")
        partido["elige8_seguro_posicion"] = posicion_por_num.get(num)
        partido["elige8_seguro_cumple_umbral"] = evaluacion.get("cumple_umbral_seguro", False)
        partido["elige8_seguro_probabilidad_top"] = evaluacion.get("probabilidad_top")
        partido["elige8_seguro_margen"] = evaluacion.get("margen")
        if elegido:
            partido["elige8_criterio"] = (
                "Entra en Elige 8 seguro por ranking de seguridad real: probabilidad, margen, "
                "baja sorpresa, calidad de datos y ausencia de favorito atacable."
            )
        else:
            partido.pop("elige8_criterio", None)

    ranking_salida = []
    for idx, item in enumerate(ranking, start=1):
        item = dict(item)
        item["posicion"] = idx
        item["seleccionado"] = item["num"] in seleccionados_nums
        ranking_salida.append(item)

    prediccion["elige8_seguro"] = {
        "version": "1.0",
        "generado_en": ahora(),
        "modo": "elige8_seguro_por_fiabilidad_real",
        "recomendado": recomendado,
        "lectura": lectura,
        "seleccionados": sorted(seleccionados_nums),
        "partidos_que_pasan_filtro_fuerte": len(fuertes),
        "criterios_bloqueo": [
            "probabilidad top < 50%",
            "margen < 10 puntos",
            "triple marcado como cobertura, no como resultado seguro",
            "calidad de datos baja",
            "favorito atacable",
            "riesgo de sorpresa alto",
            "cobertura sugerida distinta de FIJO",
        ],
        "ranking": ranking_salida,
    }

    config = prediccion.setdefault("configuracion", {})
    config["elige8"] = True
    config["elige8_modo"] = "seguro"
    config["elige8_recomendado"] = recomendado

    resumen = prediccion.setdefault("resumen", {})
    resumen["elige8_seleccionados"] = UMBRAL_PARTIDOS_SEGUROS
    resumen["elige8_seguro_recomendado"] = recomendado
    resumen["elige8_seguro_fuertes"] = len(fuertes)

    if not recomendado:
        alertas = prediccion.setdefault("alertas_boleto", [])
        alertas.append({
            "nivel": "alta",
            "titulo": "Elige 8 no tiene 8 seguros fuertes",
            "detalle": lectura,
            "accion": "Revisar el ranking antes de validar; la web marca los 8 mejores disponibles, no 8 seguros absolutos.",
        })

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
        "elige8_seguro": {
            "recomendado": resumen_actual.get("recomendado"),
            "seleccionados": resumen_actual.get("seleccionados"),
            "partidos_que_pasan_filtro_fuerte": resumen_actual.get("partidos_que_pasan_filtro_fuerte"),
        },
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
