import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
PREDICCIONES = DATA / "predicciones"
MEMORIA = DATA / "memoria_ia"
PRECIO_APUESTA = 0.75
IMPORTE_MINIMO = 1.50
PRECIO_ELIGE8 = 0.50
UMBRAL_PARTIDOS_SEGUROS = 8
SIGNOS = ("1", "X", "2")

REGLA_ELIGE8 = (
    "Elige 8 se selecciona por la probabilidad real de acierto NORMALIZADA por el coste "
    "que ese partido añade al Elige8 (eficiencia_elige8 = probabilidad_acierto / "
    "multiplicador) -un doble o un triple solo entra por delante de un fijo solido si su "
    "probabilidad de acierto compensa de verdad pagar 2x o 3x mas caro, no por defecto."
)

# Premio TIPICO (mediana real) por ganador del 8/8 de Elige8, segun el tipo de
# jornada -investigado el 2026-08 tras una pregunta de Marc: el premio NO
# depende de si la jornada es "Primera pura" (eso ni existe: Primera solo
# tiene 20 equipos = 10 partidos, Quiniela necesita 14, siempre se rellena
# con Segunda) sino de si es una jornada DOMESTICA de fin de semana
# (Primera+Segunda, mas sorpresas reales, menos gente acierta el 8/8 limpio,
# premio mucho mas alto por cabeza) o INTERNACIONAL/de relleno (Champions,
# clasificacion de selecciones, ligas nordicas de verano -favoritos mas
# obvios para el publico, miles de aciertos de 8/8, premio diluido). Datos
# reales verificados via eduardolosilla.es, temporada 2025/26: domestica
# mediana 578,70€ (13 jornadas, rango 16-3.635€), internacional mediana
# 32,62€ (5 jornadas, rango 1-118€). Se usa la MEDIANA, no la media -la
# media queda muy inflada por semanas puntuales con pocos acertantes.
PREMIO_TIPICO_ELIGE8 = {
    "domestica": 578.70,
    "internacional": 32.62,
}
COMPETICIONES_DOMESTICAS = {"primera_division", "segunda_division"}


def tipo_jornada_elige8(partidos):
    """'domestica' si la mayoria de los partidos son Primera/Segunda
    espanola, 'internacional' en cualquier otro caso (Champions, selecciones,
    Mundial, ligas extranjeras/nordicas, o sin dato)."""
    domesticos = sum(
        1 for p in partidos
        if str(p.get("competicion_resuelta") or "").lower() in COMPETICIONES_DOMESTICAS
    )
    return "domestica" if partidos and domesticos > len(partidos) / 2 else "internacional"


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
    """Probabilidad real de que el resultado caiga dentro de lo marcado en
    el boleto principal para este partido -TRIPLE=100% (cubre los 3 signos
    posibles), DOBLE=suma de sus dos signos, FIJO=probabilidad de su unico
    signo. Este numero es correcto tal cual para MOSTRAR al usuario -si el
    partido esta marcado triple, ese resultado concreto SI esta garantizado.
    No usar esto solo para decidir que 8 partidos entran por defecto en el
    Elige8 -ver eficiencia_elige8, que es lo que de verdad hay que rankear."""
    signos = signos_jugados(partido)
    if len(signos) >= 3:
        return 100.0
    probs = probabilidades(partido)
    return round(min(100.0, sum(probs.get(signo, 0.0) for signo in signos)), 3)


def multiplicador_signo(signos):
    return max(len(signo_limpio(signos)), 1)


def eficiencia_elige8(partido):
    """Probabilidad de acierto normalizada por el coste real que ese
    partido añade al Elige8 -jugarlo doble o triple en el boleto principal
    multiplica el coste del Elige8 x2 o x3 (ver multiplicador en
    recalcular_coste), asi que cubrir mas signos no hace ese partido "gratis"
    de fiable para el ranking por defecto, solo lo hace ganar mas caro.

    Fix 2026-08 (jornada 75): antes se rankeaba directamente por
    probabilidad_acierto_elige8 (REGLA_ELIGE8 antigua), lo que repetia el
    mismo sesgo que Marc ya habia identificado y corregido a mano en la
    jornada 73 (feedback_metodo_prediccion_manual.md, regla 1: "sumar el %
    real de los signos marcados y ordenar por ese numero, no asumir que
    'tiene doble' = 'es mas seguro'"). Prueba real: jornada 75, P1
    (VPS-Inter Turku, triple, empate a 3 bandas 34.1/31.1/34.8) puntuaba
    100% con la formula vieja, por encima de P2 (TPS-Mariehamn, fijo,
    favorito solido al 58.3%) -justo al reves de lo que Marc eligio a mano
    para el Elige8 real de esa jornada. Con este ajuste, P1 baja a 33.3
    (100/3) y P2 se queda en 58.3 (58.3/1): gana P2, como deberia.

    Esto NO impide meter deliberadamente un triple/doble en el Elige8 -esa
    sigue siendo una decision valida (pagar mas por garantizar un partido
    muy incierto), solo evita que el sistema lo recomiende por defecto sin
    que se haya elegido a proposito."""
    return round(probabilidad_acierto_elige8(partido) / multiplicador_signo(signos_jugados(partido)), 3)


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
        "importe_quiniela": round(max(apuestas * PRECIO_APUESTA, IMPORTE_MINIMO), 2),
        "importe_elige8": round(apuestas_elige8 * PRECIO_ELIGE8, 2),
        "importe_total": round(max(apuestas * PRECIO_APUESTA, IMPORTE_MINIMO) + apuestas_elige8 * PRECIO_ELIGE8, 2),
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
    eficiencia = eficiencia_elige8(partido)
    return {
        "num": int(partido.get("num", 0) or 0),
        "partido": f"{partido.get('local', '')} - {partido.get('visitante', '')}",
        "signo_final": signos,
        "tipo_cobertura": tipo,
        "signo_mas_probable": signo_top(probs),
        "probabilidad_top": round(prob_top(probs), 2),
        "probabilidad_acierto": round(prob_acierto, 3),
        "probabilidad_cubierta": round(prob_acierto, 3),
        "eficiencia_elige8": eficiencia,
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
        -float(item.get("eficiencia_elige8") or 0.0),
        float(item.get("incertidumbre") or 0.0),
        float(item.get("probabilidad_sorpresa") or 0.0),
        float(item.get("indice_sorpresa_quinielistica") or 0.0),
        -float(item.get("margen") or 0.0),
        int(item.get("num") or 0),
    )


def clave_ranking_maxima_seguridad(item):
    """Ordena por probabilidad real de acierto CRUDA, sin descontar el
    coste extra de doble/triple -la alternativa "pago lo que haga falta por
    la mayor probabilidad posible" que pide Marc, frente al modo
    'economico' (eficiencia_elige8, probabilidad por euro). Puede elegir
    dobles/triples si su cobertura combinada compensa, aunque cuesten mas."""
    return (
        -float(item.get("probabilidad_acierto") or 0.0),
        float(item.get("incertidumbre") or 0.0),
        float(item.get("probabilidad_sorpresa") or 0.0),
        int(item.get("num") or 0),
    )


def probabilidad_conjunta_estimada(ranking, seleccionados_nums):
    """Estimacion de la probabilidad de acertar los 8 seleccionados a la
    vez -asume independencia entre partidos (aproximacion estandar, la
    correlacion real entre resultados de ligas distintas es minima).
    Sirve para comparar modos, no como probabilidad exacta."""
    producto = 1.0
    for item in ranking:
        if item["num"] in seleccionados_nums:
            producto *= max(float(item.get("probabilidad_acierto") or 0.0), 0.0) / 100.0
    return round(producto * 100, 4)


def construir_aviso_modos(ranking, seleccion_economico, seleccion_seguridad, coste_economico, coste_seguridad, tipo_jornada):
    """Aviso explicito comparando ambos modos -solo si de verdad difieren
    (si no hay ningun doble/triple en la jornada, las 2 selecciones
    coinciden y no hace falta avisar de nada). Incluye una estimacion de
    valor esperado en euros usando el premio TIPICO real segun el tipo de
    jornada (domestica vs internacional, ver PREMIO_TIPICO_ELIGE8) -es una
    estimacion basada en la mediana historica, no una prediccion exacta del
    premio real de esta semana concreta (el premio real depende de cuantos
    acierten, algo que no se puede saber de antemano)."""
    if seleccion_economico == seleccion_seguridad:
        return None

    prob_economico = probabilidad_conjunta_estimada(ranking, seleccion_economico)
    prob_seguridad = probabilidad_conjunta_estimada(ranking, seleccion_seguridad)
    extra_coste = round(coste_seguridad - coste_economico, 2)
    extra_prob = round(prob_seguridad - prob_economico, 2)

    premio_tipico = PREMIO_TIPICO_ELIGE8[tipo_jornada]
    valor_esperado_economico = round(prob_economico / 100 * premio_tipico, 2)
    valor_esperado_seguridad = round(prob_seguridad / 100 * premio_tipico, 2)
    extra_valor_esperado = round(valor_esperado_seguridad - valor_esperado_economico, 2)
    compensa = extra_valor_esperado > extra_coste

    evaluacion_por_num = {item["num"]: item for item in ranking}
    eslabon_debil = min(
        (evaluacion_por_num[n] for n in seleccion_economico),
        key=lambda item: float(item.get("probabilidad_acierto") or 0.0),
    )

    return {
        "eslabon_mas_debil_economico": {
            "num": eslabon_debil["num"],
            "partido": eslabon_debil["partido"],
            "probabilidad_acierto": eslabon_debil["probabilidad_acierto"],
        },
        "probabilidad_conjunta_economico": prob_economico,
        "probabilidad_conjunta_maxima_seguridad": prob_seguridad,
        "extra_coste_elige8": extra_coste,
        "extra_probabilidad_conjunta": extra_prob,
        "tipo_jornada": tipo_jornada,
        "premio_tipico_elige8": premio_tipico,
        "valor_esperado_economico": valor_esperado_economico,
        "valor_esperado_maxima_seguridad": valor_esperado_seguridad,
        "extra_valor_esperado": extra_valor_esperado,
        "compensa_pagar_mas": compensa,
        "mensaje": (
            f"Modo economico: {prob_economico:.1f}% de probabilidad conjunta estimada de acertar los 8 "
            f"(eslabon mas debil: P{eslabon_debil['num']} {eslabon_debil['partido']} al {eslabon_debil['probabilidad_acierto']:.1f}%). "
            f"Modo maxima seguridad: {prob_seguridad:.1f}% pagando {extra_coste:+.2f}€ mas de Elige8. "
            f"Jornada {tipo_jornada} (premio tipico Elige8 ≈{premio_tipico:.2f}€ segun mediana historica real): "
            f"valor esperado extra ≈{extra_valor_esperado:+.2f}€ por {extra_coste:+.2f}€ de coste extra -"
            f"{'SI compensa en valor esperado' if compensa else 'NO compensa en valor esperado'} "
            "(estimacion basada en la mediana historica de esta temporada, no una prediccion del premio real de esta semana)."
        ),
    }


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
        "version": "2.3",
        "generado_en": ahora(),
        "modo": "economico",
        "modo_real": "probabilidad_real_de_acierto_por_coste",
        "regla_activa": REGLA_ELIGE8,
        "recomendado": len(seleccionados_nums) == UMBRAL_PARTIDOS_SEGUROS,
        "seleccionados": sorted(seleccionados_nums),
        "ranking": ranking_con_flags,
        "rendimiento": metricas_historicas_modos(),
    }


def coste_elige8_seleccion(ranking, seleccionados_nums):
    signos = [item["signo_final"] for item in ranking if item["num"] in seleccionados_nums]
    apuestas = multiplicador(signos)
    return apuestas, round(apuestas * PRECIO_ELIGE8, 2)


def aplicar_elige8_seguro(prediccion):
    if prediccion_bloqueada(prediccion):
        return limpiar_elige8_bloqueado(prediccion)

    partidos = [p for p in prediccion.get("partidos", []) if int(p.get("num", 0) or 0) <= 14]
    if len(partidos) < UMBRAL_PARTIDOS_SEGUROS:
        return False

    evaluaciones = [evaluar_seguridad_elige8(p) for p in partidos]
    ranking = sorted(evaluaciones, key=clave_ranking_elige8)
    seleccionados_nums = {item["num"] for item in ranking[:UMBRAL_PARTIDOS_SEGUROS]}
    posicion_por_num = {item["num"]: idx for idx, item in enumerate(ranking, start=1)}
    evaluacion_por_num = {item["num"]: item for item in ranking}

    # Modo alternativo "maxima seguridad": mismo ranking de partidos, pero
    # ordenado por probabilidad real cruda -si un doble/triple compensa de
    # verdad su coste extra, aqui es donde aparece como alternativa real,
    # no automatica (igual que boleto_millonario: se ofrecen las 2, decide Marc).
    ranking_seguridad = sorted(evaluaciones, key=clave_ranking_maxima_seguridad)
    seleccionados_seguridad = {item["num"] for item in ranking_seguridad[:UMBRAL_PARTIDOS_SEGUROS]}

    apuestas_economico, coste_economico = coste_elige8_seleccion(ranking, seleccionados_nums)
    apuestas_seguridad, coste_seguridad = coste_elige8_seleccion(ranking, seleccionados_seguridad)
    tipo_jornada = tipo_jornada_elige8(partidos)
    aviso = construir_aviso_modos(
        ranking, seleccionados_nums, seleccionados_seguridad, coste_economico, coste_seguridad, tipo_jornada,
    )

    for partido in partidos:
        num = int(partido.get("num", 0) or 0)
        evaluacion = evaluacion_por_num.get(num, {})
        elegido = num in seleccionados_nums
        prob_acierto = evaluacion.get("probabilidad_acierto", 0.0)
        partido["elige8"] = elegido
        partido["en_elige8"] = elegido
        partido["elige8_modo"] = "economico"
        partido["elige8_modo_real"] = "probabilidad_real_de_acierto_por_coste"
        partido["probabilidad_acierto_elige8"] = prob_acierto
        partido["elige8_probabilidad_acierto"] = prob_acierto
        partido["elige8_probabilidad_cubierta"] = evaluacion.get("probabilidad_cubierta", 0.0)
        partido["elige8_eficiencia"] = evaluacion.get("eficiencia_elige8")
        partido["elige8_seguro_score"] = evaluacion.get("score_seguridad")
        partido["elige8_confianza_real"] = evaluacion.get("confianza_real")
        partido["elige8_tipo_cobertura"] = evaluacion.get("tipo_cobertura")
        partido["elige8_seguro_posicion"] = posicion_por_num.get(num)
        partido["elige8_seguro_cumple_umbral"] = True
        partido["elige8_seguro_probabilidad_top"] = evaluacion.get("probabilidad_top")
        partido["elige8_seguro_margen"] = evaluacion.get("margen")
        partido["elige8_maxima_seguridad"] = num in seleccionados_seguridad
        if elegido:
            partido["elige8_criterio"] = "Entra en Elige 8 por ranking de probabilidad real de acierto por coste (economico)."
        else:
            partido.pop("elige8_criterio", None)

    resumen = construir_resumen(ranking, seleccionados_nums)
    prediccion["elige8_seguro"] = resumen
    prediccion["elige8_modos"] = {
        "version": "2.3",
        "generado_en": ahora(),
        "modo_activo": "economico",
        "regla_activa": REGLA_ELIGE8,
        "modos": {
            "economico": {
                "seleccionados": sorted(seleccionados_nums),
                "ranking": resumen["ranking"],
                "apuestas_elige8": apuestas_economico,
                "importe_elige8": coste_economico,
            },
            "maxima_seguridad": {
                "seleccionados": sorted(seleccionados_seguridad),
                "ranking": [dict(item, seleccionado=item["num"] in seleccionados_seguridad) for item in ranking_seguridad],
                "apuestas_elige8": apuestas_seguridad,
                "importe_elige8": coste_seguridad,
            },
        },
        "aviso": aviso,
        "rendimiento": resumen["rendimiento"],
    }
    config = prediccion.setdefault("configuracion", {})
    config["elige8"] = True
    config["elige8_modo"] = "economico"
    config["elige8_modo_real"] = "probabilidad_real_de_acierto_por_coste"
    config["elige8_modos_disponibles"] = ["economico", "maxima_seguridad"]
    config["elige8_recomendado"] = True
    resumen_pred = prediccion.setdefault("resumen", {})
    resumen_pred["elige8_seleccionados"] = UMBRAL_PARTIDOS_SEGUROS
    resumen_pred["elige8_seguro_recomendado"] = True
    resumen_pred["elige8_regla"] = "probabilidad_real_de_acierto_por_coste"
    if aviso:
        resumen_pred["elige8_aviso"] = aviso["mensaje"]
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
