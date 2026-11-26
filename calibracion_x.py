"""Calibracion de la X (modulo de Laboratorio, prerregistrado 26/11/2026).

Problema: el motor subestima el empate. Goto, Takeishi y Yairi (arXiv
2604.17194, 90.014 partidos, 5 casas) muestran que los conversores de cuotas
que corrigen el sesgo favorito-longshot (Shin, Power, OO-EPC) "tend to
underestimate the number of draws" (test de Poisson bilateral p<0,05 en
Bet365), mientras que el conversor multiplicativo devuelve la frecuencia real
de X. Nuestro motor desviga con Shin (modelo_dixon_coles.shin_devig) y mezcla
con el mercado Losilla, asi que hereda ese recorte.

Que hace este modulo (todo es cuaderno; NO toca el motor):
  a) Historico football-data (2.525 partidos de 1a/2a 2023/24-2025/26):
     desviga con multiplicativo, Shin y Power; compara X predichas vs reales
     global y por franja del favorito, con intervalo Poisson-binomial al 95%;
     log-loss, RPS y Brier por conversor.
  b) Snapshots pre-cierre (35 jornadas): frecuencia real de X frente a la
     P(X) del motor por franja del favorito, separando partidos domesticos y
     no domesticos; tabla factor_X[franja] = observado/predicho con
     encogimiento hacia 1 (K=20 pseudo-partidos), estimada walk-forward
     (para la jornada N solo cuentan las jornadas creadas ANTES de N).
  c) calibrar_x(probs, ...): multiplica la X por el factor y reparte el resto
     entre 1 y 2 en proporcion. Si el veredicto del backtest no es
     DESPLEGAR, la funcion es un no-op (factor 1) salvo forzar=True.

Las franjas van por la probabilidad del FAVORITO (max de P(1) y P(2)), que es
donde nos duele: "el gigante 65-79 que empata".

Criterio de exito prerregistrado (escrito en el JSON antes de calcular nada,
ver CRITERIOS_PRERREGISTRADOS): el log-loss walk-forward sobre los snapshots
mejora frente al motor sin calibrar Y la cuenta de X predichas calibradas cae
dentro del intervalo 95% en todas las franjas con datos. Si no, NO_DESPLEGAR.

Salida: data/memoria_ia/backtest_calibracion_x.json
Uso: python calibracion_x.py
"""
import json
import math
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from columna_valiente import cargar_json, guardar_json, equipos_espanoles, es_espanol
from modelo_dixon_coles import shin_devig

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
HISTORICO = DATA / "memoria_ia" / "historico_ligas_espana.json"
SNAPSHOTS_DIR = DATA / "backtesting" / "pre_cierre"
JORNADAS_DIR = DATA / "jornadas"
SALIDA = DATA / "memoria_ia" / "backtest_calibracion_x.json"

SIGNOS = ("1", "X", "2")
# (minimo inclusive, maximo exclusivo, etiqueta) sobre la P del favorito en %
FRANJAS = ((0.0, 40.0, "<40"), (40.0, 50.0, "40-50"), (50.0, 60.0, "50-60"),
           (60.0, 65.0, "60-65"), (65.0, 80.0, "65-80"), (80.0, 100.01, ">=80"))
ETIQUETAS_FRANJA = tuple(f[2] for f in FRANJAS)
COMPETICIONES = ("domestica", "no_domestica")
K_ENCOGIMIENTO = 20          # pseudo-partidos hacia factor 1
FACTOR_MIN, FACTOR_MAX = 0.5, 2.0
X_MAX = 0.95
VERSION = "1.0"

CRITERIOS_PRERREGISTRADOS = {
    "fecha": "2026-11-26",
    "descripcion": (
        "Se despliega calibrar_x SOLO si (1) el log-loss walk-forward de las probabilidades calibradas sobre los "
        "snapshots pre-cierre con resultado es MENOR que el del motor sin calibrar, Y (2) en TODAS las franjas del "
        "favorito con n>0 la cuenta real de X cae dentro del intervalo 95% Poisson-binomial de la cuenta de X "
        "predicha por las probabilidades calibradas (walk-forward). En otro caso veredicto NO_DESPLEGAR y la "
        "funcion devuelve las probabilidades sin tocar (factor 1)."
    ),
    "franjas": list(ETIQUETAS_FRANJA),
    "variable_franja": "probabilidad del favorito = max(P(1), P(2)) en %",
    "encogimiento": f"factor = 1 + (obs/pred - 1) * n/(n+{K_ENCOGIMIENTO}), recortado a [{FACTOR_MIN}, {FACTOR_MAX}]",
    "walk_forward": "para la jornada N solo se usan jornadas con creado_en anterior (orden cronologico, nunca por numero)",
    "intervalo": "cuantiles 2.5% y 97.5% de la Poisson-binomial exacta de la suma de P(X)",
    "no_se_cambia": "Este bloque no se modifica despues de ver los resultados.",
}


# ----------------------------------------------------------------------------
# utilidades de probabilidad
# ----------------------------------------------------------------------------
def _como_fraccion(probs):
    """Devuelve ({'1','X','2'} en [0,1] normalizado, escala_original) donde escala es 100 o 1."""
    vals = {s: max(float((probs or {}).get(s, 0) or 0), 0.0) for s in SIGNOS}
    total = sum(vals.values())
    escala = 100.0 if total > 1.5 else 1.0
    if total <= 0:
        return {s: 1 / 3 for s in SIGNOS}, escala
    return {s: v / total for s, v in vals.items()}, escala


def prob_favorito_pct(probs):
    frac, _ = _como_fraccion(probs)
    return 100.0 * max(frac["1"], frac["2"])


def franja_de(prob_favorito_pct):
    """Etiqueta de franja para una P(favorito) en % (acepta tambien la etiqueta ya hecha)."""
    if isinstance(prob_favorito_pct, str):
        return prob_favorito_pct if prob_favorito_pct in ETIQUETAS_FRANJA else None
    try:
        p = float(prob_favorito_pct)
    except (TypeError, ValueError):
        return None
    if p <= 1.0:
        p *= 100.0
    for lo, hi, etiqueta in FRANJAS:
        if lo <= p < hi:
            return etiqueta
    return ETIQUETAS_FRANJA[-1] if p >= 100.0 else None


def devig_multiplicativo(cuotas):
    try:
        inv = [1.0 / float(c) for c in cuotas]
    except (TypeError, ValueError, ZeroDivisionError):
        return None
    if any(v <= 0 or not math.isfinite(v) for v in inv):
        return None
    s = sum(inv)
    return {k: v / s for k, v in zip(SIGNOS, inv)}


def devig_power(cuotas):
    """Conversor Power: p_i = (1/o_i)^k con k tal que sum p_i = 1 (biseccion)."""
    try:
        inv = [1.0 / float(c) for c in cuotas]
    except (TypeError, ValueError, ZeroDivisionError):
        return None
    if any(v <= 0 or v >= 1 or not math.isfinite(v) for v in inv):
        return None
    lo, hi = 0.5, 3.0
    for _ in range(80):
        k = (lo + hi) / 2
        if sum(v ** k for v in inv) > 1.0:
            lo = k
        else:
            hi = k
    k = (lo + hi) / 2
    p = [v ** k for v in inv]
    t = sum(p)
    return {s: v / t for s, v in zip(SIGNOS, p)}


METODOS_DEVIG = {"multiplicativo": devig_multiplicativo, "shin": shin_devig, "power": devig_power}


def log_loss(items):
    if not items:
        return None
    return sum(-math.log(max(min(it["probs"][it["y"]], 1.0), 1e-15)) for it in items) / len(items)


def rps(items):
    """Ranked Probability Score 1X2 (menor es mejor)."""
    if not items:
        return None
    total = 0.0
    for it in items:
        p = it["probs"]
        cp = (p["1"], p["1"] + p["X"])
        y = it["y"]
        co = (1.0 if y == "1" else 0.0, 1.0 if y in ("1", "X") else 0.0)
        total += ((cp[0] - co[0]) ** 2 + (cp[1] - co[1]) ** 2) / 2.0
    return total / len(items)


def brier(items):
    if not items:
        return None
    total = 0.0
    for it in items:
        for s in SIGNOS:
            total += (it["probs"][s] - (1.0 if it["y"] == s else 0.0)) ** 2
    return total / len(items)


def distribucion_poisson_binomial(ps):
    """PMF exacta de la suma de Bernoullis independientes con probabilidades ps."""
    pmf = [1.0]
    for p in ps:
        nuevo = [0.0] * (len(pmf) + 1)
        for k, v in enumerate(pmf):
            if v == 0.0:
                continue
            nuevo[k] += v * (1.0 - p)
            nuevo[k + 1] += v * p
        pmf = nuevo
    return pmf


def intervalo_x(ps, observadas, nivel=0.95):
    """Intervalo central (cuantiles) de la cuenta de X bajo las probabilidades ps y p-valor bilateral de la
    cuenta observada. Devuelve dict con esperadas, lo, hi, dentro, p_valor."""
    if not ps:
        return {"n": 0, "esperadas": 0.0, "lo": 0, "hi": 0, "observadas": observadas, "dentro": True, "p_valor": 1.0}
    pmf = distribucion_poisson_binomial(ps)
    alfa = (1.0 - nivel) / 2.0
    acum, lo, hi = 0.0, None, None
    for k, v in enumerate(pmf):
        acum += v
        if lo is None and acum >= alfa:
            lo = k
        if hi is None and acum >= 1.0 - alfa - 1e-12:
            hi = k
            break
    if hi is None:
        hi = len(pmf) - 1
    obs = int(observadas)
    p_menor = sum(pmf[:obs + 1])
    p_mayor = sum(pmf[obs:])
    p_valor = min(1.0, 2.0 * min(p_menor, p_mayor))
    return {"n": len(ps), "esperadas": round(sum(ps), 2), "lo": lo, "hi": hi, "observadas": obs,
            "dentro": lo <= obs <= hi, "p_valor": round(p_valor, 4)}


def _resumen_items(items):
    """Metricas + cuenta de X para una lista de items {probs(fraccion), y}."""
    ps = [it["probs"]["X"] for it in items]
    obs = sum(1 for it in items if it["y"] == "X")
    out = {"n": len(items), "x_reales": obs, "x_predichas": round(sum(ps), 2),
           "x_pct_real": round(100.0 * obs / len(items), 2) if items else None,
           "x_pct_predicho": round(100.0 * sum(ps) / len(items), 2) if items else None,
           "log_loss": round(log_loss(items), 5) if items else None,
           "rps": round(rps(items), 5) if items else None,
           "brier": round(brier(items), 5) if items else None}
    out["intervalo_95"] = intervalo_x(ps, obs)
    return out


def _por_franja(items):
    out = {}
    for etiqueta in ETIQUETAS_FRANJA:
        sub = [it for it in items if it["franja"] == etiqueta]
        out[etiqueta] = _resumen_items(sub) if sub else {"n": 0}
    return out


# ----------------------------------------------------------------------------
# a) historico football-data
# ----------------------------------------------------------------------------
def cargar_historico(ruta=HISTORICO):
    datos = cargar_json(ruta, {}) or {}
    partidos = []
    for liga, bloque in (datos.get("ligas") or {}).items():
        temporadas = bloque.get("temporadas", bloque) if isinstance(bloque, dict) else {}
        for temporada, contenido in temporadas.items():
            lista = contenido.get("partidos", []) if isinstance(contenido, dict) else contenido
            for p in lista or []:
                signo = p.get("signo")
                cuotas = (p.get("cuota_1"), p.get("cuota_x"), p.get("cuota_2"))
                if signo not in SIGNOS or any(c in (None, 0) for c in cuotas):
                    continue
                partidos.append({"liga": liga, "temporada": temporada, "fecha": p.get("fecha"),
                                 "local": p.get("local"), "visitante": p.get("visitante"),
                                 "cuotas": tuple(float(c) for c in cuotas), "y": signo})
    return partidos


def backtest_historico(partidos):
    """Compara los tres conversores en el historico: X predichas vs reales, global y por franja."""
    resultado = {"n": len(partidos), "metodos": {}}
    for nombre, fn in METODOS_DEVIG.items():
        items = []
        for p in partidos:
            probs = fn(p["cuotas"])
            if not probs:
                continue
            # la franja se define con el multiplicativo para que sea la misma en los tres metodos
            ref = devig_multiplicativo(p["cuotas"])
            items.append({"probs": probs, "y": p["y"], "franja": franja_de(prob_favorito_pct(ref))})
        bloque = _resumen_items(items)
        bloque["por_franja"] = _por_franja(items)
        bloque["x_sesgo"] = round(bloque["x_predichas"] - bloque["x_reales"], 2)
        resultado["metodos"][nombre] = bloque
    # que metodo deja la X sin sesgo: dentro del intervalo global y en mas franjas
    ranking = []
    for nombre, b in resultado["metodos"].items():
        franjas_dentro = sum(1 for f in b["por_franja"].values() if f.get("n", 0) > 0 and f["intervalo_95"]["dentro"])
        ranking.append((b["intervalo_95"]["dentro"], franjas_dentro, -abs(b["x_sesgo"]), nombre))
    ranking.sort(reverse=True)
    resultado["metodo_x_sin_sesgo"] = ranking[0][3] if ranking else None
    resultado["lectura"] = (
        f"El conversor con la X menos sesgada en este historico es '{resultado['metodo_x_sin_sesgo']}' "
        "(global dentro del intervalo 95% y mas franjas dentro). Sesgo = X predichas - X reales: "
        + ", ".join(f"{n} {b['x_sesgo']:+.1f} (p={b['intervalo_95']['p_valor']})" for n, b in resultado["metodos"].items())
    )
    return resultado


# ----------------------------------------------------------------------------
# b) snapshots pre-cierre del motor
# ----------------------------------------------------------------------------
def _signos_reales(jornada, dir_jornadas=JORNADAS_DIR):
    datos = cargar_json(Path(dir_jornadas) / f"jornada_{jornada}.json", {}) or {}
    return {p.get("num"): p.get("signo_oficial") for p in datos.get("partidos", [])}


def _peso_mercado(partido):
    for lectura in (partido.get("ajuste_mercado_losilla") or {}).get("lecturas", []) or []:
        m = re.search(r"peso (\d+(?:\.\d+)?)", str(lectura))
        if m:
            return float(m.group(1))
    return None


def cargar_snapshots(dir_snapshots=SNAPSHOTS_DIR, dir_jornadas=JORNADAS_DIR, espanoles=None):
    """Lista de jornadas ORDENADA POR creado_en (nunca por numero) con sus partidos cerrados:
    {jornada, orden, partidos:[{num, local, visitante, motor(fraccion), mercado(fraccion|None),
    calidad, peso_mercado, extranjero, franja, y}]}."""
    espanoles = espanoles if espanoles is not None else equipos_espanoles()
    jornadas = []
    for ruta in Path(dir_snapshots).glob("jornada_*.json"):
        snap = cargar_json(ruta, {}) or {}
        pred = snap.get("prediccion") or {}
        jornada = snap.get("jornada") or pred.get("jornada")
        if jornada is None:
            continue
        reales = _signos_reales(jornada, dir_jornadas)
        partidos = []
        for p in pred.get("partidos", []):
            y = reales.get(p.get("num"))
            if y not in SIGNOS:
                continue
            motor, _ = _como_fraccion(p.get("probabilidades"))
            mercado = None
            if p.get("mercado_losilla"):
                mercado, _ = _como_fraccion(p.get("mercado_losilla"))
            extranjero = not (es_espanol(p.get("local"), espanoles) and es_espanol(p.get("visitante"), espanoles))
            partidos.append({"num": p.get("num"), "local": p.get("local"), "visitante": p.get("visitante"),
                             "motor": motor, "mercado": mercado, "calidad": p.get("calidad_datos"),
                             "peso_mercado": _peso_mercado(p), "extranjero": extranjero,
                             "competicion": "no_domestica" if extranjero else "domestica",
                             "franja": franja_de(prob_favorito_pct(motor)), "y": y})
        if partidos:
            jornadas.append({"jornada": jornada, "orden": str(snap.get("creado_en") or pred.get("generado_en") or ""),
                             "partidos": partidos})
    jornadas.sort(key=lambda j: (j["orden"], j["jornada"]))
    return jornadas


def tabla_factores(items, k_encogimiento=K_ENCOGIMIENTO):
    """items: [{franja, competicion, p_x, y}] YA filtrados (sin futuro). Devuelve
    {competicion: {franja: {n, x_obs, x_pred, factor_bruto, factor}}}."""
    tabla = {}
    for comp in COMPETICIONES:
        tabla[comp] = {}
        for etiqueta in ETIQUETAS_FRANJA:
            sub = [it for it in items if it["competicion"] == comp and it["franja"] == etiqueta]
            n = len(sub)
            x_obs = sum(1 for it in sub if it["y"] == "X")
            x_pred = sum(it["p_x"] for it in sub)
            if n == 0 or x_pred <= 0:
                bruto, factor = 1.0, 1.0
            else:
                bruto = x_obs / x_pred
                peso = n / (n + k_encogimiento)
                factor = min(FACTOR_MAX, max(FACTOR_MIN, 1.0 + (bruto - 1.0) * peso))
            tabla[comp][etiqueta] = {"n": n, "x_obs": x_obs, "x_pred": round(x_pred, 2),
                                     "factor_bruto": round(bruto, 4), "factor": round(factor, 4)}
    return tabla


def tabla_factores_hasta(jornadas, orden_limite, k_encogimiento=K_ENCOGIMIENTO):
    """Guardia anti-fuga: solo entran jornadas con orden (creado_en) ESTRICTAMENTE anterior."""
    items = [{"franja": p["franja"], "competicion": p["competicion"], "p_x": p["motor"]["X"], "y": p["y"]}
             for j in jornadas if j["orden"] < orden_limite for p in j["partidos"]]
    return tabla_factores(items, k_encogimiento)


def aplicar_factor(probs, factor):
    """Multiplica la X por factor y reparte el resto entre 1 y 2 en proporcion. Devuelve en la escala de entrada."""
    frac, escala = _como_fraccion(probs)
    x = min(X_MAX, max(0.0, frac["X"] * float(factor)))
    resto_antes = frac["1"] + frac["2"]
    resto = 1.0 - x
    if resto_antes <= 0:
        p1 = p2 = resto / 2.0
    else:
        p1 = resto * frac["1"] / resto_antes
        p2 = resto * frac["2"] / resto_antes
    out = {"1": p1, "X": x, "2": p2}
    if escala == 100.0:
        out = {s: round(v * 100.0, 2) for s, v in out.items()}
        # cierre exacto a 100 sobre el signo mayor
        desvio = round(100.0 - sum(out.values()), 2)
        if abs(desvio) >= 0.01:
            mayor = max(SIGNOS, key=lambda s: out[s])
            out[mayor] = round(out[mayor] + desvio, 2)
    return out


def backtest_walk_forward(jornadas, k_encogimiento=K_ENCOGIMIENTO):
    """Para cada jornada (orden cronologico) calibra con la tabla construida SOLO con las anteriores."""
    sin, con = [], []
    detalle = []
    for j in jornadas:
        tabla = tabla_factores_hasta(jornadas, j["orden"], k_encogimiento)
        n_hist = sum(f["n"] for comp in tabla.values() for f in comp.values())
        ll_sin_j, ll_con_j = [], []
        for p in j["partidos"]:
            factor = tabla[p["competicion"]][p["franja"]]["factor"] if p["franja"] else 1.0
            cal = aplicar_factor(p["motor"], factor)
            it_sin = {"probs": p["motor"], "y": p["y"], "franja": p["franja"], "competicion": p["competicion"]}
            it_con = {"probs": cal, "y": p["y"], "franja": p["franja"], "competicion": p["competicion"]}
            sin.append(it_sin)
            con.append(it_con)
            ll_sin_j.append(it_sin)
            ll_con_j.append(it_con)
        detalle.append({"jornada": j["jornada"], "orden": j["orden"], "n": len(j["partidos"]),
                        "n_historia": n_hist, "log_loss_sin": round(log_loss(ll_sin_j), 5),
                        "log_loss_con": round(log_loss(ll_con_j), 5),
                        "x_reales": sum(1 for it in ll_sin_j if it["y"] == "X"),
                        "x_pred_sin": round(sum(it["probs"]["X"] for it in ll_sin_j), 2),
                        "x_pred_con": round(sum(it["probs"]["X"] for it in ll_con_j), 2)})
    out = {"n": len(sin), "sin_calibrar": _resumen_items(sin), "calibrado": _resumen_items(con)}
    out["sin_calibrar"]["por_franja"] = _por_franja(sin)
    out["calibrado"]["por_franja"] = _por_franja(con)
    for comp in COMPETICIONES:
        out["sin_calibrar"][f"por_franja_{comp}"] = _por_franja([it for it in sin if it["competicion"] == comp])
        out["calibrado"][f"por_franja_{comp}"] = _por_franja([it for it in con if it["competicion"] == comp])
    out["por_jornada"] = detalle
    out["jornadas_mejoran"] = sum(1 for d in detalle if d["log_loss_con"] < d["log_loss_sin"])
    out["jornadas_empeoran"] = sum(1 for d in detalle if d["log_loss_con"] > d["log_loss_sin"])
    return out


def evaluar_criterios(wf):
    """Aplica el criterio prerregistrado al walk-forward. Devuelve (veredicto, motivos)."""
    motivos = []
    ll_sin = wf["sin_calibrar"]["log_loss"]
    ll_con = wf["calibrado"]["log_loss"]
    c1 = ll_con is not None and ll_sin is not None and ll_con < ll_sin
    motivos.append(f"(1) log-loss walk-forward calibrado {ll_con} vs sin calibrar {ll_sin}: {'CUMPLE' if c1 else 'NO cumple'}")
    fuera = [e for e, f in wf["calibrado"]["por_franja"].items() if f.get("n", 0) > 0 and not f["intervalo_95"]["dentro"]]
    c2 = not fuera
    motivos.append("(2) X reales dentro del intervalo 95% de las X predichas calibradas en todas las franjas: "
                   + ("CUMPLE" if c2 else "NO cumple, fuera en " + ", ".join(fuera)))
    return ("DESPLEGAR" if (c1 and c2) else "NO_DESPLEGAR"), motivos


# ----------------------------------------------------------------------------
# c) funcion para el motor
# ----------------------------------------------------------------------------
_CACHE = {"ruta": None, "datos": None}


def cargar_backtest(ruta=SALIDA):
    ruta = Path(ruta)
    if _CACHE["ruta"] != str(ruta) or _CACHE["datos"] is None:
        _CACHE["ruta"] = str(ruta)
        _CACHE["datos"] = cargar_json(ruta, {}) or {}
    return _CACHE["datos"]


def calibrar_x_con_traza(probs, prob_favorito_bin=None, competicion="domestica", tabla=None, veredicto=None,
                         forzar=False, ruta=SALIDA):
    """Como calibrar_x pero devuelve (probs, traza). tabla/veredicto permiten inyectar sin leer disco."""
    frac, escala = _como_fraccion(probs)
    base = {s: round(v * 100.0, 2) for s, v in frac.items()} if escala == 100.0 else dict(frac)
    if tabla is None or veredicto is None:
        datos = cargar_backtest(ruta)
        tabla = tabla if tabla is not None else datos.get("tabla_factores") or {}
        veredicto = veredicto if veredicto is not None else datos.get("veredicto", "NO_DESPLEGAR")
    comp = "domestica" if str(competicion or "domestica").lower().startswith("dom") else "no_domestica"
    franja = franja_de(prob_favorito_bin) if prob_favorito_bin is not None else franja_de(prob_favorito_pct(frac))
    traza = {"activo": False, "veredicto": veredicto, "competicion": comp, "franja": franja, "factor": 1.0,
             "x_antes": round(frac["X"] * 100.0, 2), "x_despues": round(frac["X"] * 100.0, 2), "motivo": ""}
    if veredicto != "DESPLEGAR" and not forzar:
        traza["motivo"] = f"veredicto {veredicto}: factor 1 (no-op)"
        return base, traza
    factor = ((tabla.get(comp) or {}).get(franja) or {}).get("factor", 1.0) if franja else 1.0
    try:
        factor = float(factor)
    except (TypeError, ValueError):
        factor = 1.0
    if abs(factor - 1.0) < 1e-9:
        traza["motivo"] = "factor 1 en esta franja"
        return base, traza
    out = aplicar_factor(probs, factor)
    traza.update({"activo": True, "factor": round(factor, 4),
                  "x_despues": round(out["X"] if escala == 100.0 else out["X"] * 100.0, 2),
                  "motivo": f"X x{factor:.3f} por calibracion {comp} franja {franja}" + (" (forzado)" if forzar and veredicto != "DESPLEGAR" else "")})
    return out, traza


def calibrar_x(probs, prob_favorito_bin=None, competicion="domestica", **kw):
    """Probabilidades 1X2 con la X recalibrada por franja del favorito y competicion, en la escala de
    entrada (0-100 o 0-1), renormalizadas. Si el backtest dice NO_DESPLEGAR es un no-op salvo forzar=True."""
    return calibrar_x_con_traza(probs, prob_favorito_bin, competicion, **kw)[0]


# ----------------------------------------------------------------------------
# main
# ----------------------------------------------------------------------------
def _prerregistrar(ruta):
    """Escribe los criterios ANTES de calcular. Si ya existen en disco, se conservan los originales."""
    previo = cargar_json(ruta, {}) or {}
    criterios = previo.get("criterios_prerregistrados") or CRITERIOS_PRERREGISTRADOS
    salida = {"version": VERSION, "modulo": "calibracion_x", "generado_en": datetime.now(timezone.utc).isoformat(),
              "criterios_prerregistrados": criterios, "estado": "prerregistrado_sin_resultados"}
    guardar_json(ruta, salida)
    return salida


def ejecutar(ruta=SALIDA, dir_snapshots=SNAPSHOTS_DIR, dir_jornadas=JORNADAS_DIR, ruta_historico=HISTORICO):
    salida = _prerregistrar(ruta)
    criterios_fijados = json.dumps(salida["criterios_prerregistrados"], sort_keys=True)

    partidos = cargar_historico(ruta_historico)
    salida["historico_cuotas"] = backtest_historico(partidos)

    jornadas = cargar_snapshots(dir_snapshots, dir_jornadas)
    wf = backtest_walk_forward(jornadas)
    salida["snapshots"] = {"n_jornadas": len(jornadas), "n_partidos": wf["n"],
                           "orden_cronologico": [{"jornada": j["jornada"], "creado_en": j["orden"], "n": len(j["partidos"])}
                                                 for j in jornadas],
                           "walk_forward": wf}
    # tabla final con TODO el historial (para uso prospectivo desde ahora)
    todos = [{"franja": p["franja"], "competicion": p["competicion"], "p_x": p["motor"]["X"], "y": p["y"]}
             for j in jornadas for p in j["partidos"]]
    salida["tabla_factores"] = tabla_factores(todos)
    veredicto, motivos = evaluar_criterios(wf)
    salida["veredicto"] = veredicto
    salida["motivos_veredicto"] = motivos
    salida["estado"] = "con_resultados"
    salida["aviso"] = ("Cuaderno de Laboratorio: el motor no usa calibrar_x hasta que el veredicto sea DESPLEGAR y "
                       "Marc de el OK. Con ~500 partidos de snapshot no se puede demostrar una mejora de log-loss "
                       "< 0.005; el walk-forward solo evita la fuga de futuro, no sustituye a mas temporadas.")
    assert json.dumps(salida["criterios_prerregistrados"], sort_keys=True) == criterios_fijados
    guardar_json(ruta, salida)
    _CACHE["datos"] = None
    return salida


def _imprimir(salida):
    h = salida["historico_cuotas"]
    print(f"[calibracion_x] Historico cuotas: {h['n']} partidos")
    for nombre, b in h["metodos"].items():
        iv = b["intervalo_95"]
        print(f"  {nombre:14s} X pred {b['x_predichas']:7.1f} vs real {b['x_reales']:4d} "
              f"[{iv['lo']}-{iv['hi']}] p={iv['p_valor']:.3f} dentro={iv['dentro']} "
              f"logloss={b['log_loss']:.5f} rps={b['rps']:.5f}")
        for fr, f in b["por_franja"].items():
            if f.get("n"):
                print(f"      {fr:6s} n={f['n']:4d} Xpred={f['x_predichas']:6.1f} Xreal={f['x_reales']:3d} "
                      f"[{f['intervalo_95']['lo']}-{f['intervalo_95']['hi']}] dentro={f['intervalo_95']['dentro']}")
    print(f"  -> X menos sesgada: {h['metodo_x_sin_sesgo']}")
    s = salida["snapshots"]
    wf = s["walk_forward"]
    print(f"[calibracion_x] Snapshots: {s['n_jornadas']} jornadas, {s['n_partidos']} partidos con resultado")
    for etiqueta in ("sin_calibrar", "calibrado"):
        b = wf[etiqueta]
        print(f"  {etiqueta:13s} logloss={b['log_loss']:.5f} rps={b['rps']:.5f} Xpred={b['x_predichas']:.1f} "
              f"Xreal={b['x_reales']} dentro={b['intervalo_95']['dentro']}")
        for fr, f in b["por_franja"].items():
            if f.get("n"):
                print(f"      {fr:6s} n={f['n']:3d} Xpred={f['x_predichas']:5.1f} Xreal={f['x_reales']:3d} "
                      f"[{f['intervalo_95']['lo']}-{f['intervalo_95']['hi']}] dentro={f['intervalo_95']['dentro']}")
    print(f"  jornadas que mejoran/empeoran: {wf['jornadas_mejoran']}/{wf['jornadas_empeoran']}")
    print("  tabla factores (todo el historial):")
    for comp, franjas in salida["tabla_factores"].items():
        print("   ", comp, {fr: (f["n"], f["factor"]) for fr, f in franjas.items()})
    print(f"[calibracion_x] VEREDICTO: {salida['veredicto']}")
    for m in salida["motivos_veredicto"]:
        print("   ", m)


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
