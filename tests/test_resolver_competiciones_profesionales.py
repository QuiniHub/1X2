import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from resolver_competiciones_profesionales import normalizar, resolver


class ResolverCompeticionesProfesionalesTests(unittest.TestCase):
    def test_abreviaturas_espanolas_no_caen_en_liga_extranjera(self):
        cats = {
            "primera": {"girona", "rayo vallecano madrid", "oviedo", "villarreal"},
            "segunda": set(),
            "mundial": set(),
            "selecciones": set(),
        }

        self.assertEqual(normalizar("R. Vallecano"), "rayo vallecano madrid")
        self.assertEqual(normalizar("R. Oviedo"), "oviedo")
        self.assertEqual(
            resolver({"local": "Girona", "visitante": "R. Vallecano"}, cats)["competicion"],
            "primera_division",
        )
        self.assertEqual(
            resolver({"local": "Villarreal", "visitante": "R. Oviedo"}, cats)["competicion"],
            "primera_division",
        )


if __name__ == "__main__":
    unittest.main()
