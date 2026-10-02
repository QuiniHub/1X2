import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from modelo_dixon_coles import _tau, clave_equipo, shin_devig
from motor_prediccion_quiniela import PESO_DIXON_COLES, ajustar_por_dixon_coles


class ShinDevigTests(unittest.TestCase):
    def test_probabilidades_suman_uno_y_quitan_margen(self):
        p = shin_devig((2.10, 3.30, 3.60))
        self.assertAlmostEqual(sum(p.values()), 1.0, places=6)
        # el margen bruto de esas cuotas es ~5.7%; la prob justa del favorito
        # debe quedar por debajo de su inversa bruta (1/2.10 = 47.6%)
        self.assertLess(p["1"], 1 / 2.10)

    def test_shin_recorta_menos_al_favorito_que_la_normalizacion(self):
        # El margen vive sobre todo en los longshots (Shin): con un favorito
        # claro, Shin debe dejarle MAS probabilidad que el reparto proporcional.
        cuotas = (1.20, 6.0, 12.0)
        inv = [1 / c for c in cuotas]
        norm = inv[0] / sum(inv)
        shin = shin_devig(cuotas)["1"]
        self.assertGreater(shin, norm)

    def test_cuotas_invalidas_devuelven_none(self):
        self.assertIsNone(shin_devig((0, 3.0, 4.0)))
        self.assertIsNone(shin_devig((None, 3.0, 4.0)))
        self.assertIsNone(shin_devig(("x", 3.0, 4.0)))


class TauDixonColesTests(unittest.TestCase):
    def test_rho_negativo_sube_los_empates_cortos(self):
        # rho < 0 (lo que aprende el modelo con datos reales) debe AUMENTAR
        # la probabilidad de 0-0 y 1-1 y recortar 1-0/0-1 -la correccion
        # anti-X que motivo la integracion.
        lam, mu, rho = 1.3, 1.1, -0.05
        self.assertGreater(_tau(0, 0, lam, mu, rho), 1.0)
        self.assertGreater(_tau(1, 1, lam, mu, rho), 1.0)
        self.assertLess(_tau(1, 0, lam, mu, rho), 1.0)
        self.assertLess(_tau(0, 1, lam, mu, rho), 1.0)
        self.assertEqual(_tau(2, 1, lam, mu, rho), 1.0)


class ClaveEquipoTests(unittest.TestCase):
    def test_alias_historico_football_data(self):
        # el historico usa nombres cortos; los calendarios, oficiales
        self.assertEqual(clave_equipo("Athletic Club"), clave_equipo("Ath Bilbao"))
        self.assertEqual(clave_equipo("Rayo Vallecano de Madrid"), clave_equipo("Vallecano"))
        self.assertEqual(clave_equipo("Real Sporting de Gijon"), clave_equipo("Sp Gijon"))
        self.assertNotEqual(clave_equipo("Real Madrid"), clave_equipo("Atletico de Madrid"))


class AjusteMotorTests(unittest.TestCase):
    def test_mezcla_con_peso_configurado(self):
        probs = {"1": 50.0, "X": 30.0, "2": 20.0}
        dc = {"1": 0.30, "X": 0.40, "2": 0.30}
        nuevo, traza = ajustar_por_dixon_coles(
            probs, {"local": "A", "visitante": "B"}, proveedor=lambda l, v: dc
        )
        self.assertTrue(traza["activo"])
        esperado_1 = PESO_DIXON_COLES * 30.0 + (1 - PESO_DIXON_COLES) * 50.0
        self.assertAlmostEqual(nuevo["1"], esperado_1, delta=1.0)
        self.assertAlmostEqual(sum(nuevo.values()), 100.0, delta=0.5)
        # con rho/empate alto del D-C, la X del motor debe subir
        self.assertGreater(nuevo["X"], probs["X"])

    def test_sin_cobertura_no_toca_nada(self):
        probs = {"1": 50.0, "X": 30.0, "2": 20.0}
        nuevo, traza = ajustar_por_dixon_coles(
            probs, {"local": "Liga F (F)", "visitante": "Otra (F)"}, proveedor=lambda l, v: None
        )
        self.assertFalse(traza["activo"])
        self.assertEqual(nuevo, probs)

    def test_proveedor_que_explota_no_rompe_el_motor(self):
        def proveedor_roto(l, v):
            raise RuntimeError("boom")
        # el proveedor por defecto traga excepciones; aqui se simula un
        # proveedor inyectado que explota: ajustar debe dejarlo pasar como
        # esta (el guard de excepciones vive en _proveedor_dixon_coles)
        probs = {"1": 40.0, "X": 30.0, "2": 30.0}
        with self.assertRaises(RuntimeError):
            ajustar_por_dixon_coles(probs, {"local": "A", "visitante": "B"}, proveedor=proveedor_roto)


if __name__ == "__main__":
    unittest.main()
