"""Modelo Dixon-Coles (1997) + devig de Shin para el motor de La Quiniela.

Aprobado por Marc el 02/10/2026 tras la investigacion mundial de metodos
(INVESTIGACION_METODOS_MUNDIALES.md, candidatos 1 y 2). NO esta integrado
en el motor todavia: primero el backtest (backtest_dixon_coles.py) debe
demostrar mejora sobre las senales actuales, como manda el metodo.

Dixon & Coles, "Modelling Association Football Scores and Inefficiencies
in the Football Betting Market", JRSS C 46(2), 1997:
 - goles local ~ Poisson(ataque_i * defensa_j * gamma), visitante ~ Poisson(ataque_j * defensa_i)
 - correccion tau (parametro rho) que mueve probabilidad hacia/desde los
   marcadores bajos 0-0, 1-0, 0-1, 1-1 (la Poisson independiente
   infrapredice los empates cortos -nuestra herida de las X)
 - decaimiento temporal exponencial exp(-xi * semanas) al ponderar partidos

Shin (1991-93): el margen del bookmaker NO se reparte proporcionalmente
(protege contra insiders recortando longshots). El devig de Shin estima la
fraccion z de dinero informado y devuelve probabilidades justas mejor
calibradas que la normalizacion simple.

Entrena con data/memoria_ia/historico_ligas_espana.json (3 temporadas de
1a y 2a con goles) + los resultados de la temporada en curso de
data/calendario_primera.json / data/calendario_segunda.json. Ajuste
CONJUNTO de ambas divisiones (los equipos que suben/bajan conservan su
fuerza estimada, clave para La Quiniela que mezcla 1a y 2a).
"""
import json
import math
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy.optimize import minimize

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
HISTORICO = DATA / "memoria_ia" / "historico_ligas_espana.json"
CALENDARIOS = (DATA / "calendario_primera.json", DATA / "calendario_segunda.json")

MAX_GOLES = 10          # truncado de la malla de marcadores
XI_SEMANAS = 0.0045     # decaimiento temporal por semana (se valida en backtest;
                        # D-C 1997 hallaron ~0.0065 con medias semanas, penaltyblog
                        # recomienda mas suave con ~4 temporadas)


def normalizar_nombre(texto):
    texto = str(texto or "").lower()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    texto = re.sub(r"\b(cd|cf|fc|ud|sd|rc|rcd|ca|ce|ad|cp|r|real|club|deportivo|de|la|el|los|las|balompie|futbol)\b", " ", texto)
    texto = re.sub(r"[^a-z0-9]+", " ", texto)
    return " ".join(texto.split()).strip()


# historico usa nombres estilo football-data ("Vallecano", "Sociedad", "Ath Bilbao");
# calendarios y jornadas usan nombres oficiales. Mapa de apoyo (ambos sentidos via normalizar).
ALIAS = {
    "rayo vallecano madrid": "vallecano",
    "rayo vallecano": "vallecano",
    "sociedad": "sociedad",
    "athletic": "ath bilbao",
    "athletic bilbao": "ath bilbao",
    "atletico madrid": "ath madrid",
    "sporting gijon": "sp gijon",
    "racing santander": "santander",
    "r santander": "santander",
    "racing ferrol": "ferrol",
    "espanyol barcelona": "espanol",
    "espanyol": "espanol",
    "coruna": "la coruna",
    "r coruna": "la coruna",
}


def clave_equipo(nombre):
    n = normalizar_nombre(nombre)
    return ALIAS.get(n, n)


def _fecha(valor):
    texto = str(valor or "")[:10]
    try:
        return datetime.strptime(texto, "%Y-%m-%d")
    except ValueError:
        return None


def cargar_partidos():
    """Todos los partidos espanoles con goles conocidos: historico 3 temporadas
    + temporada en curso desde los calendarios. Devuelve lista de dicts con
    local/visitante (clave canonica), gl, gv, fecha (datetime) y cuotas si hay."""
    partidos = []
    historico = json.loads(HISTORICO.read_text(encoding="utf-8"))
    for liga in ("primera", "segunda"):
        for temporada in historico["ligas"][liga]["temporadas"].values():
            for p in temporada["partidos"]:
                fecha = _fecha(p.get("fecha"))
                if fecha is None or p.get("gl") is None or p.get("gv") is None:
                    continue
                partidos.append({
                    "local": clave_equipo(p["local"]),
                    "visitante": clave_equipo(p["visitante"]),
                    "gl": int(p["gl"]), "gv": int(p["gv"]),
                    "fecha": fecha, "liga": liga,
                    "cuotas": tuple(p.get(f"cuota_{s}") for s in ("1", "x", "2")),
                })
    for archivo in CALENDARIOS:
        liga = "primera" if "primera" in archivo.name else "segunda"
        data = json.loads(archivo.read_text(encoding="utf-8"))
        for jornada in data.get("jornadas", []):
            for p in jornada.get("partidos", []):
                m = re.match(r"^\s*(\d+)\s*-\s*(\d+)\s*$", str(p.get("resultado") or ""))
                fecha = _fecha(p.get("fecha"))
                if not m or fecha is None:
                    continue
                partidos.append({
                    "local": clave_equipo(p["local"]),
                    "visitante": clave_equipo(p["visitante"]),
                    "gl": int(m.group(1)), "gv": int(m.group(2)),
                    "fecha": fecha, "liga": liga,
                    "cuotas": (None, None, None),
                })
    partidos.sort(key=lambda p: p["fecha"])
    return partidos


def _tau(x, y, lam, mu, rho):
    """Correccion Dixon-Coles para marcadores bajos (vectorizable punto a punto)."""
    if x == 0 and y == 0:
        return 1.0 - lam * mu * rho
    if x == 0 and y == 1:
        return 1.0 + lam * rho
    if x == 1 and y == 0:
        return 1.0 + mu * rho
    if x == 1 and y == 1:
        return 1.0 - rho
    return 1.0


class DixonColes:
    def __init__(self, xi=XI_SEMANAS):
        self.xi = xi
        self.equipos = []
        self.indice = {}
        self.ataque = None
        self.defensa = None
        self.gamma = 0.25   # log ventaja local
        self.rho = -0.05

    def entrenar(self, partidos, hasta_fecha):
        """Ajusta con los partidos ANTERIORES a hasta_fecha (walk-forward sin fugas)."""
        usados = [p for p in partidos if p["fecha"] < hasta_fecha]
        if len(usados) < 200:
            raise ValueError(f"Historial insuficiente: {len(usados)} partidos")
        self.equipos = sorted({p["local"] for p in usados} | {p["visitante"] for p in usados})
        self.indice = {e: i for i, e in enumerate(self.equipos)}
        n = len(self.equipos)
        il = np.array([self.indice[p["local"]] for p in usados])
        iv = np.array([self.indice[p["visitante"]] for p in usados])
        gl = np.array([p["gl"] for p in usados], dtype=float)
        gv = np.array([p["gv"] for p in usados], dtype=float)
        semanas = np.array([(hasta_fecha - p["fecha"]).days / 7.0 for p in usados])
        pesos = np.exp(-self.xi * semanas)

        def neg_log_like(params):
            ataque = params[:n]
            defensa = params[n:2 * n]
            gamma, rho = params[2 * n], params[2 * n + 1]
            lam = np.exp(ataque[il] + defensa[iv] + gamma)
            mu = np.exp(ataque[iv] + defensa[il])
            # log-verosimilitud Poisson + log(tau) en los marcadores bajos
            ll = pesos * (gl * np.log(lam) - lam + gv * np.log(mu) - mu)
            tau = np.ones_like(lam)
            m00 = (gl == 0) & (gv == 0)
            m01 = (gl == 0) & (gv == 1)
            m10 = (gl == 1) & (gv == 0)
            m11 = (gl == 1) & (gv == 1)
            tau[m00] = 1.0 - lam[m00] * mu[m00] * rho
            tau[m01] = 1.0 + lam[m01] * rho
            tau[m10] = 1.0 + mu[m10] * rho
            tau[m11] = 1.0 - rho
            tau = np.clip(tau, 1e-10, None)
            ll += pesos * np.log(tau)
            return -ll.sum()

        x0 = np.concatenate([np.zeros(n), np.zeros(n), [0.25, -0.05]])
        # identificabilidad: se fija la media de ataques a 0 via penalizacion suave
        def objetivo(params):
            return neg_log_like(params) + 1000.0 * params[:n].mean() ** 2
        res = minimize(objetivo, x0, method="L-BFGS-B",
                       bounds=[(-3, 3)] * (2 * n) + [(0, 1), (-0.9, 0.9)],
                       options={"maxiter": 400})
        self.ataque = res.x[:n]
        self.defensa = res.x[n:2 * n]
        self.gamma = float(res.x[2 * n])
        self.rho = float(res.x[2 * n + 1])
        self.convergio = bool(res.success)
        self.n_partidos = len(usados)
        return self

    def conoce(self, local, visitante):
        return clave_equipo(local) in self.indice and clave_equipo(visitante) in self.indice

    def probabilidades(self, local, visitante):
        """P(1), P(X), P(2) para local-visitante. None si falta algun equipo."""
        cl, cv = clave_equipo(local), clave_equipo(visitante)
        if cl not in self.indice or cv not in self.indice:
            return None
        i, j = self.indice[cl], self.indice[cv]
        lam = math.exp(self.ataque[i] + self.defensa[j] + self.gamma)
        mu = math.exp(self.ataque[j] + self.defensa[i])
        p1 = px = p2 = 0.0
        for x in range(MAX_GOLES + 1):
            px_l = math.exp(-lam) * lam ** x / math.factorial(x)
            for y in range(MAX_GOLES + 1):
                py_v = math.exp(-mu) * mu ** y / math.factorial(y)
                prob = px_l * py_v * _tau(x, y, lam, mu, self.rho)
                if x > y:
                    p1 += prob
                elif x == y:
                    px += prob
                else:
                    p2 += prob
        total = p1 + px + p2
        return {"1": p1 / total, "X": px / total, "2": p2 / total}


_MODELO_CACHE = None


def probabilidades_dixon_coles(local, visitante):
    """Puerta de entrada para el motor: entrena una vez por proceso (con todo
    el historial disponible hasta hoy) y devuelve {'1','X','2'} en [0,1], o
    None si el modelo no cubre alguno de los equipos (Liga F, selecciones,
    Champions...) o si algo falla. NUNCA lanza: el motor no debe caerse por
    esta senal."""
    global _MODELO_CACHE
    try:
        if _MODELO_CACHE is None:
            _MODELO_CACHE = DixonColes().entrenar(cargar_partidos(), datetime.now())
        return _MODELO_CACHE.probabilidades(local, visitante)
    except Exception:
        return None


def shin_devig(cuotas):
    """Probabilidades justas desde cuotas 1X2 con el metodo de Shin.

    Resuelve z (fraccion de dinero informado) por biseccion sobre la
    condicion de que las probabilidades de Shin sumen 1. Devuelve None si
    las cuotas no son validas. Con margen ~0 degenera a la normalizacion."""
    try:
        inv = [1.0 / float(c) for c in cuotas]
    except (TypeError, ValueError, ZeroDivisionError):
        return None
    if any(v <= 0 or not math.isfinite(v) for v in inv):
        return None
    suma = sum(inv)
    if suma <= 1.0:  # sin margen: normalizar y listo
        return {s: v / suma for s, v in zip("1X2", inv)}

    def probs_shin(z):
        return [(math.sqrt(z * z + 4 * (1 - z) * (v * v) / suma) - z) / (2 * (1 - z)) for v in inv]

    lo, hi = 0.0, 0.4
    for _ in range(80):
        z = (lo + hi) / 2
        if sum(probs_shin(z)) > 1.0:
            lo = z
        else:
            hi = z
    p = probs_shin((lo + hi) / 2)
    total = sum(p)
    return {s: v / total for s, v in zip("1X2", p)}


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    partidos = cargar_partidos()
    print(f"Partidos cargados: {len(partidos)} ({partidos[0]['fecha']:%Y-%m-%d} a {partidos[-1]['fecha']:%Y-%m-%d})")
    modelo = DixonColes().entrenar(partidos, datetime.now())
    print(f"Entrenado con {modelo.n_partidos} partidos, {len(modelo.equipos)} equipos | convergio={modelo.convergio}")
    print(f"gamma (ventaja local) = {modelo.gamma:.3f} -> factor {math.exp(modelo.gamma):.2f} | rho = {modelo.rho:.4f}")
    for l, v in (("Real Madrid", "Barcelona"), ("Cadiz", "Castellon"), ("Burgos", "Eldense")):
        pr = modelo.probabilidades(l, v)
        if pr:
            print(f"  {l}-{v}: 1={pr['1']*100:.0f}% X={pr['X']*100:.0f}% 2={pr['2']*100:.0f}%")
    print("Shin demo cuotas (2.10, 3.30, 3.60):", {k: round(v, 3) for k, v in shin_devig((2.10, 3.30, 3.60)).items()})
