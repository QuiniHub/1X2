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

    def test_celta_b_no_cae_en_liga_extranjera(self):
        # Bug real (jornada 1 de LaLiga 26/27, 2026-08-11): la fuente de
        # quinielafutbol.info usa el nombre antiguo "Celta B" para el filial
        # del Celta en Segunda -sin el alias, no coincidia con "RC Celta
        # Fortuna" (el nombre real en clasificaciones.json) y el partido
        # caia en liga_extranjera, activando el modelo equivocado.
        cats = {
            "primera": set(),
            "segunda": {"cadiz", "celta fortuna"},
            "mundial": set(),
            "selecciones": set(),
        }

        self.assertEqual(normalizar("Celta B"), "celta fortuna")
        self.assertEqual(
            resolver({"local": "Cadiz CF", "visitante": "Celta B"}, cats)["competicion"],
            "segunda_division",
        )


if __name__ == "__main__":
    unittest.main()
