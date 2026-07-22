import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import construir_memoria_ia as cmi


def equipo(nombre, posicion=1):
    return {
        "posicion": posicion,
        "equipo": nombre,
        "pj": 0,
        "g": 0,
        "e": 0,
        "p": 0,
        "gf": 0,
        "gc": 0,
        "dg": 0,
        "pts": 0,
        "racha_actual": [],
        "tendencias": {},
    }


class ObtenerTemporadaDetectadaTests(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self._original = cmi.CLASIFICACIONES_OFICIALES

    def tearDown(self):
        cmi.CLASIFICACIONES_OFICIALES = self._original

    def test_lee_el_flag_real(self):
        ruta = Path(self._tmpdir.name) / "clasificaciones_oficiales.json"
        ruta.write_text(json.dumps({"temporada_detectada": "2026/2027"}), encoding="utf-8")
        cmi.CLASIFICACIONES_OFICIALES = ruta
        self.assertEqual(cmi.obtener_temporada_detectada(), "2026/2027")

    def test_default_si_falta(self):
        ruta = Path(self._tmpdir.name) / "no_existe.json"
        cmi.CLASIFICACIONES_OFICIALES = ruta
        self.assertEqual(cmi.obtener_temporada_detectada(), "2025/2026")


class ClasificacionFinalTests(unittest.TestCase):
    def test_conserva_temporada_detectada(self):
        ligas = {
            "primera": {"equipos": [equipo("FC Barcelona", 1)]},
            "segunda": {"equipos": [equipo("Real Oviedo", 1)]},
        }
        clasificacion_final = cmi.construir_clasificaciones(ligas)
        clasificacion_final["temporada_detectada"] = "2026/2027"

        self.assertEqual(clasificacion_final["temporada_detectada"], "2026/2027")
        self.assertEqual(clasificacion_final["primera"][0]["equipo"], "FC Barcelona")
        self.assertEqual(clasificacion_final["segunda"][0]["equipo"], "Real Oviedo")


if __name__ == "__main__":
    unittest.main()
