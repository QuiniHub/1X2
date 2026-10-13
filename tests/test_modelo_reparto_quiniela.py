import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import modelo_reparto_quiniela as mrq


class NormalizarProbsTests(unittest.TestCase):
    def test_acepta_porcentajes_y_suma_uno(self):
        probs = mrq.normalizar_probs({"1": 50, "X": 30, "2": 20})
        self.assertAlmostEqual(sum(probs.values()), 1.0)
        self.assertAlmostEqual(probs["1"], 0.5)

    def test_sin_datos_devuelve_uniforme(self):
        probs = mrq.normalizar_probs({})
        self.assertAlmostEqual(probs["X"], 1 / 3)


class DistribucionMasaTests(unittest.TestCase):
    def test_un_partido_determinista(self):
        dist = mrq.distribucion_aciertos_masa([{"1": 100, "X": 0, "2": 0}], ["1"])
        self.assertAlmostEqual(dist[0], 0.0)
        self.assertAlmostEqual(dist[1], 1.0)

    def test_suma_uno_con_14_partidos(self):
        pct = [{"1": 45, "X": 30, "2": 25}] * 14
        dist = mrq.distribucion_aciertos_masa(pct, ["X"] * 14)
        self.assertAlmostEqual(sum(dist), 1.0, places=9)
        self.assertEqual(len(dist), 15)

    def test_binomial_conocida(self):
        # 2 partidos con p=0.5 de acierto de la masa -> 0.25/0.5/0.25
        pct = [{"1": 50, "X": 50, "2": 0}] * 2
        dist = mrq.distribucion_aciertos_masa(pct, ["1", "1"])
        self.assertAlmostEqual(dist[0], 0.25)
        self.assertAlmostEqual(dist[1], 0.5)
        self.assertAlmostEqual(dist[2], 0.25)


class PremioNetoTests(unittest.TestCase):
    def test_caso_real_j1_2627(self):
        """J1 real: 1 acertante de 14, fondo 16% de 1.707.590,25 EUR; Losilla
        publico 226.571,55 EUR netos (= bruto - 20% del exceso de 40.000)."""
        bruto = 0.16 * 1_707_590.25
        self.assertAlmostEqual(mrq.premio_neto(bruto), 226_571.55, places=1)

    def test_por_debajo_de_la_exencion_no_se_toca(self):
        self.assertAlmostEqual(mrq.premio_neto(17_500.75), 17_500.75)


class PremioCategoriaTests(unittest.TestCase):
    def test_caso_real_j12_categoria_14(self):
        """J12 real: recaudacion 3.500.149,50, 32 acertantes de 14 ->
        17.500,75 EUR por apuesta (exacto en el escrutinio oficial)."""
        premio = mrq.premio_categoria_modelo(14, 32, 3_500_149.50)
        self.assertAlmostEqual(premio, 17_500.75, places=2)

    def test_caso_real_j12_quinta_no_se_paga(self):
        """J12 real: la 5a categoria salia a ~1,31 EUR y LAE pago 0,00."""
        premio = mrq.premio_categoria_modelo(10, 240_653, 3_500_149.50)
        self.assertEqual(premio, 0.0)

    def test_caso_real_j1_quinta_si_se_paga(self):
        """J1 real: 13.646 acertantes de 10 con el 9%% de 1.707.590,25 ->
        11,26 EUR por apuesta."""
        premio = mrq.premio_categoria_modelo(10, 13_646, 1_707_590.25)
        self.assertAlmostEqual(premio, 11.26, places=2)


class PremioEsperadoTests(unittest.TestCase):
    def test_sin_otros_acertantes_cobra_el_fondo_neto(self):
        esperado = mrq.premio_esperado_si_acertamos(14, 0.0, 1_000_000.0)
        self.assertAlmostEqual(esperado, mrq.premio_neto(160_000.0))

    def test_con_mucha_masa_tiende_a_fondo_entre_lam(self):
        esperado = mrq.premio_esperado_si_acertamos(12, 1000.0, 1_000_000.0)
        self.assertAlmostEqual(esperado, 75_000.0 / 1000.0, places=1)

    def test_premio_minimo_devuelve_cero(self):
        # fondo 9% de 1M = 90.000; lam 200.000 -> ~0,45 EUR < 1,5 -> 0
        self.assertEqual(mrq.premio_esperado_si_acertamos(10, 200_000.0, 1_000_000.0), 0.0)


class EvaluadorEVTests(unittest.TestCase):
    def _datos(self):
        p_real = [{"1": 50, "X": 50, "2": 0}] * 14
        pct_masa = [{"1": 95, "X": 4, "2": 1}] * 14
        return p_real, pct_masa

    def test_determinista_con_la_misma_semilla(self):
        p_real, pct_masa = self._datos()
        a = mrq.EvaluadorEV(p_real, pct_masa, n_muestras=300, semilla=7).evaluar(["1"] * 14)
        b = mrq.EvaluadorEV(p_real, pct_masa, n_muestras=300, semilla=7).evaluar(["1"] * 14)
        self.assertEqual(a["ev_eur"], b["ev_eur"])

    def test_columna_rara_vale_mas_que_la_popular(self):
        """Con la misma probabilidad real de acertar (50/50 entre 1 y X), la
        columna que NO comparte signos con la masa debe tener mas EV: es el
        principio pari-mutuel que motiva todo el candidato 3."""
        p_real, pct_masa = self._datos()
        evaluador = mrq.EvaluadorEV(p_real, pct_masa, n_muestras=2000, semilla=13)
        popular = evaluador.evaluar(["1"] * 14)
        rara = evaluador.evaluar(["X"] * 14)
        self.assertGreater(rara["ev_eur"], popular["ev_eur"])

    def test_mas_columnas_no_bajan_el_ev(self):
        p_real, pct_masa = self._datos()
        evaluador = mrq.EvaluadorEV(p_real, pct_masa, n_muestras=500, semilla=3)
        sencillo = evaluador.evaluar(["X"] * 14)
        con_doble = evaluador.evaluar(["1X"] + ["X"] * 13)
        self.assertGreaterEqual(con_doble["ev_eur"], sencillo["ev_eur"])


class ColaExactaTests(unittest.TestCase):
    def test_formas_cerradas_igualan_a_la_convolucion(self):
        """Las categorias 12-14 exactas (simetricas elementales) deben dar lo
        mismo que enumerar los resultados a distancia <=2 de cada columna y
        pasar cada uno por la Poisson-binomial de referencia (convolucion)."""
        import itertools
        import random

        random.seed(4)
        p_real, pct = [], []
        for _ in range(14):
            p_real.append({"1": random.uniform(5, 80), "X": random.uniform(5, 80), "2": random.uniform(5, 80)})
            pct.append({"1": random.uniform(1, 90), "X": random.uniform(1, 90), "2": random.uniform(1, 90)})
        boleto = ["1X"] + ["2", "1", "X", "2", "1", "1", "X", "1", "2", "1", "X", "1", "1"]
        recaudacion = 2_000_000.0
        ev = mrq.EvaluadorEV(p_real, pct, recaudacion=recaudacion, n_muestras=10, semilla=1)
        e12, e13, e14 = ev._ev_cola_exacta(boleto)

        probs, masa = ev._probs, ev._masa
        apuestas = recaudacion / mrq.PRECIO_APUESTA
        opciones = [[mrq.SIGNOS.index(s) for s in mrq.SIGNOS if s in b] for b in boleto]
        pct_listas = [{mrq.SIGNOS[i]: masa[j, i] for i in range(3)} for j in range(14)]

        def pmasa_k(res, k):
            reales = [mrq.SIGNOS[r] for r in res]
            return mrq.distribucion_aciertos_masa(pct_listas, reales)[k]

        ref = {12: 0.0, 13: 0.0, 14: 0.0}
        for col in itertools.product(*opciones):
            p0 = 1.0
            for j in range(14):
                p0 *= probs[j, col[j]]
            ref[14] += p0 * mrq.premio_esperado_si_acertamos(14, apuestas * pmasa_k(col, 14), recaudacion)
            for i in range(14):
                for s in range(3):
                    if s == col[i]:
                        continue
                    r1 = list(col)
                    r1[i] = s
                    pr = p0 * probs[i, s] / probs[i, col[i]]
                    ref[13] += pr * mrq.premio_esperado_si_acertamos(13, apuestas * pmasa_k(r1, 13), recaudacion)
                    for j in range(i + 1, 14):
                        for t in range(3):
                            if t == col[j]:
                                continue
                            r2 = list(r1)
                            r2[j] = t
                            pr2 = pr * probs[j, t] / probs[j, col[j]]
                            ref[12] += pr2 * mrq.premio_esperado_si_acertamos(12, apuestas * pmasa_k(r2, 12), recaudacion)

        self.assertAlmostEqual(e14, ref[14], places=6)
        self.assertAlmostEqual(e13, ref[13], places=6)
        self.assertAlmostEqual(e12, ref[12], places=6)


class ColumnasBoletoTests(unittest.TestCase):
    def test_cuenta_dobles_y_triples(self):
        self.assertEqual(mrq.columnas_boleto(["1"] * 14), 1)
        self.assertEqual(mrq.columnas_boleto(["1X", "1X2"] + ["1"] * 12), 6)

    def test_signo_vacio_cuenta_como_fijo(self):
        self.assertEqual(mrq.columnas_boleto([""] * 14), 1)


if __name__ == "__main__":
    unittest.main()
