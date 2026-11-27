"""Ranker de favoritos en riesgo (SOLO SOMBRA, 26/11/2026).

Origen: informe "Algoritmos contra nuestros fallos 1X2" (25/11/2026), punto 6
de implantacion. Para "que favorito cae" NO existe ningun metodo publicado con
mejora demostrada sobre el cierre del mercado (Bunker et al. 2024; Goto et al.
2026: las cuotas son dificiles de batir). Este modulo pone un numero a esa
afirmacion con nuestros datos y, mientras, aplica la regla de Marc "cubrir lo
que se nombra": UN favorito nombrado por jornada, con sus señales, para que el
ojeador lo valore.

Universo: partidos cuyo favorito por la mezcla 50/50 motor + Losilla tiene
probabilidad >= 0,60. Objetivo: el favorito NO sale.

Features (todas calculables con datos del repo, sin fuga de futuro):
  gap_market             p_mix(fav) - masa_LAE(fav)  (>0: la masa infrajuega al favorito;
                         <0: la masa lo sobrejuega). Absorbe la candidata interna
                         'favorito_distinto_mercado'.
  gap_motor_losilla      p_motor(fav) - p_losilla(fav)
  motor_fav_distinto_mercado  el favorito del motor no es el del mercado (bool)
  n_senales              señales de sorpresa_nombrada sobre los signos NO favoritos
                         (especialista de rol, banquillo nuevo, H2H adverso, empatador, mercado mas alto)
  es_europeo             algun equipo no es de 1a/2a espanola (bool)
  favorito_local         el favorito es el 1 (bool)
  prob_x_mix             probabilidad de X en la mezcla

Modelo: regresion logistica minima (Newton con ridge, numpy; sin sklearn),
ajustada WALK-FORWARD sobre los snapshots pre-cierre ordenados por FECHA REAL
(nunca por numero de jornada: el numero se reinicia en agosto). Para predecir
la jornada de fecha F solo se entrena con favoritos de jornadas de fecha < F.

CRITERIO PRERREGISTRADO (26/11/2026, antes de calcular; no se cambia despues):
  baseline = 1 - p_mix(fav). El ranker "SEPARA" si en walk-forward, con
  n >= 120 favoritos evaluados, su AUC supera la del baseline en >= 0,03.
  En otro caso "NO_SEPARA" (resultado esperado segun la literatura). En
  ningun caso el ranker cambia probabilidades ni boletos: es un orden de
  vigilancia para el ojeador.

Bloque en vivo: construir_bloque_ranker(prediccion, masa) -> 'favoritos_en_riesgo'
con el ranking, las features, 'signo_si_cae' y 'nombrado' (el top-1).
Marcador en sombra: data/memoria_ia/marcador_ranker_favoritos.json anota, por
jornada cerrada, si el nombrado cayo y en que puesto del ranking quedaron los
favoritos que de verdad cayeron (percentil medio: 0,5 = azar).

Donde llamarlo: despues de sorpresa_nombrada (usa sus señales) y antes de
columna_valiente (cuya lista 'gigantes_en_riesgo' es por masa; este ranking
es por score). Solo informa; jugar dinero lo decide Marc.
"""
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from columna_valiente import (cargar_masa, equipos_espanoles, es_espanol, masa_de, prediccion_publicable,
                              publicar_bloque_sombra)
from elige8_ev import _a_fraccion, probs_mix

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
PREDICCION = DATA / "predicciones" / "ultima_prediccion.json"
PREDICCIONES_DIR = DATA / "predicciones"
PRE_CIERRE = DATA / "backtesting" / "pre_cierre"
JORNADAS_DIR = DATA / "jornadas"
MARCADOR = DATA / "memoria_ia" / "marcador_ranker_favoritos.json"
BACKTEST = DATA / "memoria_ia" / "backtest_ranker_favoritos.json"

SIGNOS = ("1", "X", "2")
UMBRAL_FAVORITO = 0.60
FEATURES = ("gap_market", "gap_motor_losilla", "motor_fav_distinto_mercado", "n_senales",
            "es_europeo", "favorito_local", "prob_x_mix")
MIN_ENTRENAMIENTO = 40
MIN_N_CRITERIO = 120
MEJORA_AUC_MIN = 0.03
RIDGE = 1.0
NEWTON_ITER = 25
GRADUACION_MIN_JORNADAS = 10
GRADUACION_FACTOR = 1.2
GRADUACION_MIN_ACIERTOS = 4
DESPIDO_FRACCION = 0.6

AVISO_SOMBRA = ("Experimental, MODO SOMBRA: el ranker ordena favoritos por riesgo y nombra uno; no cambia "
                "probabilidades ni boletos. La literatura dice que nadie bate al mercado en esto; el marcador "
                "prospectivo decide. Jugar dinero lo decide siempre Marc.")
CRITERIO = (
    f"Prerregistrado 26/11/2026: universo favoritos con p_mix >= {UMBRAL_FAVORITO:.2f}; baseline = 1 - p_mix(fav). "
    f"Walk-forward por fecha real (entrenar solo con jornadas anteriores). SEPARA si n >= {MIN_N_CRITERIO} favoritos "
    f"evaluados y AUC_ranker - AUC_baseline >= {MEJORA_AUC_MIN:.2f}; si no, NO_SEPARA."
)
CRITERIO_MARCADOR = (
    f"Prerregistrado 26/11/2026: con >={GRADUACION_MIN_JORNADAS} jornadas cerradas, si el nombrado (top-1) cae "
    f">= {GRADUACION_FACTOR}x lo esperado (suma de 1 - p_fav) y >= {GRADUACION_MIN_ACIERTOS} veces -> 'candidata'; "
    f"si cae < {int(DESPIDO_FRACCION * 100)}% de lo esperado -> 'despido'; en otro caso 'en_prueba'."
)


def cargar_json(ruta, defecto=None):
    try:
        return json.loads(Path(ruta).read_text(encoding="utf-8"))
    except Exception:
        return defecto


def guardar_json(ruta, datos):
    Path(ruta).parent.mkdir(parents=True, exist_ok=True)
    Path(ruta).write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")


def _fecha(valor):
    try:
        return datetime.strptime(str(valor or "")[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Features
# ---------------------------------------------------------------------------

def _senales(partido, signos, fecha, fuentes):
    if not fecha or fuentes is None:
        return 0
    try:
        from sorpresa_nombrada import senales_candidata
    except Exception:
        return 0
    total = 0
    for s in signos:
        try:
            total += len(senales_candidata(partido, s, fecha, fuentes) or [])
        except Exception:
            continue
    return total


def features_partido(partido, masa=None, fecha=None, fuentes=None, espanoles=None, umbral=UMBRAL_FAVORITO):
    """Dict con features del favorito, o None si no hay favorito >= umbral."""
    num = partido.get("num")
    motor = _a_fraccion(partido.get("probabilidades"))
    mercado = partido.get("mercado_losilla") or {}
    losilla = _a_fraccion(mercado) if all(s in mercado for s in SIGNOS) else None
    mix = probs_mix(partido)
    fav = max(SIGNOS, key=lambda s: mix[s])
    p_fav = mix[fav]
    if p_fav < umbral:
        return None
    m = masa_de(partido, masa or {})
    if m:
        m = _a_fraccion(m)
        fuente_masa = "porcentajes_lae" if (masa or {}).get(num) else "mercado_losilla"
    else:
        m, fuente_masa = mix, "mix_motor"
    no_fav = [s for s in SIGNOS if s != fav]
    espanoles = espanoles if espanoles is not None else equipos_espanoles()
    europeo = not (es_espanol(partido.get("local"), espanoles) and es_espanol(partido.get("visitante"), espanoles))
    fav_motor = max(SIGNOS, key=lambda s: motor[s])
    fav_losilla = max(SIGNOS, key=lambda s: losilla[s]) if losilla else fav_motor
    return {
        "num": num, "local": partido.get("local"), "visitante": partido.get("visitante"),
        "favorito": fav, "p_fav": round(p_fav, 4), "p_motor_fav": round(motor[fav], 4),
        "p_losilla_fav": round(losilla[fav], 4) if losilla else None, "masa_fav": round(m[fav], 4),
        "fuente_masa": fuente_masa,
        "gap_market": round(p_fav - m[fav], 4),
        "gap_motor_losilla": round(motor[fav] - losilla[fav], 4) if losilla else 0.0,
        "motor_fav_distinto_mercado": int(fav_motor != fav_losilla),
        "n_senales": _senales(partido, no_fav, fecha, fuentes),
        "es_europeo": int(europeo),
        "favorito_local": int(fav == "1"),
        "prob_x_mix": round(mix["X"], 4),
        "signo_si_cae": max(no_fav, key=lambda s: mix[s]),
        "baseline": round(1 - p_fav, 4),
    }


def matriz(filas):
    return np.array([[float(f[k]) for k in FEATURES] for f in filas], dtype=float)


# ---------------------------------------------------------------------------
# Regresion logistica minima (Newton + ridge)
# ---------------------------------------------------------------------------

def ajustar_logistica(X, y, ridge=RIDGE, iteraciones=NEWTON_ITER):
    """Devuelve {'media','desvio','coef','intercepto'}; features estandarizadas."""
    X = np.asarray(X, dtype=float)
    y = np.asarray(y, dtype=float)
    media = X.mean(axis=0)
    desvio = X.std(axis=0)
    desvio[desvio == 0] = 1.0
    Z = np.hstack([np.ones((len(X), 1)), (X - media) / desvio])
    w = np.zeros(Z.shape[1])
    penal = np.eye(Z.shape[1]) * ridge
    penal[0, 0] = 0.0
    for _ in range(iteraciones):
        p = 1.0 / (1.0 + np.exp(-Z @ w))
        grad = Z.T @ (p - y) + penal @ w
        W = p * (1 - p)
        H = (Z * W[:, None]).T @ Z + penal
        try:
            paso = np.linalg.solve(H, grad)
        except np.linalg.LinAlgError:
            break
        w = w - paso
        if np.max(np.abs(paso)) < 1e-8:
            break
    return {"media": media.tolist(), "desvio": desvio.tolist(), "intercepto": float(w[0]), "coef": w[1:].tolist(),
            "features": list(FEATURES), "n": int(len(y)), "positivos": int(y.sum())}


def predecir(modelo, filas):
    if not modelo or not filas:
        return [f["baseline"] for f in filas]
    X = matriz(filas)
    Z = (X - np.array(modelo["media"])) / np.array(modelo["desvio"])
    logit = modelo["intercepto"] + Z @ np.array(modelo["coef"])
    return (1.0 / (1.0 + np.exp(-logit))).tolist()


# ---------------------------------------------------------------------------
# Metricas
# ---------------------------------------------------------------------------

def auc(scores, y):
    """AUC por rangos (Mann-Whitney), con empates a mitad."""
    pos = [s for s, t in zip(scores, y) if t]
    neg = [s for s, t in zip(scores, y) if not t]
    if not pos or not neg:
        return None
    total = 0.0
    for a in pos:
        for b in neg:
            total += 1.0 if a > b else (0.5 if a == b else 0.0)
    return round(total / (len(pos) * len(neg)), 4)


def _rangos(valores):
    orden = sorted(range(len(valores)), key=lambda i: valores[i])
    rangos = [0.0] * len(valores)
    i = 0
    while i < len(orden):
        j = i
        while j + 1 < len(orden) and valores[orden[j + 1]] == valores[orden[i]]:
            j += 1
        r = (i + j) / 2 + 1
        for k in range(i, j + 1):
            rangos[orden[k]] = r
        i = j + 1
    return rangos


def spearman(a, b):
    if len(a) < 3:
        return None
    ra, rb = _rangos(a), _rangos(b)
    ma, mb = sum(ra) / len(ra), sum(rb) / len(rb)
    num = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    den = math.sqrt(sum((x - ma) ** 2 for x in ra) * sum((y - mb) ** 2 for y in rb))
    return round(num / den, 4) if den else None


def percentil_caidos(scores, y):
    """Percentil medio (0 = primero del ranking, 1 = ultimo) de los favoritos
    que cayeron, ordenando por score descendente. 0,5 = azar."""
    caidos = [i for i, t in enumerate(y) if t]
    if not caidos or len(scores) < 2:
        return None
    orden = sorted(range(len(scores)), key=lambda i: -scores[i])
    pos = {i: r for r, i in enumerate(orden)}
    return round(sum(pos[i] / (len(scores) - 1) for i in caidos) / len(caidos), 4)


# ---------------------------------------------------------------------------
# Dataset y walk-forward
# ---------------------------------------------------------------------------

def fecha_jornada(jornada, dir_jornadas=None, pred=None):
    datos = cargar_json(Path(dir_jornadas or JORNADAS_DIR) / f"jornada_{jornada}.json", {}) or {}
    fechas = sorted(f for f in (_fecha(p.get("fecha")) for p in datos.get("partidos") or []) if f)
    if fechas:
        return fechas[0]
    return _fecha((pred or {}).get("fecha_generacion"))


def reales_jornada(jornada, dir_jornadas=None):
    datos = cargar_json(Path(dir_jornadas or JORNADAS_DIR) / f"jornada_{jornada}.json", {}) or {}
    reales = {p["num"]: str(p.get("signo_oficial") or "").upper() for p in datos.get("partidos") or []
              if isinstance(p.get("num"), int) and p["num"] <= 14}
    if len(reales) < 14 or any(s not in SIGNOS for s in reales.values()):
        return None
    return reales


def filas_jornada(pred, masa, reales, fecha, fuentes=None, espanoles=None, etiqueta=None):
    filas = []
    fechas_partidos = {}
    if isinstance(pred.get("jornada"), int):
        datos = cargar_json(JORNADAS_DIR / f"jornada_{pred['jornada']}.json", {}) or {}
        fechas_partidos = {p.get("num"): _fecha(p.get("fecha")) for p in datos.get("partidos") or []}
    for p in pred.get("partidos") or []:
        num = p.get("num")
        if not isinstance(num, int) or not 1 <= num <= 14:
            continue
        f = features_partido(p, masa, fechas_partidos.get(num) or fecha, fuentes, espanoles)
        if not f:
            continue
        f.update({"jornada": pred.get("jornada"), "temporada": etiqueta, "fecha": fecha.isoformat() if fecha else None,
                  "real": reales.get(num) if reales else None,
                  "cayo": int(reales.get(num) != f["favorito"]) if reales else None})
        filas.append(f)
    return filas


def construir_dataset(jornadas=None, dir_snapshots=None, dir_jornadas=None, fuentes=None, masa_por_jornada=None):
    """Favoritos de todos los snapshots pre-cierre con resultados, con fecha
    real. Si no se pasan `jornadas`, se usan todos los snapshots."""
    dir_snapshots = Path(dir_snapshots or PRE_CIERRE)
    espanoles = equipos_espanoles()
    if fuentes is None:
        try:
            from sorpresa_nombrada import cargar_fuentes
            fuentes = cargar_fuentes()
        except Exception as exc:
            # Sin fuentes la feature n_senales vale 0 en todas las filas: que se vea.
            print(f"AVISO ranker_favoritos: fuentes de senales no disponibles ({type(exc).__name__}: {exc}); "
                  "n_senales = 0 en todo el dataset.")
            fuentes = None
    dataset = []
    rutas = sorted(dir_snapshots.glob("jornada_*.json"))
    for ruta in rutas:
        snap = cargar_json(ruta, {}) or {}
        pred = snap.get("prediccion", snap)
        j = pred.get("jornada")
        if not isinstance(j, int) or (jornadas is not None and j not in jornadas) or not pred.get("partidos"):
            continue
        # Auditoria 26/11: el numero no identifica la jornada. Un snapshot de
        # otra temporada no se cruza con los resultados de jornada_N.json.
        from guardar_snapshot_prediccion import snapshot_de_otra_jornada
        datos_jornada = cargar_json(Path(dir_jornadas or JORNADAS_DIR) / f"jornada_{j}.json", {}) or {}
        if snapshot_de_otra_jornada(snap, datos_jornada):
            continue
        reales = reales_jornada(j, dir_jornadas)
        fecha = fecha_jornada(j, dir_jornadas, pred)
        if not reales or not fecha:
            continue
        # La temporada sale de la fecha real y del numero (corte a mediados
        # de agosto: la J76 de la 25/26 se jugo el 07-09/08/2026), no de julio.
        import cronologia_jornadas as cj
        etiqueta = cj.temporada_de_fecha(fecha, j)
        masa = (masa_por_jornada or {}).get(j) if masa_por_jornada is not None else cargar_masa(j, etiqueta)
        dataset.extend(filas_jornada(pred, masa or {}, reales, fecha, fuentes, espanoles, etiqueta))
    dataset.sort(key=lambda f: (f["fecha"], f["jornada"], f["num"]))
    return dataset


def filas_entrenamiento(dataset, fecha_iso):
    """Guardia anti-fuga: solo filas de jornadas con fecha ESTRICTAMENTE anterior."""
    return [f for f in dataset if f["fecha"] and f["fecha"] < fecha_iso]


def walk_forward(dataset, min_entrenamiento=MIN_ENTRENAMIENTO):
    evaluadas = []
    fechas = sorted({(f["fecha"], f["jornada"]) for f in dataset})
    for fecha, jornada in fechas:
        test = [f for f in dataset if f["fecha"] == fecha and f["jornada"] == jornada]
        train = filas_entrenamiento(dataset, fecha)
        if len(train) < min_entrenamiento or sum(f["cayo"] for f in train) < 5:
            continue
        modelo = ajustar_logistica(matriz(train), [f["cayo"] for f in train])
        scores = predecir(modelo, test)
        for f, s in zip(test, scores):
            evaluadas.append({**{k: f[k] for k in ("jornada", "temporada", "fecha", "num", "local", "visitante",
                                                   "favorito", "p_fav", "baseline", "cayo")},
                              "score": round(float(s), 4), "n_entrenamiento": len(train)})
    return evaluadas


def resumen_walk_forward(evaluadas):
    n = len(evaluadas)
    if not n:
        return {"n": 0, "veredicto": "SIN_DATOS"}
    y = [e["cayo"] for e in evaluadas]
    auc_r = auc([e["score"] for e in evaluadas], y)
    auc_b = auc([e["baseline"] for e in evaluadas], y)
    por_jornada = {}
    for e in evaluadas:
        por_jornada.setdefault((e["fecha"], e["jornada"]), []).append(e)
    sp_r, sp_b, pc_r, pc_b = [], [], [], []
    for filas in por_jornada.values():
        yy = [f["cayo"] for f in filas]
        if 0 < sum(yy) < len(yy):
            for lista, clave in ((sp_r, "score"), (sp_b, "baseline")):
                v = spearman([f[clave] for f in filas], yy)
                if v is not None:
                    lista.append(v)
            pc_r.append(percentil_caidos([f["score"] for f in filas], yy))
            pc_b.append(percentil_caidos([f["baseline"] for f in filas], yy))
    media = lambda xs: round(sum(xs) / len(xs), 4) if xs else None
    mejora = round(auc_r - auc_b, 4) if auc_r is not None and auc_b is not None else None
    if n < MIN_N_CRITERIO:
        veredicto, motivo = "NO_SEPARA", f"n={n} < {MIN_N_CRITERIO}: muestra insuficiente por prerregistro"
    elif mejora is not None and mejora >= MEJORA_AUC_MIN:
        veredicto, motivo = "SEPARA", f"AUC ranker {auc_r} vs baseline {auc_b} (+{mejora})"
    else:
        veredicto, motivo = "NO_SEPARA", f"AUC ranker {auc_r} vs baseline {auc_b} ({mejora:+} < {MEJORA_AUC_MIN})"
    return {"n": n, "caidos": int(sum(y)), "tasa_caida": round(sum(y) / n, 4), "auc_ranker": auc_r, "auc_baseline": auc_b,
            "mejora_auc": mejora, "spearman_intra_jornada_ranker": media(sp_r), "spearman_intra_jornada_baseline": media(sp_b),
            "percentil_caidos_ranker": media(pc_r), "percentil_caidos_baseline": media(pc_b),
            "jornadas_evaluadas": len(por_jornada), "veredicto": veredicto, "motivo": motivo}


def backtest(ruta_salida=BACKTEST, dataset=None, escribir=True):
    """Backtest prerregistrado: el criterio se escribe en el JSON antes que los numeros."""
    salida = {"generado_en": datetime.now(timezone.utc).isoformat(), "modo": "sombra", "criterio": CRITERIO,
              "features": list(FEATURES), "umbral_favorito": UMBRAL_FAVORITO, "min_entrenamiento": MIN_ENTRENAMIENTO}
    dataset = dataset if dataset is not None else construir_dataset()
    evaluadas = walk_forward(dataset)
    salida["dataset"] = {"favoritos": len(dataset), "caidos": int(sum(f["cayo"] for f in dataset)),
                         "jornadas": len({(f["fecha"], f["jornada"]) for f in dataset}),
                         "fuente_masa": sorted({f["fuente_masa"] for f in dataset})}
    salida["walk_forward"] = resumen_walk_forward(evaluadas)
    salida["evaluadas"] = evaluadas
    if len(dataset) >= MIN_ENTRENAMIENTO and sum(f["cayo"] for f in dataset) >= 5:
        modelo = ajustar_logistica(matriz(dataset), [f["cayo"] for f in dataset])
        salida["modelo_final"] = modelo
        salida["coeficientes_legibles"] = {k: round(v, 3) for k, v in zip(FEATURES, modelo["coef"])}
        salida["auc_in_sample"] = auc(predecir(modelo, dataset), [f["cayo"] for f in dataset])
    por_tramo = {}
    for f in dataset:
        tramo = "60-69" if f["p_fav"] < 0.70 else ("70-79" if f["p_fav"] < 0.80 else ">=80")
        d = por_tramo.setdefault(tramo, {"n": 0, "caidos": 0})
        d["n"] += 1
        d["caidos"] += f["cayo"]
    salida["caidas_por_tramo"] = {t: {**d, "tasa": round(d["caidos"] / d["n"], 3)} for t, d in sorted(por_tramo.items())}
    salida["lectura"] = ("El ranker NO separa mejor que 1 - p(fav): queda en sombra como orden de vigilancia y para "
                         "nombrar un favorito por jornada." if salida["walk_forward"]["veredicto"] != "SEPARA" else
                         "El ranker separa por encima del baseline en walk-forward: avisar a Marc antes de darle peso.")
    if escribir:
        guardar_json(ruta_salida, salida)
    return salida


# ---------------------------------------------------------------------------
# Bloque en vivo
# ---------------------------------------------------------------------------

def modelo_actual():
    return (cargar_json(BACKTEST, {}) or {}).get("modelo_final")


def construir_bloque_ranker(prediccion, masa=None, fechas=None, fuentes=None, modelo="auto", espanoles=None):
    """Bloque 'favoritos_en_riesgo': ranking de favoritos (>= 0,60) por score
    del ranker (o por baseline si no hay modelo), features, 'signo_si_cae' y
    'nombrado' = top-1 (uno por jornada: cubrir lo que se nombra).
    modelo: 'auto' carga el del backtest; None fuerza el baseline 1 - p(fav)."""
    jornada = prediccion.get("jornada")
    base = {"modo": "sombra", "generado_en": datetime.now(timezone.utc).isoformat(), "jornada": jornada,
            "aviso": AVISO_SOMBRA, "criterio": CRITERIO, "criterio_marcador": CRITERIO_MARCADOR}
    partidos = [p for p in prediccion.get("partidos") or [] if isinstance(p.get("num"), int) and 1 <= p["num"] <= 14]
    if len(partidos) < 14:
        return {**base, "estado": "no_disponible", "motivo": "prediccion incompleta"}
    if masa is None:
        masa = cargar_masa(jornada, partidos=partidos) if isinstance(jornada, int) else {}
    if fechas is None and isinstance(jornada, int):
        datos = cargar_json(JORNADAS_DIR / f"jornada_{jornada}.json", {}) or {}
        fechas = {p.get("num"): _fecha(p.get("fecha")) for p in datos.get("partidos") or []}
    fechas = fechas or {}
    if fuentes is None:
        # Auditoria 26/11: n_senales es una FEATURE del modelo. Si las fuentes
        # de señales no cargan, antes valia 0 en silencio para los 14 partidos
        # y el marcador prerregistrado media un modelo cojo: ahora no se puntua.
        try:
            from sorpresa_nombrada import cargar_fuentes
            fuentes = cargar_fuentes()
        except Exception as exc:
            return {**base, "estado": "no_disponible", "fuentes_senales": f"error: {type(exc).__name__}: {exc}",
                    "motivo": "no se pudieron cargar las fuentes de señales (feature n_senales): no se puntua"}
    modelo = modelo_actual() if modelo == "auto" else modelo
    espanoles = espanoles if espanoles is not None else equipos_espanoles()
    filas = []
    for p in partidos:
        f = features_partido(p, masa, fechas.get(p["num"]), fuentes, espanoles)
        if f:
            filas.append(f)
    if not filas:
        return {**base, "estado": "sin_favoritos", "motivo": f"ningun favorito >= {UMBRAL_FAVORITO:.2f} en la mezcla"}
    scores = predecir(modelo, filas) if modelo else [f["baseline"] for f in filas]
    for f, s in zip(filas, scores):
        f["score"] = round(float(s), 4)
    filas.sort(key=lambda f: (-f["score"], -f["baseline"], f["num"]))
    for i, f in enumerate(filas, start=1):
        f["puesto"] = i
    veredicto = ((cargar_json(BACKTEST, {}) or {}).get("walk_forward") or {}).get("veredicto")
    nombrado = filas[0]
    return {**base, "estado": "ok", "fuentes_senales": "ok",
            "origen_score": "ranker_logistico" if modelo else "baseline_1_menos_p",
            "veredicto_backtest": veredicto, "n_favoritos": len(filas), "ranking": filas,
            "nombrado": {k: nombrado[k] for k in ("num", "local", "visitante", "favorito", "p_fav", "masa_fav",
                                                 "score", "signo_si_cae", "n_senales", "gap_market")},
            "lectura": (f"Favorito nombrado: P{nombrado['num']} {nombrado['local']} - {nombrado['visitante']} "
                        f"(favorito {nombrado['favorito']} al {nombrado['p_fav'] * 100:.0f}%; si cae, "
                        f"{nombrado['signo_si_cae']}). Regla de Marc: lo que se nombra se cubre; el ranker solo ordena.")}


# ---------------------------------------------------------------------------
# Marcador de sombra
# ---------------------------------------------------------------------------

def evaluar_bloque(bloque, reales):
    ranking = bloque.get("ranking") or []
    caidos = [f for f in ranking if reales.get(f["num"]) != f["favorito"]]
    nombrado = bloque.get("nombrado") or {}
    n = len(ranking)
    return {
        "n_favoritos": n, "caidos": len(caidos),
        "caidos_detalle": [{"num": f["num"], "puesto": f["puesto"], "favorito": f["favorito"], "real": reales.get(f["num"])}
                           for f in caidos],
        "nombrado_num": nombrado.get("num"), "nombrado_esperado": round(1 - float(nombrado.get("p_fav") or 0), 4),
        "nombrado_cayo": bool(nombrado) and reales.get(nombrado.get("num")) != nombrado.get("favorito"),
        "nombrado_signo_si_cae_acierta": bool(nombrado) and reales.get(nombrado.get("num")) == nombrado.get("signo_si_cae"),
        "percentil_caidos": (round(sum((f["puesto"] - 1) / (n - 1) for f in caidos) / len(caidos), 4)
                             if caidos and n > 1 else None),
    }


def resumen_marcador(registros):
    n = len(registros)
    if not n:
        return {"jornadas_evaluadas": 0, "veredicto": "sin_datos", "criterio": CRITERIO_MARCADOR}
    aciertos = sum(1 for r in registros if r.get("nombrado_cayo"))
    esperados = round(sum(r.get("nombrado_esperado") or 0 for r in registros), 2)
    percentiles = [r["percentil_caidos"] for r in registros if r.get("percentil_caidos") is not None]
    if n >= GRADUACION_MIN_JORNADAS and aciertos >= GRADUACION_FACTOR * esperados and aciertos >= GRADUACION_MIN_ACIERTOS:
        veredicto = "candidata"
    elif n >= GRADUACION_MIN_JORNADAS and aciertos < DESPIDO_FRACCION * esperados:
        veredicto = "despido"
    else:
        veredicto = "en_prueba"
    # 'esperado' es el alias que pinta index.html (renderFavoritosRiesgo lee
    # resumen.esperado); 'nombrado_esperados' se conserva por compatibilidad.
    return {"jornadas_evaluadas": n, "nombrado_cayo": aciertos, "nombrado_esperados": esperados,
            "esperado": esperados,
            "signo_si_cae_aciertos": sum(1 for r in registros if r.get("nombrado_signo_si_cae_acierta")),
            "favoritos_total": sum(r.get("n_favoritos", 0) for r in registros),
            "caidos_total": sum(r.get("caidos", 0) for r in registros),
            "percentil_caidos_medio": round(sum(percentiles) / len(percentiles), 4) if percentiles else None,
            "veredicto": veredicto, "avisar_a_marc": veredicto == "candidata", "criterio": CRITERIO_MARCADOR}


def actualizar_marcador(dir_predicciones=None, dir_jornadas=None, ruta_marcador=None, etiqueta=None, ahora=None,
                        dir_snapshots=None):
    """Anota cada jornada cerrada con bloque publicado una sola vez (idempotente
    por (temporada, jornada)); las jornadas abiertas se saltan.

    Auditoria 26/11: el bloque se lee del snapshot PRE-CIERRE (no del espejo
    data/predicciones, que se reescribe con la jornada en juego) y la
    temporada sale de la fecha de la jornada, no de now(). dir_predicciones
    se conserva en la firma pero ya no se lee."""
    from senal_valiente import bloques_del_cierre
    dir_jornadas = Path(dir_jornadas or JORNADAS_DIR)
    ruta_marcador = Path(ruta_marcador or MARCADOR)
    ahora = ahora or datetime.now(timezone.utc)
    marcador = cargar_json(ruta_marcador, {}) or {}
    registros = marcador.get("registros") or []
    vistos = {(r.get("temporada"), r.get("jornada")) for r in registros}
    nuevas = 0
    for etiqueta, jornada, bloque, _pred, _datos in bloques_del_cierre(
            "favoritos_en_riesgo", dir_jornadas, dir_snapshots, etiqueta):
        if bloque.get("estado") != "ok" or (etiqueta, jornada) in vistos:
            continue
        reales = reales_jornada(jornada, dir_jornadas)
        if not reales:
            continue
        registros.append({"temporada": etiqueta, "jornada": jornada, "registrado_en": ahora.isoformat(),
                          **evaluar_bloque(bloque, reales)})
        vistos.add((etiqueta, jornada))
        nuevas += 1
    if not nuevas and marcador:
        return {"nuevas": 0, "resumen": marcador.get("resumen") or {}}
    registros.sort(key=lambda r: (r.get("temporada"), r.get("registrado_en")))
    resumen = resumen_marcador(registros)
    guardar_json(ruta_marcador, {"version": 1, "modo": "sombra", "actualizado_en": ahora.isoformat(),
                                 "criterio": CRITERIO_MARCADOR, "resumen": resumen, "registros": registros})
    return {"nuevas": nuevas, "resumen": resumen}


# ---------------------------------------------------------------------------
# Script (solo lectura por defecto)
# ---------------------------------------------------------------------------

def main():
    if "--backtest" in sys.argv:
        r = backtest()
        wf = r["walk_forward"]
        print(f"Backtest ranker favoritos: dataset {r['dataset']['favoritos']} favoritos / {r['dataset']['caidos']} caidos "
              f"en {r['dataset']['jornadas']} jornadas; walk-forward n={wf['n']} AUC ranker {wf.get('auc_ranker')} vs "
              f"baseline {wf.get('auc_baseline')} -> {wf['veredicto']} ({wf.get('motivo')})")
        print("  coeficientes:", json.dumps(r.get("coeficientes_legibles")))
        print("  caidas por tramo:", json.dumps(r["caidas_por_tramo"]))
        return
    prediccion = cargar_json(PREDICCION, {})
    publicar = "--solo-lectura" not in sys.argv
    if not prediccion:
        print("Sin ultima_prediccion.json; nada que rankear.")
        return
    # Auditoria 26/11: misma guarda que los demas modulos en sombra. Sobre una
    # prediccion bloqueada no se publica nada y el bloque anterior se retira.
    if not prediccion_publicable(prediccion):
        if publicar:
            publicar_bloque_sombra("favoritos_en_riesgo", None, prediccion, PREDICCION, PREDICCIONES_DIR)
        print("Prediccion bloqueada o no disponible; bloque favoritos_en_riesgo retirado.")
        return
    if not prediccion.get("partidos"):
        print("Sin partidos en ultima_prediccion.json; nada que rankear.")
        return
    bloque = construir_bloque_ranker(prediccion)
    jornada = prediccion.get("jornada")
    if bloque.get("estado") != "ok":
        # No se deja en disco el bloque de una ejecucion anterior.
        if publicar:
            publicar_bloque_sombra("favoritos_en_riesgo", None, prediccion, PREDICCION, PREDICCIONES_DIR)
        print(f"Ranker favoritos (sombra) J{jornada}: {bloque.get('estado')} - {bloque.get('motivo')}")
        return
    ascii_ = lambda t: str(t).encode("ascii", "replace").decode("ascii")
    print(f"Ranker favoritos (sombra) J{jornada}, score {bloque['origen_score']}, backtest {bloque.get('veredicto_backtest')}")
    for f in bloque["ranking"]:
        print(f"  {f['puesto']:>2}. P{f['num']:<2} {ascii_(f['local'])} - {ascii_(f['visitante'])}: fav {f['favorito']} "
              f"p {f['p_fav']:.2f} masa {f['masa_fav']:.2f} gap {f['gap_market']:+.2f} senales {f['n_senales']} "
              f"score {f['score']:.3f} si cae {f['signo_si_cae']}")
    print("  " + ascii_(bloque["lectura"]))
    if publicar:  # en el pipeline publica el bloque (sombra)
        publicar_bloque_sombra("favoritos_en_riesgo", bloque, prediccion, PREDICCION, PREDICCIONES_DIR)
        print("  bloque 'favoritos_en_riesgo' escrito en la prediccion.")


if __name__ == "__main__":
    main()
