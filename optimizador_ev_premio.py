"""Optimizador del EV DEL PREMIO (candidato 3, estilo pena Q84).

El motor y la recomendacion conservadora maximizan P(aciertos); este script
maximiza E[euros]: como el reparto de La Quiniela es pari-mutuel, una columna
rara que acierta cobra mucho mas que una columna que comparte signos con la
masa. Usa:

- probabilidad real por partido = mezcla 50/50 del motor
  (ultima_prediccion.json) y del mercado Losilla (fuente_losilla.json),
- % de apostantes LAE por signo (data/memoria_ia/porcentajes_lae/...,
  capturado por actualizar_porcentajes_lae.py),
- el modelo de reparto validado contra escrutinios reales
  (modelo_reparto_quiniela.py).

Busca, con el MISMO presupuesto (nº de apuestas) que la recomendacion
publicada, la estructura de fijos/dobles/triples que maximiza el EV en euros
(hill-climbing multi-arranque sobre muestras Monte Carlo compartidas, con
semilla fija para que el resultado sea reproducible dentro del mismo ciclo).

Exporta el bloque "boleto_ev_premio" en ultima_prediccion.json SIN tocar la
recomendacion conservadora ni el boleto_millonario: es una tercera lectura,
informativa -jugar dinero real lo decide siempre Marc.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

from actualizar_porcentajes_lae import ruta_porcentajes, temporada_etiqueta, SALIDA_BASE
from modelo_reparto_quiniela import (
    EvaluadorEV,
    PRECIO_APUESTA,
    RECAUDACION_DEFECTO,
    SIGNOS,
    columnas_boleto,
    normalizar_probs,
)

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
PREDICCION = DATA / "predicciones" / "ultima_prediccion.json"
FUENTE_LOSILLA = DATA / "memoria_ia" / "fuente_losilla.json"
BACKTEST = DATA / "memoria_ia" / "backtest_ev_premio.json"
AJUSTES_AUTOMATICOS = DATA / "memoria_ia" / "ajustes_automaticos.json"

OPCIONES_SIGNOS = ("1", "X", "2", "1X", "12", "X2", "1X2")
# Dos conjuntos de muestras INDEPENDIENTES: uno para que el hill-climbing
# compare candidatos y otro (mas grande, semilla distinta) para el EV que se
# publica. Sin esta separacion, el EV publicado hereda el winner's curse del
# optimizador: el candidato elegido es el que tuvo suerte en SUS muestras.
N_MUESTRAS_SELECCION = 20000
N_MUESTRAS_FINAL = 60000
SEMILLA = 20261013
PESO_LOSILLA = 0.5  # mezcla motor+Losilla al 50%, la misma que usamos a mano


def cargar_json(path, defecto=None):
    if not path.exists():
        return defecto if defecto is not None else {}
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return defecto if defecto is not None else {}


def guardar_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def mezclar_probabilidades(prob_motor, prob_losilla, peso_losilla=PESO_LOSILLA):
    motor = normalizar_probs(prob_motor or {})
    if not prob_losilla:
        return motor
    losilla = normalizar_probs(prob_losilla)
    return {s: (1 - peso_losilla) * motor[s] + peso_losilla * losilla[s] for s in SIGNOS}


def probabilidades_losilla_por_numero(fuente_losilla, jornada):
    prob = (fuente_losilla or {}).get("probabilidades") or {}
    if prob.get("jornada") != jornada:
        return {}
    salida = {}
    for partido in prob.get("partidos") or []:
        numero = partido.get("numero")
        valores = partido.get("probabilidades_signo") or {}
        if isinstance(numero, int) and all(valores.get(s) is not None for s in SIGNOS):
            salida[numero] = {s: float(valores[s]) for s in SIGNOS}
    return salida


def porcentajes_masa(jornada, fuente_losilla):
    """% de apostantes LAE por partido: archivo versionado de la jornada o,
    de respaldo, la columna lae de fuente_losilla.json. None si no hay."""
    etiqueta = temporada_etiqueta(datetime.now())
    registro = cargar_json(ruta_porcentajes(jornada, etiqueta), {})
    partidos = {
        p.get("numero"): p.get("porcentajes")
        for p in registro.get("partidos") or []
        if isinstance(p.get("numero"), int) and p.get("porcentajes")
    }
    if len(partidos) >= 14:
        return partidos, f"porcentajes_lae/{etiqueta}/jornada_{jornada}.json"
    prob = (fuente_losilla or {}).get("probabilidades") or {}
    if prob.get("jornada") == jornada:
        partidos = {}
        for partido in prob.get("partidos") or []:
            numero = partido.get("numero")
            lae = (partido.get("fuentes_detalle") or {}).get("lae") or {}
            if isinstance(numero, int) and all(lae.get(s) is not None for s in SIGNOS):
                partidos[numero] = {s: float(lae[s]) for s in SIGNOS}
        if len(partidos) >= 14:
            return partidos, "fuente_losilla.json (columna LAE, sin versionar)"
    return None, None


def factor_acertantes_actual(ruta=None):
    """Factor de overdispersion de acertantes del meta-aprendizaje
    (aprendizaje_modulos.py, 15/10/2026): re-ajustado con cada escrutinio
    nuevo SOLO con >=10 escrutinios y acotado a [0,5x - 2x] (el clamp se
    repite en EvaluadorEV por si el JSON llegara corrupto). Devuelve
    (factor, descripcion_origen); 1.0 si aun no hay ajuste."""
    datos = cargar_json(Path(ruta) if ruta else AJUSTES_AUTOMATICOS, {})
    bloque = datos.get("factor_acertantes") or {}
    valor = bloque.get("valor")
    if not isinstance(valor, (int, float)) or valor <= 0:
        return 1.0, "sin ajuste (modelo original)"
    factor = min(max(float(valor), 0.5), 2.0)
    return factor, (
        f"meta-aprendizaje: mediana real/modelo sobre {bloque.get('celdas', '?')} celdas de "
        f"{bloque.get('escrutinios', '?')} escrutinios reales, acotado [0,5x-2x]"
    )


def recaudacion_estimada():
    """Media de las recaudaciones reales capturadas en la temporada actual;
    RECAUDACION_DEFECTO si aun no hay ningun escrutinio capturado."""
    etiqueta = temporada_etiqueta(datetime.now())
    carpeta = SALIDA_BASE / etiqueta
    valores = []
    if carpeta.exists():
        for path in carpeta.glob("jornada_*.json"):
            escrutinio = cargar_json(path, {}).get("escrutinio") or {}
            valor = escrutinio.get("recaudacion_eur")
            if isinstance(valor, (int, float)) and valor > 0:
                valores.append(float(valor))
    if valores:
        return round(sum(valores) / len(valores), 2), len(valores)
    return RECAUDACION_DEFECTO, 0


def optimizar_boleto(evaluador, boleto_inicial, presupuesto_apuestas,
                     boletos_arranque_extra=None):
    """Hill-climbing multi-arranque: desde cada boleto de partida, prueba en
    cada partido todas las opciones de signos (fijo/doble/triple) que quepan
    en el presupuesto y se queda el mejor cambio hasta que ninguno mejore.
    Muestras Monte Carlo compartidas -> comparaciones estables."""
    n = evaluador.n_partidos

    def ev(boleto):
        return evaluador.evaluar(boleto)["ev_eur"]

    arranques = [list(boleto_inicial)]
    for extra in boletos_arranque_extra or []:
        if columnas_boleto(extra) <= presupuesto_apuestas:
            arranques.append(list(extra))

    mejor_global, mejor_ev_global = None, float("-inf")
    for arranque in arranques:
        actual = list(arranque)
        ev_actual = ev(actual)
        mejorado = True
        while mejorado:
            mejorado = False
            mejor_cambio, mejor_ev = None, ev_actual
            for i in range(n):
                original = actual[i]
                base = columnas_boleto(actual) // max(columnas_boleto([original]), 1)
                for opcion in OPCIONES_SIGNOS:
                    if opcion == original:
                        continue
                    if base * columnas_boleto([opcion]) > presupuesto_apuestas:
                        continue
                    actual[i] = opcion
                    candidato_ev = ev(actual)
                    if candidato_ev > mejor_ev + 1e-9:
                        mejor_ev, mejor_cambio = candidato_ev, (i, opcion)
                actual[i] = original
            if mejor_cambio:
                actual[mejor_cambio[0]] = mejor_cambio[1]
                ev_actual = mejor_ev
                mejorado = True
        if ev_actual > mejor_ev_global:
            mejor_global, mejor_ev_global = actual, ev_actual
    return mejor_global


def advertencia_backtest():
    """Resumen honesto del ultimo backtest prerregistrado (TEST B): el EV
    maximiza euros de cola, y en la muestra corta de jornadas reales el
    boleto EV habria cobrado MENOS que lo jugado. El dato va en el propio
    bloque para que la web nunca lo venda sin su contexto."""
    datos = cargar_json(BACKTEST, {})
    test_b = datos.get("test_b_ev_walk_forward") or {}
    jornadas = test_b.get("jornadas_evaluadas")
    real = test_b.get("total_cobrado_real_eur")
    simulado = test_b.get("total_simulado_boleto_ev_eur")
    if not jornadas or real is None or simulado is None:
        return None
    return (
        f"Backtest 26/27 ({jornadas} jornadas cerradas): este optimizador habria cobrado "
        f"{simulado:.2f} EUR frente a los {real:.2f} EUR reales de lo jugado. Es una estrategia "
        "de cola (bote/categorias altas): pierde los premios pequenos frecuentes a cambio de "
        "premios raros y grandes que en una muestra corta no aparecen. Umbral prerregistrado de "
        f"sanidad (>=50% de lo real): {'cumplido' if test_b.get('pasa_umbral') else 'NO cumplido'}."
    )


def construir_bloque_no_disponible(motivo):
    return {
        "estado": "no_disponible",
        "motivo": motivo,
        "generado_en": datetime.now(timezone.utc).isoformat(),
    }


def calcular_bloque_ev(prediccion, fuente_losilla, n_muestras=N_MUESTRAS_SELECCION,
                       n_muestras_final=N_MUESTRAS_FINAL, semilla=SEMILLA,
                       recaudacion=None):
    """Nucleo puro (testeable): devuelve el bloque boleto_ev_premio."""
    jornada = prediccion.get("jornada")
    partidos = sorted(
        [p for p in prediccion.get("partidos") or []
         if isinstance(p.get("num"), int) and 1 <= p["num"] <= 14],
        key=lambda p: p["num"],
    )
    if len(partidos) != 14:
        return construir_bloque_no_disponible("La prediccion no tiene los 14 partidos.")
    if any(not p.get("probabilidades") for p in partidos):
        return construir_bloque_no_disponible("Partidos sin probabilidades del motor.")

    masa, fuente_masa = porcentajes_masa(jornada, fuente_losilla)
    if not masa:
        return construir_bloque_no_disponible(
            "Sin % de apostantes LAE para esta jornada (ejecutar "
            "actualizar_porcentajes_lae.py o crear el JSON manual)."
        )
    if any(p["num"] not in masa for p in partidos):
        return construir_bloque_no_disponible(
            "Los % de apostantes LAE no cubren los 14 partidos de la jornada."
        )

    losilla = probabilidades_losilla_por_numero(fuente_losilla, jornada)
    p_real = [
        mezclar_probabilidades(p.get("probabilidades"), losilla.get(p["num"]))
        for p in partidos
    ]
    pct_masa = [masa[p["num"]] for p in partidos]

    if recaudacion is None:
        recaudacion, n_escrutinios = recaudacion_estimada()
    else:
        n_escrutinios = None

    boleto_conservador = [
        str(p.get("signo_final") or p.get("signo_base") or "1").upper()
        for p in partidos
    ]
    presupuesto = int((prediccion.get("coste") or {}).get("apuestas") or 0)
    if presupuesto < 1:
        presupuesto = columnas_boleto(boleto_conservador)

    factor_acertantes, origen_factor = factor_acertantes_actual()
    evaluador = EvaluadorEV(p_real, pct_masa, recaudacion=recaudacion,
                            n_muestras=n_muestras, semilla=semilla,
                            factor_acertantes=factor_acertantes)

    # arranques alternativos: favoritos puros y señal de valor (prob/masa)
    arranque_favorito = [
        max(SIGNOS, key=lambda s: p_real[i][s]) for i in range(14)
    ]
    arranque_valor = [
        max(SIGNOS, key=lambda s: p_real[i][s] / max(normalizar_probs(pct_masa[i])[s], 1e-6))
        for i in range(14)
    ]
    boleto_ev = optimizar_boleto(
        evaluador,
        boleto_conservador if columnas_boleto(boleto_conservador) <= presupuesto
        else arranque_favorito,
        presupuesto,
        boletos_arranque_extra=[arranque_favorito, arranque_valor],
    )

    # EV publicado: muestras frescas e independientes de las de seleccion.
    evaluador_final = EvaluadorEV(p_real, pct_masa, recaudacion=recaudacion,
                                  n_muestras=n_muestras_final, semilla=semilla + 1,
                                  factor_acertantes=factor_acertantes)
    eval_ev = evaluador_final.evaluar(boleto_ev)
    eval_conservador = evaluador_final.evaluar(boleto_conservador)
    # Salvaguarda anti-ruido: si con muestras frescas el optimizado no supera
    # a la conservadora, el "boleto EV" ES la conservadora (0 cambios).
    if eval_ev["ev_eur"] < eval_conservador["ev_eur"]:
        boleto_ev = list(boleto_conservador)
        eval_ev = eval_conservador

    cambios = []
    for i, p in enumerate(partidos):
        conservador = boleto_conservador[i]
        nuevo = boleto_ev[i]
        if set(conservador) != set(nuevo):
            cambios.append({
                "num": p["num"],
                "local": p.get("local"),
                "visitante": p.get("visitante"),
                "signo_conservador": conservador,
                "signo_ev": nuevo,
            })

    apuestas = columnas_boleto(boleto_ev)
    return {
        "estado": "ok",
        "generado_en": datetime.now(timezone.utc).isoformat(),
        "jornada": jornada,
        "metodo": (
            "EV del premio (pari-mutuel): mezcla motor+Losilla 50/50 como probabilidad real, "
            "% apostantes LAE como masa, modelo de reparto validado con escrutinios reales, "
            f"hill-climbing multi-arranque sobre {n_muestras} muestras Monte Carlo (14 exacta) "
            f"y EV publicado sobre {n_muestras_final} muestras independientes (semillas fijas)."
        ),
        "fuente_masa": fuente_masa,
        "recaudacion_estimada_eur": recaudacion,
        "escrutinios_usados_para_recaudacion": n_escrutinios,
        "factor_acertantes": factor_acertantes,
        "factor_acertantes_origen": origen_factor,
        "presupuesto_apuestas": presupuesto,
        "apuestas": apuestas,
        "coste_eur": round(max(apuestas * PRECIO_APUESTA, 1.5), 2),
        "ev_premio_eur": round(eval_ev["ev_eur"], 2),
        "ev_por_categoria": {k: round(v, 3) for k, v in eval_ev["ev_por_categoria"].items()},
        "probabilidad_algun_premio": round(eval_ev["probabilidad_premio"], 4),
        "ev_boleto_conservador_eur": round(eval_conservador["ev_eur"], 2),
        "probabilidad_algun_premio_conservador": round(eval_conservador["probabilidad_premio"], 4),
        "partidos": [
            {
                "num": p["num"],
                "local": p.get("local"),
                "visitante": p.get("visitante"),
                "signo": boleto_ev[i],
                "es_cambio_ev": any(c["num"] == p["num"] for c in cambios),
            }
            for i, p in enumerate(partidos)
        ],
        "cambios_respecto_a_conservadora": cambios,
        "total_cambios": len(cambios),
        "resumen": (
            f"Boleto EV del premio: {len(cambios)} cambio(s) sobre la conservadora con el mismo "
            f"presupuesto ({apuestas} apuestas). EV estimado {eval_ev['ev_eur']:.2f} EUR/jornada "
            f"frente a {eval_conservador['ev_eur']:.2f} EUR de la conservadora. "
            "Es la lectura 'contra la masa' (premios mas grandes cuando acierta, acierta menos veces): "
            "informativa, NO sustituye a la recomendacion conservadora."
        ),
        "aviso": (
            "EV en euros solo de las categorias 10-14 (sin Pleno al 15 ni Elige 8). "
            "Jugar dinero real lo decide siempre Marc."
        ),
        "advertencia_backtest": advertencia_backtest(),
    }


def main():
    prediccion = cargar_json(PREDICCION, {})
    if not prediccion:
        print("Sin ultima_prediccion.json; nada que optimizar.")
        return
    if not prediccion.get("prediccion_disponible") or not prediccion.get("prediccion_permitida"):
        if prediccion.pop("boleto_ev_premio", None) is not None:
            guardar_json(PREDICCION, prediccion)
        print("Prediccion bloqueada o no disponible; boleto_ev_premio retirado.")
        return

    fuente_losilla = cargar_json(FUENTE_LOSILLA, {})
    bloque = calcular_bloque_ev(prediccion, fuente_losilla)
    prediccion["boleto_ev_premio"] = bloque
    guardar_json(PREDICCION, prediccion)

    # mantener coherente el espejo por jornada que escribe el motor
    jornada = prediccion.get("jornada")
    espejo = DATA / "predicciones" / f"jornada_{jornada}.json"
    if isinstance(jornada, int) and espejo.exists():
        datos_espejo = cargar_json(espejo, {})
        if datos_espejo.get("jornada") == jornada:
            datos_espejo["boleto_ev_premio"] = bloque
            guardar_json(espejo, datos_espejo)

    if bloque.get("estado") == "ok":
        print(bloque["resumen"])
    else:
        print(f"boleto_ev_premio no disponible: {bloque.get('motivo')}")


if __name__ == "__main__":
    main()
