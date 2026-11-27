"""Prior europeo de empate (modulo de Laboratorio, prerregistrado 26/11/2026).

Evidencia (research_notes/.../europa.md, arXiv 2508.20075): la fase liga de la
Champions dio 12,5% de empates en 2024/25 y 17,4% en 2025/26, con ~50% de
victorias locales, frente al 26,4% de X de las grandes ligas; la Europa League
se mueve en el 17-24%. Un Poisson domestico predijo 31 empates en la UCL
2024/25 y hubo 18. Un motor calibrado en Liga sobreestima la X europea, y el
mercado (20-22% a Arsenal y City en la J24) tenia razon.

Que hace este modulo (cuaderno; NO toca el motor):
  a) ajustar_por_competicion_europea(probs, mercado=None, ...): en partidos
     extranjeros encoge P(X) hacia X_PRIOR (defecto 0,16) con peso w (defecto
     0,5) y reparte la masa retirada entre 1 y 2 en proporcion a sus valores
     actuales. Devuelve (probs, traza) con activo, x_antes, x_despues, motivo.
     Si el veredicto del backtest no es DESPLEGAR, es un no-op salvo forzar=True.
  b) Backtest sobre las jornadas europeas con snapshot pre-cierre (5, 13, 15,
     19, 22 y los partidos jugados de la 24): RPS, log-loss y X predichas vs
     reales del motor actual, del motor ajustado (rejilla X_PRIOR x w elegida
     con leave-one-jornada-out) y del mercado Losilla solo como benchmark.

HONESTIDAD: n ~ 80 partidos. Con ese tamano NO se puede demostrar una mejora
de RPS < 0,005 (hacen falta 1.200-2.700 partidos); el backtest sirve para
descartar que el ajuste haga dano y para fijar los parametros sin mirar el
futuro, no para "demostrar" nada.

Criterio prerregistrado (escrito en el JSON antes de calcular, ver
CRITERIOS_PRERREGISTRADOS): el ajuste leave-one-out gana al motor actual en
log-loss en >= 5 de las 6 jornadas Y no pierde contra el mercado Losilla por
mas de 0,002 de RPS. Si no, NO_DESPLEGAR.

Salida: data/memoria_ia/backtest_prior_europeo.json
Uso: python prior_europeo.py
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from calibracion_x import (SNAPSHOTS_DIR, JORNADAS_DIR, SIGNOS, _como_fraccion, cargar_snapshots, log_loss, rps,
                           intervalo_x)
from columna_valiente import cargar_json, guardar_json

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
SALIDA = DATA / "memoria_ia" / "backtest_prior_europeo.json"

X_PRIOR_DEFECTO = 0.16
W_DEFECTO = 0.5
REJILLA_X_PRIOR = (0.14, 0.16, 0.18)
REJILLA_W = (0.25, 0.5, 0.75)
JORNADAS_EUROPEAS = (5, 13, 15, 19, 22, 24)
# Auditoria 26/11: esos numeros son jornadas de la temporada 26/27. La
# numeracion se reinicia cada temporada: la J5 de la 27/28 es OTRA jornada y
# no puede entrar en la muestra prerregistrada. Se identifican por
# (temporada, numero), con la temporada sacada de la fecha real.
TEMPORADA_MUESTRA = "2026_2027"
MIN_JORNADAS_GANADAS = 5
TOLERANCIA_RPS_MERCADO = 0.002
VERSION = "1.0"

CRITERIOS_PRERREGISTRADOS = {
    "fecha": "2026-11-26",
    "descripcion": (
        "Se despliega ajustar_por_competicion_europea SOLO si (1) el motor ajustado con parametros elegidos "
        f"leave-one-jornada-out gana al motor actual en log-loss en al menos {MIN_JORNADAS_GANADAS} de las "
        f"{len(JORNADAS_EUROPEAS)} jornadas europeas Y (2) su RPS agregado no es peor que el del mercado Losilla "
        f"en mas de {TOLERANCIA_RPS_MERCADO}. En otro caso veredicto NO_DESPLEGAR y la funcion es un no-op "
        "salvo forzar=True."
    ),
    "jornadas": list(JORNADAS_EUROPEAS),
    "rejilla": {"x_prior": list(REJILLA_X_PRIOR), "w": list(REJILLA_W)},
    "seleccion": "leave-one-jornada-out: para cada jornada se elige la pareja (x_prior, w) con menor log-loss en las otras",
    "ajuste": "x' = (1-w)*x + w*x_prior; la masa retirada va a 1 y 2 en proporcion a sus valores actuales",
    "limite_muestral": "n ~ 80 partidos: no permite demostrar una mejora de RPS < 0.005; solo descarta dano",
    "no_se_cambia": "Este bloque no se modifica despues de ver los resultados.",
}


# ----------------------------------------------------------------------------
# a) funcion para el motor
# ----------------------------------------------------------------------------
_CACHE = {"ruta": None, "datos": None}


def cargar_backtest(ruta=SALIDA):
    ruta = Path(ruta)
    if _CACHE["ruta"] != str(ruta) or _CACHE["datos"] is None:
        _CACHE["ruta"] = str(ruta)
        _CACHE["datos"] = cargar_json(ruta, {}) or {}
    return _CACHE["datos"]


def encoger_x(frac, x_prior, w):
    """frac en [0,1] normalizado. Devuelve dict en [0,1] con la X encogida hacia x_prior."""
    x = frac["X"]
    x_nuevo = (1.0 - w) * x + w * x_prior
    x_nuevo = min(0.95, max(0.0, x_nuevo))
    resto_antes = frac["1"] + frac["2"]
    resto = 1.0 - x_nuevo
    if resto_antes <= 0:
        return {"1": resto / 2.0, "X": x_nuevo, "2": resto / 2.0}
    return {"1": resto * frac["1"] / resto_antes, "X": x_nuevo, "2": resto * frac["2"] / resto_antes}


def _a_escala(frac, escala):
    if escala != 100.0:
        return dict(frac)
    out = {s: round(v * 100.0, 2) for s, v in frac.items()}
    desvio = round(100.0 - sum(out.values()), 2)
    if abs(desvio) >= 0.01:
        mayor = max(SIGNOS, key=lambda s: out[s])
        out[mayor] = round(out[mayor] + desvio, 2)
    return out


def ajustar_por_competicion_europea(probs, mercado=None, x_prior=None, w=None, es_extranjero=True, forzar=False,
                                    veredicto=None, ruta=SALIDA):
    """Devuelve (probs_ajustadas, traza). Solo actua en partidos extranjeros (es_extranjero=True).

    probs/mercado en 0-100 o 0-1 (se respeta la escala de entrada). x_prior y w por defecto salen de los
    parametros recomendados del backtest si el veredicto es DESPLEGAR; si no, de X_PRIOR_DEFECTO/W_DEFECTO.
    Si el veredicto no es DESPLEGAR y forzar=False la funcion no toca nada (activo=False)."""
    frac, escala = _como_fraccion(probs)
    base = _a_escala(frac, escala)
    datos = {}
    if veredicto is None or x_prior is None or w is None:
        datos = cargar_backtest(ruta)
    veredicto = veredicto if veredicto is not None else datos.get("veredicto", "NO_DESPLEGAR")
    rec = datos.get("parametros_recomendados") or {}
    x_prior = float(x_prior if x_prior is not None else rec.get("x_prior", X_PRIOR_DEFECTO))
    w = float(w if w is not None else rec.get("w", W_DEFECTO))
    merc_x = None
    if mercado:
        merc_x = round(_como_fraccion(mercado)[0]["X"] * 100.0, 2)
    traza = {"activo": False, "veredicto": veredicto, "x_prior": x_prior, "w": w,
             "x_antes": round(frac["X"] * 100.0, 2), "x_despues": round(frac["X"] * 100.0, 2),
             "x_mercado": merc_x, "motivo": ""}
    if not es_extranjero:
        traza["motivo"] = "partido domestico: el prior europeo no aplica"
        return base, traza
    if veredicto != "DESPLEGAR" and not forzar:
        traza["motivo"] = f"veredicto {veredicto}: sin ajuste (no-op)"
        return base, traza
    nuevo = encoger_x(frac, x_prior, w)
    traza.update({"activo": True, "x_despues": round(nuevo["X"] * 100.0, 2),
                  "motivo": (f"prior europeo: X {frac['X']*100:.1f}% -> {nuevo['X']*100:.1f}% "
                             f"(hacia {x_prior*100:.0f}% con peso {w:.2f})" + (" (forzado)" if forzar and veredicto != "DESPLEGAR" else ""))})
    return _a_escala(nuevo, escala), traza


# ----------------------------------------------------------------------------
# b) backtest
# ----------------------------------------------------------------------------
def cargar_partidos_europeos(jornadas=JORNADAS_EUROPEAS, dir_snapshots=SNAPSHOTS_DIR, dir_jornadas=JORNADAS_DIR,
                             temporada=TEMPORADA_MUESTRA):
    """{jornada: [partidos extranjeros con resultado]} de los snapshots pre-cierre.
    Solo jornadas de `temporada` (por fecha real); una jornada sin ninguna
    fecha (temporada None) se acepta para no descartar a ciegas."""
    todas = cargar_snapshots(dir_snapshots, dir_jornadas)
    out = {}
    for j in todas:
        if j["jornada"] in jornadas and j.get("temporada") in (None, temporada):
            ext = [p for p in j["partidos"] if p["extranjero"]]
            if ext:
                out[j["jornada"]] = ext
    return out


def _items(partidos, x_prior=None, w=None, fuente="motor"):
    items = []
    for p in partidos:
        if fuente == "mercado":
            if not p.get("mercado"):
                continue
            probs = p["mercado"]
        elif x_prior is None:
            probs = p["motor"]
        else:
            probs = encoger_x(p["motor"], x_prior, w)
        items.append({"probs": probs, "y": p["y"]})
    return items


def _metricas(items):
    if not items:
        return {"n": 0}
    ps = [it["probs"]["X"] for it in items]
    obs = sum(1 for it in items if it["y"] == "X")
    return {"n": len(items), "log_loss": round(log_loss(items), 5), "rps": round(rps(items), 5),
            "x_reales": obs, "x_predichas": round(sum(ps), 2), "intervalo_95": intervalo_x(ps, obs)}


def backtest(por_jornada):
    jornadas = sorted(por_jornada)
    todos = [p for j in jornadas for p in por_jornada[j]]
    salida = {"n_partidos": len(todos), "jornadas": jornadas,
              "n_por_jornada": {str(j): len(por_jornada[j]) for j in jornadas},
              "x_reales_pct": round(100.0 * sum(1 for p in todos if p["y"] == "X") / len(todos), 2) if todos else None}
    # benchmarks
    salida["motor_actual"] = _metricas(_items(todos))
    salida["mercado_losilla"] = _metricas(_items(todos, fuente="mercado"))
    # rejilla completa (in-sample, informativa)
    rejilla = []
    for xp in REJILLA_X_PRIOR:
        for w in REJILLA_W:
            m = _metricas(_items(todos, xp, w))
            m.update({"x_prior": xp, "w": w,
                      "por_jornada": {str(j): round(log_loss(_items(por_jornada[j], xp, w)), 5) for j in jornadas}})
            rejilla.append(m)
    salida["rejilla_in_sample"] = rejilla
    # leave-one-jornada-out
    loo_items, loo_detalle = [], []
    for j in jornadas:
        entren = [p for k in jornadas if k != j for p in por_jornada[k]]
        mejor = min(((log_loss(_items(entren, xp, w)), xp, w) for xp in REJILLA_X_PRIOR for w in REJILLA_W),
                    key=lambda t: t[0])
        _, xp, w = mejor
        it_adj = _items(por_jornada[j], xp, w)
        it_mot = _items(por_jornada[j])
        it_mer = _items(por_jornada[j], fuente="mercado")
        loo_items.extend(it_adj)
        loo_detalle.append({"jornada": j, "n": len(it_mot), "x_prior": xp, "w": w,
                            "log_loss_motor": round(log_loss(it_mot), 5), "log_loss_ajustado": round(log_loss(it_adj), 5),
                            "log_loss_mercado": round(log_loss(it_mer), 5) if it_mer else None,
                            "rps_motor": round(rps(it_mot), 5), "rps_ajustado": round(rps(it_adj), 5),
                            "rps_mercado": round(rps(it_mer), 5) if it_mer else None,
                            "x_reales": sum(1 for it in it_mot if it["y"] == "X"),
                            "x_pred_motor": round(sum(it["probs"]["X"] for it in it_mot), 2),
                            "x_pred_ajustado": round(sum(it["probs"]["X"] for it in it_adj), 2),
                            "x_pred_mercado": round(sum(it["probs"]["X"] for it in it_mer), 2) if it_mer else None,
                            "gana_al_motor": log_loss(it_adj) < log_loss(it_mot)})
    salida["ajustado_leave_one_out"] = _metricas(loo_items)
    salida["ajustado_leave_one_out"]["por_jornada"] = loo_detalle
    salida["jornadas_ganadas_al_motor"] = sum(1 for d in loo_detalle if d["gana_al_motor"])
    # parametros recomendados: la pareja con menor log-loss sobre todas las jornadas (para uso prospectivo)
    mejor_global = min(rejilla, key=lambda m: m["log_loss"])
    salida["parametros_recomendados"] = {"x_prior": mejor_global["x_prior"], "w": mejor_global["w"],
                                         "nota": "pareja con menor log-loss in-sample sobre las 6 jornadas; el LOO mide su honestidad"}
    return salida


def evaluar_criterios(bt):
    motivos = []
    ganadas = bt["jornadas_ganadas_al_motor"]
    total = len(bt["jornadas"])
    c1 = ganadas >= MIN_JORNADAS_GANADAS
    motivos.append(f"(1) ajustado LOO gana al motor en log-loss en {ganadas}/{total} jornadas (minimo {MIN_JORNADAS_GANADAS}): "
                   + ("CUMPLE" if c1 else "NO cumple"))
    rps_adj = bt["ajustado_leave_one_out"].get("rps")
    rps_mer = bt["mercado_losilla"].get("rps")
    if rps_mer is None:
        c2 = True
        motivos.append("(2) sin mercado Losilla en los snapshots: no se puede comparar, se da por cumplido con aviso")
    else:
        c2 = rps_adj is not None and rps_adj <= rps_mer + TOLERANCIA_RPS_MERCADO
        motivos.append(f"(2) RPS ajustado LOO {rps_adj} vs mercado Losilla {rps_mer} (tolerancia +{TOLERANCIA_RPS_MERCADO}): "
                       + ("CUMPLE" if c2 else "NO cumple"))
    return ("DESPLEGAR" if (c1 and c2) else "NO_DESPLEGAR"), motivos


def _prerregistrar(ruta):
    previo = cargar_json(ruta, {}) or {}
    criterios = previo.get("criterios_prerregistrados") or CRITERIOS_PRERREGISTRADOS
    salida = {"version": VERSION, "modulo": "prior_europeo", "generado_en": datetime.now(timezone.utc).isoformat(),
              "criterios_prerregistrados": criterios, "estado": "prerregistrado_sin_resultados"}
    guardar_json(ruta, salida)
    return salida


def ejecutar(ruta=SALIDA, dir_snapshots=SNAPSHOTS_DIR, dir_jornadas=JORNADAS_DIR, jornadas=JORNADAS_EUROPEAS):
    previo = cargar_json(ruta, {}) or {}
    por_jornada = cargar_partidos_europeos(jornadas, dir_snapshots, dir_jornadas)
    # Auditoria 26/11: el backtest prerregistrado es un experimento CERRADO.
    # Si ya hay resultado y a la muestra de hoy le faltan jornadas que entonces
    # estaban (la temporada nueva ha reescrito jornada_N.json o su snapshot),
    # se conserva el veredicto guardado en vez de recalcularlo con otra muestra.
    previas = set((previo.get("backtest") or {}).get("jornadas") or [])
    if previo.get("estado") == "con_resultados" and previas and not previas <= set(por_jornada):
        previo["muestra_congelada"] = {
            "desde": (previo.get("muestra_congelada") or {}).get("desde") or datetime.now(timezone.utc).isoformat(),
            "jornadas_que_faltan": sorted(previas - set(por_jornada)),
            "motivo": ("La muestra prerregistrada ya no esta completa en disco: se conserva el backtest guardado "
                       "y no se recalcula el veredicto."),
        }
        guardar_json(ruta, previo)
        _CACHE["datos"] = None
        return previo
    salida = _prerregistrar(ruta)
    fijados = json.dumps(salida["criterios_prerregistrados"], sort_keys=True)
    bt = backtest(por_jornada)
    salida["backtest"] = bt
    veredicto, motivos = evaluar_criterios(bt)
    salida["veredicto"] = veredicto
    salida["motivos_veredicto"] = motivos
    salida["parametros_recomendados"] = bt["parametros_recomendados"]
    salida["estado"] = "con_resultados"
    salida["aviso"] = (f"n={bt['n_partidos']} partidos en {len(bt['jornadas'])} jornadas: este tamano NO demuestra una mejora "
                       "de RPS < 0.005 (hacen falta 1.200-2.700 partidos). El backtest solo descarta dano y fija parametros "
                       "sin mirar el futuro. El motor no usa el ajuste hasta el OK de Marc.")
    assert json.dumps(salida["criterios_prerregistrados"], sort_keys=True) == fijados
    guardar_json(ruta, salida)
    _CACHE["datos"] = None
    return salida


def _imprimir(salida):
    bt = salida["backtest"]
    print(f"[prior_europeo] {bt['n_partidos']} partidos extranjeros en jornadas {bt['jornadas']} "
          f"(X real {bt['x_reales_pct']}%)")
    for clave in ("motor_actual", "mercado_losilla", "ajustado_leave_one_out"):
        m = bt[clave]
        if m.get("n"):
            iv = m["intervalo_95"]
            print(f"  {clave:24s} n={m['n']} logloss={m['log_loss']:.5f} rps={m['rps']:.5f} "
                  f"Xpred={m['x_predichas']:.1f} Xreal={m['x_reales']} [{iv['lo']}-{iv['hi']}] dentro={iv['dentro']}")
    print("  rejilla in-sample (x_prior, w): logloss rps Xpred")
    for m in bt["rejilla_in_sample"]:
        print(f"    ({m['x_prior']:.2f}, {m['w']:.2f}) {m['log_loss']:.5f} {m['rps']:.5f} {m['x_predichas']:.1f}")
    print("  leave-one-out por jornada:")
    for d in bt["ajustado_leave_one_out"]["por_jornada"]:
        print(f"    J{d['jornada']:<3d} n={d['n']:2d} ({d['x_prior']:.2f},{d['w']:.2f}) motor={d['log_loss_motor']:.4f} "
              f"ajust={d['log_loss_ajustado']:.4f} mercado={d['log_loss_mercado']} X real={d['x_reales']} "
              f"pred motor={d['x_pred_motor']} ajust={d['x_pred_ajustado']} gana={d['gana_al_motor']}")
    print(f"  parametros recomendados: {salida['parametros_recomendados']}")
    print(f"[prior_europeo] VEREDICTO: {salida['veredicto']}")
    for m in salida["motivos_veredicto"]:
        print("   ", m)
    print("  AVISO:", salida["aviso"])


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    salida = ejecutar()
    _imprimir(salida)
    print(f"Guardado en {SALIDA}")


if __name__ == "__main__":
    main()
