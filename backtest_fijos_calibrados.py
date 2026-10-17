"""Backtest prerregistrado de la COLOCACION calibrada de dobles/triples
("fijos calibrados") ANTES de encender el flag (17/10/2026).

Pregunta: si la prioridad de cobertura (prioridad_triple/prioridad_doble del
motor) hubiera visto al favorito corregido a su tasa REAL de acierto por
banda (rps_calibracion.calibracion_favorito), con el MISMO presupuesto que
Marc jugo de verdad cada jornada, ¿el boleto habria cubierto mas signos
acertados?

Datos, todos sin fuga de futuro:
- probabilidades y prioridades crudas: snapshots INMUTABLES de
  data/backtesting/pre_cierre (congelados antes de cada cierre; patron del
  TEST B del boleto EV y del backtest de La Valiente);
- tabla de calibracion del favorito: reconstruida WALK-FORWARD para cada
  jornada N solo con revisiones de jornadas cerradas ANTES de N
  (cronologicamente: las de la temporada anterior -numeracion alta, la
  numeracion se reinicia- mas las 26/27 con numero < N), con el mismo freno
  de muestra n>=30 por banda que usara el motor;
- presupuesto por jornada: la estructura REALMENTE jugada
  (data/quinielas_jugadas.json, solo lectura): mismos contadores de dobles y
  triples para la variante cruda y la calibrada;
- signos oficiales: data/jornadas/jornada_N.json (solo aportan el resultado,
  que es justo lo que se evalua).

CAVEAT honesto (documentado tambien en DECISION_LOG.md): las revisiones de
revisiones_prediccion_resultado.json toman probabilidades_usadas del espejo
data/predicciones/jornada_N.json, la misma fuente con la que se construyo la
tabla de produccion; el walk-forward corta por jornada, que es el patron
estandar de la casa, pero no re-congela ese espejo commit a commit.

METODO de puntuacion calibrada: para cada partido se reconstruye el dict que
consumen las funciones REALES del motor (probabilidades, incertidumbre,
mercado, contexto competitivo del propio snapshot, indice de sorpresa...) y
la puntuacion calibrada = prioridad_exportada_cruda + (prioridad del motor
con _probs_cobertura - prioridad del motor sin el). Asi cualquier campo que
la reconstruccion no capture bien se CANCELA en la resta, y de propina se
mide cuanto se desvia la reconstruccion cruda de lo exportado (sanity).

UMBRAL PRERREGISTRADO (escrito en DECISION_LOG.md 2026-10-17 ANTES de ver
ningun resultado): la colocacion calibrada debe (a) cubrir en el acumulado
AL MENOS los mismos signos acertados que la cruda y (b) ganar >=1 acierto
neto acumulado. Si no cumple ambas, USAR_CALIBRACION_EN_COBERTURA se queda
en False y el experimento queda documentado (patron vetos v2 de La Valiente).
"""
import sys
from collections import defaultdict
from pathlib import Path

from actualizar_porcentajes_lae import ruta_porcentajes, temporada_etiqueta
from aprendizaje_modulos import (
    fixture_jornada,
    jornada_cerrada,
    jornadas_cerradas_temporada,
    jugada_temporada,
    partidos_snapshot,
    snapshot_prediccion,
)
from datetime import datetime
from motor_prediccion_quiniela import (
    CALIBRACION_COBERTURA_N_MINIMO,
    buscar_contexto_competitivo,
    cargar_json,
    doble_top,
    prioridad_doble,
    prioridad_triple,
    probs_calibradas_cobertura,
    puntos_calibracion_favorito,
    signo_top,
)
from optimizador_ev_premio import guardar_json

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
REVISIONES = DATA / "memoria_ia" / "revisiones_prediccion_resultado.json"
SALIDA = DATA / "memoria_ia" / "backtest_fijos_calibrados.json"
PRE_CIERRE = DATA / "backtesting" / "pre_cierre"

SIGNOS = ("1", "X", "2")

UMBRAL_PRERREGISTRADO = (
    "Acumulado calibrado >= acumulado crudo Y mejora neta >= +1 signo "
    "acertado cubierto. Si no cumple ambas: flag OFF y experimento documentado."
)


def _signos_de(texto):
    return "".join(s for s in SIGNOS if s in str(texto or "").upper())


def estructura_jugada(signos_jugados):
    """(dobles, triples) de la estructura realmente jugada."""
    dobles = sum(1 for s in signos_jugados if len(_signos_de(s)) == 2)
    triples = sum(1 for s in signos_jugados if len(_signos_de(s)) == 3)
    return dobles, triples


def jornadas_temporada_actual(etiqueta, hasta=60):
    """Numeros de jornada que pertenecen a ESTA temporada (tienen % LAE
    versionados bajo su etiqueta). Todo lo demas en las revisiones es de
    temporadas anteriores, es decir, pasado seguro para cualquier N."""
    return {j for j in range(1, hasta + 1) if ruta_porcentajes(j, etiqueta).exists()}


def bandas_walk_forward(revisiones, jornada_limite, jornadas_actuales):
    """Tabla calibracion_favorito reconstruida SOLO con revisiones anteriores
    a jornada_limite (misma agregacion por bandas que
    generar_artefactos_compuerta_aprendizaje.construir_bloque_rps_calibracion)."""
    bandas = defaultdict(lambda: {"n": 0, "suma_prob": 0.0, "aciertos": 0})
    for item in revisiones:
        j = item.get("jornada")
        if not isinstance(j, int):
            continue
        if j in jornadas_actuales and j >= jornada_limite:
            continue  # presente o futuro de la temporada actual: fuera
        probs = item.get("probabilidades_usadas") or {}
        try:
            valores = {s: float(probs[s]) for s in SIGNOS}
        except (KeyError, TypeError, ValueError):
            continue
        real = str(item.get("signo_real") or "").upper()
        if real not in SIGNOS:
            continue
        favorito = max(SIGNOS, key=lambda s: valores[s])
        p_fav = valores[favorito]
        banda = f"{int(p_fav // 10) * 10}-{int(p_fav // 10) * 10 + 10}"
        registro = bandas[banda]
        registro["n"] += 1
        registro["suma_prob"] += p_fav
        registro["aciertos"] += 1 if real == favorito else 0
    return {
        banda: {
            "n": v["n"],
            "prob_media": round(v["suma_prob"] / v["n"], 1),
            "acierto_real_pct": round(100.0 * v["aciertos"] / v["n"], 1),
        }
        for banda, v in sorted(bandas.items())
        if v["n"]
    }


def partido_para_prioridad(p_snap, contexto_competitivo):
    """Dict minimo con los campos que leen prioridad_cobertura/doble/triple,
    reconstruido del snapshot pre-cierre (el contexto competitivo viene del
    propio snapshot, congelado pre-cierre)."""
    return {
        "num": p_snap.get("num"),
        "local": p_snap.get("local"),
        "visitante": p_snap.get("visitante"),
        "probabilidades": p_snap.get("probabilidades") or {},
        "incertidumbre": p_snap.get("incertidumbre") or 0,
        "riesgo_necesidad_real": bool(p_snap.get("riesgo_necesidad_real")),
        "mercado_losilla": p_snap.get("mercado_losilla") or {},
        "forzar_cobertura_motivacion": p_snap.get("forzar_cobertura_motivacion") or "",
        "contexto_competitivo_local": buscar_contexto_competitivo(
            contexto_competitivo, p_snap.get("local", "")
        ),
        "contexto_competitivo_visitante": buscar_contexto_competitivo(
            contexto_competitivo, p_snap.get("visitante", "")
        ),
        "_indice_sorpresa_quinielistica": {
            "indice": p_snap.get("indice_sorpresa_quinielistica") or 0,
            "favorito_atacable": bool(p_snap.get("favorito_atacable")),
            "cobertura_sugerida": p_snap.get("cobertura_sorpresa_sugerida") or "",
        },
    }


def asignar_cobertura(numeros, score_triple, score_doble, n_triples, n_dobles):
    """Reparte triples y dobles igual que predecir(): primero los N mejores
    por prioridad de triple, luego, entre los restantes, los M mejores por
    prioridad de doble (orden estable: empates los decide el numero)."""
    por_triple = sorted(numeros, key=lambda n: score_triple[n], reverse=True)
    triples_set = set(por_triple[:n_triples])
    por_doble = sorted(
        [n for n in numeros if n not in triples_set],
        key=lambda n: score_doble[n],
        reverse=True,
    )
    dobles_set = set(por_doble[:n_dobles])
    return triples_set, dobles_set


def signos_cubiertos(p_snap, num, triples_set, dobles_set):
    if num in triples_set:
        return "1X2"
    probs = p_snap.get("probabilidades") or {}
    if num in dobles_set:
        return doble_top(probs)
    return str(p_snap.get("signo_base") or signo_top(probs)).upper()


def evaluar_jornada(jornada, etiqueta, revisiones, jornadas_actuales,
                    datos_jugadas=None, dir_pre_cierre=None, dir_jornadas=None):
    """Una jornada cerrada: aciertos cubiertos con colocacion cruda (la
    exportada en el snapshot) vs calibrada, mismo presupuesto real jugado."""
    fixture = fixture_jornada(jornada, dir_jornadas)
    if not jornada_cerrada(fixture):
        return {"estado": "sin_cerrar"}
    jugada = jugada_temporada(jornada, etiqueta, datos_jugadas)
    if not jugada:
        return {"estado": "sin_jugada_real"}
    prediccion = snapshot_prediccion(jornada, dir_pre_cierre)
    partidos = partidos_snapshot(prediccion)
    if len(partidos) != 14:
        return {"estado": "sin_snapshot"}
    if any(p.get("prioridad_cobertura_triple") is None or p.get("prioridad_cobertura_doble") is None
           for p in partidos):
        return {"estado": "sin_prioridades", "motivo": "snapshot de un motor anterior al 06/09/2026"}

    n_dobles, n_triples = estructura_jugada(jugada)
    bandas = bandas_walk_forward(revisiones, jornada, jornadas_actuales)
    puntos = puntos_calibracion_favorito(bandas)
    contexto = prediccion.get("contexto_competitivo") or {}

    numeros = [p["num"] for p in partidos]
    por_num = {p["num"]: p for p in partidos}
    crudo_t, crudo_d, cal_t, cal_d = {}, {}, {}, {}
    desvio_max = 0.0
    for p in partidos:
        base = partido_para_prioridad(p, contexto)
        t0, d0 = prioridad_triple(base), prioridad_doble(base)
        base["_probs_cobertura"] = probs_calibradas_cobertura(base["probabilidades"], puntos)
        t1, d1 = prioridad_triple(base), prioridad_doble(base)
        num = p["num"]
        crudo_t[num] = float(p["prioridad_cobertura_triple"])
        crudo_d[num] = float(p["prioridad_cobertura_doble"])
        # la calibrada = exportada + delta: lo que la reconstruccion no capte
        # igual en ambas pasadas se cancela en la resta
        cal_t[num] = crudo_t[num] + (t1 - t0)
        cal_d[num] = crudo_d[num] + (d1 - d0)
        desvio_max = max(desvio_max, abs(t0 - crudo_t[num]), abs(d0 - crudo_d[num]))

    resultados = {}
    detalle_variantes = {}
    for variante, (st, sd) in (("crudo", (crudo_t, crudo_d)), ("calibrado", (cal_t, cal_d))):
        triples_set, dobles_set = asignar_cobertura(numeros, st, sd, n_triples, n_dobles)
        aciertos = 0
        cobertura = {}
        for num in numeros:
            cubiertos = signos_cubiertos(por_num[num], num, triples_set, dobles_set)
            oficial = (fixture.get(num) or {}).get("signo_oficial")
            cobertura[num] = cubiertos
            if oficial in SIGNOS and oficial in cubiertos:
                aciertos += 1
        resultados[variante] = aciertos
        detalle_variantes[variante] = cobertura

    cambios = [
        {
            "num": num,
            "partido": f"{por_num[num].get('local', '')} - {por_num[num].get('visitante', '')}",
            "crudo": detalle_variantes["crudo"][num],
            "calibrado": detalle_variantes["calibrado"][num],
            "signo_oficial": (fixture.get(num) or {}).get("signo_oficial"),
        }
        for num in numeros
        if detalle_variantes["crudo"][num] != detalle_variantes["calibrado"][num]
    ]
    return {
        "estado": "ok",
        "dobles": n_dobles,
        "triples": n_triples,
        "bandas_validas_walk_forward": [
            b for b, v in bandas.items() if v["n"] >= CALIBRACION_COBERTURA_N_MINIMO
        ],
        "aciertos_cubiertos_crudo": resultados["crudo"],
        "aciertos_cubiertos_calibrado": resultados["calibrado"],
        "cambios_de_colocacion": cambios,
        "desvio_max_reconstruccion_vs_exportado": round(desvio_max, 2),
    }


def ejecutar(etiqueta=None):
    etiqueta = etiqueta or temporada_etiqueta(datetime.now())
    revisiones = (cargar_json(REVISIONES, {}) or {}).get("revisiones") or []
    jornadas_actuales = jornadas_temporada_actual(etiqueta)
    datos_jugadas = cargar_json(DATA / "quinielas_jugadas.json", {})
    cerradas = jornadas_cerradas_temporada(etiqueta)

    jornadas = {}
    total_crudo = total_calibrado = evaluadas = 0
    for j in cerradas:
        fila = evaluar_jornada(j, etiqueta, revisiones, jornadas_actuales, datos_jugadas)
        jornadas[str(j)] = fila
        if fila.get("estado") == "ok":
            evaluadas += 1
            total_crudo += fila["aciertos_cubiertos_crudo"]
            total_calibrado += fila["aciertos_cubiertos_calibrado"]

    mejora = total_calibrado - total_crudo
    cumple = total_calibrado >= total_crudo and mejora >= 1
    resultado = {
        "version": 1,
        "generado_en": datetime.now().isoformat(),
        "temporada": etiqueta,
        "descripcion": (
            "Backtest prerregistrado de colocacion de dobles/triples con el favorito "
            "corregido a su tasa real de banda (walk-forward, presupuesto real jugado "
            "por jornada, snapshots pre-cierre inmutables). Decide el flag "
            "USAR_CALIBRACION_EN_COBERTURA del motor."
        ),
        "umbral_prerregistrado": UMBRAL_PRERREGISTRADO,
        "jornadas": jornadas,
        "resumen": {
            "jornadas_evaluadas": evaluadas,
            "aciertos_cubiertos_crudo": total_crudo,
            "aciertos_cubiertos_calibrado": total_calibrado,
            "mejora_neta": mejora,
            "cumple_umbral": cumple,
            "decision": (
                "ACTIVAR (USAR_CALIBRACION_EN_COBERTURA = True)" if cumple
                else "NO ACTIVAR: flag en False, experimento documentado"
            ),
        },
    }
    guardar_json(SALIDA, resultado)
    return resultado


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    resultado = ejecutar()
    resumen = resultado["resumen"]
    print(
        f"Backtest fijos calibrados ({resumen['jornadas_evaluadas']} jornadas): "
        f"cubiertos crudo {resumen['aciertos_cubiertos_crudo']} vs calibrado "
        f"{resumen['aciertos_cubiertos_calibrado']} (mejora {resumen['mejora_neta']:+d})."
    )
    print(f"Umbral prerregistrado: {resultado['umbral_prerregistrado']}")
    print(f"Decision: {resumen['decision']}")
    for j, fila in sorted(resultado["jornadas"].items(), key=lambda kv: int(kv[0])):
        if fila.get("estado") != "ok":
            print(f"  J{j}: {fila.get('estado')} {fila.get('motivo', '')}")
            continue
        print(
            f"  J{j} ({fila['dobles']}D+{fila['triples']}T): crudo {fila['aciertos_cubiertos_crudo']} "
            f"vs calibrado {fila['aciertos_cubiertos_calibrado']} · bandas {fila['bandas_validas_walk_forward']} "
            f"· cambios {len(fila['cambios_de_colocacion'])} · desvio_reconstruccion {fila['desvio_max_reconstruccion_vs_exportado']}"
        )


if __name__ == "__main__":
    main()
