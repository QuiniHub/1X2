"""Modelo de reparto de premios de La Quiniela (estilo pena Q84).

La Quiniela es pari-mutuel: el premio por categoria depende de CUANTA masa
de apostantes comparte los signos acertados. Este modulo estima, para unos
porcentajes de apostantes LAE por signo y partido:

- la distribucion de aciertos de una columna "de la masa" (multinomial
  independiente por partido con los % oficiales de apostantes),
- el numero esperado de acertantes por categoria (10-14),
- el premio esperado por columna acertante en cada categoria,
- el EV en euros de un boleto propio (Monte Carlo sobre resultados muestreados
  de nuestras probabilidades reales, con numeros aleatorios comunes para poder
  comparar boletos candidatos de forma estable).

Reparto oficial, DESCUBIERTO calibrando contra 11 escrutinios reales de la
26/27 (J1-J12; los cocientes premio*acertantes/recaudacion salen exactos):
16% de la recaudacion a 1a (14), 7,5% a 2a (13), 3a (12) y 4a (11), 9% a
5a (10) y 7,5% al Pleno al 15 (bote) -55% en total. El Pleno al 15 y el
Elige 8 quedan FUERA de este modelo a proposito (fondos aparte; su omision
hace el EV conservador, nunca optimista).

Dos reglas mas, tambien verificadas contra escrutinios reales:
- El premio publicado (y cobrado) es NETO del gravamen del 20% sobre el
  exceso de 40.000 EUR por premio (J1: 273.214,44 brutos - 20% x 233.214,44
  = 226.571,55 EUR netos, exacto; tambien exacto en J3, J6 y J9).
- Un premio por apuesta por debajo de ~1,5 EUR no se paga (J8: 1,46 EUR
  calculados -> 0,00 pagado; J3: 2,32 -> pagado). El umbral real esta entre
  1,46 y 2,32; se usa 1,50 (el precio de la apuesta minima).
"""
import math

import numpy as np

SIGNOS = ("1", "X", "2")
PRECIO_APUESTA = 0.75
# Fraccion de la RECAUDACION total destinada a cada categoria.
FRACCION_RECAUDACION = {14: 0.16, 13: 0.075, 12: 0.075, 11: 0.075, 10: 0.09}
CATEGORIAS = (10, 11, 12, 13, 14)
PREMIO_MINIMO_PAGADO = 1.5
GRAVAMEN_EXENTO = 40_000.0
GRAVAMEN_TIPO = 0.20
# Respaldo si no hay escrutinios capturados de los que estimar la recaudacion
# (la 26/27 real va de 0,73M a 3,78M EUR por jornada; media ~2,2M).
RECAUDACION_DEFECTO = 2_200_000.0


def premio_neto(premio_bruto):
    """Premio cobrado tras el gravamen del 20% sobre el exceso de 40.000 EUR."""
    exceso = max(float(premio_bruto) - GRAVAMEN_EXENTO, 0.0)
    return float(premio_bruto) - GRAVAMEN_TIPO * exceso


def normalizar_probs(valores):
    """{signo: peso} -> {signo: probabilidad} que suma 1 (acepta % 0-100)."""
    pesos = {s: max(float(valores.get(s) or 0.0), 0.0) for s in SIGNOS}
    total = sum(pesos.values())
    if total <= 0:
        return {s: 1.0 / 3.0 for s in SIGNOS}
    return {s: v / total for s, v in pesos.items()}


def distribucion_aciertos_masa(pct_masa, signos_reales):
    """P(una columna de la masa acierte exactamente k) para k=0..14.

    pct_masa: lista de 14 dicts {1,X,2} (porcentajes de apostantes LAE).
    signos_reales: lista de 14 signos oficiales "1"/"X"/"2".
    Poisson-binomial por convolucion (independencia entre partidos: es la
    aproximacion Q84, validada contra escrutinios reales en el backtest).
    """
    dist = [1.0] + [0.0] * len(pct_masa)
    for i, (pct, signo) in enumerate(zip(pct_masa, signos_reales)):
        p = normalizar_probs(pct)[str(signo).upper()]
        nueva = [0.0] * len(dist)
        for k in range(i + 1):  # tras i partidos solo hay masa hasta k=i
            nueva[k] += dist[k] * (1.0 - p)
            nueva[k + 1] += dist[k] * p
        dist = nueva
    return dist


def acertantes_esperados(dist_masa, recaudacion):
    """Numero esperado de acertantes por categoria dado P(masa acierte k)."""
    apuestas_totales = recaudacion / PRECIO_APUESTA
    return {k: apuestas_totales * dist_masa[k] for k in CATEGORIAS}


def premio_categoria_modelo(categoria, acertantes, recaudacion):
    """Premio por apuesta acertante que predice el modelo (determinista,
    para validar contra el escrutinio real: fondo / acertantes)."""
    fondo = FRACCION_RECAUDACION[categoria] * recaudacion
    if acertantes <= 0:
        return 0.0
    premio = fondo / acertantes
    if premio < PREMIO_MINIMO_PAGADO:
        return 0.0
    return premio_neto(premio)


def premio_esperado_si_acertamos(categoria, lam, recaudacion):
    """E[premio] para UNA columna nuestra que acierta `categoria`, cuando el
    numero de OTROS acertantes es Poisson(lam): fondo * E[1/(1+X)]
    = fondo * (1 - e^-lam) / lam. Respeta la regla del premio minimo y aplica
    el gravamen del 20% sobre el valor esperado (aproximacion: el gravamen
    solo muerde con pocos acertantes, justo cuando E[premio] ~ premio)."""
    fondo = FRACCION_RECAUDACION[categoria] * recaudacion
    if lam < 1e-9:
        esperado = fondo
    else:
        esperado = fondo * (1.0 - math.exp(-lam)) / lam
    if fondo / (lam + 1.0) < PREMIO_MINIMO_PAGADO:
        return 0.0
    return premio_neto(esperado)


class EvaluadorEV:
    """Evalua el EV en euros de boletos candidatos sobre un MISMO conjunto de
    resultados muestreados (numeros aleatorios comunes), para que comparar dos
    boletos no dependa del ruido del muestreo.

    Las categorias 12, 13 y 14 se calculan EXACTAS: acertar 14 fija el vector
    de resultados entero, acertar 13 lo fija salvo un partido y acertar 12
    salvo dos, y para esos resultados la cola de la Poisson-binomial de la
    masa tiene forma cerrada via simetricas elementales de x_j=(1-q_j)/q_j:
    P_masa(14)=prod(q), P_masa(13)=prod(q)*S1, P_masa(12)=prod(q)*(S1^2-S2)/2.
    Sin eso, los premios gordos -raros y enormes- dominan el ruido Monte
    Carlo y un optimizador que compare miles de candidatos acaba eligiendo
    el que tuvo suerte EN LAS MUESTRAS (winner's curse), no el mejor de
    verdad: en la primera version el "optimizado" marcaba 58 EUR de EV en
    sus muestras y 3 EUR al reevaluarlo con muestras frescas. Las categorias
    10-11 van por Monte Carlo (alli el ruido es de centimos).

    p_real: 14 dicts {1,X,2} con nuestra probabilidad real por partido.
    pct_masa: 14 dicts {1,X,2} con el % de apostantes LAE por signo.
    """

    def __init__(self, p_real, pct_masa, recaudacion=RECAUDACION_DEFECTO,
                 n_muestras=4000, semilla=20261013):
        if len(p_real) != len(pct_masa):
            raise ValueError("p_real y pct_masa deben tener el mismo numero de partidos")
        self.n_partidos = len(p_real)
        self.recaudacion = float(recaudacion)
        self.n_muestras = int(n_muestras)
        probs = np.array([[normalizar_probs(p)[s] for s in SIGNOS] for p in p_real])
        masa = np.array([[normalizar_probs(m)[s] for s in SIGNOS] for m in pct_masa])
        # suelos minimos: evitar divisiones por cero en las formas cerradas
        # (un signo con 0% de apostantes LAE sigue teniendo alguna apuesta)
        probs = np.clip(probs, 1e-6, None)
        masa = np.clip(masa, 1e-4, None)
        self._probs = probs
        self._masa = masa

        rng = np.random.default_rng(semilla)
        acumuladas = probs.cumsum(axis=1)
        u = rng.random((self.n_muestras, self.n_partidos))
        # indice de signo 0/1/2 muestreado por partido y muestra
        self.resultados = (u[:, :, None] > acumuladas[None, :, :]).sum(axis=2).clip(0, 2)

        # Probabilidad de que una columna de la masa acierte cada partido,
        # dado el resultado muestreado.
        p_hit_masa = np.take_along_axis(
            masa[None, :, :].repeat(self.n_muestras, axis=0),
            self.resultados[:, :, None], axis=2,
        )[:, :, 0]
        dist = np.zeros((self.n_muestras, self.n_partidos + 1))
        dist[:, 0] = 1.0
        for i in range(self.n_partidos):
            p = p_hit_masa[:, i][:, None]
            nueva = dist * (1.0 - p)
            nueva[:, 1:] += dist[:, :-1] * p[:, 0][:, None]
            dist = nueva

        apuestas_totales = self.recaudacion / PRECIO_APUESTA
        cats = np.array(CATEGORIAS)
        lam = apuestas_totales * dist[:, cats]  # (n_muestras, 5)
        fondo = np.array([FRACCION_RECAUDACION[k] for k in CATEGORIAS]) * self.recaudacion
        with np.errstate(divide="ignore", invalid="ignore"):
            esperado = np.where(lam < 1e-9, fondo, fondo * (1.0 - np.exp(-lam)) / np.maximum(lam, 1e-9))
        por_debajo_minimo = fondo / (lam + 1.0) < PREMIO_MINIMO_PAGADO
        esperado[por_debajo_minimo] = 0.0
        # gravamen del 20% sobre el exceso de 40.000 EUR (premio neto cobrado)
        esperado -= GRAVAMEN_TIPO * np.maximum(esperado - GRAVAMEN_EXENTO, 0.0)
        # premio esperado por columna nuestra acertante, por muestra y categoria
        self._premios_completos = esperado.copy()  # (n_muestras, 5) con 12-14
        esperado = esperado.copy()
        for cat_exacta in (12, 13, 14):  # las colas van exactas, no por MC
            esperado[:, CATEGORIAS.index(cat_exacta)] = 0.0
        self._premios = esperado

    def _conteo_columnas(self, signos_boleto):
        """Numero de columnas nuestras con exactamente k aciertos, por muestra."""
        elegidos = np.zeros((self.n_partidos, 3), dtype=float)
        tam = np.zeros(self.n_partidos)
        for i, signos in enumerate(signos_boleto):
            limpios = [s for s in SIGNOS if s in str(signos or "").upper()]
            if not limpios:
                limpios = ["1"]
            for s in limpios:
                elegidos[i, SIGNOS.index(s)] = 1.0
            tam[i] = len(limpios)
        hit = np.take_along_axis(
            elegidos[None, :, :].repeat(self.n_muestras, axis=0),
            self.resultados[:, :, None], axis=2,
        )[:, :, 0]  # (n_muestras, n_partidos) en {0,1}
        cuenta = np.zeros((self.n_muestras, self.n_partidos + 1))
        cuenta[:, 0] = 1.0
        for i in range(self.n_partidos):
            h = hit[:, i][:, None]
            fallo = (tam[i] - hit[:, i])[:, None]
            nueva = cuenta * fallo
            nueva[:, 1:] += cuenta[:, :-1] * h[:, 0][:, None]
            cuenta = nueva
        return cuenta

    MAX_COLUMNAS_EXACTO = 2048

    def _premio_vec(self, categoria, lam):
        """premio_esperado_si_acertamos vectorizado sobre un array de lam."""
        fondo = FRACCION_RECAUDACION[categoria] * self.recaudacion
        lam = np.asarray(lam, dtype=float)
        with np.errstate(divide="ignore", invalid="ignore"):
            esperado = np.where(
                lam < 1e-9, fondo, fondo * (1.0 - np.exp(-lam)) / np.maximum(lam, 1e-9)
            )
        esperado = np.where(fondo / (lam + 1.0) < PREMIO_MINIMO_PAGADO, 0.0, esperado)
        return esperado - GRAVAMEN_TIPO * np.maximum(esperado - GRAVAMEN_EXENTO, 0.0)

    def _ev_cola_exacta(self, signos_boleto):
        """EV exacto de las categorias 12, 13 y 14 enumerando las columnas del
        boleto. Acertar 14 fija el resultado (= la columna); acertar 13/12 lo
        fija salvo 1/2 partidos. La cola de la Poisson-binomial de la masa
        para esos resultados tiene forma cerrada con las simetricas
        elementales de x_j = (1-q_j)/q_j: P(14)=prod(q)*e0, P(13)=prod(q)*e1,
        P(12)=prod(q)*e2, con e1=S1 y e2=(S1^2-S2)/2."""
        import itertools

        opciones = []
        for signos in signos_boleto:
            limpios = [SIGNOS.index(s) for s in SIGNOS if s in str(signos or "").upper()]
            opciones.append(limpios or [0])
        columnas = np.array(list(itertools.product(*opciones)))  # (C, 14)
        n_cols, n = columnas.shape
        pos = np.arange(n)
        apuestas_totales = self.recaudacion / PRECIO_APUESTA

        p_col = self._probs[pos, columnas]   # (C, 14) prob real del signo jugado
        q_col = self._masa[pos, columnas]    # (C, 14) % masa del signo jugado
        ratio = (1.0 - self._masa) / self._masa  # (14, 3)
        r_col = ratio[pos, columnas]         # (C, 14)
        P0 = p_col.prod(axis=1)              # (C,)
        M0 = q_col.prod(axis=1)
        S1 = r_col.sum(axis=1)
        S2 = (r_col ** 2).sum(axis=1)

        # signos alternativos por posicion: OTROS[c] = los 2 signos != c
        OTROS = np.array([[1, 2], [0, 2], [0, 1]])
        alt = OTROS[columnas]                           # (C, 14, 2)
        pos3 = pos[None, :, None]
        # factores de cambiar la posicion i de la columna al signo alternativo
        f_p = self._probs[pos3, alt] / p_col[:, :, None]   # (C, 14, 2)
        f_m = self._masa[pos3, alt] / q_col[:, :, None]
        d_r = ratio[pos3, alt] - r_col[:, :, None]         # (C, 14, 2)

        ev_14 = float((P0 * self._premio_vec(14, apuestas_totales * M0)).sum())

        # distancia 1 (categoria 13)
        p_r = P0[:, None, None] * f_p                      # (C, 14, 2)
        m_r = M0[:, None, None] * f_m
        s1_r = S1[:, None, None] + d_r
        lam13 = apuestas_totales * m_r * s1_r
        ev_13 = float((p_r * self._premio_vec(13, lam13)).sum())

        # distancia 2 (categoria 12): pares de posiciones i<j
        ii, jj = np.triu_indices(n, k=1)                   # (91,)
        p_r = (P0[:, None, None, None]
               * f_p[:, ii, :, None] * f_p[:, jj, None, :])    # (C, 91, 2, 2)
        m_r = (M0[:, None, None, None]
               * f_m[:, ii, :, None] * f_m[:, jj, None, :])
        s1_r = S1[:, None, None, None] + d_r[:, ii, :, None] + d_r[:, jj, None, :]
        d_r2 = ratio[pos3, alt] ** 2 - (r_col ** 2)[:, :, None]
        s2_r = S2[:, None, None, None] + d_r2[:, ii, :, None] + d_r2[:, jj, None, :]
        e2 = (s1_r ** 2 - s2_r) / 2.0
        lam12 = apuestas_totales * m_r * e2
        ev_12 = float((p_r * self._premio_vec(12, lam12)).sum())

        return ev_12, ev_13, ev_14

    def evaluar(self, signos_boleto):
        """EV en euros del boleto (solo categorias 10-14; sin Pleno al 15 ni
        Elige 8). Devuelve ev total, desglose por categoria y P(algun premio)."""
        cuenta = self._conteo_columnas(signos_boleto)
        cats = np.array(CATEGORIAS)
        nuestras = cuenta[:, cats]  # columnas nuestras por categoria y muestra
        exacto = columnas_boleto(signos_boleto) <= self.MAX_COLUMNAS_EXACTO
        euros = nuestras * (self._premios if exacto else self._premios_completos)
        euros_completos = nuestras * self._premios_completos
        con_premio = (euros_completos.sum(axis=1) > 0).mean()
        ev_por_categoria = {
            str(k): float(euros[:, idx].mean()) for idx, k in enumerate(CATEGORIAS)
        }
        ev_cola = 0.0
        if exacto:
            ev_12, ev_13, ev_14 = self._ev_cola_exacta(signos_boleto)
            ev_por_categoria["12"] = ev_12
            ev_por_categoria["13"] = ev_13
            ev_por_categoria["14"] = ev_14
            ev_cola = ev_12 + ev_13 + ev_14
        return {
            "ev_eur": float(euros.sum(axis=1).mean()) + ev_cola,
            "ev_por_categoria": ev_por_categoria,
            "probabilidad_premio": float(con_premio),
            "n_muestras": self.n_muestras,
            "cola_12_14_exacta": exacto,
        }


def columnas_boleto(signos_boleto):
    """Numero de apuestas/columnas que genera un boleto (producto de signos)."""
    total = 1
    for signos in signos_boleto:
        limpios = [s for s in SIGNOS if s in str(signos or "").upper()]
        total *= max(len(limpios), 1)
    return total
