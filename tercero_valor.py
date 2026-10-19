"""Tercero de Valor (modo sombra): el tercero mejor pagado de la jornada.

HALLAZGO QUE LO MOTIVA (20/10/2026, datos propios 26/27): el signo de MENOR
probabilidad del motor ("el tercero") salio 42 veces en 196 partidos -3 por
jornada de media y NINGUNA jornada con cero- cuando el modelo esperaba 44.
El motor esta bien calibrado EN CONJUNTO y no hay edge en predecir CUAL
tercero concreto cae (nadie lo logra: INVESTIGACION_SORPRESAS.md). La
monetizacion posible esta en el pari-mutuel: terceros que la masa juega muy
por debajo de su probabilidad calibrada pagan desproporcionado al caer (J14:
el 2 del Depor, 28% real vs 15% de masa, acertado).

ADVERTENCIA DE DISEÑO (por que probabilidad CALIBRADA y no cruda): el
selector ingenuo de maxima brecha modelo-vs-masa ya fue refutado en casa
(14/10/2026: 1/13 aciertos cuando declaraba 28%) porque cosechaba las
sobreestimaciones de X del propio motor -el error del MOTOR, no el de la
masa. Aqui la probabilidad del tercero se corrige por calibracion ANTES de
compararla con la masa.

CORRECCION DE CALIBRACION ELEGIDA (documentada y prerregistrada ANTES del
backtest): para signos NO favoritos no existe tabla por bandas (solo el
favorito la tiene: rps_calibracion.calibracion_favorito). Lo que si existe es
rps_calibracion.calibracion_por_signo (metricas_probabilisticas.json): el
sesgo GLOBAL por signo medido sobre todos los partidos evaluados (hoy n=250;
p. ej. la X se pronostica de media al 30,3% y sale el 22,0%). Se aplica un
factor MULTIPLICATIVO por signo:

    prob_calibrada = prob_cruda * (frecuencia_real_pct / prob_media_pronosticada)

Multiplicativo y no aditivo porque el sesgo esta medido en la media (~30
pts): restar 8,3 puntos planos a un tercero del 18% lo sobrecorrige (y puede
dar negativo); el factor conserva proporciones y positividad. DECLARACION
honesta: es calibracion global por signo, NO por bandas -no hay base
estadistica por tramos para no-favoritos-, y asi lo dice el propio bloque
publicado (calibracion.metodo y calibracion.declaracion). Freno de muestra
prerregistrado: con menos de CALIBRACION_N_MINIMO (100) partidos evaluados se
usa la probabilidad CRUDA y se DECLARA (metodo "cruda_sin_calibrar").

UMBRALES PRERREGISTRADOS (escritos ANTES del backtest; solo ajustables en
este prerregistro inicial, jamas tras ver resultados):
- tercero: el signo de MENOR probabilidad cruda del motor en cada partido
  (desempate exacto: el primero en el orden 1, X, 2).
- chip "Tercero de Valor": prob_calibrada >= 18% Y ventaja sobre la masa
  (prob_calibrada - % masa LAE del tercero) >= 6 puntos.
- ranking de los 14 terceros: ventaja desc; desempate por prob_calibrada
  desc y despues por numero de partido. El mejor clasificado QUE CUMPLE
  ambos umbrales es el chip (el UNICO que mide el marcador de sombra); se
  publica ademas el top-3 del ranking completo como informativo, cada uno
  con su flag cumple_umbrales. Si ninguno cumple -> estado
  "sin_tercero_valor" (declararlo es parte del diseño).

GRADUACION (marcador de sombra, data/memoria_ia/marcador_tercero_valor.json),
prerregistrada igual que La Valiente: con >=12 terceros evaluados, si
aciertos reales >= esperados (suma de prob_calibrada declaradas) Y aciertos
>= 3 -> "candidata_a_dinero" (avisar a Marc); si aciertos < 60% de esperados
-> "suspendida"; en otro caso sigue "en_sombra". El pago hipotetico es
ilustrativo: 1 EUR por chip a cuota justa pari-mutuel 100/% masa.

Exporta el bloque "tercero_valor" en ultima_prediccion.json SIN tocar la
recomendacion conservadora, el boleto millonario, el EV ni La Valiente.
Jugar dinero real lo decide siempre Marc: esto es un instrumento de la web,
no un protocolo impuesto.
"""
from datetime import datetime, timezone
from pathlib import Path

from actualizar_porcentajes_lae import temporada_etiqueta
from optimizador_ev_premio import cargar_json, guardar_json, porcentajes_masa
from senal_valiente import _signo_real_verificado

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
PREDICCION = DATA / "predicciones" / "ultima_prediccion.json"
FUENTE_LOSILLA = DATA / "memoria_ia" / "fuente_losilla.json"
METRICAS = DATA / "memoria_ia" / "metricas_probabilisticas.json"
MARCADOR = DATA / "memoria_ia" / "marcador_tercero_valor.json"
BACKTEST = DATA / "memoria_ia" / "backtest_tercero_valor.json"
JORNADAS_DIR = DATA / "jornadas"
PREDICCIONES_DIR = DATA / "predicciones"

SIGNOS = ("1", "X", "2")

# --- Umbrales prerregistrados (ver docstring; no tocar sin nuevo prerregistro) ---
PROB_CALIBRADA_MIN = 18.0
VENTAJA_MIN = 6.0
CALIBRACION_N_MINIMO = 100
TOP_INFORMATIVO = 3
GRADUACION_MIN_EVALUADOS = 12
GRADUACION_MIN_ACIERTOS = 3
SUSPENSION_FRACCION = 0.6
APUESTA_HIPOTETICA_EUR = 1.0

CRITERIO_GRADUACION = (
    f"Prerregistrado: con >={GRADUACION_MIN_EVALUADOS} terceros evaluados, si aciertos "
    f"reales >= esperados (suma de probabilidades CALIBRADAS declaradas) y aciertos >= "
    f"{GRADUACION_MIN_ACIERTOS} -> 'candidata_a_dinero' (avisar a Marc); si aciertos < "
    f"{int(SUSPENSION_FRACCION * 100)}% de lo esperado -> 'suspendida'; en otro caso "
    "sigue 'en_sombra'. El criterio no se cambia despues de ver los datos."
)

AVISO_SOMBRA = (
    "Experimental, MODO SOMBRA: se publica y se mide, pero no entra en ningun boleto "
    "hasta graduarse con el criterio prerregistrado del marcador. Jugar dinero real "
    "lo decide siempre Marc."
)

CRITERIO_CHIP = (
    "Se clasifican los 14 terceros (el signo de MENOR probabilidad del motor de cada "
    f"partido) por ventaja = prob CALIBRADA - % masa LAE. Chip: el mejor con prob "
    f"calibrada >= {PROB_CALIBRADA_MIN:.0f}% y ventaja >= {VENTAJA_MIN:.0f} puntos "
    "(umbrales prerregistrados antes del backtest). La calibracion corrige el sesgo "
    "global por signo del motor -la trampa del selector ingenuo refutado el 14/10/2026 "
    "era justo comparar la prob CRUDA con la masa. Solo el chip mide en el marcador; "
    "el top-3 es informativo."
)


# ---------------------------------------------------------------------------
# Calibracion por signo (no-favoritos): factor global declarado
# ---------------------------------------------------------------------------

def _declaracion(metodo, n):
    if metodo == "factor_global_por_signo":
        return (
            f"Prob calibrada = prob del motor x (frecuencia real / prob media) de su signo, "
            f"medido sobre {n} partidos evaluados (calibracion_por_signo de "
            "metricas_probabilisticas.json). Es calibracion GLOBAL por signo, no por bandas: "
            "para signos no-favoritos no existe tabla por bandas con base estadistica."
        )
    return (
        f"SIN CALIBRAR: menos de {CALIBRACION_N_MINIMO} partidos evaluados con "
        f"probabilidades ({n}), el freno de muestra prerregistrado. Se usa la probabilidad "
        "CRUDA del motor y se declara aqui, como exige el prerregistro."
    )


def _construir_calibracion(por_signo, n):
    """Estructura de calibracion a partir de la tabla por signo y su muestra.
    Con muestra insuficiente (o tabla rota) -> probabilidad cruda DECLARADA."""
    try:
        n = int(n or 0)
    except (TypeError, ValueError):
        n = 0
    factores = {}
    if n >= CALIBRACION_N_MINIMO:
        for s in SIGNOS:
            fila = (por_signo or {}).get(s) or {}
            try:
                media = float(fila.get("prob_media_pronosticada"))
                real = float(fila.get("frecuencia_real_pct"))
            except (TypeError, ValueError):
                factores = {}
                break
            if media <= 0:
                factores = {}
                break
            factores[s] = round(real / media, 4)
    if len(factores) == len(SIGNOS):
        return {
            "metodo": "factor_global_por_signo",
            "n": n,
            "factores": factores,
            "declaracion": _declaracion("factor_global_por_signo", n),
        }
    return {
        "metodo": "cruda_sin_calibrar",
        "n": n,
        "factores": None,
        "declaracion": _declaracion("cruda_sin_calibrar", n),
    }


def factores_calibracion(metricas=None):
    """Calibracion VIVA: leida del artefacto metricas_probabilisticas.json
    (que recalcula generar_artefactos_compuerta_aprendizaje.py en cada ciclo
    de aprendizaje con la formula replicada en calibracion_desde_registros)."""
    if metricas is None:
        metricas = cargar_json(METRICAS, {})
    rps = (metricas or {}).get("rps_calibracion") or {}
    return _construir_calibracion(
        rps.get("calibracion_por_signo"), rps.get("partidos_con_probabilidades")
    )


def calibracion_desde_registros(items):
    """Misma formula que construir_bloque_rps_calibracion (generar_artefactos
    _compuerta_aprendizaje.py) sobre una lista de partidos evaluados
    {probabilidades_usadas, signo_real}: la usa el backtest para reconstruir
    la calibracion SIN fuga de futuro (solo partidos anteriores a la jornada
    evaluada)."""
    evaluables = []
    for it in items or []:
        probs = it.get("probabilidades_usadas") or {}
        try:
            valores = [float(probs[s]) for s in SIGNOS]
        except (KeyError, TypeError, ValueError):
            continue
        if sum(valores) <= 0 or str(it.get("signo_real") or "").upper() not in SIGNOS:
            continue
        evaluables.append(it)
    n = len(evaluables)
    por_signo = {}
    if n:
        for s in SIGNOS:
            prob_media = sum(
                float((it.get("probabilidades_usadas") or {}).get(s) or 0)
                for it in evaluables
            ) / n
            frecuencia = 100.0 * sum(
                1 for it in evaluables if str(it.get("signo_real")).upper() == s
            ) / n
            por_signo[s] = {
                "prob_media_pronosticada": round(prob_media, 1),
                "frecuencia_real_pct": round(frecuencia, 1),
            }
    return _construir_calibracion(por_signo, n)


def prob_calibrada_tercero(prob, signo, calibracion):
    """Probabilidad calibrada del tercero: factor multiplicativo de su signo,
    acotada a [0, 100]. Sin factores (freno de muestra) -> la cruda tal cual."""
    try:
        prob = float(prob or 0)
    except (TypeError, ValueError):
        return 0.0
    factores = (calibracion or {}).get("factores") or {}
    factor = factores.get(signo)
    if factor is None:
        return round(prob, 1)
    return round(min(100.0, max(0.0, prob * float(factor))), 1)


# ---------------------------------------------------------------------------
# Ranking de terceros y eleccion del chip (nucleo puro, testeable)
# ---------------------------------------------------------------------------

def signo_tercero(probs):
    """El signo de MENOR probabilidad cruda del motor; en empate exacto, el
    primero en el orden 1, X, 2 (prerregistrado). None sin probabilidades."""
    try:
        valores = {s: float((probs or {}).get(s) or 0) for s in SIGNOS}
    except (TypeError, ValueError):
        return None
    if sum(valores.values()) <= 0:
        return None
    return min(SIGNOS, key=lambda s: valores[s])


def clasificar_terceros(partidos, masa, calibracion):
    """Los 14 terceros ordenados por ventaja (prob calibrada - % masa) desc;
    desempate por prob calibrada desc y despues por numero de partido.
    Partidos sin probabilidades o sin masa de su tercero quedan fuera."""
    filas = []
    for partido in partidos or []:
        probs = partido.get("probabilidades") or {}
        num = partido.get("num")
        signo = signo_tercero(probs)
        masa_partido = (masa or {}).get(num) or {}
        if signo is None or masa_partido.get(signo) is None:
            continue
        prob = float(probs.get(signo) or 0)
        p_cal = prob_calibrada_tercero(prob, signo, calibracion)
        masa_pct = round(float(masa_partido[signo]), 1)
        ventaja = round(p_cal - masa_pct, 1)
        filas.append({
            "num": num,
            "local": partido.get("local"),
            "visitante": partido.get("visitante"),
            "signo": signo,
            "prob_motor": round(prob, 1),
            "prob_calibrada": p_cal,
            "masa_pct": masa_pct,
            "ventaja_sobre_masa": ventaja,
            "cumple_umbrales": bool(
                p_cal >= PROB_CALIBRADA_MIN and ventaja >= VENTAJA_MIN
            ),
        })
    filas.sort(key=lambda f: (-f["ventaja_sobre_masa"], -f["prob_calibrada"], f["num"] or 99))
    return filas


def elegir_tercero_valor(partidos, masa, calibracion):
    """(chip, ranking): el chip es el mejor clasificado que cumple ambos
    umbrales prerregistrados; None si ninguno cumple."""
    filas = clasificar_terceros(partidos, masa, calibracion)
    chip = next((f for f in filas if f["cumple_umbrales"]), None)
    return chip, filas


def advertencia_backtest():
    """Resumen honesto del backtest retrospectivo prerregistrado, incrustado
    en el propio bloque para que la web nunca lo venda sin contexto (mismo
    patron que el boleto EV y La Valiente)."""
    datos = cargar_json(BACKTEST, {})
    resumen = datos.get("resumen") or {}
    n = resumen.get("terceros")
    aciertos = resumen.get("aciertos")
    esperados = resumen.get("esperados")
    if not n or aciertos is None or esperados is None:
        return None
    veredicto = resumen.get("veredicto") or ""
    return (
        f"Backtest retrospectivo 26/27 (criterio identico, calibracion reconstruida "
        f"sin fuga de futuro): {aciertos} acierto(s) en {n} chips cuando se esperaban "
        f"{esperados:.1f}. {veredicto} Muestra pequeña: por eso esta en modo sombra y "
        "no toca ningun boleto."
    )


def construir_bloque_no_disponible(motivo):
    return {
        "estado": "no_disponible",
        "modo": "sombra",
        "motivo": motivo,
        "generado_en": datetime.now(timezone.utc).isoformat(),
    }


def construir_bloque_tercero_valor(prediccion, fuente_losilla, calibracion=None):
    """Nucleo del bloque `tercero_valor` de ultima_prediccion.json (testeable)."""
    jornada = prediccion.get("jornada")
    partidos = sorted(
        [p for p in prediccion.get("partidos") or []
         if isinstance(p.get("num"), int) and 1 <= p["num"] <= 14],
        key=lambda p: p["num"],
    )
    if len(partidos) != 14 or any(not p.get("probabilidades") for p in partidos):
        return construir_bloque_no_disponible(
            "La prediccion no tiene los 14 partidos con probabilidades del motor."
        )
    masa, fuente_masa = porcentajes_masa(jornada, fuente_losilla)
    if not masa:
        return construir_bloque_no_disponible(
            "Sin % de apostantes LAE para esta jornada: sin masa no hay pari-mutuel que medir."
        )
    if calibracion is None:
        calibracion = factores_calibracion()
    chip, ranking = elegir_tercero_valor(partidos, masa, calibracion)
    top3 = [
        {"orden": i, "es_el_chip": bool(chip) and f["num"] == chip["num"], **f}
        for i, f in enumerate(ranking[:TOP_INFORMATIVO], start=1)
    ]
    base = {
        "modo": "sombra",
        "generado_en": datetime.now(timezone.utc).isoformat(),
        "jornada": jornada,
        "fuente_masa": fuente_masa,
        "calibracion": calibracion,
        "criterio": CRITERIO_CHIP,
        "aviso": AVISO_SOMBRA,
        "advertencia_backtest": advertencia_backtest(),
        "top3": top3,
    }
    if chip is None:
        return {
            **base,
            "estado": "sin_tercero_valor",
            "motivo": (
                "Ningun tercero cumple los umbrales prerregistrados esta jornada "
                f"(prob calibrada >= {PROB_CALIBRADA_MIN:.0f}% y ventaja >= "
                f"{VENTAJA_MIN:.0f} pts). No se fuerza: declararlo es parte del diseño."
            ),
        }
    masa_pct = float(chip["masa_pct"] or 0)
    return {
        **base,
        "estado": "ok",
        **chip,
        "pago_estimado_eur": round(100.0 / masa_pct * APUESTA_HIPOTETICA_EUR, 2)
        if masa_pct > 0 else None,
    }


# ---------------------------------------------------------------------------
# Marcador de sombra (se engancha al ciclo de aprendizaje)
# ---------------------------------------------------------------------------

def _resumen_marcador(terceros):
    evaluados = [t for t in terceros if t.get("acierto") in (True, False)]
    aciertos = sum(1 for t in evaluados if t["acierto"])
    esperados = round(sum(float(t.get("prob_declarada") or 0) for t in evaluados) / 100.0, 2)
    cobrado = round(sum(float(t.get("pago_hipotetico_eur") or 0) for t in evaluados), 2)
    estado = "en_sombra"
    if len(evaluados) >= GRADUACION_MIN_EVALUADOS:
        if aciertos >= esperados and aciertos >= GRADUACION_MIN_ACIERTOS:
            estado = "candidata_a_dinero"
        elif aciertos < SUSPENSION_FRACCION * esperados:
            estado = "suspendida"
    return {
        "evaluados": len(evaluados),
        "aciertos": aciertos,
        "esperados": esperados,
        "apostado_hipotetico_eur": round(len(evaluados) * APUESTA_HIPOTETICA_EUR, 2),
        "cobrado_hipotetico_eur": cobrado,
        "estado": estado,
        "avisar_a_marc": estado == "candidata_a_dinero",
    }


def actualizar_marcador_tercero_valor(dir_predicciones=None, dir_jornadas=None,
                                      ruta_marcador=None, etiqueta=None, ahora=None):
    """Al cerrar cada jornada, registra si el chip publicado acerto y
    actualiza el acumulado con el criterio de graduacion prerregistrado.
    Idempotente: cada (temporada, jornada) se registra una sola vez. La
    verificacion del signo real exige que al menos un nombre del fixture
    case (misma regla que La Valiente: la numeracion de jornadas se reinicia
    cada temporada)."""
    dir_predicciones = Path(dir_predicciones or PREDICCIONES_DIR)
    dir_jornadas = Path(dir_jornadas or JORNADAS_DIR)
    ruta_marcador = Path(ruta_marcador or MARCADOR)
    ahora = ahora or datetime.now(timezone.utc)
    etiqueta = etiqueta or temporada_etiqueta(datetime.now())

    marcador = cargar_json(ruta_marcador, {})
    terceros = marcador.get("terceros") or []
    registrados = {(t.get("temporada"), t.get("jornada")) for t in terceros}
    nuevos = 0
    for path in sorted(dir_predicciones.glob("jornada_*.json")):
        bloque = (cargar_json(path, {}) or {}).get("tercero_valor") or {}
        if bloque.get("estado") != "ok":
            continue
        jornada = bloque.get("jornada")
        if (etiqueta, jornada) in registrados:
            continue
        signo_real = _signo_real_verificado(bloque, dir_jornadas)
        if signo_real is None:
            continue  # jornada aun abierta o fixture de otra temporada
        acierto = signo_real == str(bloque.get("signo") or "").upper()
        masa = float(bloque.get("masa_pct") or 0)
        pago = round(100.0 / masa * APUESTA_HIPOTETICA_EUR, 2) if acierto and masa > 0 else 0.0
        terceros.append({
            "temporada": etiqueta,
            "jornada": jornada,
            "num": bloque.get("num"),
            "partido": f"{bloque.get('local')} - {bloque.get('visitante')}",
            "signo": bloque.get("signo"),
            # lo declarado (y lo que mide la graduacion) es la prob CALIBRADA
            "prob_declarada": bloque.get("prob_calibrada"),
            "prob_motor": bloque.get("prob_motor"),
            "masa_pct": bloque.get("masa_pct"),
            "calibracion_metodo": (bloque.get("calibracion") or {}).get("metodo"),
            "signo_real": signo_real,
            "acierto": acierto,
            "pago_hipotetico_eur": pago,
            "modo": "sombra",
            "registrado_en": ahora.isoformat(),
        })
        registrados.add((etiqueta, jornada))
        nuevos += 1

    resumen = _resumen_marcador(terceros)
    marcador = {
        "version": 1,
        "descripcion": (
            "Marcador de sombra del Tercero de Valor: el tercero mejor pagado por jornada "
            "(prob calibrada muy por encima del % de masa), publicado y medido sin dinero. "
            "El pago hipotetico es ilustrativo (1 EUR por chip a cuota justa pari-mutuel "
            "100/% masa)."
        ),
        "criterio_graduacion": CRITERIO_GRADUACION,
        "actualizado_en": ahora.isoformat(),
        "terceros": terceros,
        "resumen": resumen,
    }
    guardar_json(ruta_marcador, marcador)
    if resumen["avisar_a_marc"]:
        print(
            "TERCERO_VALOR_CANDIDATO_A_DINERO: el marcador de sombra cumple el criterio "
            f"prerregistrado ({resumen['aciertos']} aciertos vs {resumen['esperados']} esperados "
            f"en {resumen['evaluados']} chips). Avisar a Marc antes de tocar dinero."
        )
    return {"nuevos": nuevos, "resumen": resumen}


# ---------------------------------------------------------------------------
# Script de pipeline (patron senal_valiente / optimizador_ev_premio)
# ---------------------------------------------------------------------------

def main():
    prediccion = cargar_json(PREDICCION, {})
    if not prediccion:
        print("Sin ultima_prediccion.json; nada que clasificar.")
        return
    if not prediccion.get("prediccion_disponible") or not prediccion.get("prediccion_permitida"):
        if prediccion.pop("tercero_valor", None) is not None:
            guardar_json(PREDICCION, prediccion)
        print("Prediccion bloqueada o no disponible; bloque tercero_valor retirado.")
        return

    fuente_losilla = cargar_json(FUENTE_LOSILLA, {})
    bloque = construir_bloque_tercero_valor(prediccion, fuente_losilla)
    prediccion["tercero_valor"] = bloque
    guardar_json(PREDICCION, prediccion)

    # mantener coherente el espejo por jornada que escribe el motor
    jornada = prediccion.get("jornada")
    espejo = PREDICCIONES_DIR / f"jornada_{jornada}.json"
    if isinstance(jornada, int) and espejo.exists():
        datos_espejo = cargar_json(espejo, {})
        if datos_espejo.get("jornada") == jornada:
            datos_espejo["tercero_valor"] = bloque
            guardar_json(espejo, datos_espejo)

    if bloque.get("estado") == "ok":
        print(
            f"Tercero de Valor (sombra) J{jornada}: {bloque['local']} - {bloque['visitante']} -> "
            f"{bloque['signo']} ({bloque['prob_motor']}% motor, {bloque['prob_calibrada']}% "
            f"calibrada vs {bloque['masa_pct']}% masa; ventaja +{bloque['ventaja_sobre_masa']} pts)."
        )
    else:
        print(f"Tercero de Valor (sombra) J{jornada}: {bloque.get('estado')} - {bloque.get('motivo')}")


if __name__ == "__main__":
    main()
