"""Backtest retrospectivo del Tercero de Valor ANTES de desplegar (prerregistrado).

Reconstruye que chip habria publicado el criterio de tercero_valor.py en las
jornadas 26/27 disponibles con datos estrictamente pre-cierre:

- probabilidades del motor: snapshots INMUTABLES de data/backtesting/pre_cierre
  (los mismos del boleto EV y de La Valiente; congelados antes de cada cierre),
- % de apostantes LAE: data/memoria_ia/porcentajes_lae/2026_2027/ (reconstruidos
  de commits pre-cierre, ya auditados para el backtest del EV),
- calibracion por signo SIN FUGA DE FUTURO: en cada jornada J se RECONSTRUYE
  calibracion_por_signo con la misma formula que genera el artefacto vivo
  (calibracion_desde_registros replica construir_bloque_rps_calibracion),
  usando SOLO partidos evaluados ANTES de J: los de temporadas anteriores
  completas (jornadas fuera de la numeracion con % LAE 26/27 versionados) mas
  las jornadas 26/27 estrictamente anteriores a J. Si esa muestra queda por
  debajo del freno prerregistrado (100 partidos), la jornada se evalua con la
  probabilidad CRUDA y asi se registra -exactamente lo que habria hecho el
  criterio vivo con esa muestra.

CRITERIOS PRERREGISTRADOS (escritos antes de la primera ejecucion, calcados
del patron de La Valiente):
- VERDE: aciertos reales >= esperados (suma de probabilidades CALIBRADAS
  declaradas) y al menos 2 aciertos.
- ROJO: aciertos < 60% de lo esperado -> se despliega IGUALMENTE en sombra,
  pero con la advertencia roja visible en el bloque de la web y en
  DECISION_LOG.md (como el boleto EV).
- Entre medias: NEUTRO (sombra sin advertencia roja, muestra insuficiente).

El pago hipotetico es ilustrativo: 1 EUR por chip a cuota justa pari-mutuel
100/% masa. Se registra tambien la suma de probabilidades CRUDAS para dejar a
la vista cuanto corrige la calibracion (transparencia, no criterio).

Salida: data/memoria_ia/backtest_tercero_valor.json + resumen por pantalla.
"""
from datetime import datetime, timezone

from backtest_valiente import (
    APRENDIZAJE,
    ETIQUETA,
    fixture_jornada,
    masa_jornada,
    partidos_snapshot,
)
from optimizador_ev_premio import cargar_json, guardar_json
from senal_valiente import jornadas_con_porcentajes
from tercero_valor import (
    APUESTA_HIPOTETICA_EUR,
    BACKTEST as SALIDA,
    SIGNOS,
    calibracion_desde_registros,
    elegir_tercero_valor,
)

UMBRAL_VERDE_ACIERTOS_MIN = 2
UMBRAL_ROJO_FRACCION = 0.6


def registros_previos(detalle, jornadas_temporada, jornada_limite):
    """Partidos evaluados ANTES de jornada_limite: todo lo de temporadas
    anteriores (jornadas fuera del conjunto con % LAE 26/27 versionados, la
    misma convencion que sorpresas_por_equipo) + jornadas 26/27 < limite."""
    previos = []
    for it in detalle or []:
        jornada = it.get("jornada")
        if jornada in jornadas_temporada and not (
            isinstance(jornada, int) and jornada < jornada_limite
        ):
            continue
        previos.append(it)
    return previos


def evaluar_criterio():
    """Corre el criterio sobre las jornadas con % LAE versionados y devuelve
    (filas, resumen)."""
    detalle = (cargar_json(APRENDIZAJE, {}) or {}).get("detalle") or []
    jornadas = sorted(jornadas_con_porcentajes(ETIQUETA))
    filas = []
    for jornada in jornadas:
        fixture = fixture_jornada(jornada)
        if len(fixture) != 14:
            filas.append({"jornada": jornada, "estado": "fixture_incompleto"})
            continue
        partidos = partidos_snapshot(jornada, fixture)
        masa = masa_jornada(jornada)
        if len(partidos) != 14 or not masa:
            filas.append({"jornada": jornada, "estado": "sin_snapshot_o_masa"})
            continue
        calibracion = calibracion_desde_registros(
            registros_previos(detalle, set(jornadas), jornada)
        )
        chip, ranking = elegir_tercero_valor(partidos, masa, calibracion)
        base = {
            "jornada": jornada,
            "calibracion_metodo": calibracion["metodo"],
            "calibracion_n": calibracion["n"],
            "calibracion_factores": calibracion["factores"],
        }
        if chip is None:
            mejor = ranking[0] if ranking else None
            filas.append({
                **base,
                "estado": "sin_tercero",
                "mejor_descartado": {
                    "partido": f"{mejor['local']} - {mejor['visitante']}",
                    "signo": mejor["signo"],
                    "prob_calibrada": mejor["prob_calibrada"],
                    "masa_pct": mejor["masa_pct"],
                    "ventaja_sobre_masa": mejor["ventaja_sobre_masa"],
                } if mejor else None,
            })
            continue
        elegido = next(p for p in partidos if p["num"] == chip["num"])
        if not elegido["_fixture_ok"]:
            # el snapshot y el fixture no hablan del mismo partido: no se
            # puntua a ciegas (misma regla que el backtest de La Valiente)
            filas.append({
                **base,
                "estado": "nombres_no_casan_con_fixture",
                "num": chip["num"],
                "partido": f"{chip['local']} - {chip['visitante']}",
            })
            continue
        signo_real = fixture[chip["num"]]["signo_oficial"]
        if signo_real not in SIGNOS:
            filas.append({
                **base,
                "estado": "chip_pendiente",
                "num": chip["num"],
                "partido": f"{chip['local']} - {chip['visitante']}",
                "signo": chip["signo"],
                "prob_declarada": chip["prob_calibrada"],
                "prob_motor": chip["prob_motor"],
                "masa_pct": chip["masa_pct"],
            })
            continue
        acierto = signo_real == chip["signo"]
        masa_pct = float(chip["masa_pct"] or 0)
        filas.append({
            **base,
            "estado": "chip",
            "num": chip["num"],
            "partido": f"{chip['local']} - {chip['visitante']}",
            "signo": chip["signo"],
            "prob_declarada": chip["prob_calibrada"],
            "prob_motor": chip["prob_motor"],
            "masa_pct": chip["masa_pct"],
            "ventaja_sobre_masa": chip["ventaja_sobre_masa"],
            "signo_real": signo_real,
            "acierto": acierto,
            "pago_hipotetico_eur": round(100.0 / masa_pct * APUESTA_HIPOTETICA_EUR, 2)
            if acierto and masa_pct > 0 else 0.0,
        })

    chips = [f for f in filas if f.get("estado") == "chip"]
    aciertos = sum(1 for f in chips if f["acierto"])
    esperados = round(sum(float(f["prob_declarada"]) for f in chips) / 100.0, 2)
    esperados_crudos = round(sum(float(f["prob_motor"]) for f in chips) / 100.0, 2)
    cobrado = round(sum(f["pago_hipotetico_eur"] for f in chips), 2)
    if chips and aciertos >= esperados and aciertos >= UMBRAL_VERDE_ACIERTOS_MIN:
        veredicto = (
            "VERDE segun el prerregistro (aciertos >= esperados con >=2 aciertos): la señal "
            "merece la sombra, sigue sin merecer dinero."
        )
    elif not chips or aciertos < UMBRAL_ROJO_FRACCION * esperados:
        veredicto = (
            "ROJO segun el prerregistro (aciertos < 60% de lo esperado): se despliega en sombra "
            "igualmente, con esta advertencia visible."
        )
    else:
        veredicto = (
            "NEUTRO segun el prerregistro (entre el 60% y el 100% de lo esperado): sombra sin "
            "advertencia roja, muestra insuficiente para concluir."
        )
    resumen = {
        "jornadas_evaluadas": len([f for f in filas if f.get("estado") != "fixture_incompleto"]),
        "terceros": len(chips),
        "aciertos": aciertos,
        "esperados": esperados,
        "esperados_con_prob_cruda": esperados_crudos,
        "apostado_hipotetico_eur": round(len(chips) * APUESTA_HIPOTETICA_EUR, 2),
        "cobrado_hipotetico_eur": cobrado,
        "veredicto": veredicto,
    }
    return filas, resumen


def ejecutar_backtest():
    filas, resumen = evaluar_criterio()
    resultado = {
        "version": 1,
        "generado_en": datetime.now(timezone.utc).isoformat(),
        "descripcion": (
            "Backtest retrospectivo prerregistrado del Tercero de Valor en las jornadas "
            "26/27 disponibles, con snapshots pre-cierre inmutables, % LAE versionados y "
            "calibracion por signo RECONSTRUIDA por jornada sin fuga de futuro (solo "
            "partidos evaluados antes de cada jornada; con <100 la jornada se evalua con "
            "probabilidad cruda y asi queda registrado)."
        ),
        "criterios_prerregistrados": {
            "verde": "aciertos >= esperados (suma de prob CALIBRADAS declaradas) y aciertos >= 2",
            "rojo": "aciertos < 60% de esperados (se despliega en sombra con advertencia roja)",
            "neutro": "entre medias",
            "umbrales_chip": "prob calibrada >= 18% y ventaja sobre la masa >= 6 puntos",
            "calibracion": (
                "factor multiplicativo global por signo (frecuencia real / prob media de "
                "calibracion_por_signo), freno de muestra n>=100; ver docstring de "
                "tercero_valor.py"
            ),
        },
        "jornadas": filas,
        "resumen": resumen,
    }
    guardar_json(SALIDA, resultado)
    return resultado


def main():
    resultado = ejecutar_backtest()
    resumen = resultado["resumen"]
    print(
        f"Backtest Tercero de Valor: {resumen['terceros']} chips en "
        f"{resumen['jornadas_evaluadas']} jornadas; {resumen['aciertos']} aciertos vs "
        f"{resumen['esperados']} esperados (crudos: {resumen['esperados_con_prob_cruda']}); "
        f"pago hipotetico {resumen['cobrado_hipotetico_eur']} EUR sobre "
        f"{resumen['apostado_hipotetico_eur']} EUR apostados."
    )
    print(resumen["veredicto"])
    for fila in resultado["jornadas"]:
        if fila.get("estado") == "chip":
            print(
                f"  J{fila['jornada']}: {fila['partido']} -> {fila['signo']} "
                f"(calibrada {fila['prob_declarada']}%, motor {fila['prob_motor']}%, "
                f"masa {fila['masa_pct']}%) [{fila['calibracion_metodo']}, n={fila['calibracion_n']}] "
                f"real={fila['signo_real']} {'ACIERTO' if fila['acierto'] else 'fallo'}"
            )
        else:
            print(f"  J{fila['jornada']}: {fila.get('estado')}")


if __name__ == "__main__":
    main()
