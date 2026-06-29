"""Selecciona el Pleno al 15 con criterio predictivo.

Lee data/predicciones/ultima_prediccion.json, puntua candidatos por seguridad real
(probabilidad top, margen, incertidumbre, surprise_score, motivacion/clasificacion y
calidad de datos), guarda data/predicciones/pleno15_jornada_actual.json y actualiza
el campo pleno15 de la prediccion vigente.
"""

import json
import math
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
PREDICCIONES = DATA / "predicciones"
ULTIMA = PREDICCIONES / "ultima_prediccion.json"
SALIDA = PREDICCIONES / "pleno15_jornada_actual.json"
SIGNOS = ("1", "X", "2")


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


def ahora_iso():
    return datetime.now(timezone.utc).isoformat()


def numero(valor, defecto=0.0):
    try:
        return float(valor)
    except (TypeError, ValueError):
        return defecto


def probabilidades(partido):
    probs = partido.get("probabilidades") or {}
    if not isinstance(probs, dict):
        return {}
    salida = {}
    for signo in SIGNOS:
        if signo in probs:
            salida[signo] = numero(probs.get(signo), 0.0)
    if not all(signo in salida for signo in SIGNOS):
        return {}
    total = sum(salida.values())
    if 0 < total <= 1.5:
        salida = {signo: valor * 100.0 for signo, valor in salida.items()}
    return salida


def signo_top(probs):
    return sorted(probs.items(), key=lambda item: item[1], reverse=True)[0][0]


def margen_top(probs):
    valores = sorted((numero(v) for v in probs.values()), reverse=True)
    if len(valores) < 2:
        return 0.0
    return round(valores[0] - valores[1], 2)


def top_prob(probs):
    return round(max((numero(v) for v in probs.values()), default=0.0), 2)


def calidad_factor(partido):
    calidad = str(partido.get("calidad_datos") or "").lower()
    origen = str(partido.get("origen_probabilidades") or "").lower()
    if calidad in {"profesional", "alta"}:
        return 8.0
    if calidad in {"media", "media_alta"}:
        return 3.5
    if calidad in {"media_baja", "baja"}:
        return -8.0
    if "fallback" in origen:
        return -10.0
    return 0.0


def riesgo_sorpresa(partido):
    return max(
        numero(partido.get("surprise_score"), 0.0),
        numero(partido.get("indice_sorpresa_quinielistica"), 0.0),
        numero(partido.get("probabilidad_sorpresa"), 0.0),
    )


def categoria_penalizacion(partido):
    categoria = str(partido.get("categoria_sorpresa") or "").lower()
    sugerida = str(partido.get("cobertura_sorpresa_sugerida") or "").upper()
    penaliza = 0.0
    if "muy" in categoria or "abierto" in categoria:
        penaliza += 14.0
    elif "vigilada" in categoria or "alta" in categoria:
        penaliza += 8.0
    elif "controlado" in categoria:
        penaliza -= 3.0
    if sugerida == "TRIPLE":
        penaliza += 16.0
    elif sugerida == "DOBLE":
        penaliza += 8.0
    return penaliza


def motivacion_penalizacion(partido):
    penaliza = 0.0
    ajuste = partido.get("ajuste_clasificacion_mundial_2026") or {}
    for lado in ("local", "visitante"):
        datos = ajuste.get(lado) or {}
        situacion = str(datos.get("situacion") or "").lower()
        if datos.get("rotacion_probable"):
            penaliza += 7.0
        if situacion == "necesita_ganar":
            penaliza += 3.0
        elif situacion == "le_vale_empate":
            penaliza += 2.0
        elif situacion == "depende_de_otros_resultados":
            penaliza += 4.0
        elif situacion in {"ya_clasificada", "eliminada"}:
            penaliza += 6.0
    if partido.get("riesgo_necesidad_real"):
        penaliza += 4.5
    return penaliza


def candidato_valido(partido):
    if not isinstance(partido, dict):
        return False
    if not partido.get("local") or not partido.get("visitante"):
        return False
    return bool(probabilidades(partido))


def evaluar_partido(partido):
    probs = probabilidades(partido)
    signo = signo_top(probs)
    prob = top_prob(probs)
    margen = margen_top(probs)
    incertidumbre = numero(partido.get("incertidumbre"), 100.0)
    sorpresa = riesgo_sorpresa(partido)
    penalizacion_categoria = categoria_penalizacion(partido)
    penalizacion_motivacion = motivacion_penalizacion(partido)
    factor_calidad = calidad_factor(partido)
    # Elige 8 ya significa alta probabilidad real de acierto; no se penaliza aqui.
    score = (
        prob * 1.35
        + margen * 1.55
        + factor_calidad
        - incertidumbre * 0.28
        - sorpresa * 0.38
        - penalizacion_categoria
        - penalizacion_motivacion
    )
    razonamiento = construir_razonamiento(
        partido,
        signo,
        prob,
        margen,
        incertidumbre,
        sorpresa,
        factor_calidad,
        penalizacion_motivacion,
        penalizacion_categoria,
        score,
    )
    return {
        "num": partido.get("num"),
        "local": partido.get("local"),
        "visitante": partido.get("visitante"),
        "signo_recomendado": signo,
        "probabilidad": prob,
        "margen_probabilidad": margen,
        "incertidumbre": round(incertidumbre, 2),
        "surprise_score": round(sorpresa, 2),
        "categoria_sorpresa": partido.get("categoria_sorpresa"),
        "calidad_datos": partido.get("calidad_datos"),
        "origen_probabilidades": partido.get("origen_probabilidades"),
        "riesgo_necesidad_real": bool(partido.get("riesgo_necesidad_real")),
        "elige8": bool(partido.get("elige8")),
        "elige8_probabilidad_acierto": partido.get("elige8_probabilidad_acierto"),
        "ajuste_clasificacion_mundial_2026": partido.get("ajuste_clasificacion_mundial_2026", {}),
        "score_pleno15": round(score, 2),
        "razonamiento": razonamiento,
    }


def construir_razonamiento(partido, signo, prob, margen, incertidumbre, sorpresa, calidad, penal_motivacion, penal_categoria, score):
    piezas = [
        f"Se recomienda el signo {signo} porque es el signo con mayor probabilidad estimada ({prob:.1f}%).",
        f"El margen frente al segundo signo es de {margen:.1f} puntos, que mide la separacion real del favorito.",
        f"La incertidumbre del partido es {incertidumbre:.1f} y el riesgo de sorpresa usado por el sistema es {sorpresa:.1f}.",
    ]
    if calidad > 0:
        piezas.append("La calidad de datos suma confianza al pronostico.")
    elif calidad < 0:
        piezas.append("La calidad de datos penaliza el candidato, por eso no basta con mirar solo la probabilidad top.")
    if penal_motivacion:
        piezas.append("La motivacion/clasificacion competitiva introduce riesgo adicional de rotaciones, necesidad o resultado tactico.")
    if penal_categoria:
        piezas.append("La categoria de sorpresa o cobertura sugerida exige prudencia para el Pleno al 15.")
    if partido.get("elige8"):
        piezas.append("El partido tambien aparece en Elige 8 por probabilidad real de acierto; eso no se penaliza para el Pleno al 15.")
    lecturas = partido.get("lecturas_motivacion") or []
    if lecturas:
        piezas.append("Lectura contextual: " + str(lecturas[0]))
    piezas.append(f"Score conservador Pleno al 15: {score:.2f}; se elige el candidato con mayor seguridad combinada, no solo el favorito mas alto.")
    return " ".join(piezas)


def poisson_goles(lam, max_goles=4):
    """Distribución Poisson truncada en 0,1,2,M(3+)."""
    probs = {}
    acum = 0.0
    for k in range(max_goles):
        p = math.exp(-lam) * (lam ** k) / math.factorial(k)
        probs[k] = p
        acum += p
    probs["M"] = max(0.0, 1.0 - acum)
    return probs


def calcular_probs_goles(partido):
    """Estima probabilidades de goles (0,1,2,M) para local y visitante
    usando la distribución de Poisson calibrada con las probs 1X2."""
    probs = probabilidades(partido)
    if not probs:
        return None
    p1 = numero(probs.get("1", 0)) / 100
    p2 = numero(probs.get("2", 0)) / 100

    # Lambda esperada: equipo fuerte tiene más goles esperados
    # Referencia: media fútbol europeo ~1.4 local, ~1.05 visitante
    lam_local = max(0.3, 0.5 + p1 * 2.2)
    lam_visitante = max(0.3, 0.5 + p2 * 2.2)

    def _format(dist):
        total = sum(dist.values()) or 1.0
        return {
            "0": round(dist[0] / total * 100, 1),
            "1": round(dist[1] / total * 100, 1),
            "2": round(dist[2] / total * 100, 1),
            "M": round(dist["M"] / total * 100, 1),
        }

    return {
        "local": _format(poisson_goles(lam_local)),
        "visitante": _format(poisson_goles(lam_visitante)),
        "lambda_local": round(lam_local, 2),
        "lambda_visitante": round(lam_visitante, 2),
    }


def candidatos_prediccion(data):
    candidatos = []
    for partido in data.get("partidos", []):
        if int(partido.get("num") or 0) <= 14:
            candidatos.append(partido)
    pleno = data.get("pleno15")
    if isinstance(pleno, dict):
        candidatos.append(pleno)
    return candidatos


def construir_salida_sin_candidatos(data, motivo):
    return {
        "version": "1.0",
        "generado_en": ahora_iso(),
        "jornada": data.get("jornada"),
        "estado": "sin_recomendacion",
        "motivo": motivo,
        "recomendacion": None,
        "candidatos_evaluados": [],
        "criterio": "Se requiere que los partidos tengan probabilidades 1/X/2 calculadas por el motor.",
    }


def actualizar_pleno15(data, recomendacion):
    pleno_actual = data.get("pleno15") if isinstance(data.get("pleno15"), dict) else {}
    pleno = dict(pleno_actual)
    for clave in ("num", "local", "visitante"):
        pleno[clave] = recomendacion.get(clave)
    pleno["signo_recomendado"] = recomendacion.get("signo_recomendado")
    pleno["signo_base"] = recomendacion.get("signo_recomendado")
    pleno["signo_final"] = recomendacion.get("signo_recomendado")
    pleno["probabilidad"] = recomendacion.get("probabilidad")
    pleno["probabilidades"] = recomendacion.get("probabilidades", pleno.get("probabilidades", {}))
    pleno["probabilidades_goles"] = recomendacion.get("probabilidades_goles") or pleno.get("probabilidades_goles") or {}
    pleno["margen_probabilidad"] = recomendacion.get("margen_probabilidad")
    pleno["incertidumbre"] = recomendacion.get("incertidumbre")
    pleno["surprise_score"] = recomendacion.get("surprise_score")
    pleno["categoria_sorpresa"] = recomendacion.get("categoria_sorpresa")
    pleno["calidad_datos"] = recomendacion.get("calidad_datos")
    pleno["estado_prediccion"] = "seleccionado_por_criterio_pleno15"
    pleno["razonamiento_pleno15"] = recomendacion.get("razonamiento")
    pleno["actualizado_por"] = "seleccionar_pleno15.py"
    pleno["actualizado_en"] = ahora_iso()
    data["pleno15"] = pleno
    return data


def main():
    data = cargar_json(ULTIMA, {})
    if not data:
        salida = construir_salida_sin_candidatos({}, "No existe data/predicciones/ultima_prediccion.json o no se pudo leer.")
        guardar_json(SALIDA, salida)
        print("Pleno al 15: sin prediccion base disponible.")
        return

    evaluados = []
    descartados = []
    for partido in candidatos_prediccion(data):
        if candidato_valido(partido):
            evaluado = evaluar_partido(partido)
            evaluado["probabilidades"] = probabilidades(partido)
            evaluado["probabilidades_goles"] = calcular_probs_goles(partido)
            evaluados.append(evaluado)
        else:
            descartados.append({
                "num": partido.get("num"),
                "local": partido.get("local"),
                "visitante": partido.get("visitante"),
                "motivo": "Sin probabilidades 1/X/2 calculadas por el motor.",
            })

    if not evaluados:
        salida = construir_salida_sin_candidatos(
            data,
            "La jornada existe, pero ningun partido tiene probabilidades 1/X/2 disponibles. Probablemente la prediccion esta bloqueada por aprendizaje pendiente.",
        )
        salida["descartados"] = descartados
        guardar_json(SALIDA, salida)
        data.setdefault("pleno15", {})["estado_prediccion"] = "pendiente_probabilidades_pleno15"
        data["pleno15"]["razonamiento_pleno15"] = salida["motivo"]
        guardar_json(ULTIMA, data)
        print("Pleno al 15: pendiente, no hay probabilidades calculadas.")
        return

    ordenados = sorted(evaluados, key=lambda item: item["score_pleno15"], reverse=True)
    recomendacion = dict(ordenados[0])
    salida = {
        "version": "1.1",
        "generado_en": ahora_iso(),
        "jornada": data.get("jornada"),
        "estado": "recomendado",
        "recomendacion": recomendacion,
        "candidatos_evaluados": ordenados,
        "descartados": descartados,
        "criterio": {
            "prioriza": ["probabilidad_top", "margen_probabilidad", "baja_incertidumbre", "bajo_surprise_score", "calidad_datos"],
            "penaliza": ["categoria_sorpresa_alta", "rotacion_probable", "necesidad_competitiva_extrema", "fallback_o_baja_calidad"],
            "elige8": "No se penaliza: si un partido entra en Elige 8 es porque tiene alta probabilidad real de acierto.",
        },
    }
    guardar_json(SALIDA, salida)
    actualizar_pleno15(data, recomendacion)
    guardar_json(ULTIMA, data)
    jornada = data.get("jornada")
    if jornada:
        guardar_json(PREDICCIONES / f"jornada_{jornada}.json", data)
    print(
        "Pleno al 15 recomendado: "
        f"partido {recomendacion.get('num')} {recomendacion.get('local')} - {recomendacion.get('visitante')} "
        f"signo {recomendacion.get('signo_recomendado')} ({recomendacion.get('probabilidad')}%)."
    )


if __name__ == "__main__":
    main()
