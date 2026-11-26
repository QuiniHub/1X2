"""Mezcla de Benter (modelo + mercado en escala log) -- pieza de Laboratorio.

Pregunta prerregistrada (DECISION_LOG 25/11, implantacion 4 de "Algoritmos
contra nuestros fallos 1X2"): el motor mezcla hoy sus probabilidades con el
consenso de mercado (Losilla) con un peso FIJO por calidad de dato
(baja 0,65 / media_baja 0,45 / alta 0,20; motor_prediccion_quiniela.
PESO_MERCADO_LOSILLA_POR_CALIDAD) y en escala LINEAL. La literatura
(Benter 1994; OddsPapi second-stage; arXiv 2608.11505) dice que la mezcla se
ESTIMA, en escala log:

    c_i  proporcional a  exp(alpha * ln p_motor_i + beta * ln q_mercado_i)

con alpha, beta ajustados por log-verosimilitud multinomial sobre
predicciones out-of-sample, y que el resultado honesto mas probable es
alpha ~ 0 (el motor no aporta nada a la probabilidad y debe quedarse solo
como generador de dobles).

Datos: snapshots inmutables pre-cierre (data/backtesting/pre_cierre) con
   - probabilidades      : motor DESPUES de la mezcla lineal con el mercado
   - mercado_losilla     : consenso de mercado (1/X/2 en %)
   - ajuste_mercado_losilla.lecturas : texto "peso 0.XX" realmente usado
 y el signo oficial de data/jornadas/jornada_N.json.

Probabilidad PRE-mezcla del motor: se recupera invirtiendo la mezcla lineal
   p_pre = (p_post - peso * q) / (1 - peso), recorte a [0,01, 0,98] y
   renormalizacion. ADVERTENCIA documentada: despues de la mezcla el motor
   aplica todavia lesiones, revulsivo y motivacion, asi que "p_pre" es el
   motor sin mercado MAS esos retoques posteriores (que son informacion del
   motor, no del mercado) y el recorte introduce un pequeño error cuando el
   motor estaba muy lejos del mercado. Es la mejor reconstruccion posible sin
   re-ejecutar el motor del pasado.

Validacion: walk-forward por jornada en ORDEN CRONOLOGICO (nunca por numero
de jornada: la numeracion de LAE reinicia en cada temporada), ajustando en
todas las jornadas anteriores y prediciendo la siguiente; ademas
leave-one-season-out si hay dos temporadas. Bootstrap emparejado POR JORNADA
(los 14 partidos de una jornada no son independientes para el pool).

Criterio prerregistrado (escrito en el JSON antes de los resultados):
Benter es "CANDIDATA" solo si alpha > 0 en >= 80 % de los folds Y su
log-loss walk-forward bate a la vez al mercado solo y al motor actual
(motor_post). Si no, veredicto NO_DESPLEGAR. Este modulo NO toca el motor:
`cargar_parametros()` devuelve None mientras el veredicto sea NO_DESPLEGAR.

Salida: data/memoria_ia/mezcla_benter.json
"""
from __future__ import annotations

import json
import math
import random
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    import numpy as np
except Exception:  # pragma: no cover - numpy es dependencia del proyecto
    np = None

try:
    from scipy.optimize import minimize as _scipy_minimize
except Exception:  # pragma: no cover
    _scipy_minimize = None

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
PRE_CIERRE = DATA / "backtesting" / "pre_cierre"
JORNADAS = DATA / "jornadas"
SALIDA = DATA / "memoria_ia" / "mezcla_benter.json"

SIGNOS = ("1", "X", "2")
P_MIN, P_MAX = 0.01, 0.98          # recorte al invertir la mezcla lineal
EPS = 1e-9

# Frenos prerregistrados (no se tocan despues de ver los datos).
MIN_PARTIDOS_ENTRENAMIENTO = 56     # 4 jornadas completas antes del primer fold
FRACCION_FOLDS_ALPHA_POSITIVO = 0.80
BOOTSTRAP_REPETICIONES = 2000
BOOTSTRAP_SEMILLA = 20261125
DELTA_LOGLOSS_REFERENCIA = 0.01     # con n~400-500 partidos solo se detecta ~>=0,01
MEZCLA_LINEAL_REFERENCIA = 0.5      # el 50/50 de Egidi, como control negativo

CRITERIO_PRERREGISTRADO = {
    "fecha": "2026-11-25",
    "origen": "reports/Algoritmos contra nuestros fallos 1X2.md, implantacion 4 (Benter walk-forward)",
    "candidata_si": [
        f"alpha > 0 en >= {int(FRACCION_FOLDS_ALPHA_POSITIVO * 100)} % de los folds walk-forward",
        "log-loss walk-forward de Benter < log-loss del mercado solo",
        "log-loss walk-forward de Benter < log-loss del motor actual (motor_post, pesos fijos por calidad)",
    ],
    "si_no": "NO_DESPLEGAR: el motor sigue como generador de dobles/triples; la probabilidad no cambia",
    "nota_potencia": (
        f"Con n~400-500 partidos emparejados solo es detectable un delta de log-loss del orden de >= "
        f"{DELTA_LOGLOSS_REFERENCIA} (se publica el IC95 bootstrap por jornada real); una diferencia menor "
        "es ruido aunque tenga el signo deseado."
    ),
    "temperatura": (
        "La recalibracion por temperatura se ajusta en los folds de entrenamiento y se aplica fuera de muestra. "
        "Para Benter T es matematicamente redundante (alpha y beta ya absorben la escala) y debe salir ~1; "
        "se publica como control. Donde importa es en la mezcla lineal (Ranjan & Gneiting 2010)."
    ),
}

MESES_ES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6, "julio": 7,
    "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
}

# Espejo de PESO_MERCADO_LOSILLA_POR_CALIDAD del motor: SOLO se usa si la
# lectura del snapshot no trae el "peso 0.XX" (snapshots antiguos). El valor
# vivo se intenta importar del motor en tiempo de ejecucion.
_PESOS_POR_CALIDAD_RESPALDO = {"profesional": 0.15, "alta": 0.20, "media": 0.35, "media_baja": 0.45, "baja": 0.65}
_PESO_DEFECTO_RESPALDO = 0.18


def ahora_iso():
    return datetime.now(timezone.utc).isoformat()


def cargar_json(path, defecto=None):
    path = Path(path)
    if not path.exists():
        return {} if defecto is None else defecto
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {} if defecto is None else defecto


def guardar_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


# --------------------------------------------------------------------------
# Utilidades de probabilidad
# --------------------------------------------------------------------------
def normalizar(probs):
    """Dict 1/X/2 (en % o en fraccion) -> dict en fraccion que suma 1."""
    vals = {s: max(float((probs or {}).get(s) or 0.0), 0.0) for s in SIGNOS}
    total = sum(vals.values())
    if total <= 0:
        return {s: 1.0 / 3 for s in SIGNOS}
    return {s: vals[s] / total for s in SIGNOS}


def recortar_y_normalizar(probs, p_min=P_MIN, p_max=P_MAX):
    vals = {s: min(max(float(probs.get(s, 0.0)), p_min), p_max) for s in SIGNOS}
    total = sum(vals.values())
    return {s: vals[s] / total for s in SIGNOS}


def invertir_mezcla_lineal(p_post, mercado, peso):
    """Recupera la probabilidad del motor ANTES de la mezcla lineal
    p_post = (1-peso)*p_pre + peso*q  =>  p_pre = (p_post - peso*q)/(1-peso).

    Entradas en % o fraccion (se normalizan). Recorte a [0,01, 0,98] y
    renormalizacion: cuando el motor estaba lejisimos del mercado la
    inversion puede dar valores negativos o >1; el recorte los devuelve al
    simplex a costa de un pequeño error (documentado en la cabecera)."""
    peso = float(peso)
    post = normalizar(p_post)
    q = normalizar(mercado)
    if peso >= 1.0 - 1e-6:
        return dict(post)
    if peso <= 0.0:
        return dict(post)
    bruto = {s: (post[s] - peso * q[s]) / (1.0 - peso) for s in SIGNOS}
    return recortar_y_normalizar(bruto)


def mezclar_lineal(p, q, peso):
    p, q = normalizar(p), normalizar(q)
    return {s: (1.0 - peso) * p[s] + peso * q[s] for s in SIGNOS}


def mezclar_benter(p_motor, q_mercado, alpha, beta, T=1.0):
    """Mezcla de Benter: c_i prop. exp((alpha*ln p_i + beta*ln q_i)/T).

    p_motor y q_mercado son dicts 1/X/2 en % o en fraccion. Devuelve un dict
    en la MISMA escala que p_motor (si p_motor suma ~100 devuelve %), para
    poder sustituir la salida de ajustar_por_mercado_losilla sin tocar el
    resto del motor. T=1 es la mezcla pura; T>1 aplana, T<1 afila."""
    escala = sum(float((p_motor or {}).get(s) or 0.0) for s in SIGNOS)
    escala = 100.0 if escala > 1.5 else 1.0
    p = normalizar(p_motor)
    q = normalizar(q_mercado)
    T = max(float(T), 1e-6)
    logit = {s: (float(alpha) * math.log(max(p[s], EPS)) + float(beta) * math.log(max(q[s], EPS))) / T for s in SIGNOS}
    tope = max(logit.values())
    expo = {s: math.exp(logit[s] - tope) for s in SIGNOS}
    total = sum(expo.values())
    return {s: expo[s] / total * escala for s in SIGNOS}


def rps_fila(probs, indice_real):
    """RPS de una fila (lista [p1, pX, p2] en fraccion, indice real 0/1/2)."""
    acum_p = acum_o = suma = 0.0
    for i in range(2):
        acum_p += probs[i]
        acum_o += 1.0 if i == indice_real else 0.0
        suma += (acum_p - acum_o) ** 2
    return suma / 2.0


# --------------------------------------------------------------------------
# Dataset
# --------------------------------------------------------------------------
def parsear_fecha_jornada(texto, respaldo=None):
    """'Domingo, 16 de agosto de 2026' | '2026-06-07' | ISO -> date (o None)."""
    texto = str(texto or "").strip()
    if not texto or texto.lower() == "none":
        texto = str(respaldo or "").strip()
    if not texto or texto.lower() == "none":
        return None
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", texto)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).date()
        except ValueError:
            return None
    m = re.search(r"(\d{1,2})\s+de\s+([a-zA-Záéíóúñ]+)\s+de\s+(\d{4})", texto)
    if m:
        mes = MESES_ES.get(m.group(2).lower())
        if mes:
            try:
                return datetime(int(m.group(3)), mes, int(m.group(1))).date()
            except ValueError:
                return None
    return None


def temporada_de(fecha, declarada=None):
    """Temporada LAE por FECHA real (corte 15 de agosto: la J1 26/27 fue el
    16/08/2026 y las J75-J76 de verano, 2 y 9/08, aun eran 25/26). La
    temporada_base declarada en el snapshot solo es respaldo: la J1 26/27 la
    declaraba todavia como 2025/2026."""
    if fecha is not None:
        inicio = fecha.year if (fecha.month > 8 or (fecha.month == 8 and fecha.day >= 15)) else fecha.year - 1
        return f"{inicio}/{inicio + 1}"
    if declarada:
        return str(declarada)
    return "desconocida"


def _pesos_vivos():
    try:
        from motor_prediccion_quiniela import PESO_MERCADO_LOSILLA_DEFECTO, PESO_MERCADO_LOSILLA_POR_CALIDAD
        return dict(PESO_MERCADO_LOSILLA_POR_CALIDAD), float(PESO_MERCADO_LOSILLA_DEFECTO)
    except Exception:
        return dict(_PESOS_POR_CALIDAD_RESPALDO), _PESO_DEFECTO_RESPALDO


def peso_mercado_usado(partido, pesos_por_calidad=None, peso_defecto=None):
    """Peso de mercado realmente usado en el snapshot: primero el texto
    'peso 0.XX' de las lecturas; si no, el peso por calidad_datos."""
    lecturas = (partido.get("ajuste_mercado_losilla") or {}).get("lecturas") or []
    m = re.search(r"peso\s+(\d+(?:[.,]\d+)?)", " ".join(str(x) for x in lecturas))
    if m:
        return float(m.group(1).replace(",", ".")), "lectura"
    if pesos_por_calidad is None or peso_defecto is None:
        pesos_por_calidad, peso_defecto = _pesos_vivos()
    return float(pesos_por_calidad.get(partido.get("calidad_datos"), peso_defecto)), "calidad_datos"


def construir_dataset(dir_pre_cierre=PRE_CIERRE, dir_jornadas=JORNADAS):
    """Filas (jornada, temporada, fecha, num, p_pre, p_post, q, y, peso...)
    ordenadas por FECHA real (no por numero de jornada)."""
    pesos_por_calidad, peso_defecto = _pesos_vivos()
    filas = []
    for ruta in sorted(Path(dir_pre_cierre).glob("jornada_*.json")):
        snap = cargar_json(ruta, {})
        pred = snap.get("prediccion") or {}
        jornada = snap.get("jornada") or pred.get("jornada")
        if jornada is None:
            continue
        fixture = cargar_json(Path(dir_jornadas) / f"jornada_{jornada}.json", {})
        fecha = parsear_fecha_jornada(fixture.get("fecha"), snap.get("primer_partido_utc"))
        temporada = temporada_de(fecha, pred.get("temporada_base"))
        reales = {int(p.get("num") or 0): p.get("signo_oficial") for p in fixture.get("partidos") or []}
        for p in pred.get("partidos") or []:
            try:
                num = int(p.get("num") or 0)
            except (TypeError, ValueError):
                continue
            if num < 1 or num > 14:
                continue
            real = reales.get(num)
            mercado = p.get("mercado_losilla") or {}
            probs = p.get("probabilidades") or {}
            if real not in SIGNOS or not probs:
                continue
            if sum(float(mercado.get(s) or 0) for s in SIGNOS) <= 0:
                continue
            if sum(float(probs.get(s) or 0) for s in SIGNOS) <= 0:
                continue
            peso, origen_peso = peso_mercado_usado(p, pesos_por_calidad, peso_defecto)
            p_post = normalizar(probs)
            q = normalizar(mercado)
            filas.append({
                "jornada": int(jornada),
                "temporada": temporada,
                "fecha": fecha.isoformat() if fecha else None,
                "num": num,
                "local": p.get("local"),
                "visitante": p.get("visitante"),
                "calidad_datos": p.get("calidad_datos"),
                "peso_mercado": peso,
                "origen_peso": origen_peso,
                "p_post": p_post,
                "p_pre": invertir_mezcla_lineal(p_post, q, peso),
                "q": q,
                "y": real,
            })
    filas.sort(key=lambda f: (f["fecha"] or "9999-99-99", f["jornada"], f["num"]))
    return filas


def _matrices(filas, clave):
    M = np.array([[f[clave][s] for s in SIGNOS] for f in filas], dtype=float)
    return np.clip(M, EPS, 1.0)


def _y(filas):
    return np.array([SIGNOS.index(f["y"]) for f in filas], dtype=int)


# --------------------------------------------------------------------------
# Ajuste de alpha, beta (logit condicional) y temperatura
# --------------------------------------------------------------------------
def _softmax_filas(L):
    L = L - L.max(axis=1, keepdims=True)
    E = np.exp(L)
    return E / E.sum(axis=1, keepdims=True)


def benter_matriz(P, Q, alpha, beta, T=1.0):
    L = (alpha * np.log(P) + beta * np.log(Q)) / max(float(T), 1e-6)
    return _softmax_filas(L)


def log_loss_matriz(C, y):
    return float(-np.log(np.clip(C[np.arange(len(y)), y], 1e-15, 1.0)).mean())


def _minimizar(fun, x0, bounds):
    """scipy L-BFGS-B; respaldo sin scipy: busqueda por coordenadas afinada."""
    if _scipy_minimize is not None:
        res = _scipy_minimize(fun, x0=np.array(x0, dtype=float), bounds=bounds, method="L-BFGS-B")
        return [float(v) for v in res.x]
    x = [float(v) for v in x0]
    paso = 0.5
    mejor = fun(np.array(x))
    while paso > 1e-4:
        mejorado = False
        for i in range(len(x)):
            for d in (-paso, paso):
                cand = list(x)
                cand[i] = min(max(cand[i] + d, bounds[i][0]), bounds[i][1])
                v = fun(np.array(cand))
                if v < mejor - 1e-12:
                    mejor, x, mejorado = v, cand, True
        if not mejorado:
            paso /= 2
    return x


def ajustar_alpha_beta(P, Q, y, limites=((-2.0, 4.0), (-2.0, 4.0))):
    """Minimiza la log-loss multinomial de softmax(alpha ln P + beta ln Q).
    Se permite alpha < 0 a proposito: si sale negativo o ~0 el diagnostico
    honesto es que el motor no aporta nada al precio."""
    def nll(ab):
        return log_loss_matriz(benter_matriz(P, Q, ab[0], ab[1]), y)
    alpha, beta = _minimizar(nll, [0.3, 0.8], list(limites))
    return alpha, beta


def ajustar_temperatura(C, y, limites=(0.2, 5.0)):
    """Temperature scaling (1 parametro) sobre una matriz de probabilidades
    ya mezclada: softmax(ln C / T)."""
    logC = np.log(np.clip(C, EPS, 1.0))

    def nll(t):
        return log_loss_matriz(_softmax_filas(logC / max(float(t[0]), 1e-6)), y)
    return float(_minimizar(nll, [1.0], [limites])[0])


def aplicar_temperatura(C, T):
    return _softmax_filas(np.log(np.clip(C, EPS, 1.0)) / max(float(T), 1e-6))


# --------------------------------------------------------------------------
# Evaluacion
# --------------------------------------------------------------------------
def _metricas(C, y):
    rps = [rps_fila(C[i], int(y[i])) for i in range(len(y))]
    return {"n": int(len(y)), "log_loss": round(log_loss_matriz(C, y), 5), "rps": round(float(np.mean(rps)), 5)}


def _por_partido(C, y):
    ll = -np.log(np.clip(C[np.arange(len(y)), y], 1e-15, 1.0))
    rps = np.array([rps_fila(C[i], int(y[i])) for i in range(len(y))])
    return ll, rps


def bootstrap_por_jornada(diferencias, jornadas, repeticiones=BOOTSTRAP_REPETICIONES, semilla=BOOTSTRAP_SEMILLA):
    """IC95 bootstrap de la media de una diferencia emparejada por partido,
    remuestreando JORNADAS completas con reemplazo (cluster bootstrap)."""
    diferencias = np.asarray(diferencias, dtype=float)
    jornadas = list(jornadas)
    grupos = {}
    for d, j in zip(diferencias, jornadas):
        grupos.setdefault(j, []).append(float(d))
    claves = sorted(grupos)
    if len(claves) < 2:
        media = float(diferencias.mean()) if len(diferencias) else 0.0
        return {"media": round(media, 5), "ic95": [None, None], "jornadas": len(claves)}
    sumas = np.array([sum(grupos[k]) for k in claves])
    tam = np.array([len(grupos[k]) for k in claves], dtype=float)
    rng = random.Random(semilla)
    medias = []
    for _ in range(repeticiones):
        idx = [rng.randrange(len(claves)) for _ in claves]
        medias.append(sumas[idx].sum() / tam[idx].sum())
    medias.sort()
    lo = medias[int(0.025 * (len(medias) - 1))]
    hi = medias[int(0.975 * (len(medias) - 1))]
    return {
        "media": round(float(diferencias.mean()), 5),
        "ic95": [round(float(lo), 5), round(float(hi), 5)],
        "jornadas": len(claves),
        "significativa_95": bool(lo > 0 or hi < 0),
    }


def tamano_para_detectar(delta, sd_diferencia, potencia=0.80, alfa=0.05):
    """n = ((z_{1-alfa/2} + z_potencia) * sd / delta)^2 (test emparejado bilateral)."""
    z = {0.80: 0.8416, 0.90: 1.2816}.get(potencia, 0.8416)
    za = 1.96 if abs(alfa - 0.05) < 1e-9 else 2.5758
    if delta <= 0 or sd_diferencia <= 0:
        return None
    return int(math.ceil(((za + z) * sd_diferencia / delta) ** 2))


def delta_minimo_detectable(n, sd_diferencia, potencia=0.80, alfa=0.05):
    z = {0.80: 0.8416, 0.90: 1.2816}.get(potencia, 0.8416)
    za = 1.96 if abs(alfa - 0.05) < 1e-9 else 2.5758
    if n <= 0 or sd_diferencia <= 0:
        return None
    return (za + z) * sd_diferencia / math.sqrt(n)


def _candidatos(filas, idx_test, alpha, beta, T_benter, T_lineal):
    """Probabilidades out-of-sample de los cinco (seis) candidatos."""
    sub = [filas[i] for i in idx_test]
    P = _matrices(sub, "p_pre")
    Q = _matrices(sub, "q")
    Ppost = _matrices(sub, "p_post")
    benter = benter_matriz(P, Q, alpha, beta)
    lineal = (1 - MEZCLA_LINEAL_REFERENCIA) * P + MEZCLA_LINEAL_REFERENCIA * Q
    return {
        "motor_pre": P,
        "mercado": Q,
        "motor_post": Ppost,
        "benter": benter,
        "benter_T": aplicar_temperatura(benter, T_benter),
        "lineal_50": lineal,
        "lineal_50_T": aplicar_temperatura(lineal, T_lineal),
    }


def walk_forward(filas, min_entrenamiento=MIN_PARTIDOS_ENTRENAMIENTO):
    """Ajusta en todas las jornadas anteriores (orden cronologico) y predice
    la siguiente. Devuelve folds + predicciones OOS apiladas por candidato."""
    orden = []
    vistos = set()
    for f in filas:
        clave = (f["fecha"] or "", f["jornada"])
        if clave not in vistos:
            vistos.add(clave)
            orden.append(clave)
    indices_por_jornada = {clave: [] for clave in orden}
    for i, f in enumerate(filas):
        indices_por_jornada[(f["fecha"] or "", f["jornada"])].append(i)

    folds = []
    oos = {k: [] for k in ("motor_pre", "mercado", "motor_post", "benter", "benter_T", "lineal_50", "lineal_50_T")}
    oos_y, oos_jornadas = [], []
    acumulado = []
    for clave in orden:
        idx_test = indices_por_jornada[clave]
        if len(acumulado) >= min_entrenamiento:
            train = [filas[i] for i in acumulado]
            P, Q, y = _matrices(train, "p_pre"), _matrices(train, "q"), _y(train)
            alpha, beta = ajustar_alpha_beta(P, Q, y)
            T_b = ajustar_temperatura(benter_matriz(P, Q, alpha, beta), y)
            T_l = ajustar_temperatura((1 - MEZCLA_LINEAL_REFERENCIA) * P + MEZCLA_LINEAL_REFERENCIA * Q, y)
            cands = _candidatos(filas, idx_test, alpha, beta, T_b, T_l)
            for k, M in cands.items():
                oos[k].append(M)
            y_test = _y([filas[i] for i in idx_test])
            oos_y.append(y_test)
            oos_jornadas.extend([f"{clave[0]}|J{clave[1]}"] * len(idx_test))
            folds.append({
                "jornada": clave[1],
                "fecha": clave[0] or None,
                "n_entrenamiento": len(acumulado),
                "n_test": len(idx_test),
                "alpha": round(alpha, 4),
                "beta": round(beta, 4),
                "T_benter": round(T_b, 4),
                "T_lineal_50": round(T_l, 4),
                "log_loss_test": {k: round(log_loss_matriz(M, y_test), 5) for k, M in cands.items()},
            })
        acumulado.extend(idx_test)
    if not folds:
        return {"estado": "muestra_insuficiente", "folds": [], "partidos_oos": 0}
    y_all = np.concatenate(oos_y)
    apilado = {k: np.vstack(v) for k, v in oos.items()}
    return {"estado": "ok", "folds": folds, "oos": apilado, "y": y_all, "jornadas": oos_jornadas, "partidos_oos": int(len(y_all))}


def leave_one_season_out(filas):
    temporadas = sorted({f["temporada"] for f in filas})
    if len(temporadas) < 2:
        return {"estado": "una_sola_temporada", "temporadas": temporadas}
    salida = {"estado": "ok", "folds": []}
    for test_t in temporadas:
        train = [f for f in filas if f["temporada"] != test_t]
        test = [f for f in filas if f["temporada"] == test_t]
        if len(train) < MIN_PARTIDOS_ENTRENAMIENTO or not test:
            salida["folds"].append({"temporada_test": test_t, "estado": "muestra_insuficiente", "n_entrenamiento": len(train), "n_test": len(test)})
            continue
        P, Q, y = _matrices(train, "p_pre"), _matrices(train, "q"), _y(train)
        alpha, beta = ajustar_alpha_beta(P, Q, y)
        T_b = ajustar_temperatura(benter_matriz(P, Q, alpha, beta), y)
        T_l = ajustar_temperatura((1 - MEZCLA_LINEAL_REFERENCIA) * P + MEZCLA_LINEAL_REFERENCIA * Q, y)
        cands = _candidatos(filas, [i for i, f in enumerate(filas) if f["temporada"] == test_t], alpha, beta, T_b, T_l)
        y_test = _y(test)
        salida["folds"].append({
            "temporada_test": test_t, "n_entrenamiento": len(train), "n_test": len(test),
            "alpha": round(alpha, 4), "beta": round(beta, 4), "T_benter": round(T_b, 4),
            "metricas_test": {k: _metricas(M, y_test) for k, M in cands.items()},
        })
    return salida


def _estabilidad(folds):
    alphas = [f["alpha"] for f in folds]
    betas = [f["beta"] for f in folds]
    if not alphas:
        return {}
    pos = sum(1 for a in alphas if a > 0)
    return {
        "folds": len(alphas),
        "alpha_media": round(float(np.mean(alphas)), 4),
        "alpha_sd": round(float(np.std(alphas)), 4),
        "alpha_min": round(min(alphas), 4),
        "alpha_max": round(max(alphas), 4),
        "alpha_positivo_folds": pos,
        "alpha_positivo_fraccion": round(pos / len(alphas), 3),
        "beta_media": round(float(np.mean(betas)), 4),
        "beta_sd": round(float(np.std(betas)), 4),
        "beta_min": round(min(betas), 4),
        "beta_max": round(max(betas), 4),
        "ultimo_fold": {"alpha": alphas[-1], "beta": betas[-1]},
    }


def veredicto(estabilidad, metricas_oos):
    """Aplica el criterio prerregistrado. Devuelve (veredicto, lectura)."""
    if not estabilidad or "benter" not in metricas_oos:
        return "NO_DESPLEGAR", "Sin folds suficientes para evaluar."
    frac = estabilidad.get("alpha_positivo_fraccion", 0.0)
    ll_b = metricas_oos["benter"]["log_loss"]
    ll_m = metricas_oos["mercado"]["log_loss"]
    ll_post = metricas_oos["motor_post"]["log_loss"]
    cumple_alpha = frac >= FRACCION_FOLDS_ALPHA_POSITIVO
    bate_mercado = ll_b < ll_m
    bate_motor = ll_b < ll_post
    partes = []
    if cumple_alpha and bate_mercado and bate_motor:
        return "CANDIDATA", (
            f"alpha > 0 en {frac:.0%} de los folds y la mezcla de Benter bate fuera de muestra al mercado "
            f"({ll_b:.4f} vs {ll_m:.4f}) y al motor actual ({ll_post:.4f}). Candidata a Laboratorio: NO se "
            "despliega sola; exige IC95 bootstrap que excluya el 0 y decision de Marc."
        )
    if not cumple_alpha:
        a = estabilidad.get("alpha_media", 0.0)
        if abs(a) < 0.15:
            partes.append(
                f"alpha ~ 0 (media {a:+.3f}, positivo en {frac:.0%} de los folds): el motor no aporta "
                "informacion al precio del mercado para la PROBABILIDAD; debe seguir solo como generador de dobles/triples."
            )
        elif a < 0:
            partes.append(
                f"alpha NEGATIVO (media {a:+.3f}): cuando el motor se separa del mercado, acierta MENOS que el mercado; "
                "cualquier peso fijo del motor empeora la probabilidad."
            )
        else:
            partes.append(f"alpha inestable entre folds (positivo solo en {frac:.0%}; sd {estabilidad.get('alpha_sd')}).")
    if not bate_mercado:
        partes.append(
            f"Benter no bate al mercado solo fuera de muestra ({ll_b:.4f} vs {ll_m:.4f})"
            + (f" aunque alpha salga positivo en el ajuste ({estabilidad.get('alpha_media'):+.3f} de media): "
               "la ganancia in-sample del motor no sobrevive al walk-forward." if cumple_alpha else ".")
        )
    if not bate_motor:
        partes.append(f"Benter no bate al motor actual con pesos fijos ({ll_b:.4f} vs {ll_post:.4f}).")
    elif ll_post > ll_m:
        partes.append(
            f"Dato colateral: el motor actual con pesos fijos pierde {ll_post - ll_m:+.4f} de log-loss frente al "
            "mercado solo; la mezcla estimada recorta esa perdida pero no la invierte. El mejor predictor de "
            "probabilidad disponible sigue siendo el mercado; el motor conserva su papel de generador de dobles/triples."
        )
    return "NO_DESPLEGAR", " ".join(partes)


def analizar(dir_pre_cierre=PRE_CIERRE, dir_jornadas=JORNADAS, filas=None):
    """Pipeline completo. Devuelve el dict que se guarda en el JSON."""
    filas = construir_dataset(dir_pre_cierre, dir_jornadas) if filas is None else filas
    salida = {
        "version": "1.0",
        "generado_en": ahora_iso(),
        "criterio_prerregistrado": CRITERIO_PRERREGISTRADO,
        "metodo": {
            "mezcla": "c_i prop. exp(alpha*ln p_motor_pre_i + beta*ln q_mercado_i); alpha, beta por log-loss multinomial (scipy L-BFGS-B)",
            "p_motor_pre": "inversion de la mezcla lineal del motor: p_pre=(p_post-peso*q)/(1-peso), recorte [0.01,0.98] y renormalizacion; incluye los retoques posteriores a la mezcla (lesiones, revulsivo, motivacion)",
            "validacion": "walk-forward por jornada en orden cronologico (ajuste con todas las anteriores) + leave-one-season-out; bootstrap emparejado por jornada",
            "orden": "por fecha real de la jornada, nunca por numero (reinicio de temporada LAE)",
        },
        "dataset": {
            "partidos": len(filas),
            "jornadas": len({(f["fecha"], f["jornada"]) for f in filas}),
            "temporadas": sorted({f["temporada"] for f in filas}),
            "por_calidad_datos": {},
            "por_peso_mercado": {},
            "origen_peso": {},
        },
    }
    for f in filas:
        d = salida["dataset"]
        d["por_calidad_datos"][str(f["calidad_datos"])] = d["por_calidad_datos"].get(str(f["calidad_datos"]), 0) + 1
        d["por_peso_mercado"][f"{f['peso_mercado']:.2f}"] = d["por_peso_mercado"].get(f"{f['peso_mercado']:.2f}", 0) + 1
        d["origen_peso"][f["origen_peso"]] = d["origen_peso"].get(f["origen_peso"], 0) + 1

    if np is None or len(filas) < MIN_PARTIDOS_ENTRENAMIENTO + 14:
        salida.update({"estado": "muestra_insuficiente", "veredicto": "NO_DESPLEGAR",
                       "lectura": "Menos de 5 jornadas con mercado y signo oficial: no hay walk-forward posible."})
        return salida

    wf = walk_forward(filas)
    if wf["estado"] != "ok":
        salida.update({"estado": wf["estado"], "veredicto": "NO_DESPLEGAR", "lectura": "Sin folds walk-forward."})
        return salida

    y = wf["y"]
    metricas_oos = {k: _metricas(M, y) for k, M in wf["oos"].items()}
    ll, rps = {}, {}
    for k, M in wf["oos"].items():
        ll[k], rps[k] = _por_partido(M, y)
    comparaciones = {}
    for a, b in (("benter", "mercado"), ("benter", "motor_post"), ("benter_T", "mercado"), ("motor_post", "mercado"),
                 ("motor_pre", "mercado"), ("lineal_50", "mercado"), ("lineal_50_T", "mercado")):
        comparaciones[f"{a}_menos_{b}"] = {
            "log_loss": bootstrap_por_jornada(ll[a] - ll[b], wf["jornadas"]),
            "rps": bootstrap_por_jornada(rps[a] - rps[b], wf["jornadas"]),
        }
    estabilidad = _estabilidad(wf["folds"])
    sd_ll = float(np.std(ll["benter"] - ll["mercado"], ddof=1))
    sd_rps = float(np.std(rps["motor_post"] - rps["mercado"], ddof=1))
    n = int(len(y))
    potencia = {
        "n_partidos_oos": n,
        "sd_diferencia_log_loss_benter_vs_mercado": round(sd_ll, 4),
        "sd_diferencia_rps_motor_post_vs_mercado": round(sd_rps, 4),
        "delta_log_loss_minimo_detectable_con_n": round(delta_minimo_detectable(n, sd_ll) or 0.0, 4),
        "delta_rps_minimo_detectable_con_n": round(delta_minimo_detectable(n, sd_rps) or 0.0, 4),
        f"partidos_para_detectar_delta_log_loss_{DELTA_LOGLOSS_REFERENCIA}": tamano_para_detectar(DELTA_LOGLOSS_REFERENCIA, sd_ll),
        "partidos_para_detectar_delta_rps_0.002": tamano_para_detectar(0.002, sd_rps),
        "partidos_para_detectar_delta_rps_0.005": tamano_para_detectar(0.005, sd_rps),
        "nota": "potencia 80 %, alfa 0,05 bilateral, test emparejado por partido; el bootstrap por jornada es mas conservador",
    }
    ver, lectura = veredicto(estabilidad, metricas_oos)

    # Parametros ajustados con TODO el dataset (solo informativos salvo CANDIDATA).
    P, Q, yy = _matrices(filas, "p_pre"), _matrices(filas, "q"), _y(filas)
    alpha_f, beta_f = ajustar_alpha_beta(P, Q, yy)
    T_f = ajustar_temperatura(benter_matriz(P, Q, alpha_f, beta_f), yy)

    salida.update({
        "estado": "ok",
        "walk_forward": {
            "partidos_oos": n,
            "folds": wf["folds"],
            "estabilidad": estabilidad,
            "metricas_oos": metricas_oos,
            "comparaciones_bootstrap_por_jornada": comparaciones,
        },
        "leave_one_season_out": leave_one_season_out(filas),
        "potencia": potencia,
        "parametros_finales_todo_el_dataset": {"alpha": round(alpha_f, 4), "beta": round(beta_f, 4), "T": round(T_f, 4),
                                               "nota": "ajuste in-sample con todas las filas; solo se usa si el veredicto es CANDIDATA"},
        "veredicto": ver,
        "lectura": lectura,
        "implicacion_para_el_motor": (
            "NO se toca ajustar_por_mercado_losilla ni PESO_MERCADO_LOSILLA_POR_CALIDAD. Si algun dia el veredicto "
            "es CANDIDATA, el punto de enganche es sustituir la mezcla lineal de ajustar_por_mercado_losilla por "
            "mezclar_benter(probs, mercado, alpha, beta, T) con los parametros de cargar_parametros()."
        ),
    })
    return salida


def cargar_parametros(path=SALIDA):
    """Parametros desplegables o None. Devuelve None si no hay fichero, si el
    veredicto es NO_DESPLEGAR o si faltan alpha/beta (no-op garantizado)."""
    data = cargar_json(path, {})
    if not data or data.get("veredicto") != "CANDIDATA":
        return None
    par = data.get("parametros_finales_todo_el_dataset") or {}
    try:
        alpha, beta = float(par["alpha"]), float(par["beta"])
    except (KeyError, TypeError, ValueError):
        return None
    return {"alpha": alpha, "beta": beta, "T": float(par.get("T") or 1.0)}


def _fmt(v):
    return "-" if v is None else f"{v:.4f}"


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    salida = analizar()
    guardar_json(SALIDA, salida)
    print("Mezcla de Benter (Laboratorio) -> " + str(SALIDA.relative_to(ROOT)))
    print(f"Dataset: {salida['dataset']['partidos']} partidos, {salida['dataset']['jornadas']} jornadas, temporadas {salida['dataset']['temporadas']}")
    if salida.get("estado") != "ok":
        print(f"Estado: {salida.get('estado')} -> {salida.get('veredicto')}")
        return salida
    wf = salida["walk_forward"]
    print(f"Walk-forward: {wf['partidos_oos']} partidos fuera de muestra, {len(wf['folds'])} folds")
    print("  fold   jornada  n_train  alpha    beta     T")
    for f in wf["folds"]:
        print(f"  {f['fecha'] or '?':10} J{f['jornada']:<4} {f['n_entrenamiento']:>6} {f['alpha']:+.3f}  {f['beta']:+.3f}  {f['T_benter']:.3f}")
    est = wf["estabilidad"]
    print(f"  alpha media {est['alpha_media']:+.3f} (sd {est['alpha_sd']}), positivo en {est['alpha_positivo_folds']}/{est['folds']} folds; beta media {est['beta_media']:+.3f}")
    print("Metricas OOS (menor = mejor):")
    for k, m in wf["metricas_oos"].items():
        print(f"  {k:12} log-loss {m['log_loss']:.4f}  RPS {m['rps']:.4f}")
    print("Bootstrap por jornada (diferencia, IC95):")
    for k, c in wf["comparaciones_bootstrap_por_jornada"].items():
        print(f"  {k:28} log-loss {c['log_loss']['media']:+.4f} {c['log_loss']['ic95']}   RPS {c['rps']['media']:+.4f} {c['rps']['ic95']}")
    pot = salida["potencia"]
    print(f"Potencia: n={pot['n_partidos_oos']}, delta log-loss minimo detectable {pot['delta_log_loss_minimo_detectable_con_n']}, "
          f"delta RPS minimo detectable {pot['delta_rps_minimo_detectable_con_n']}")
    print(f"VEREDICTO: {salida['veredicto']}")
    print("  " + salida["lectura"])
    return salida


if __name__ == "__main__":
    main()
