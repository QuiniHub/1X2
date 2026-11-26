"""Optimizador de boleto (Laboratorio, prerregistrado 26/11/2026).

Implementa la implantacion nº 3 del informe "Algoritmos contra nuestros
fallos 1X2" (reports/) y de research_notes/.../reparto_presupuesto.md:
repartir los 14 partidos entre fijos, dobles y triples es un KNAPSACK en
logaritmos, no una intuicion. Un sistema producto elige por partido un
subconjunto no vacio de {1,X,2}; coste = producto de tamanos (columnas) a
0,75 EUR/columna. Para un sistema:

  - masa cubierta por partido c_i = suma de p sobre el subconjunto;
  - P(la mejor columna acierta k) = Poisson-binomial exacta sobre c_i
    (DP por partidos) -> P14, P(>=13), P(>=12), P(>=10);
  - premio esperado pari-mutuel (categorias 10-14, SIN Pleno al 15 ni
    Elige 8), modelo documentado en Evaluador.premio_esperado:
      * 12, 13 y 14 EXACTAS: se enumeran todos los resultados con 0, 1 o 2
        partidos sin cubrir (los unicos que dan columnas con >=12), con la
        probabilidad real P(x), el numero de columnas nuestras en cada
        categoria y la masa rival P_masa_k(x) en forma cerrada (simetricas
        elementales de (1-q)/q, como en modelo_reparto_quiniela). Rivales
        por categoria ~ Poisson(N * P_masa_k(x)), N = recaudacion/0,75 x
        factor_acertantes (meta-aprendizaje). Premio por columna
        = fondo_k * E[1/(X+m)] con m = nuestras columnas en la categoria
        (Clair & Letscher 2007, aproximacion 1/(N*P_k(x)) para N grande).
      * 10 y 11 por CAMPO MEDIO: E[columnas nuestras con k] exacto (polinomio
        generador) dividido por el numero esperado incondicional de
        acertantes rivales; ignora la correlacion "si acertamos 11 la masa
        tambien acierta mas". Son premios de centimos a pocos euros y casi
        planos entre sistemas del mismo coste: sesgo pequeno, documentado.
      * reglas verificadas con escrutinios: premio < 1,5 EUR no se paga;
        gravamen 20% sobre el exceso de 40.000 EUR.

Busqueda (Clair & Letscher: hill-climbing que termina en un maximo entre
sus vecinos a distancia 2 "never failed" frente a exhaustiva en 14-16
partidos): se recorren las estructuras (t triples, d dobles) con
3^t*2^d <= presupuesto; cada una se rellena con las reglas de ranking
(dobles por p(2)/p(1), triples por 1/(p(1)+p(2))); de las mejores
estructuras arranca una busqueda local con vecinos a distancia 1 (7 opciones
por partido) y a distancia 2 (intercambios/transferencias de tamano entre
dos partidos; en los objetivos baratos P14/P13plus, todos los pares de
opciones). Determinista: sin aleatoriedad, orden fijo, mejora estricta.

Regla "contra la masa" (toggle contra_masa): el signo base es argmax p/s
(edge real/masa, Proposicion 3.4 de Clair & Letscher) en vez de argmax p.

API publica: optimizar(partidos_probs, masa, presupuesto_columnas,
objetivo='premio_esperado', contra_masa=False) -> dict.

SOLO LECTURA: no escribe en ultima_prediccion.json ni toca ningun modulo.
El backtest prerregistrado vive en backtest_optimizador_boleto.py.
"""
import itertools
import math
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np

from modelo_reparto_quiniela import (
    CATEGORIAS,
    FRACCION_RECAUDACION,
    GRAVAMEN_EXENTO,
    GRAVAMEN_TIPO,
    PRECIO_APUESTA,
    PREMIO_MINIMO_PAGADO,
    RECAUDACION_DEFECTO,
    SIGNOS,
    columnas_boleto,
    normalizar_probs,
)

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
PREDICCION = DATA / "predicciones" / "ultima_prediccion.json"
FUENTE_LOSILLA = DATA / "memoria_ia" / "fuente_losilla.json"

OPCIONES = ("1", "X", "2", "1X", "12", "X2", "1X2")
OBJETIVOS = ("P14", "P13plus", "premio_esperado")
PRESUPUESTOS_SOPORTADOS = (1, 2, 3, 4, 6, 8, 9, 12, 16, 18, 24, 27, 32, 36, 48,
                           54, 64, 72, 96, 108, 128, 144)
PRESUPUESTOS_WEB = (9, 16, 18, 24, 32, 48)
N_ARRANQUES = 3          # estructuras desde las que arranca la busqueda local
_K_POISSON = 90          # truncamiento de la suma de Poisson para E[m/(X+m)]
_LOG_FACT = np.concatenate(([0.0], np.cumsum(np.log(np.arange(1, _K_POISSON + 1)))))


# ---------------------------------------------------------------------------
# representacion
# ---------------------------------------------------------------------------
def normalizar_signos(signos):
    """"X1" -> "1X", "21" -> "12", "2X1" -> "1X2"; vacio -> "1"."""
    limpio = "".join(s for s in SIGNOS if s in str(signos or "").upper())
    return limpio or "1"


def mascara(signos_sistema):
    """Lista de 14 strings -> matriz booleana (n, 3) en el orden 1, X, 2."""
    m = np.zeros((len(signos_sistema), 3), dtype=bool)
    for i, signos in enumerate(signos_sistema):
        for s in normalizar_signos(signos):
            m[i, SIGNOS.index(s)] = True
    return m


def signos_desde_mascara(m):
    return ["".join(SIGNOS[j] for j in range(3) if m[i, j]) for i in range(m.shape[0])]


def coste_columnas(signos_sistema):
    return columnas_boleto([normalizar_signos(s) for s in signos_sistema])


def coste_eur(columnas):
    return round(max(int(columnas) * PRECIO_APUESTA, PRECIO_APUESTA), 2)


def matriz_probs(lista_dicts):
    """Lista de dicts {1,X,2} (en % o en fraccion) -> (n, 3) normalizada."""
    return np.array([[normalizar_probs(d)[s] for s in SIGNOS] for d in lista_dicts], dtype=float)


# ---------------------------------------------------------------------------
# probabilidad de aciertos (exacta)
# ---------------------------------------------------------------------------
def distribucion_aciertos(cubierta):
    """P(exactamente k aciertos de la mejor columna), k=0..n, Poisson-binomial
    sobre la masa cubierta por partido (DP por partidos)."""
    dist = np.array([1.0])
    for c in cubierta:
        nueva = np.zeros(len(dist) + 1)
        nueva[:-1] += dist * (1.0 - c)
        nueva[1:] += dist * c
        dist = nueva
    return dist


def esperanza_columnas_por_aciertos(cubierta, tamanos):
    """E[numero de columnas nuestras con exactamente k aciertos], k=0..n:
    coeficientes de prod_i (c_i z + (t_i - c_i)) (independencia entre
    partidos; exacto)."""
    poli = np.array([1.0])
    for c, t in zip(cubierta, tamanos):
        nueva = np.zeros(len(poli) + 1)
        nueva[:-1] += poli * (t - c)
        nueva[1:] += poli * c
        poli = nueva
    return poli


_LAM_CORTE = 35.0
_GRID_LOG_LAM = np.linspace(np.log(1e-9), np.log(_LAM_CORTE), 2500)
_TABLAS_G = {}


def _tabla_g(m):
    """Tabla de g_m(lam) = E[m/(X+m)], X ~ Poisson(lam), sobre la malla
    logaritmica de lam (suma de Poisson truncada en _K_POISSON terminos)."""
    tabla = _TABLAS_G.get(m)
    if tabla is None:
        l = np.exp(_GRID_LOG_LAM)[:, None]
        k = np.arange(_K_POISSON + 1)[None, :]
        pmf = np.exp(-l + k * np.log(l) - _LOG_FACT[None, :])
        tabla = (pmf * m / (k + m)).sum(axis=1)
        _TABLAS_G[m] = tabla
    return tabla


def _esperanza_m_entre_x_mas_m(lam, m):
    """E[m/(X+m)] con X ~ Poisson(lam), vectorizado (lam, m arrays). Para
    lam >= 35 vale m/(lam+m) (error < 1e-3 relativo); por debajo se interpola
    la suma exacta de Poisson en una malla logaritmica fina, por cada valor
    distinto de m (siempre un entero: numero de columnas nuestras)."""
    lam = np.asarray(lam, dtype=float)
    m = np.asarray(m, dtype=float)
    lam, m = np.broadcast_arrays(lam, m)
    salida = m / (lam + m)
    chico = lam < _LAM_CORTE
    if np.any(chico):
        lam_c = np.log(np.clip(lam[chico], 1e-9, None))
        m_c = m[chico]
        res = np.empty(lam_c.shape)
        for valor in np.unique(m_c):
            sel = m_c == valor
            res[sel] = np.interp(lam_c[sel], _GRID_LOG_LAM, _tabla_g(float(valor)))
        salida[chico] = res
    return salida


def _cartesiano(listas):
    grids = np.meshgrid(*listas, indexing="ij")
    return np.stack([g.ravel() for g in grids], axis=1)


class Evaluador:
    """Metricas exactas de P(k) y premio esperado pari-mutuel de un sistema.

    probs: (14, 3) probabilidad real por partido; masa: (14, 3) fraccion de
    apostantes LAE por signo (None -> sin premio_esperado)."""

    def __init__(self, probs, masa=None, recaudacion=RECAUDACION_DEFECTO, factor_acertantes=1.0):
        self.probs = np.clip(np.asarray(probs, dtype=float), 1e-6, None)
        self.probs = self.probs / self.probs.sum(axis=1, keepdims=True)
        self.n = self.probs.shape[0]
        self.masa = None
        if masa is not None:
            self.masa = np.clip(np.asarray(masa, dtype=float), 1e-4, None)
            self.masa = self.masa / self.masa.sum(axis=1, keepdims=True)
            self._ratio = (1.0 - self.masa) / self.masa
        self.recaudacion = float(recaudacion)
        self.factor_acertantes = min(max(float(factor_acertantes or 1.0), 0.5), 2.0)
        self.apuestas_rivales = self.recaudacion / PRECIO_APUESTA * self.factor_acertantes
        self.fondo = {k: FRACCION_RECAUDACION[k] * self.recaudacion for k in CATEGORIAS}

    # -- probabilidades -----------------------------------------------------
    def cubierta(self, m):
        return (self.probs * m).sum(axis=1)

    def probabilidades(self, m):
        dist = distribucion_aciertos(self.cubierta(m))
        n = self.n
        return {
            "P14": float(dist[n]) if n >= 14 else float(dist[-1]),
            "P13plus": float(dist[max(n - 1, 0):].sum()),
            "P12plus": float(dist[max(n - 2, 0):].sum()),
            "P10plus": float(dist[max(n - 4, 0):].sum()),
            "distribucion": dist,
        }

    # -- premio -------------------------------------------------------------
    def _premio_desde(self, p_x, M0, S1, S2, ours, pesos=None):
        """Suma pesos * P(x) * sum_k ours_k * premio_neto_por_columna para un
        lote de resultados descrito por P(x), M0 = prod q, S1 = sum r,
        S2 = sum r^2 (r = (1-q)/q de la masa), con ours = {categoria: array
        (r,) o escalar}; `pesos` corrige resultados repetidos en el lote."""
        p_x = np.asarray(p_x, dtype=float).ravel()
        if p_x.size == 0:
            return {k: 0.0 for k in ours}
        if pesos is not None:
            p_x = p_x * np.asarray(pesos, dtype=float).ravel()
        M0 = np.asarray(M0, dtype=float).ravel()
        S1 = np.asarray(S1, dtype=float).ravel()
        S2 = np.asarray(S2, dtype=float).ravel()
        p_masa = {14: M0, 13: M0 * S1, 12: M0 * (S1 ** 2 - S2) / 2.0}
        salida = {}
        for k, m in ours.items():
            m = np.broadcast_to(np.asarray(m, dtype=float).ravel() if np.ndim(m) else np.asarray(m, dtype=float), p_x.shape)
            if not np.any(m > 0):
                salida[k] = 0.0
                continue
            m_seguro = np.where(m > 0, m, 1.0)
            lam = self.apuestas_rivales * p_masa[k]
            fondo = self.fondo[k]
            por_columna = fondo * _esperanza_m_entre_x_mas_m(lam, m_seguro) / m_seguro
            por_columna = np.where(fondo / (lam + m_seguro) < PREMIO_MINIMO_PAGADO, 0.0, por_columna)
            por_columna = por_columna - GRAVAMEN_TIPO * np.maximum(por_columna - GRAVAMEN_EXENTO, 0.0)
            salida[k] = float((p_x * m * por_columna).sum())
        return salida

    def premio_esperado(self, m):
        """EV en euros por categoria (10-14) del sistema con mascara m."""
        if self.masa is None:
            raise ValueError("premio_esperado necesita la masa (porcentajes LAE)")
        tam = m.sum(axis=1)
        resto = tam - 1
        T1 = float(resto.sum())
        T2 = float((T1 ** 2 - (resto ** 2).sum()) / 2.0)
        cubiertos = [np.flatnonzero(m[i]) for i in range(self.n)]
        ev = {k: 0.0 for k in CATEGORIAS}
        pos = np.arange(self.n)

        # u = 0: el resultado es una de nuestras C columnas
        X0 = _cartesiano(cubiertos)
        C = X0.shape[0]
        p_col = self.probs[pos, X0]      # (C, n)
        q_col = self.masa[pos, X0]
        r_col = self._ratio[pos, X0]
        P0 = p_col.prod(axis=1)
        M0 = q_col.prod(axis=1)
        S1 = r_col.sum(axis=1)
        S2 = (r_col ** 2).sum(axis=1)
        for k, v in self._premio_desde(P0, M0, S1, S2, {14: 1.0, 13: T1, 12: T2}).items():
            ev[k] += v

        # Resultados con 1 o 2 partidos sin cubrir: se parte de las C columnas
        # y se sustituye el signo en esos partidos por uno NO cubierto; las
        # cantidades se actualizan por cocientes/diferencias (sin re-gather).
        # Cada resultado unico aparece tam_i (o tam_i*tam_j) veces -> peso 1/dup.
        descubiertos = [(i, s) for i in range(self.n) for s in range(3) if not m[i, s]]
        if descubiertos:
            K1 = len(descubiertos)
            idx_i = np.array([i for i, _ in descubiertos])
            idx_s = np.array([s for _, s in descubiertos])
            # factores (K1, C)
            f_p = self.probs[idx_i, idx_s][:, None] / p_col[:, idx_i].T
            f_m = self.masa[idx_i, idx_s][:, None] / q_col[:, idx_i].T
            d_r = self._ratio[idx_i, idx_s][:, None] - r_col[:, idx_i].T
            d_r2 = self._ratio[idx_i, idx_s][:, None] ** 2 - (r_col[:, idx_i].T) ** 2
            ti = tam[idx_i].astype(float)
            r = self._premio_desde(
                P0[None, :] * f_p, M0[None, :] * f_m, S1[None, :] + d_r, S2[None, :] + d_r2,
                {13: np.repeat(ti, C), 12: np.repeat(ti * (T1 - resto[idx_i]), C)},
                pesos=np.repeat(1.0 / ti, C),
            )
            for k, v in r.items():
                ev[k] += v
            # u = 2: pares de entradas descubiertas en partidos distintos
            a, b = np.triu_indices(K1, k=1)
            distintos = idx_i[a] != idx_i[b]
            a, b = a[distintos], b[distintos]
            if a.size:
                dup = (tam[idx_i[a]] * tam[idx_i[b]]).astype(float)
                r = self._premio_desde(
                    P0[None, :] * f_p[a] * f_p[b], M0[None, :] * f_m[a] * f_m[b],
                    S1[None, :] + d_r[a] + d_r[b], S2[None, :] + d_r2[a] + d_r2[b],
                    {12: np.repeat(dup, C)}, pesos=np.repeat(1.0 / dup, C),
                )
                ev[12] += r[12]

        # 10 y 11: campo medio (ver docstring del modulo)
        esperadas = esperanza_columnas_por_aciertos(self.cubierta(m), tam)
        acuerdo = (self.probs * self.masa).sum(axis=1)  # P(columna de la masa acierte el partido i)
        dist_masa = distribucion_aciertos(acuerdo)
        for k in (10, 11):
            if k > self.n:
                continue
            lam = self.apuestas_rivales * dist_masa[k]
            nuestras = float(esperadas[k])
            fondo = self.fondo[k]
            por_columna = fondo / (lam + 1.0)
            if por_columna < PREMIO_MINIMO_PAGADO:
                por_columna = 0.0
            por_columna -= GRAVAMEN_TIPO * max(por_columna - GRAVAMEN_EXENTO, 0.0)
            ev[k] = float(nuestras * por_columna)
        return ev

    # -- objetivo -------------------------------------------------------------
    def metricas(self, m):
        res = self.probabilidades(m)
        res.pop("distribucion")
        res["columnas"] = int(np.prod(m.sum(axis=1)))
        if self.masa is not None:
            ev = self.premio_esperado(m)
            res["premio_esperado"] = float(sum(ev.values()))
            res["premio_por_categoria"] = {str(k): float(v) for k, v in ev.items()}
        return res

    def objetivo(self, m, nombre):
        """Valor del objetivo para la mascara m (con cache por sistema: la
        busqueda local revisita candidatos)."""
        cache = self.__dict__.setdefault("_cache", {})
        clave = (nombre, m.tobytes())
        if clave in cache:
            return cache[clave]
        if nombre == "P14":
            valor = self.probabilidades(m)["P14"]
        elif nombre == "P13plus":
            valor = self.probabilidades(m)["P13plus"]
        elif nombre == "premio_esperado":
            valor = sum(self.premio_esperado(m).values())
        else:
            raise ValueError(f"objetivo desconocido: {nombre}")
        cache[clave] = valor
        return valor


# ---------------------------------------------------------------------------
# reglas de ranking y construccion de subconjuntos
# ---------------------------------------------------------------------------
def orden_signos(probs_i, masa_i=None, contra_masa=False):
    """Orden de preferencia de los signos de un partido: el base primero
    (argmax p, o argmax p/s si contra_masa), luego el resto por p."""
    p = np.asarray(probs_i, dtype=float)
    if contra_masa and masa_i is not None:
        edge = p / np.clip(np.asarray(masa_i, dtype=float), 1e-4, None)
        base = int(np.argmax(edge))
    else:
        base = int(np.argmax(p))
    resto = sorted((j for j in range(3) if j != base), key=lambda j: (-p[j], j))
    return [base] + resto


def ratios_ranking(probs):
    """Por partido: ratio_doble = p(2)/p(1), ratio_triple = 1/(p(1)+p(2)) con
    p ordenadas de mayor a menor."""
    salida = []
    for fila in np.asarray(probs, dtype=float):
        p = np.sort(fila)[::-1]
        salida.append({
            "p1": float(p[0]), "p2": float(p[1]), "p3": float(p[2]),
            "ratio_doble": float(p[1] / max(p[0], 1e-9)),
            "ratio_triple": float(1.0 / max(p[0] + p[1], 1e-9)),
        })
    return salida


def subconjunto(orden, tamano):
    m = np.zeros(3, dtype=bool)
    for j in orden[:tamano]:
        m[j] = True
    return m


def estructuras_posibles(presupuesto, n=14):
    """[(t, d, coste)] con 3^t * 2^d <= presupuesto, t + d <= n."""
    lista = []
    for t in range(0, n + 1):
        for d in range(0, n - t + 1):
            coste = 3 ** t * 2 ** d
            if coste <= presupuesto:
                lista.append((t, d, coste))
    return lista


def asignar_estructura(ordenes, ratios, t, d):
    """Triples a los t partidos de mayor 1/(p1+p2); dobles a los d de mayor
    p2/p1 entre el resto. Devuelve la mascara (n, 3)."""
    n = len(ordenes)
    idx_triples = sorted(range(n), key=lambda i: (-ratios[i]["ratio_triple"], i))[:t]
    resto = [i for i in range(n) if i not in idx_triples]
    idx_dobles = sorted(resto, key=lambda i: (-ratios[i]["ratio_doble"], i))[:d]
    tam = np.ones(n, dtype=int)
    tam[idx_triples] = 3
    tam[idx_dobles] = 2
    return np.array([subconjunto(ordenes[i], tam[i]) for i in range(n)])


# ---------------------------------------------------------------------------
# busqueda local (vecinos a distancia 1 y 2)
# ---------------------------------------------------------------------------
def _opciones_mascara():
    return [mascara([o])[0] for o in OPCIONES]


def busqueda_local(evaluador, m_inicial, presupuesto, objetivo, ordenes, completo=False):
    """Hill-climbing determinista con mejora estricta. Vecinos:
      - distancia 1: cualquiera de las 7 opciones en un partido;
      - distancia 2: para cada par (i, j), cambio de tamanos (a, b) con el
        contenido dado por el ranking; si `completo`, todas las 7x7 opciones.
    Siempre dentro del presupuesto. Devuelve (mascara, valor, n_evaluaciones)."""
    opciones = _opciones_mascara()
    n = m_inicial.shape[0]
    actual = m_inicial.copy()
    valor = evaluador.objetivo(actual, objetivo)
    evaluaciones = 1

    def coste(m):
        return int(np.prod(m.sum(axis=1)))

    while True:
        mejor_valor, mejor_m = valor, None
        # distancia 1
        for i in range(n):
            tam_resto = coste(actual) // int(actual[i].sum())
            for op in opciones:
                if np.array_equal(op, actual[i]) or tam_resto * int(op.sum()) > presupuesto:
                    continue
                cand = actual.copy()
                cand[i] = op
                v = evaluador.objetivo(cand, objetivo)
                evaluaciones += 1
                if v > mejor_valor + 1e-12:
                    mejor_valor, mejor_m = v, cand
        if mejor_m is None:
            # distancia 2
            for i, j in itertools.combinations(range(n), 2):
                ti, tj = int(actual[i].sum()), int(actual[j].sum())
                tam_resto = coste(actual) // (ti * tj)
                if completo:
                    pares = [(a, b) for a in opciones for b in opciones]
                else:
                    pares = [(subconjunto(ordenes[i], a), subconjunto(ordenes[j], b))
                             for a in (1, 2, 3) for b in (1, 2, 3)]
                for a, b in pares:
                    if tam_resto * int(a.sum()) * int(b.sum()) > presupuesto:
                        continue
                    if np.array_equal(a, actual[i]) and np.array_equal(b, actual[j]):
                        continue
                    cand = actual.copy()
                    cand[i] = a
                    cand[j] = b
                    v = evaluador.objetivo(cand, objetivo)
                    evaluaciones += 1
                    if v > mejor_valor + 1e-12:
                        mejor_valor, mejor_m = v, cand
        if mejor_m is None:
            return actual, valor, evaluaciones
        actual, valor = mejor_m, mejor_valor


# ---------------------------------------------------------------------------
# API publica
# ---------------------------------------------------------------------------
def _columna(indices, n):
    m = np.zeros((n, 3), dtype=bool)
    for i, j in enumerate(indices):
        m[i, j] = True
    return m


def _motivo(signos, ratios_i, tam):
    if tam == 3:
        return f"triple: 1/(p1+p2) = {ratios_i['ratio_triple']:.2f} (p1+p2 = {ratios_i['p1'] + ratios_i['p2']:.0%})"
    if tam == 2:
        return f"doble: p2/p1 = {ratios_i['ratio_doble']:.2f} ({ratios_i['p2']:.0%}/{ratios_i['p1']:.0%})"
    return f"fijo {signos}: p1 = {ratios_i['p1']:.0%}, p2/p1 = {ratios_i['ratio_doble']:.2f}"


def optimizar(partidos_probs, masa, presupuesto_columnas, objetivo="premio_esperado",
              contra_masa=False, recaudacion=None, factor_acertantes=1.0,
              n_arranques=N_ARRANQUES):
    """Mejor sistema producto para 14 partidos dentro de un presupuesto.

    partidos_probs: 14 dicts {1,X,2} (probabilidad real, % o fraccion).
    masa: 14 dicts {1,X,2} con el % de apostantes LAE (None solo para P14 /
          P13plus; entonces no hay premio_esperado ni columna de la masa).
    presupuesto_columnas: entero >= 1 (columnas; 0,75 EUR cada una).
    objetivo: 'P14' | 'P13plus' | 'premio_esperado'.
    contra_masa: signo base = argmax p/s en vez de argmax p.
    """
    if objetivo not in OBJETIVOS:
        raise ValueError(f"objetivo debe ser uno de {OBJETIVOS}")
    presupuesto = int(presupuesto_columnas)
    if presupuesto < 1:
        raise ValueError("presupuesto_columnas debe ser >= 1")
    if len(partidos_probs) != 14:
        raise ValueError("se esperan 14 partidos")
    if masa is None and (objetivo == "premio_esperado" or contra_masa):
        raise ValueError("premio_esperado y contra_masa necesitan la masa LAE")

    t0 = time.perf_counter()
    probs = matriz_probs(partidos_probs)
    masa_m = matriz_probs(masa) if masa is not None else None
    if recaudacion is None:
        recaudacion = RECAUDACION_DEFECTO
    ev = Evaluador(probs, masa_m, recaudacion=recaudacion, factor_acertantes=factor_acertantes)
    n = probs.shape[0]
    ordenes = [orden_signos(probs[i], masa_m[i] if masa_m is not None else None, contra_masa) for i in range(n)]
    ratios = ratios_ranking(probs)

    # 1) estructuras rellenadas por ranking
    candidatos = []
    for t, d, coste in estructuras_posibles(presupuesto, n):
        m = asignar_estructura(ordenes, ratios, t, d)
        candidatos.append((ev.objetivo(m, objetivo), -coste, t, d, m))
    candidatos.sort(key=lambda c: (-c[0], c[1], c[2], c[3]))
    mejor_greedy = candidatos[0]

    # 2) busqueda local desde las mejores estructuras
    completo = objetivo != "premio_esperado"
    mejor_m, mejor_valor, evaluaciones = None, -np.inf, len(candidatos)
    for valor_ini, _, t, d, m in candidatos[:max(1, int(n_arranques))]:
        m_loc, v_loc, ne = busqueda_local(ev, m, presupuesto, objetivo, ordenes, completo=completo)
        evaluaciones += ne
        if v_loc > mejor_valor + 1e-12:
            mejor_valor, mejor_m = v_loc, m_loc
    signos = signos_desde_mascara(mejor_m)
    met = ev.metricas(mejor_m)
    columnas = met["columnas"]

    # 3) comparaciones: columna de la masa y columna de fijos del motor
    comparaciones = {}
    col_motor = _columna([int(np.argmax(probs[i])) for i in range(n)], n)
    comparaciones["motor_fijos"] = {"signos": signos_desde_mascara(col_motor), **_redondear(ev.metricas(col_motor))}
    if masa_m is not None:
        col_masa = _columna([int(np.argmax(masa_m[i])) for i in range(n)], n)
        comparaciones["masa"] = {"signos": signos_desde_mascara(col_masa), **_redondear(ev.metricas(col_masa))}
        col_edge = _columna([int(np.argmax(probs[i] / masa_m[i])) for i in range(n)], n)
        comparaciones["edge_p_entre_s"] = {"signos": signos_desde_mascara(col_edge), **_redondear(ev.metricas(col_edge))}
    comparaciones["mejor_estructura_sin_busqueda_local"] = {
        "signos": signos_desde_mascara(mejor_greedy[4]),
        "triples": mejor_greedy[2], "dobles": mejor_greedy[3],
        "valor_objetivo": float(mejor_greedy[0]),
    }

    detalle = []
    tam = mejor_m.sum(axis=1)
    for i in range(n):
        fila = {
            "num": i + 1,
            "signos": signos[i],
            "tamano": int(tam[i]),
            "p": {s: round(float(probs[i, j]), 4) for j, s in enumerate(SIGNOS)},
            "ratio_doble": round(ratios[i]["ratio_doble"], 4),
            "ratio_triple": round(ratios[i]["ratio_triple"], 4),
            "motivo": _motivo(signos[i], ratios[i], int(tam[i])),
        }
        if masa_m is not None:
            fila["masa"] = {s: round(float(masa_m[i, j]), 4) for j, s in enumerate(SIGNOS)}
            fila["edge_p_entre_s"] = {s: round(float(probs[i, j] / masa_m[i, j]), 3) for j, s in enumerate(SIGNOS)}
            fila["base_contra_masa"] = SIGNOS[int(np.argmax(probs[i] / masa_m[i]))]
        detalle.append(fila)

    salida = {
        "objetivo": objetivo,
        "contra_masa": bool(contra_masa),
        "presupuesto_columnas": presupuesto,
        "signos": signos,
        "columnas": columnas,
        "coste_eur": coste_eur(columnas),
        "triples": int((tam == 3).sum()),
        "dobles": int((tam == 2).sum()),
        "valor_objetivo": float(mejor_valor),
        "detalle_partidos": detalle,
        "comparaciones": comparaciones,
        "recaudacion_eur": float(recaudacion),
        "factor_acertantes": ev.factor_acertantes,
        "evaluaciones": int(evaluaciones),
        "segundos": round(time.perf_counter() - t0, 3),
        "modelo_premio": (
            "pari-mutuel categorias 10-14 sin Pleno al 15 ni Elige 8; 12-14 exactas "
            "(enumeracion de resultados con <=2 partidos sin cubrir, rivales Poisson(N*P_masa_k(x)), "
            "E[1/(X+m)]), 10-11 por campo medio; premio minimo 1,5 EUR y gravamen 20% > 40.000 EUR."
        ),
    }
    salida.update(_redondear(met))
    return salida


def _redondear(met):
    out = {}
    for k, v in met.items():
        if k == "premio_por_categoria":
            out[k] = {c: round(x, 4) for c, x in v.items()}
        elif isinstance(v, float):
            out[k] = round(v, 6) if k.startswith("P") else round(v, 4)
        else:
            out[k] = v
    return out


# ---------------------------------------------------------------------------
# datos de la jornada actual (solo lectura)
# ---------------------------------------------------------------------------
RECAUDACION_PLAUSIBLE = (300_000.0, 20_000_000.0)


def recaudacion_media_plausible(etiqueta=None):
    """Media de las recaudaciones reales de la temporada que sean plausibles
    (0,3-20 M EUR); si un escrutinio trae una recaudacion fuera de rango (J23
    26/27 guarda 294 M por un error de parseo) se reconstruye de la 3a
    categoria (acertantes x premio / 7,5%). (valor, n_escrutinios)."""
    from actualizar_porcentajes_lae import SALIDA_BASE, temporada_etiqueta
    from optimizador_ev_premio import cargar_json

    etiqueta = etiqueta or temporada_etiqueta(datetime.now())
    carpeta = SALIDA_BASE / etiqueta
    valores = []
    if carpeta.exists():
        for path in carpeta.glob("jornada_*.json"):
            escrutinio = cargar_json(path, {}).get("escrutinio") or {}
            valor = escrutinio.get("recaudacion_eur")
            if not (isinstance(valor, (int, float)) and RECAUDACION_PLAUSIBLE[0] <= valor <= RECAUDACION_PLAUSIBLE[1]):
                cat = (escrutinio.get("categorias") or {}).get("13") or {}
                acert, premio = cat.get("acertantes") or 0, cat.get("premio_eur") or 0.0
                valor = acert * premio / FRACCION_RECAUDACION[13] if acert > 0 and premio > 0 else None
            if isinstance(valor, (int, float)) and RECAUDACION_PLAUSIBLE[0] <= valor <= RECAUDACION_PLAUSIBLE[1]:
                valores.append(float(valor))
    if valores:
        return round(sum(valores) / len(valores), 2), len(valores)
    return RECAUDACION_DEFECTO, 0


def datos_jornada_actual():
    """(jornada, partidos, probs_mezcla, masa, recaudacion, factor, fuente_masa)
    a partir de ultima_prediccion.json + fuente_losilla.json + % LAE. Sin
    escribir nada."""
    from optimizador_ev_premio import (
        cargar_json,
        factor_acertantes_actual,
        mezclar_probabilidades,
        porcentajes_masa,
        probabilidades_losilla_por_numero,
    )

    prediccion = cargar_json(PREDICCION, {})
    jornada = prediccion.get("jornada")
    partidos = sorted(
        [p for p in prediccion.get("partidos") or []
         if isinstance(p.get("num"), int) and 1 <= p["num"] <= 14 and p.get("probabilidades")],
        key=lambda p: p["num"],
    )
    if len(partidos) != 14:
        return None
    fuente_losilla = cargar_json(FUENTE_LOSILLA, {})
    losilla = probabilidades_losilla_por_numero(fuente_losilla, jornada)
    probs = []
    for p in partidos:
        mercado = p.get("mercado_losilla") if isinstance(p.get("mercado_losilla"), dict) else None
        if not mercado or not all(mercado.get(s) is not None for s in SIGNOS):
            mercado = losilla.get(p["num"])
        probs.append(mezclar_probabilidades(p.get("probabilidades"), mercado))
    masa_dict, fuente_masa = porcentajes_masa(jornada, fuente_losilla)
    masa = [masa_dict[p["num"]] for p in partidos] if masa_dict and all(p["num"] in masa_dict for p in partidos) else None
    recaudacion, _ = recaudacion_media_plausible()
    factor, _ = factor_acertantes_actual()
    return {
        "jornada": jornada,
        "partidos": partidos,
        "probs": probs,
        "masa": masa,
        "recaudacion": recaudacion,
        "factor_acertantes": factor,
        "fuente_masa": fuente_masa,
        "presupuesto_publicado": int((prediccion.get("coste") or {}).get("apuestas") or 0),
    }


def main(argv=None):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    datos = datos_jornada_actual()
    if not datos:
        print("Sin ultima_prediccion.json con 14 partidos; nada que optimizar.")
        return
    print(f"Optimizador de boleto - jornada {datos['jornada']} (solo lectura) - {datetime.now():%Y-%m-%d %H:%M}")
    print(f"Recaudacion estimada {datos['recaudacion']:,.0f} EUR, factor acertantes {datos['factor_acertantes']:.2f}, "
          f"masa: {datos['fuente_masa'] or 'NO DISPONIBLE (solo P14/P13plus)'}")
    for i, p in enumerate(datos["partidos"]):
        pr = datos["probs"][i]
        linea = f"  {p['num']:>2}. {str(p.get('local'))[:22]:<22} - {str(p.get('visitante'))[:22]:<22} " \
                f"p(mezcla) {pr['1']:.0%}/{pr['X']:.0%}/{pr['2']:.0%}"
        if datos["masa"]:
            ms = normalizar_probs(datos["masa"][i])
            linea += f"  masa {ms['1']:.0%}/{ms['X']:.0%}/{ms['2']:.0%}"
        print(linea)
    objetivos = OBJETIVOS if datos["masa"] else ("P14", "P13plus")
    for presupuesto in PRESUPUESTOS_WEB:
        print(f"\n== Presupuesto {presupuesto} columnas ({coste_eur(presupuesto):.2f} EUR) ==")
        for objetivo in objetivos:
            for contra in ((False, True) if datos["masa"] else (False,)):
                res = optimizar(datos["probs"], datos["masa"], presupuesto, objetivo=objetivo,
                                contra_masa=contra, recaudacion=datos["recaudacion"],
                                factor_acertantes=datos["factor_acertantes"])
                etiqueta = f"{objetivo}{' contra_masa' if contra else ''}"
                premio = f" EV {res['premio_esperado']:.2f} EUR" if "premio_esperado" in res else ""
                print(f"  {etiqueta:<28} {' '.join(f'{s:<3}' for s in res['signos'])} "
                      f"| {res['columnas']:>3} col {res['triples']}T+{res['dobles']}D "
                      f"| P14 {res['P14']:.5f} P13+ {res['P13plus']:.4f}{premio} | {res['segundos']:.1f}s")
        if datos["masa"]:
            comp = res["comparaciones"]
            print(f"  {'columna masa (1 col)':<28} {' '.join(f'{s:<3}' for s in comp['masa']['signos'])} "
                  f"| P14 {comp['masa']['P14']:.5f} P13+ {comp['masa']['P13plus']:.4f} EV {comp['masa']['premio_esperado']:.2f} EUR")
            print(f"  {'columna motor fijos (1 col)':<28} {' '.join(f'{s:<3}' for s in comp['motor_fijos']['signos'])} "
                  f"| P14 {comp['motor_fijos']['P14']:.5f} P13+ {comp['motor_fijos']['P13plus']:.4f} EV {comp['motor_fijos']['premio_esperado']:.2f} EUR")


if __name__ == "__main__":
    main()
