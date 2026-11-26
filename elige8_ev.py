"""Elige 8: calculadora de EV y regla de edge (modo INFORMATIVO, 26/11/2026).

Origen: informe "Algoritmos contra nuestros fallos 1X2" (25/11/2026), punto 5
de implantacion. El Elige 8 de jueves construido con los 8 favoritos mas claros
es el peor perfil observado: cuando acierta, acierta el 9,6-15 % de las
apuestas y el premio queda en 1,82-2,85 EUR por 0,50 EUR apostados (J17, J22,
10/09). El premio por acertante es pari-mutuel puro: 0,55 x R / N, y como cada
apuesta cuesta 0,50 EUR, premio = 0,275 / (fraccion de apuestas ganadoras).
Lo que paga no es "Europa" ni "Liga": es que caiga algun favorito de la masa.

Que hace este modulo (NO toca aplicar_elige8_seguro.py ni la prediccion):

  1. Aritmetica: para cualquier seleccion de 8 partidos del boleto (con sus
     fijos/dobles/triples) P(8/8) = prod(masa cubierta), coste = 0,50 x
     prod(tamano del subconjunto) y break-even = coste / P.
  2. Premio condicional: una tabla empirica premio ~ numero de sorpresas de la
     jornada (sorpresa = el favorito de la masa LAE no sale), ajustada de forma
     monotona (PAVA) con los escrutinios 26/27 de
     data/memoria_ia/elige8_premios_historicos.json. E[premio | nuestros 8
     aciertan] se obtiene por Monte Carlo condicionado: los 8 elegidos se
     muestrean dentro del subconjunto jugado y los otros 6 libres; se cuenta
     cuantos favoritos de la masa caen y se consulta la tabla. Asi el EV
     recoge la correlacion negativa acierto-premio (cuando aciertas tu,
     aciertan muchos).
  3. Tres reglas de seleccion: 'mas_probables' (la actual: eficiencia =
     probabilidad cubierta / multiplicador), 'edge' (Clair & Letscher: a/p,
     seis partidos con edge >= 1 y hasta dos con a/p claramente > 1) y
     'triples_dentro' (los triples/dobles del boleto entran cubiertos al 100 %).
  4. Backtest PRERREGISTRADO (CRITERIO_BACKTEST) sobre las jornadas 26/27 con
     premio conocido, desde el snapshot pre-cierre. Salida en
     data/memoria_ia/backtest_elige8_ev.json.

Las probabilidades "reales" son la mezcla 50/50 motor + mercado Losilla
(cuotas = benchmark); la masa es el % LAE de porcentajes_lae (proxy de lo que
juega la masa en Elige 8, que SELAE no publica).

Donde llamarlo: despues de aplicar_elige8_seguro (lee la seleccion
'elige8_seguro' de la prediccion y la compara con las alternativas). Solo
informa; jugar dinero lo decide Marc.
"""
import json
import math
import random
import sys
from datetime import datetime, timezone
from pathlib import Path

from columna_valiente import cargar_masa, es_jornada_europea, masa_de

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
PREDICCION = DATA / "predicciones" / "ultima_prediccion.json"
PRE_CIERRE = DATA / "backtesting" / "pre_cierre"
JORNADAS_DIR = DATA / "jornadas"
PREMIOS = DATA / "memoria_ia" / "elige8_premios_historicos.json"
BACKTEST = DATA / "memoria_ia" / "backtest_elige8_ev.json"

SIGNOS = ("1", "X", "2")
PRECIO_ELIGE8 = 0.50
FRACCION_PREMIOS = 0.55
N_SELECCION = 8
UMBRAL_EDGE = 1.0
UMBRAL_VALOR = 1.15
MAX_VALOR = 2
MIN_EDGE = 6
MC_MUESTRAS = 4000
SEMILLA = 20261126
FACTOR_PREMIO = 3.0
FRACCION_MINIMA_DENTRO_FACTOR = 0.70
MASA_MINIMA = 0.005

AVISO = ("Calculadora informativa: el premio esperado sale de una tabla empirica con pocas jornadas "
         "(escrutinios 26/27) y de la masa LAE como proxy de lo que juega la gente en Elige 8. "
         "Jugar dinero lo decide Marc.")
CRITERIO_BACKTEST = (
    "Prerregistrado 26/11/2026, antes de calcular: sobre las jornadas 26/27 con premio de Elige 8 conocido, "
    "simuladas desde el snapshot pre-cierre, (a) la regla 'edge' no puede perder mas dinero neto que "
    "'mas_probables' y (b) E[premio | 8/8] de la calculadora (tabla ajustada SIN la jornada evaluada, "
    f"leave-one-out) debe quedar dentro de un factor {FACTOR_PREMIO:g} del premio real en al menos el "
    f"{int(FRACCION_MINIMA_DENTRO_FACTOR * 100)} % de las jornadas. Si falla cualquiera de las dos, veredicto "
    "NO_DESPLEGAR para la bandera 'recomendado' (la calculadora se publica solo como informacion)."
)


def cargar_json(ruta, defecto=None):
    try:
        return json.loads(Path(ruta).read_text(encoding="utf-8"))
    except Exception:
        return defecto


def guardar_json(ruta, datos):
    Path(ruta).parent.mkdir(parents=True, exist_ok=True)
    Path(ruta).write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# Preparacion de partidos
# ---------------------------------------------------------------------------

def signos_de(partido):
    texto = str(partido.get("signo_final") or partido.get("signo_base") or "").upper()
    signos = "".join(s for s in SIGNOS if s in texto)
    if signos:
        return signos
    probs = partido.get("probabilidades") or {}
    return max(SIGNOS, key=lambda s: float(probs.get(s, 0) or 0))


def _normalizar(d):
    total = sum(d.values())
    if total <= 0:
        return {s: 1.0 / 3 for s in SIGNOS}
    return {s: d[s] / total for s in SIGNOS}


def _a_fraccion(d):
    out = {s: max(float((d or {}).get(s, 0) or 0), 0.0) for s in SIGNOS}
    if sum(out.values()) > 1.5:
        out = {s: v / 100.0 for s, v in out.items()}
    return _normalizar(out)


def probs_mix(partido, peso_mercado=0.5):
    """Mezcla 50/50 motor + mercado Losilla, en fraccion [0,1]."""
    motor = _a_fraccion(partido.get("probabilidades"))
    mercado = partido.get("mercado_losilla") or {}
    if all(s in mercado for s in SIGNOS):
        mercado = _a_fraccion(mercado)
        return _normalizar({s: (1 - peso_mercado) * motor[s] + peso_mercado * mercado[s] for s in SIGNOS})
    return motor


def masa_partido(partido, masa):
    """Masa LAE (fraccion). Si no hay LAE usa Losilla, y si no, la mezcla."""
    m = masa_de(partido, masa or {})
    if m:
        return _a_fraccion(m), ("porcentajes_lae" if (masa or {}).get(partido.get("num")) else "mercado_losilla")
    return probs_mix(partido), "mix_motor"


def preparar_partidos(prediccion, masa=None):
    """Lista de 14 partidos con subconjunto jugado, p_mix, masa, p_cubierta,
    masa_cubierta y edge = p_cubierta / masa_cubierta."""
    prep = []
    for p in prediccion.get("partidos") or []:
        num = p.get("num")
        if not isinstance(num, int) or not 1 <= num <= 14:
            continue
        signos = signos_de(p)
        mix = probs_mix(p)
        m, fuente = masa_partido(p, masa)
        p_cub = 1.0 if len(signos) >= 3 else sum(mix[s] for s in signos)
        m_cub = 1.0 if len(signos) >= 3 else sum(m[s] for s in signos)
        prep.append({
            "num": num, "local": p.get("local"), "visitante": p.get("visitante"),
            "signos": signos, "mult": len(signos), "p_mix": mix, "masa": m, "fuente_masa": fuente,
            "fav_masa": max(SIGNOS, key=lambda s: m[s]), "fav_mix": max(SIGNOS, key=lambda s: mix[s]),
            "p_cubierta": round(p_cub, 4), "masa_cubierta": round(m_cub, 4),
            "edge": round(p_cub / max(m_cub, MASA_MINIMA), 3),
            "eficiencia": round(p_cub / len(signos), 4),
        })
    prep.sort(key=lambda x: x["num"])
    return prep


# ---------------------------------------------------------------------------
# Aritmetica de la seleccion
# ---------------------------------------------------------------------------

def evaluar_seleccion(prep, nums):
    """P(8/8), coste y break-even de una seleccion (lista de num)."""
    nums = sorted(set(nums))
    por_num = {x["num"]: x for x in prep}
    p, apuestas = 1.0, 1
    for n in nums:
        x = por_num[n]
        p *= x["p_cubierta"]
        apuestas *= x["mult"]
    coste = round(apuestas * PRECIO_ELIGE8, 2)
    return {"seleccion": nums, "p_8de8": round(p, 6), "apuestas": apuestas, "coste": coste,
            "break_even": round(coste / p, 2) if p > 0 else None}


# ---------------------------------------------------------------------------
# Tabla premio ~ numero de sorpresas (PAVA monotono)
# ---------------------------------------------------------------------------

def relevantes_top8(prep, n=N_SELECCION):
    """Los 8 partidos con el favorito de la masa mas alto: la seleccion tipica
    de la gente en Elige 8 (variante EXPLORATORIA, no prerregistrada)."""
    orden = sorted(prep, key=lambda x: (-x["masa"][x["fav_masa"]], x["num"]))
    return {x["num"] for x in orden[:n]}


def n_sorpresas(prep, reales, relevantes=None):
    """Cuantos favoritos de la masa NO salieron (entre los 14, o entre
    `relevantes` si se pasa un conjunto de num)."""
    return sum(1 for x in prep if (relevantes is None or x["num"] in relevantes)
               and reales.get(x["num"]) in SIGNOS and reales[x["num"]] != x["fav_masa"])


def ajustar_monotono(pares):
    """pares: [(n_sorpresas, premio)] -> {n: premio_ajustado}, log-premio no
    decreciente en n (pool adjacent violators, ponderado por cuenta)."""
    grupos = {}
    for n, premio in pares:
        if premio and premio > 0:
            grupos.setdefault(int(n), []).append(math.log(premio))
    if not grupos:
        return {}
    bloques = [[n, sum(v) / len(v), len(v)] for n, v in sorted(grupos.items())]
    bloques = [[[b[0]], b[1], b[2]] for b in bloques]
    i = 0
    while i < len(bloques) - 1:
        if bloques[i][1] > bloques[i + 1][1]:
            a, b = bloques[i], bloques[i + 1]
            peso = a[2] + b[2]
            bloques[i] = [a[0] + b[0], (a[1] * a[2] + b[1] * b[2]) / peso, peso]
            del bloques[i + 1]
            i = max(i - 1, 0)
        else:
            i += 1
    tabla = {}
    for ns, media, _ in bloques:
        for n in ns:
            tabla[n] = round(math.exp(media), 2)
    return tabla


def premio_por_sorpresas(tabla, n):
    """Consulta la tabla; fuera del rango observado se usa el extremo."""
    if not tabla:
        return None
    claves = sorted(tabla)
    if n in tabla:
        return tabla[n]
    if n < claves[0]:
        return tabla[claves[0]]
    if n > claves[-1]:
        return tabla[claves[-1]]
    inferior = max(k for k in claves if k < n)
    superior = min(k for k in claves if k > n)
    peso = (n - inferior) / (superior - inferior)
    return round(math.exp((1 - peso) * math.log(tabla[inferior]) + peso * math.log(tabla[superior])), 2)


# ---------------------------------------------------------------------------
# Premio condicional por Monte Carlo
# ---------------------------------------------------------------------------

def _muestrear(rng, probs, permitidos=None):
    signos = [s for s in SIGNOS if permitidos is None or s in permitidos]
    pesos = [probs[s] for s in signos]
    total = sum(pesos)
    if total <= 0:
        return rng.choice(signos)
    u = rng.random() * total
    acum = 0.0
    for s, w in zip(signos, pesos):
        acum += w
        if u <= acum:
            return s
    return signos[-1]


def premio_condicional(prep, nums, tabla, muestras=MC_MUESTRAS, semilla=SEMILLA, relevantes=None):
    """E[premio | los 8 elegidos aciertan]: los elegidos se muestrean DENTRO
    de su subconjunto (condicionar = renormalizar, con independencia), los
    otros 6 libres; se cuentan los favoritos de la masa que caen (entre los 14
    o entre `relevantes`, con la misma definicion que uso la tabla)."""
    if not tabla:
        return {"premio_esperado": None, "motivo": "sin tabla de premios"}
    rng = random.Random(semilla)
    elegidos = set(nums)
    premios, distribucion = [], {}
    for _ in range(muestras):
        caidos = 0
        for x in prep:
            signo = _muestrear(rng, x["p_mix"], x["signos"] if x["num"] in elegidos else None)
            if signo != x["fav_masa"] and (relevantes is None or x["num"] in relevantes):
                caidos += 1
        distribucion[caidos] = distribucion.get(caidos, 0) + 1
        premios.append(premio_por_sorpresas(tabla, caidos))
    premios.sort()
    k = len(premios)
    return {
        "premio_esperado": round(sum(premios) / k, 2),
        "premio_mediana": round(premios[k // 2], 2),
        "premio_p10": round(premios[int(k * 0.10)], 2),
        "premio_p90": round(premios[int(k * 0.90) - 1], 2),
        "sorpresas_esperadas": round(sum(n * c for n, c in distribucion.items()) / k, 2),
        "distribucion_sorpresas": {str(n): round(c / k, 3) for n, c in sorted(distribucion.items())},
        "muestras": k,
    }


# ---------------------------------------------------------------------------
# Reglas de seleccion
# ---------------------------------------------------------------------------

def seleccion_mas_probables(prep, n=N_SELECCION):
    """La regla actual de aplicar_elige8_seguro: eficiencia = p_cubierta / multiplicador."""
    orden = sorted(prep, key=lambda x: (-x["eficiencia"], -x["p_cubierta"], x["num"]))
    return sorted(x["num"] for x in orden[:n]), [{"num": x["num"], "motivo": "eficiencia"} for x in orden[:n]]


def seleccion_edge(prep, n=N_SELECCION, umbral_edge=UMBRAL_EDGE, umbral_valor=UMBRAL_VALOR,
                   max_valor=MAX_VALOR, min_edge=MIN_EDGE, max_mult=1):
    """Clair & Letscher: a/p. Hasta `min_edge` partidos con edge >= umbral_edge
    (los mas probables entre ellos), hasta `max_valor` con a/p >= umbral_valor
    (los de mas edge), y relleno con el resto por probabilidad. Solo fijos por
    defecto (max_mult=1) para comparar con 'mas_probables' al mismo coste; los
    dobles/triples (edge 1 por definicion y coste x2/x3) van en 'triples_dentro'."""
    candidatos = [x for x in prep if x["mult"] <= max_mult] or [x for x in prep if x["mult"] < 3]
    elegidos, detalle = [], []
    seguros = sorted([x for x in candidatos if x["edge"] >= umbral_edge], key=lambda x: (-x["p_cubierta"], x["num"]))
    for x in seguros[:min_edge]:
        elegidos.append(x["num"])
        detalle.append({"num": x["num"], "motivo": "edge>=%.2f" % umbral_edge, "edge": x["edge"]})
    valor = sorted([x for x in candidatos if x["num"] not in elegidos and x["edge"] >= umbral_valor],
                   key=lambda x: (-x["edge"], x["num"]))
    for x in valor[:max_valor]:
        if len(elegidos) >= n:
            break
        elegidos.append(x["num"])
        detalle.append({"num": x["num"], "motivo": "valor a/p>=%.2f" % umbral_valor, "edge": x["edge"]})
    relleno = 0
    for x in sorted(candidatos, key=lambda x: (-(x["edge"] >= umbral_edge), -x["p_cubierta"], x["num"])):
        if len(elegidos) >= n:
            break
        if x["num"] not in elegidos:
            elegidos.append(x["num"])
            relleno += 1
            detalle.append({"num": x["num"], "motivo": "relleno por probabilidad", "edge": x["edge"]})
    return sorted(elegidos), detalle + ([{"aviso": f"{relleno} partidos de relleno sin edge"}] if relleno else [])


def seleccion_triples_dentro(prep, n=N_SELECCION):
    """Los dobles/triples del boleto entran cubiertos (P=1 el triple); el
    resto se rellena con los fijos mas probables. Paga el multiplicador."""
    cubiertos = sorted([x for x in prep if x["mult"] > 1], key=lambda x: (-x["eficiencia"], x["num"]))[:n]
    elegidos = [x["num"] for x in cubiertos]
    for x in sorted(prep, key=lambda x: (-x["p_cubierta"], x["num"])):
        if len(elegidos) >= n:
            break
        if x["num"] not in elegidos:
            elegidos.append(x["num"])
    return sorted(elegidos), [{"num": k, "motivo": "cubierto" if k in {c["num"] for c in cubiertos} else "fijo"}
                              for k in sorted(elegidos)]


REGLAS = {
    "mas_probables": seleccion_mas_probables,
    "edge": seleccion_edge,
    "triples_dentro": seleccion_triples_dentro,
}


def evaluar_regla(prep, nums, tabla, muestras=MC_MUESTRAS, detalle=None, relevantes=None):
    base = evaluar_seleccion(prep, nums)
    cond = premio_condicional(prep, nums, tabla, muestras, relevantes=relevantes)
    premio = cond.get("premio_esperado")
    ev = round(base["p_8de8"] * premio - base["coste"], 2) if premio is not None else None
    recomendado = bool(ev is not None and ev > 0 and base["p_8de8"] * premio > base["coste"])
    if premio is None:
        motivo = "sin tabla de premios: no se puede estimar el EV"
    elif premio < base["break_even"]:
        motivo = (f"no_recomendado: E[premio | 8/8] {premio:.2f} EUR < break-even {base['break_even']:.2f} EUR "
                  f"(cuando aciertas tu, acierta la masa y el premio se diluye)")
    elif recomendado:
        motivo = f"recomendado: EV {ev:+.2f} EUR con P(8/8) {base['p_8de8'] * 100:.1f} % y premio esperado {premio:.2f} EUR"
    else:
        motivo = f"no_recomendado: EV {ev:+.2f} EUR"
    return {**base, **cond, "ev": ev, "recomendado": recomendado, "motivo": motivo,
            "detalle": detalle or [], "partidos": [
                {"num": n, "signos": x["signos"], "p_cubierta": x["p_cubierta"], "masa_cubierta": x["masa_cubierta"],
                 "edge": x["edge"]} for n, x in ((n, next(y for y in prep if y["num"] == n)) for n in base["seleccion"])]}


def tipo_jornada(prediccion):
    partidos = [p for p in prediccion.get("partidos") or [] if isinstance(p.get("num"), int) and p["num"] <= 14]
    try:
        europea, _ = es_jornada_europea(partidos)
    except Exception:
        europea = False
    return "europea" if europea else "domestica"


def evaluar_jornada(prediccion, masa, tabla, muestras=MC_MUESTRAS, seleccion_actual=None, modo_sorpresas="14"):
    """Evalua la seleccion actual (elige8_seguro) y las tres reglas.
    modo_sorpresas: '14' (prerregistrado: caidas del favorito de la masa entre
    los 14) o 'top8' (exploratorio: solo entre los 8 mas jugados); la tabla
    debe haberse ajustado con la misma definicion."""
    prep = preparar_partidos(prediccion, masa)
    if len(prep) < 14:
        return {"estado": "no_disponible", "motivo": "prediccion incompleta"}
    relevantes = relevantes_top8(prep) if modo_sorpresas == "top8" else None
    salida = {"estado": "ok", "jornada": prediccion.get("jornada"), "tipo_jornada": tipo_jornada(prediccion),
              "modo_sorpresas": modo_sorpresas, "aviso": AVISO,
              "fuente_masa": sorted({x["fuente_masa"] for x in prep}), "reglas": {}}
    actual = seleccion_actual or (prediccion.get("elige8_seguro") or {}).get("seleccionados")
    if actual and len(actual) == N_SELECCION:
        salida["reglas"]["actual_elige8_seguro"] = evaluar_regla(prep, actual, tabla, muestras, relevantes=relevantes)
    for nombre, fn in REGLAS.items():
        nums, detalle = fn(prep)
        salida["reglas"][nombre] = evaluar_regla(prep, nums, tabla, muestras, detalle, relevantes=relevantes)
    mejor = max(salida["reglas"].items(), key=lambda kv: kv[1]["ev"] if kv[1]["ev"] is not None else -1e9)
    salida["mejor_regla_por_ev"] = mejor[0]
    salida["alguna_recomendada"] = any(r["recomendado"] for r in salida["reglas"].values())
    veredicto = (cargar_json(BACKTEST, {}) or {}).get("veredicto")
    salida["veredicto_backtest"] = veredicto
    salida["bandera_recomendado_publicable"] = veredicto == "DESPLEGAR_BANDERA"
    if not salida["bandera_recomendado_publicable"]:
        salida["lectura_bandera"] = ("La bandera 'recomendado' es solo informativa: el backtest prerregistrado dio "
                                     f"{veredicto or 'sin backtest'}; valen P(8/8), coste, break-even y premio esperado.")
    return salida


# ---------------------------------------------------------------------------
# Datos historicos y backtest prerregistrado
# ---------------------------------------------------------------------------

def _reales(jornada, dir_jornadas=None):
    datos = cargar_json(Path(dir_jornadas or JORNADAS_DIR) / f"jornada_{jornada}.json", {}) or {}
    reales = {p["num"]: str(p.get("signo_oficial") or "").upper() for p in datos.get("partidos") or []
              if isinstance(p.get("num"), int) and p["num"] <= 14}
    if len(reales) < 14 or any(s not in SIGNOS for s in reales.values()):
        return None
    return reales


def _snapshot(jornada, dir_snapshots=None):
    snap = cargar_json(Path(dir_snapshots or PRE_CIERRE) / f"jornada_{jornada}.json", {}) or {}
    pred = snap.get("prediccion", snap)
    return pred if pred.get("partidos") else None


def datos_historicos(premios=None, etiqueta="2026_2027", dir_snapshots=None, dir_jornadas=None, masa_por_jornada=None):
    """Para cada jornada con premio conocido Y masa LAE Y resultados: prep,
    reales, n_sorpresas y premio. Las jornadas sin masa LAE (2025/26) quedan
    fuera de la tabla, que exige la misma definicion de sorpresa en todas."""
    premios = premios if premios is not None else (cargar_json(PREMIOS, {}) or {}).get("jornadas", [])
    filas = []
    for fila in premios:
        if fila.get("temporada") != etiqueta:
            continue
        j = fila.get("jornada")
        pred = _snapshot(j, dir_snapshots)
        reales = _reales(j, dir_jornadas)
        masa = (masa_por_jornada or {}).get(j) if masa_por_jornada is not None else cargar_masa(j, etiqueta)
        if not pred or not reales or not masa:
            continue
        prep = preparar_partidos(pred, masa)
        if len(prep) < 14:
            continue
        filas.append({"jornada": j, "fecha": fila.get("fecha"), "tipo": fila.get("tipo"), "pred": pred, "prep": prep,
                      "reales": reales, "n_sorpresas": n_sorpresas(prep, reales),
                      "n_sorpresas_top8": n_sorpresas(prep, reales, relevantes_top8(prep)),
                      "premio": float(fila["premio_eur"]), "acertantes": fila.get("acertantes")})
    filas.sort(key=lambda f: str(f.get("fecha")))
    return filas


def tabla_desde_filas(filas, excluir=None, clave="n_sorpresas"):
    return ajustar_monotono([(f[clave], f["premio"]) for f in filas if f["jornada"] != excluir])


def acierta(prep, nums, reales):
    por_num = {x["num"]: x for x in prep}
    return all(reales.get(n) in por_num[n]["signos"] for n in nums)


def backtest(etiqueta="2026_2027", muestras=1500, ruta_salida=BACKTEST, filas=None, escribir=True):
    """Backtest prerregistrado (CRITERIO_BACKTEST). Se escribe el criterio en
    el JSON ANTES de los numeros; la tabla LOO evita medir la calculadora con
    la jornada que se esta evaluando."""
    filas = filas if filas is not None else datos_historicos(etiqueta=etiqueta)
    salida = {"generado_en": datetime.now(timezone.utc).isoformat(), "modo": "informativo", "criterio": CRITERIO_BACKTEST,
              "parametros": {"umbral_edge": UMBRAL_EDGE, "umbral_valor": UMBRAL_VALOR, "max_valor": MAX_VALOR,
                             "min_edge": MIN_EDGE, "mezcla": "50% motor + 50% Losilla", "masa": "porcentajes_lae",
                             "muestras_mc": muestras},
              "jornadas": [], "por_regla": {}, "tabla_premio_por_sorpresas": {}, "veredicto": None}
    if not filas:
        salida["veredicto"] = "SIN_DATOS"
        if escribir:
            guardar_json(ruta_salida, salida)
        return salida
    acum = {r: {"jornadas": 0, "aciertos_8de8": 0, "coste": 0.0, "premio": 0.0} for r in REGLAS}
    dentro_factor, evaluadas, dentro_factor_top8 = 0, 0, 0
    for f in filas:
        tabla_loo = tabla_desde_filas(filas, excluir=f["jornada"])
        tabla_loo_top8 = tabla_desde_filas(filas, excluir=f["jornada"], clave="n_sorpresas_top8")
        fila = {"jornada": f["jornada"], "fecha": f["fecha"], "tipo": f["tipo"], "n_sorpresas": f["n_sorpresas"],
                "n_sorpresas_top8": f["n_sorpresas_top8"],
                "premio_real": f["premio"], "acertantes": f["acertantes"], "reglas": {}}
        for nombre, fn in REGLAS.items():
            nums, _ = fn(f["prep"])
            ev = evaluar_regla(f["prep"], nums, tabla_loo, muestras)
            hit = acierta(f["prep"], nums, f["reales"])
            cobrado = round(f["premio"] if hit else 0.0, 2)
            fila["reglas"][nombre] = {"seleccion": nums, "p_8de8": ev["p_8de8"], "coste": ev["coste"],
                                      "break_even": ev["break_even"], "premio_esperado_loo": ev["premio_esperado"],
                                      "recomendado_loo": ev["recomendado"], "acierto_8de8": hit,
                                      "premio_cobrado": cobrado, "neto": round(cobrado - ev["coste"], 2)}
            a = acum[nombre]
            a["jornadas"] += 1
            a["aciertos_8de8"] += int(hit)
            a["coste"] += ev["coste"]
            a["premio"] += cobrado
            if nombre == "mas_probables" and ev["premio_esperado"]:
                evaluadas += 1
                ratio = ev["premio_esperado"] / f["premio"]
                fila["ratio_estimado_real"] = round(ratio, 2)
                dentro_factor += int(1 / FACTOR_PREMIO <= ratio <= FACTOR_PREMIO)
                cond8 = premio_condicional(f["prep"], nums, tabla_loo_top8, muestras, relevantes=relevantes_top8(f["prep"]))
                if cond8.get("premio_esperado"):
                    ratio8 = cond8["premio_esperado"] / f["premio"]
                    fila["ratio_estimado_real_top8_exploratorio"] = round(ratio8, 2)
                    dentro_factor_top8 += int(1 / FACTOR_PREMIO <= ratio8 <= FACTOR_PREMIO)
        salida["jornadas"].append(fila)
    for nombre, a in acum.items():
        salida["por_regla"][nombre] = {**{k: round(v, 2) for k, v in a.items()}, "neto": round(a["premio"] - a["coste"], 2)}
    frac = dentro_factor / evaluadas if evaluadas else 0.0
    neto_edge = salida["por_regla"]["edge"]["neto"]
    neto_mp = salida["por_regla"]["mas_probables"]["neto"]
    salida["chequeos"] = {
        "edge_no_pierde_mas_que_mas_probables": neto_edge >= neto_mp,
        "neto_edge": neto_edge, "neto_mas_probables": neto_mp,
        "fraccion_dentro_factor": round(frac, 3), "jornadas_dentro_factor": dentro_factor, "jornadas_evaluadas": evaluadas,
        "calculadora_dentro_factor_ok": frac >= FRACCION_MINIMA_DENTRO_FACTOR,
    }
    ok = salida["chequeos"]["edge_no_pierde_mas_que_mas_probables"] and salida["chequeos"]["calculadora_dentro_factor_ok"]
    salida["veredicto"] = "DESPLEGAR_BANDERA" if ok else "NO_DESPLEGAR"
    salida["lectura"] = (
        "La bandera 'recomendado' puede publicarse." if ok else
        "La bandera 'recomendado' NO se despliega; la calculadora se publica solo como informacion (P, coste, "
        "break-even, premio esperado y EV).")
    salida["tabla_premio_por_sorpresas"] = {str(k): v for k, v in sorted(tabla_desde_filas(filas).items())}
    salida["exploratorio_top8"] = {
        "aviso": ("NO prerregistrado, calculado despues de ver la tabla de 14: sorpresas contadas solo entre los 8 "
                  "partidos con el favorito de la masa mas alto (la seleccion tipica de la gente). No decide el "
                  "veredicto; si se quisiera usar habria que prerregistrarlo y medirlo en jornadas nuevas."),
        "tabla_premio_por_sorpresas_top8": {str(k): v for k, v in sorted(tabla_desde_filas(filas, clave="n_sorpresas_top8").items())},
        "fraccion_dentro_factor_loo": round(dentro_factor_top8 / evaluadas, 3) if evaluadas else None,
        "jornadas_dentro_factor": dentro_factor_top8,
    }
    salida["puntos_tabla"] = [{"jornada": f["jornada"], "tipo": f["tipo"], "n_sorpresas": f["n_sorpresas"],
                               "n_sorpresas_top8": f["n_sorpresas_top8"], "premio": f["premio"]} for f in filas]
    por_tipo = {}
    for f in filas:
        d = por_tipo.setdefault(f["tipo"] or "sin_tipo", {"jornadas": 0, "sorpresas": 0, "premios": []})
        d["jornadas"] += 1
        d["sorpresas"] += f["n_sorpresas"]
        d["premios"].append(f["premio"])
    salida["por_tipo_jornada"] = {t: {"jornadas": d["jornadas"], "sorpresas_medias": round(d["sorpresas"] / d["jornadas"], 2),
                                      "premio_mediana": sorted(d["premios"])[len(d["premios"]) // 2]} for t, d in por_tipo.items()}
    if escribir:
        guardar_json(ruta_salida, salida)
    return salida


def tabla_actual():
    """Tabla para uso en vivo: la del backtest si existe, si no se ajusta ahora."""
    bt = cargar_json(BACKTEST, {}) or {}
    tabla = {int(k): float(v) for k, v in (bt.get("tabla_premio_por_sorpresas") or {}).items()}
    if tabla:
        return tabla
    return tabla_desde_filas(datos_historicos())


# ---------------------------------------------------------------------------
# Vivo (solo lectura)
# ---------------------------------------------------------------------------

def _linea(nombre, r):
    return (f"  {nombre:<22} P(8/8) {r['p_8de8'] * 100:5.1f}%  coste {r['coste']:5.2f}  break-even {r['break_even']:7.2f}  "
            f"E[premio|8/8] {r['premio_esperado'] if r['premio_esperado'] is not None else float('nan'):8.2f}  "
            f"EV {r['ev'] if r['ev'] is not None else float('nan'):+7.2f}  "
            f"{'RECOMENDADO' if r['recomendado'] else 'no recomendado'}  sel {r['seleccion']}")


def main():
    if "--backtest" in sys.argv:
        r = backtest()
        print(f"Backtest Elige 8 EV ({len(r['jornadas'])} jornadas): veredicto {r['veredicto']}")
        for nombre, a in r["por_regla"].items():
            print(f"  {nombre:<16} 8/8 {a['aciertos_8de8']}/{a['jornadas']}  coste {a['coste']:.2f}  cobrado {a['premio']:.2f}  neto {a['neto']:+.2f}")
        print("  chequeos:", json.dumps(r["chequeos"]))
        return
    prediccion = cargar_json(PREDICCION, {})
    if not prediccion or not prediccion.get("partidos"):
        print("Sin ultima_prediccion.json; nada que evaluar.")
        return
    jornada = prediccion.get("jornada")
    masa = cargar_masa(jornada) if isinstance(jornada, int) else {}
    tabla = tabla_actual()
    r = evaluar_jornada(prediccion, masa, tabla)
    if r.get("estado") != "ok":
        print(f"Elige 8 EV J{jornada}: {r.get('estado')} - {r.get('motivo')}")
        return
    print(f"Elige 8 EV J{jornada} ({r['tipo_jornada']}, masa: {', '.join(r['fuente_masa'])}) - solo informacion")
    print(f"  tabla premio~sorpresas: {json.dumps({str(k): v for k, v in sorted(tabla.items())})}")
    for nombre, regla in r["reglas"].items():
        print(_linea(nombre, regla))
    print(f"  mejor regla por EV: {r['mejor_regla_por_ev']}; alguna recomendada: {r['alguna_recomendada']}")
    bt = cargar_json(BACKTEST, {}) or {}
    if bt.get("veredicto"):
        print(f"  veredicto backtest para la bandera 'recomendado': {bt['veredicto']}")
    if "--solo-lectura" not in sys.argv:  # en el pipeline publica el bloque (solo informacion)
        r["veredicto_backtest"] = bt.get("veredicto")
        r["aviso"] = ("Calculadora informativa: P(8/8), coste, break-even y premio esperado condicionado a la jornada. "
                      "La bandera 'recomendado' NO se despliega (backtest NO_DESPLEGAR). Jugar lo decide Marc.")
        prediccion["elige8_ev"] = r
        guardar_json(PREDICCION, prediccion)
        espejo = PREDICCION.parent / f"jornada_{jornada}.json"
        if isinstance(jornada, int) and espejo.exists():
            datos = cargar_json(espejo, {})
            if datos.get("jornada") == jornada:
                datos["elige8_ev"] = r
                guardar_json(espejo, datos)


if __name__ == "__main__":
    main()
