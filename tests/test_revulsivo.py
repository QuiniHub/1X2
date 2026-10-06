import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from motor_prediccion_quiniela import ajustar_por_revulsivo

CESES = [{
    "equipo": "Valencia CF",
    "fecha_cese": "2026-09-13",
    "interino": "Oscar Sanchez",
    "fecha_nuevo": "2026-09-23",
    "nuevo": "Javier Aguirre",
}]
PROBS = {"1": 44.0, "X": 29.0, "2": 27.0}


class RevulsivoTests(unittest.TestCase):
    def test_debut_fuera_sube_el_signo_del_tecnico_nuevo(self):
        partido = {"local": "Real Racing Club de Santander", "visitante": "Valencia CF", "fecha": "2026-10-11"}
        p, riesgo, lecturas, traza = ajustar_por_revulsivo(
            PROBS, partido, ceses=CESES, contador=lambda e, d, h: 0
        )
        self.assertTrue(traza["activo"])
        self.assertEqual(traza["lado"], "visitante")
        self.assertEqual(traza["etapa"], "debut")
        self.assertGreater(p["2"], PROBS["2"])
        self.assertLess(p["1"], PROBS["1"])
        self.assertIn("FUERA", lecturas[0])
        self.assertAlmostEqual(sum(p.values()), 100.0, delta=0.5)

    def test_debut_en_casa_recorta_al_equipo_del_tecnico_nuevo(self):
        partido = {"local": "Valencia CF", "visitante": "Sevilla FC", "fecha": "2026-10-11"}
        p, riesgo, lecturas, traza = ajustar_por_revulsivo(
            PROBS, partido, ceses=CESES, contador=lambda e, d, h: 0
        )
        self.assertTrue(traza["activo"])
        self.assertEqual(traza["lado"], "local")
        self.assertLess(p["1"], PROBS["1"])
        self.assertIn("CASA", lecturas[0])

    def test_segundo_partido_aplica_mitad_de_efecto(self):
        partido = {"local": "Real Racing Club de Santander", "visitante": "Valencia CF", "fecha": "2026-10-11"}
        completo, _, _, _ = ajustar_por_revulsivo(PROBS, partido, ceses=CESES, contador=lambda e, d, h: 0)
        medio, _, _, traza = ajustar_por_revulsivo(PROBS, partido, ceses=CESES, contador=lambda e, d, h: 1)
        self.assertEqual(traza["etapa"], "2o partido")
        self.assertGreater(completo["2"], medio["2"])
        self.assertGreater(medio["2"], PROBS["2"])

    def test_efecto_agotado_con_dos_partidos_jugados(self):
        partido = {"local": "Real Racing Club de Santander", "visitante": "Valencia CF", "fecha": "2026-10-11"}
        p, riesgo, lecturas, traza = ajustar_por_revulsivo(PROBS, partido, ceses=CESES, contador=lambda e, d, h: 2)
        self.assertFalse(traza["activo"])
        self.assertEqual(p, PROBS)

    def test_equipo_sin_cese_no_se_toca(self):
        partido = {"local": "FC Barcelona", "visitante": "Getafe CF", "fecha": "2026-10-10"}
        p, riesgo, lecturas, traza = ajustar_por_revulsivo(PROBS, partido, ceses=CESES, contador=lambda e, d, h: 0)
        self.assertFalse(traza["activo"])
        self.assertEqual(p, PROBS)

    def test_integracion_real_p7_racing_valencia(self):
        # Caso real J12: con la fuente y los calendarios del repo, el motor
        # debe detectar solo el debut de Aguirre (Valencia visitante) y nada
        # en el resto de partidos de la jornada sin cese reciente.
        partido = {"local": "Real Racing Club de Santander", "visitante": "Valencia CF", "fecha": "2026-10-11"}
        p, riesgo, lecturas, traza = ajustar_por_revulsivo(PROBS, partido)
        self.assertTrue(traza["activo"], "el debut de Aguirre fuera debe activar el revulsivo con datos reales")
        self.assertEqual(traza["lado"], "visitante")


if __name__ == "__main__":
    unittest.main()
