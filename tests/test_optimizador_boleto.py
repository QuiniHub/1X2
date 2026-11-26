"""Tests del optimizador de boleto (Laboratorio, 26/11/2026): exactitud de la
Poisson-binomial frente a fuerza bruta, premio exacto 12-14 frente a una
enumeracion lenta independiente y al modelo de reparto, coste, reglas de
ranking, busqueda local >= greedy, presupuesto y determinismo."""
import itertools
import math
import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import optimizador_boleto as ob
from modelo_reparto_quiniela import EvaluadorEV


def _probs_14(semilla=7):
    rng = np.random.default_rng(semilla)
    base = rng.dirichlet((4.0, 2.5, 2.0), size=14)
    return [dict(zip(("1", "X", "2"), fila)) for fila in base]


def _masa_14(probs, semilla=11):
    """Masa parecida a la real: sobrejuega al favorito, infrajuega la X."""
    rng = np.random.default_rng(semilla)
    salida = []
    for p in probs:
        v = np.array([p["1"], p["X"], p["2"]]) ** 1.6
        v = v / v.sum() + rng.uniform(0, 0.03, 3)
        salida.append(dict(zip(("1", "X", "2"), v / v.sum())))
    return salida


class PoissonBinomialTests(unittest.TestCase):
    def test_distribucion_vs_fuerza_bruta_3_partidos(self):
        rng = np.random.default_rng(3)
        probs = rng.dirichlet((2, 2, 2), size=3)
        sistema = ["1X", "2", "1X2"]
        m = ob.mascara(sistema)
        cubierta = (probs * m).sum(axis=1)
        dist = ob.distribucion_aciertos(cubierta)
        bruto = np.zeros(4)
        for x in itertools.product(range(3), repeat=3):
            p = math.prod(probs[i, x[i]] for i in range(3))
            k = sum(1 for i in range(3) if m[i, x[i]])
            bruto[k] += p
        np.testing.assert_allclose(dist, bruto, atol=1e-12)
        self.assertAlmostEqual(dist.sum(), 1.0, places=12)

    def test_esperanza_columnas_vs_fuerza_bruta(self):
        rng = np.random.default_rng(5)
        probs = rng.dirichlet((2, 2, 2), size=3)
        sistema = ["1X", "X2", "1X2"]
        m = ob.mascara(sistema)
        tam = m.sum(axis=1)
        esperado = ob.esperanza_columnas_por_aciertos((probs * m).sum(axis=1), tam)
        columnas = list(itertools.product(*[np.flatnonzero(m[i]) for i in range(3)]))
        bruto = np.zeros(4)
        for x in itertools.product(range(3), repeat=3):
            p = math.prod(probs[i, x[i]] for i in range(3))
            for col in columnas:
                k = sum(1 for i in range(3) if col[i] == x[i])
                bruto[k] += p
        np.testing.assert_allclose(esperado, bruto, atol=1e-12)
        self.assertAlmostEqual(esperado.sum(), 12.0, places=9)  # 2*2*3 columnas

    def test_p14_un_fijo_es_producto(self):
        probs = _probs_14()
        ev = ob.Evaluador(ob.matriz_probs(probs))
        fijos = ob.mascara([max("1X2", key=lambda s: p[s]) for p in probs])
        esperado = math.prod(max(p.values()) for p in probs)
        self.assertAlmostEqual(ev.probabilidades(fijos)["P14"], esperado, places=12)


class PremioTests(unittest.TestCase):
    def _premio_lento(self, ev, m):
        """Enumeracion independiente: todos los resultados a distancia <= 2 de
        alguna columna, columnas nuestras por categoria via polinomio y masa
        rival por DP (sin formas cerradas)."""
        n = ev.n
        columnas = list(itertools.product(*[np.flatnonzero(m[i]) for i in range(n)]))
        resultados = set()
        for col in columnas:
            resultados.add(col)
            for i in range(n):
                for s in range(3):
                    if s != col[i]:
                        x1 = col[:i] + (s,) + col[i + 1:]
                        resultados.add(x1)
                        for j in range(i + 1, n):
                            for s2 in range(3):
                                if s2 != col[j]:
                                    resultados.add(x1[:j] + (s2,) + x1[j + 1:])
        tam = m.sum(axis=1)
        ev_cat = {12: 0.0, 13: 0.0, 14: 0.0}
        for x in resultados:
            p_x = math.prod(ev.probs[i, x[i]] for i in range(n))
            hit = [1 if m[i, x[i]] else 0 for i in range(n)]
            poli = np.array([1.0])
            for i in range(n):
                nueva = np.zeros(len(poli) + 1)
                nueva[:-1] += poli * (tam[i] - hit[i])
                nueva[1:] += poli * hit[i]
                poli = nueva
            dist_masa = ob.distribucion_aciertos([ev.masa[i, x[i]] for i in range(n)])
            for k in (12, 13, 14):
                ours = poli[k]
                if ours <= 0:
                    continue
                lam = ev.apuestas_rivales * dist_masa[k]
                fondo = ev.fondo[k]
                por_col = fondo * float(ob._esperanza_m_entre_x_mas_m(np.array([lam]), np.array([ours]))[0]) / ours
                if fondo / (lam + ours) < ob.PREMIO_MINIMO_PAGADO:
                    por_col = 0.0
                por_col -= ob.GRAVAMEN_TIPO * max(por_col - ob.GRAVAMEN_EXENTO, 0.0)
                ev_cat[k] += p_x * ours * por_col
        return ev_cat

    def test_premio_12_14_vs_enumeracion_lenta(self):
        probs, masa = _probs_14(), _masa_14(_probs_14())
        ev = ob.Evaluador(ob.matriz_probs(probs), ob.matriz_probs(masa), recaudacion=1_500_000)
        sistema = ["1X2", "1", "1X", "1", "1", "X2", "1", "1", "12", "1", "1", "1", "1", "1"]
        m = ob.mascara(sistema)
        rapido = ev.premio_esperado(m)
        lento = self._premio_lento(ev, m)
        for k in (12, 13, 14):
            self.assertAlmostEqual(rapido[k], lento[k], delta=1e-9 * max(1.0, lento[k]), msg=f"categoria {k}")

    def test_un_fijo_coincide_con_modelo_reparto(self):
        """Con una sola columna (m = 1 en todas las categorias) el 12-14 exacto
        debe coincidir con EvaluadorEV._ev_cola_exacta (mismas formulas)."""
        probs, masa = _probs_14(), _masa_14(_probs_14())
        fijos = [max("1X2", key=lambda s: p[s]) for p in probs]
        ev = ob.Evaluador(ob.matriz_probs(probs), ob.matriz_probs(masa), recaudacion=2_200_000)
        mio = ev.premio_esperado(ob.mascara(fijos))
        referencia = EvaluadorEV(probs, masa, recaudacion=2_200_000, n_muestras=200)._ev_cola_exacta(fijos)
        for k, ref in zip((12, 13, 14), referencia):
            self.assertAlmostEqual(mio[k], ref, delta=2e-3 * max(ref, 1e-6), msg=f"categoria {k}")

    def test_esperanza_poisson(self):
        # lam -> 0: E[m/(X+m)] -> 1 ; lam grande: ~ m/(lam+m) ; m=1 forma cerrada
        self.assertAlmostEqual(float(ob._esperanza_m_entre_x_mas_m(np.array([1e-9]), np.array([3.0]))[0]), 1.0, places=6)
        lam = np.array([2.0, 7.5, 20.0])
        cerrada = (1 - np.exp(-lam)) / lam
        np.testing.assert_allclose(ob._esperanza_m_entre_x_mas_m(lam, 1.0), cerrada, rtol=2e-4)
        self.assertAlmostEqual(float(ob._esperanza_m_entre_x_mas_m(np.array([500.0]), np.array([2.0]))[0]), 2 / 502, places=6)


class CosteYRankingTests(unittest.TestCase):
    def test_coste(self):
        self.assertEqual(ob.coste_columnas(["1X2", "1X", "1"] + ["1"] * 11), 6)
        self.assertEqual(ob.coste_columnas(["X1", "21", "2X1"] + ["2"] * 11), 12)
        self.assertEqual(ob.coste_eur(24), 18.0)
        self.assertEqual(ob.normalizar_signos("2X1"), "1X2")
        self.assertEqual(ob.normalizar_signos(""), "1")

    def test_estructuras_dentro_de_presupuesto(self):
        for presupuesto in ob.PRESUPUESTOS_SOPORTADOS:
            for t, d, coste in ob.estructuras_posibles(presupuesto):
                self.assertLessEqual(coste, presupuesto)
                self.assertEqual(coste, 3 ** t * 2 ** d)
        self.assertIn((2, 4, 144), ob.estructuras_posibles(144))

    def test_ranking_doble_y_triple(self):
        probs = ob.matriz_probs([
            {"1": 70, "X": 20, "2": 10},   # favorito claro
            {"1": 45, "X": 35, "2": 20},   # mayor p2/p1 -> doble
            {"1": 36, "X": 30, "2": 34},   # menor p1+p2 -> triple
        ] + [{"1": 60, "X": 25, "2": 15}] * 11)
        ratios = ob.ratios_ranking(probs)
        ordenes = [ob.orden_signos(probs[i]) for i in range(14)]
        m = ob.asignar_estructura(ordenes, ratios, t=1, d=1)
        self.assertEqual(ob.signos_desde_mascara(m)[2], "1X2")
        self.assertEqual(ob.signos_desde_mascara(m)[1], "1X")
        self.assertEqual(ob.signos_desde_mascara(m)[0], "1")

    def test_contra_masa_cambia_el_signo_base(self):
        p = np.array([0.50, 0.28, 0.22])
        masa = np.array([0.80, 0.12, 0.08])
        self.assertEqual(ob.orden_signos(p)[0], 0)                       # argmax p = 1
        self.assertEqual(ob.orden_signos(p, masa, contra_masa=True)[0], 2)  # argmax p/s = 2


class OptimizarTests(unittest.TestCase):
    def setUp(self):
        self.probs = _probs_14()
        self.masa = _masa_14(self.probs)

    def test_busqueda_local_no_empeora_al_greedy(self):
        for objetivo in ob.OBJETIVOS:
            res = ob.optimizar(self.probs, self.masa, 24, objetivo=objetivo, recaudacion=2_000_000)
            greedy = res["comparaciones"]["mejor_estructura_sin_busqueda_local"]["valor_objetivo"]
            self.assertGreaterEqual(res["valor_objetivo"] + 1e-12, greedy, objetivo)

    def test_presupuesto_respetado_y_aprovechado(self):
        for presupuesto in (1, 2, 3, 6, 9, 16, 24, 48):
            res = ob.optimizar(self.probs, self.masa, presupuesto, objetivo="P13plus")
            self.assertLessEqual(res["columnas"], presupuesto)
            self.assertEqual(res["columnas"], ob.coste_columnas(res["signos"]))
            # P(>=13) es monotona en anadir signos: no se deja mas de la mitad sin usar
            self.assertGreater(res["columnas"] * 2, presupuesto)
            self.assertAlmostEqual(res["coste_eur"], res["columnas"] * 0.75, places=6)

    def test_determinista(self):
        a = ob.optimizar(self.probs, self.masa, 18, objetivo="premio_esperado", recaudacion=2_000_000)
        b = ob.optimizar(self.probs, self.masa, 18, objetivo="premio_esperado", recaudacion=2_000_000)
        self.assertEqual(a["signos"], b["signos"])
        self.assertEqual(a["valor_objetivo"], b["valor_objetivo"])
        self.assertEqual(a["detalle_partidos"], b["detalle_partidos"])

    def test_salida_completa(self):
        res = ob.optimizar(self.probs, self.masa, 16, objetivo="P14", contra_masa=True, recaudacion=2_000_000)
        for clave in ("signos", "columnas", "coste_eur", "P14", "P13plus", "P12plus", "P10plus",
                      "premio_esperado", "premio_por_categoria", "detalle_partidos", "comparaciones"):
            self.assertIn(clave, res)
        self.assertEqual(len(res["signos"]), 14)
        self.assertEqual(len(res["detalle_partidos"]), 14)
        for fila in res["detalle_partidos"]:
            self.assertIn("ratio_doble", fila)
            self.assertIn("ratio_triple", fila)
            self.assertIn("edge_p_entre_s", fila)
        for nombre in ("masa", "motor_fijos", "edge_p_entre_s"):
            self.assertEqual(res["comparaciones"][nombre]["columnas"], 1)
        # P14 con 16 columnas supera a cualquier columna sola
        self.assertGreater(res["P14"], res["comparaciones"]["motor_fijos"]["P14"])

    def test_p14_un_doble_va_al_mayor_ratio(self):
        probs = [{"1": 70, "X": 20, "2": 10}] * 13 + [{"1": 45, "X": 35, "2": 20}]
        res = ob.optimizar(probs, None, 2, objetivo="P14")
        self.assertEqual(res["signos"][13], "1X")
        self.assertEqual(res["columnas"], 2)

    def test_sin_masa_rechaza_premio(self):
        with self.assertRaises(ValueError):
            ob.optimizar(self.probs, None, 4, objetivo="premio_esperado")
        with self.assertRaises(ValueError):
            ob.optimizar(self.probs, self.masa, 4, objetivo="otro")


if __name__ == "__main__":
    unittest.main()
