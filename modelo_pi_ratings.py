"""Pi-ratings (Constantinou & Fenton 2013) — EXPERIMENTO aprobado por Marc
el 03/10/2026 (candidato 4 de la investigacion mundial). Regla de la casa:
solo se integra al motor si gana el backtest contra la configuracion actual
(Dixon-Coles 0,7); si no, queda documentado como probado-y-descartado.

Idea del paper ("Determining the level of ability of football teams by
dynamic ratings based on the relative discrepancies in scores between
adversaries", J. Quantitative Analysis in Sports 9(1), 2013):
 - cada equipo lleva DOS ratings: uno jugando en casa y otro fuera
   (la objecion de Marc del Sevilla F que solo gana fuera, hecha modelo)
 - los ratings viven en "espacio de diferencia de goles": la diferencia
   esperada de un cruce sale de los ratings, el error observado actualiza
 - DOS velocidades: lambda (cuanto aprende el rating del escenario jugado)
   y gamma (cuanto se contagia al rating del otro escenario) -eso captura
   la forma reciente sin tirar la historia
 - rendimientos decrecientes en goleadas: psi(e) = c*log10(1+e)

Conversion a probabilidades 1X2: la diferencia de goles esperada alimenta
un logit ordenado con dos cortes, ajustado walk-forward sobre el propio
historial (sin fugas de futuro).
"""
import math
from collections import defaultdict

import numpy as np
from scipy.optimize import minimize

# parametros del paper (validados alli sobre 5 temporadas de la EPL)
LAMBDA = 0.035
GAMMA = 0.7
B, C = 10.0, 3.0


def _g(rating):
    """rating -> diferencia de goles esperada aportada por ese rating."""
    return math.copysign(B ** (abs(rating) / C) - 1.0, rating)


def _psi(error):
    return C * math.log10(1.0 + error)


class PiRatings:
    def __init__(self, lam=LAMBDA, gamma=GAMMA):
        self.lam = lam
        self.gamma = gamma
        self.casa = defaultdict(float)
        self.fuera = defaultdict(float)

    def diferencia_esperada(self, local, visitante):
        return _g(self.casa[local]) - _g(self.fuera[visitante])

    def actualizar(self, local, visitante, gl, gv):
        esperada = self.diferencia_esperada(local, visitante)
        error = abs((gl - gv) - esperada)
        ajuste = _psi(error)
        if (gl - gv) < esperada:
            ajuste = -ajuste
        # el equipo local aprende en su rating de casa; una fraccion gamma
        # se contagia a su rating de fuera (y simetrico para el visitante)
        self.casa[local] += ajuste * self.lam
        self.fuera[local] += ajuste * self.lam * self.gamma
        self.fuera[visitante] -= ajuste * self.lam
        self.casa[visitante] -= ajuste * self.lam * self.gamma

    def conoce(self, equipo):
        return equipo in self.casa or equipo in self.fuera


def entrenar_pi(partidos, hasta_fecha, lam=LAMBDA, gamma=GAMMA, calibrar_desde=200):
    """Pasa secuencial por los partidos anteriores a hasta_fecha actualizando
    ratings, y recoge pares (diferencia_esperada, signo) para calibrar el
    logit ordenado. Devuelve (ratings, modelo_logit)."""
    pi = PiRatings(lam, gamma)
    pares = []
    vistos = 0
    for p in partidos:
        if p["fecha"] >= hasta_fecha:
            break
        if vistos >= calibrar_desde:
            signo = "1" if p["gl"] > p["gv"] else ("X" if p["gl"] == p["gv"] else "2")
            pares.append((pi.diferencia_esperada(p["local"], p["visitante"]), signo))
        pi.actualizar(p["local"], p["visitante"], p["gl"], p["gv"])
        vistos += 1
    logit = ajustar_logit_ordenado(pares)
    return pi, logit


def ajustar_logit_ordenado(pares):
    """Logit ordenado 2>X>1 sobre la diferencia esperada: 3 parametros
    (pendiente beta y cortes c1<c2). P(2)=sigma(c1-beta*d), P(2 o X)=sigma(c2-beta*d)."""
    if len(pares) < 100:
        return None
    d = np.array([x for x, _ in pares])
    y = np.array([{"2": 0, "X": 1, "1": 2}[s] for _, s in pares])

    def neg_ll(params):
        beta, c1, delta = params
        c2 = c1 + abs(delta) + 1e-6
        z1 = 1.0 / (1.0 + np.exp(-(c1 - beta * d)))
        z2 = 1.0 / (1.0 + np.exp(-(c2 - beta * d)))
        p2 = np.clip(z1, 1e-9, 1)
        px = np.clip(z2 - z1, 1e-9, 1)
        p1 = np.clip(1 - z2, 1e-9, 1)
        ll = np.where(y == 0, np.log(p2), np.where(y == 1, np.log(px), np.log(p1)))
        return -ll.sum()

    res = minimize(neg_ll, x0=np.array([1.0, -0.6, 1.2]), method="Nelder-Mead",
                   options={"maxiter": 2000, "xatol": 1e-6, "fatol": 1e-6})
    beta, c1, delta = res.x
    return {"beta": float(beta), "c1": float(c1), "c2": float(c1 + abs(delta) + 1e-6)}


def probabilidades_pi(pi, logit, local, visitante):
    """P(1/X/2) desde los ratings + logit calibrado. None si falta algo."""
    if logit is None or not (pi.conoce(local) and pi.conoce(visitante)):
        return None
    d = pi.diferencia_esperada(local, visitante)
    z1 = 1.0 / (1.0 + math.exp(-(logit["c1"] - logit["beta"] * d)))
    z2 = 1.0 / (1.0 + math.exp(-(logit["c2"] - logit["beta"] * d)))
    p2, px, p1 = max(z1, 1e-9), max(z2 - z1, 1e-9), max(1 - z2, 1e-9)
    total = p1 + px + p2
    return {"1": p1 / total, "X": px / total, "2": p2 / total}


if __name__ == "__main__":
    import sys
    from datetime import datetime
    from modelo_dixon_coles import cargar_partidos
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    partidos = cargar_partidos()
    pi, logit = entrenar_pi(partidos, datetime.now())
    print("logit:", logit)
    top = sorted(pi.casa.items(), key=lambda kv: -kv[1])[:8]
    print("top ratings casa:", [(e, round(r, 2)) for e, r in top])
    for l, v in (("castellon", "ceuta"), ("sabadell", "andorra fc"), ("girona", "mallorca")):
        print(l, "-", v, probabilidades_pi(pi, logit, l, v))
