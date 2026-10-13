"""Backtest del optimizador de EV del premio (candidato 3) ANTES de desplegar.

Metodo (estandar de la casa: validar antes de desplegar, sin fugas de futuro).
CRITERIOS PRERREGISTRADOS antes de ejecutar por primera vez:

TEST A - modelo de reparto vs escrutinios reales 26/27 (5+ jornadas):
  con los % de apostantes LAE pre-cierre y los resultados oficiales, el modelo
  (modelo_reparto_quiniela) predice acertantes y premio por categoria; se
  compara contra el escrutinio real capturado (acertantes/premios netos).
  UMBRAL: mediana del cociente acertantes_modelo/acertantes_real en [0,67; 1,5]
  sobre las celdas con >=10 acertantes reales (las de 0-9 son puro ruido
  Poisson). Si falla, el bloque EV no se publica en la web.

TEST B - EV walk-forward sobre jornadas cerradas 26/27 jugadas de verdad:
  para cada jornada con (a) snapshot pre-cierre INMUTABLE de la prediccion,
  (b) % LAE reconstruidos de commits pre-cierre, (c) jugada real registrada y
  (d) escrutinio real: se corre el optimizador con los datos que habia ANTES
  del cierre y el MISMO presupuesto (nº de columnas) que se jugo de verdad, y
  se calcula cuanto habria cobrado ese boleto con los resultados y el reparto
  reales (ajustando los acertantes por nuestras propias columnas). Se compara
  contra el premio realmente cobrado (historial_premios.json).
  UMBRAL (sanity, no de superioridad: con ~10 jornadas el EV+ de colas no es
  testeable): el acumulado simulado del boleto EV no debe quedar por debajo
  del 50% del acumulado real cobrado. La comparacion completa se documenta en
  DECISION_LOG.md sea cual sea el signo.

Recaudacion walk-forward en TEST B: media de los escrutinios de jornadas
ANTERIORES a la evaluada; si aun no hay, RECAUDACION_DEFECTO (parametro de
escala, unico dato no estrictamente pre-cierre; sesga igual a ambos boletos).

Salida: data/memoria_ia/backtest_ev_premio.json + resumen por pantalla.
"""
import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

from actualizar_porcentajes_lae import ruta_porcentajes, temporada_etiqueta
from modelo_reparto_quiniela import (
    CATEGORIAS,
    FRACCION_RECAUDACION,
    PREMIO_MINIMO_PAGADO,
    RECAUDACION_DEFECTO,
    EvaluadorEV,
    acertantes_esperados,
    columnas_boleto,
    distribucion_aciertos_masa,
    premio_categoria_modelo,
    premio_neto,
)
from optimizador_ev_premio import mezclar_probabilidades, optimizar_boleto

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
SALIDA = DATA / "memoria_ia" / "backtest_ev_premio.json"
PRE_CIERRE = DATA / "backtesting" / "pre_cierre"
ETIQUETA = "2026_2027"
N_MUESTRAS_BACKTEST = 10000
N_MUESTRAS_EVAL_FINAL = 40000
SEMILLA = 20261013

UMBRAL_A_MIN, UMBRAL_A_MAX = 0.67, 1.5
UMBRAL_B_FRACCION = 0.5


def cargar_json(path, defecto=None):
    if not path.exists():
        return defecto if defecto is not None else {}
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return defecto if defecto is not None else {}


def signos_oficiales(jornada):
    data = cargar_json(DATA / "jornadas" / f"jornada_{jornada}.json", {})
    signos = {}
    for p in data.get("partidos") or []:
        num = p.get("num")
        signo = str(p.get("signo_oficial") or "").upper()
        if isinstance(num, int) and 1 <= num <= 14 and signo in ("1", "X", "2"):
            signos[num] = signo
    return signos if len(signos) == 14 else None


def porcentajes_jornada(jornada):
    registro = cargar_json(ruta_porcentajes(jornada, ETIQUETA), {})
    partidos = {
        p["numero"]: p["porcentajes"]
        for p in registro.get("partidos") or []
        if isinstance(p.get("numero"), int) and p.get("porcentajes")
    }
    escrutinio = registro.get("escrutinio") or {}
    return (partidos if len(partidos) >= 14 else None), escrutinio


def jugada_real(jornada):
    data = cargar_json(DATA / "quinielas_jugadas.json", {"jugadas": []})
    for jugada in data.get("jugadas") or []:
        if jugada.get("jornada") == jornada:
            signos = [str(s or "").upper() for s in (jugada.get("signos") or [])[:14]]
            if len(signos) == 14:
                return signos
    return None


def premio_cobrado_real(jornada):
    historial = cargar_json(DATA / "premios" / "historial_premios.json", {"jornadas": []})
    for entry in historial.get("jornadas") or []:
        if entry.get("jornada") == jornada:
            return float(entry.get("premio_eur") or 0.0), int(entry.get("aciertos") or 0)
    return 0.0, 0


def conteo_columnas_exacto(boleto, signos_reales):
    """Numero de columnas del boleto con exactamente k aciertos (convolucion
    determinista con conteos, sin Monte Carlo)."""
    conteo = [1.0] + [0.0] * len(boleto)
    for i, signos in enumerate(boleto):
        limpios = [s for s in ("1", "X", "2") if s in str(signos or "").upper()]
        acierta = 1 if signos_reales[i] in limpios else 0
        falla = max(len(limpios), 1) - acierta
        nueva = [0.0] * len(conteo)
        for k in range(i + 1):
            nueva[k] += conteo[k] * falla
            nueva[k + 1] += conteo[k] * acierta
        conteo = nueva
    return {k: int(round(v)) for k, v in enumerate(conteo) if v > 0}


def premio_simulado(boleto, signos_14, escrutinio):
    """Euros netos que habria cobrado `boleto` con los resultados y el reparto
    reales, sumando nuestras columnas a los acertantes reales de cada
    categoria (con 1 acertante real en la 14, entrar nosotros parte el fondo)."""
    orden = sorted(signos_14)
    reales = [signos_14[n] for n in orden]
    conteo = conteo_columnas_exacto(boleto, reales)
    recaudacion = float(escrutinio.get("recaudacion_eur") or 0.0)
    categorias = escrutinio.get("categorias") or {}
    total = 0.0
    desglose = {}
    for cat in CATEGORIAS:
        nuestras = conteo.get(cat, 0)
        if not nuestras:
            continue
        real = categorias.get(str(cat)) or {}
        acertantes_reales = int(real.get("acertantes") or 0)
        if recaudacion > 0:
            fondo = FRACCION_RECAUDACION[cat] * recaudacion
            premio_unitario = fondo / (acertantes_reales + nuestras)
            if premio_unitario < PREMIO_MINIMO_PAGADO:
                premio_unitario = 0.0
            else:
                premio_unitario = premio_neto(premio_unitario)
        else:
            premio_unitario = float(real.get("premio_eur") or 0.0)
        ganado = premio_unitario * nuestras
        total += ganado
        if ganado:
            desglose[str(cat)] = {"columnas": nuestras, "premio_unitario": round(premio_unitario, 2)}
    aciertos_max = max(conteo) if conteo else 0
    return round(total, 2), desglose, aciertos_max


def test_a():
    """Modelo de reparto vs escrutinios reales."""
    celdas = []
    jornadas_usadas = []
    for jornada in range(1, 40):
        masa, escrutinio = porcentajes_jornada(jornada)
        signos = signos_oficiales(jornada)
        if not masa or not escrutinio.get("categorias") or not signos:
            continue
        recaudacion = float(escrutinio.get("recaudacion_eur") or 0.0)
        if recaudacion <= 0:
            continue
        orden = sorted(signos)
        dist = distribucion_aciertos_masa([masa[n] for n in orden], [signos[n] for n in orden])
        esperados = acertantes_esperados(dist, recaudacion)
        detalle = {}
        for cat in CATEGORIAS:
            real = escrutinio["categorias"].get(str(cat)) or {}
            acert_real = int(real.get("acertantes") or 0)
            modelo = esperados[cat]
            detalle[str(cat)] = {
                "acertantes_real": acert_real,
                "acertantes_modelo": round(modelo, 1),
                "premio_real_eur": real.get("premio_eur"),
                "premio_modelo_eur": round(premio_categoria_modelo(cat, modelo, recaudacion), 2),
            }
            if acert_real >= 10:
                celdas.append(modelo / acert_real)
        jornadas_usadas.append({"jornada": jornada, "recaudacion_eur": recaudacion, "categorias": detalle})
    mediana = statistics.median(celdas) if celdas else None
    return {
        "jornadas_evaluadas": len(jornadas_usadas),
        "celdas_con_10_o_mas_acertantes": len(celdas),
        "mediana_cociente_modelo_real": round(mediana, 3) if mediana else None,
        "umbral_prerregistrado": [UMBRAL_A_MIN, UMBRAL_A_MAX],
        "pasa_umbral": bool(mediana and UMBRAL_A_MIN <= mediana <= UMBRAL_A_MAX),
        "detalle": jornadas_usadas,
    }


def prediccion_pre_cierre(jornada):
    snapshot = cargar_json(PRE_CIERRE / f"jornada_{jornada}.json", {})
    prediccion = snapshot.get("prediccion") or {}
    if prediccion.get("jornada") != jornada:
        return None
    partidos = sorted(
        [p for p in prediccion.get("partidos") or []
         if isinstance(p.get("num"), int) and 1 <= p["num"] <= 14],
        key=lambda p: p["num"],
    )
    if len(partidos) != 14 or any(not p.get("probabilidades") for p in partidos):
        return None
    return partidos


def test_b():
    """Optimizador walk-forward vs lo realmente jugado y cobrado."""
    filas = []
    recaudaciones_previas = []
    for jornada in range(1, 40):
        masa, escrutinio = porcentajes_jornada(jornada)
        signos = signos_oficiales(jornada)
        partidos = prediccion_pre_cierre(jornada)
        jugado = jugada_real(jornada)
        if not (masa and escrutinio.get("categorias") and signos and partidos and jugado):
            continue
        recaudacion_wf = (
            sum(recaudaciones_previas) / len(recaudaciones_previas)
            if recaudaciones_previas else RECAUDACION_DEFECTO
        )
        p_real = [
            mezclar_probabilidades(p.get("probabilidades"), p.get("mercado_losilla"))
            for p in partidos
        ]
        pct_masa = [masa[p["num"]] for p in partidos]
        presupuesto = columnas_boleto(jugado)
        evaluador = EvaluadorEV(p_real, pct_masa, recaudacion=recaudacion_wf,
                                n_muestras=N_MUESTRAS_BACKTEST, semilla=SEMILLA)
        arranque_favorito = [max(("1", "X", "2"), key=lambda s: pr[s]) for pr in p_real]
        boleto_ev = optimizar_boleto(
            evaluador, jugado, presupuesto, boletos_arranque_extra=[arranque_favorito]
        )
        premio_ev, desglose_ev, aciertos_ev = premio_simulado(boleto_ev, signos, escrutinio)
        cobrado, aciertos_reales = premio_cobrado_real(jornada)
        # EV reportado sobre muestras independientes de las de seleccion
        # (sin esto, el EV del boleto elegido hereda el winner's curse).
        evaluador_final = EvaluadorEV(p_real, pct_masa, recaudacion=recaudacion_wf,
                                      n_muestras=N_MUESTRAS_EVAL_FINAL, semilla=SEMILLA + 1)
        filas.append({
            "jornada": jornada,
            "presupuesto_apuestas": presupuesto,
            "recaudacion_walk_forward_eur": round(recaudacion_wf, 2),
            "boleto_jugado": jugado,
            "boleto_ev": boleto_ev,
            "ev_modelo_jugado_eur": round(evaluador_final.evaluar(jugado)["ev_eur"], 2),
            "ev_modelo_optimizado_eur": round(evaluador_final.evaluar(boleto_ev)["ev_eur"], 2),
            "aciertos_reales_jugado": aciertos_reales,
            "aciertos_max_boleto_ev": aciertos_ev,
            "premio_cobrado_real_eur": cobrado,
            "premio_simulado_boleto_ev_eur": premio_ev,
            "desglose_boleto_ev": desglose_ev,
        })
        recaudacion_real = float(escrutinio.get("recaudacion_eur") or 0.0)
        if recaudacion_real > 0:
            recaudaciones_previas.append(recaudacion_real)

    total_real = round(sum(f["premio_cobrado_real_eur"] for f in filas), 2)
    total_ev = round(sum(f["premio_simulado_boleto_ev_eur"] for f in filas), 2)
    return {
        "jornadas_evaluadas": len(filas),
        "total_cobrado_real_eur": total_real,
        "total_simulado_boleto_ev_eur": total_ev,
        "umbral_prerregistrado": f"simulado >= {UMBRAL_B_FRACCION:.0%} de lo real",
        "pasa_umbral": bool(total_ev >= UMBRAL_B_FRACCION * total_real),
        "detalle": filas,
    }


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print("== TEST A: modelo de reparto vs escrutinios reales 26/27 ==")
    a = test_a()
    print(json.dumps({k: v for k, v in a.items() if k != "detalle"}, ensure_ascii=False, indent=1))
    print("\n== TEST B: optimizador EV walk-forward vs jugado real ==")
    b = test_b()
    print(json.dumps({k: v for k, v in b.items() if k != "detalle"}, ensure_ascii=False, indent=1))
    for fila in b["detalle"]:
        print(
            f"  J{fila['jornada']}: jugado {fila['aciertos_reales_jugado']} aciertos / "
            f"{fila['premio_cobrado_real_eur']:.2f} EUR -> boleto EV {fila['aciertos_max_boleto_ev']} "
            f"aciertos / {fila['premio_simulado_boleto_ev_eur']:.2f} EUR "
            f"(EV modelo: {fila['ev_modelo_jugado_eur']:.2f} vs {fila['ev_modelo_optimizado_eur']:.2f})"
        )
    salida = {
        "version": 1,
        "generado_en": datetime.now(timezone.utc).isoformat(),
        "descripcion": (
            "Backtest prerregistrado del optimizador de EV del premio (candidato 3, estilo Q84). "
            "TEST A: modelo de reparto vs escrutinios reales. TEST B: optimizador walk-forward "
            "con datos pre-cierre vs lo realmente jugado/cobrado."
        ),
        "test_a_modelo_reparto": a,
        "test_b_ev_walk_forward": b,
    }
    SALIDA.write_text(json.dumps(salida, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("\nGuardado en", SALIDA)
