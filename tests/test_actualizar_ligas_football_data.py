import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import actualizar_ligas_football_data as alfd


class CodigoTemporadaDesdeUrlTests(unittest.TestCase):
    def test_extrae_el_codigo_de_una_url_football_data(self):
        url = "https://www.football-data.co.uk/mmz4281/2526/SP1.csv"
        self.assertEqual(alfd.codigo_temporada_desde_url(url), "2526")

    def test_devuelve_none_si_no_hay_codigo(self):
        self.assertIsNone(alfd.codigo_temporada_desde_url("https://example.com/otra-cosa.csv"))
        self.assertIsNone(alfd.codigo_temporada_desde_url(None))


class EsRetrocesoDeTemporadaTests(unittest.TestCase):
    def test_no_pisa_el_roster_2026_2027_con_fallback_a_temporada_anterior(self):
        data = {"temporada_detectada": "2026/2027"}
        fuentes = {"primera": {"url": "https://www.football-data.co.uk/mmz4281/2526/SP1.csv"}}
        self.assertTrue(alfd.es_retroceso_de_temporada(data, "primera", fuentes))

    def test_permite_escribir_si_football_data_ya_tiene_2627(self):
        data = {"temporada_detectada": "2026/2027"}
        fuentes = {"primera": {"url": "https://www.football-data.co.uk/mmz4281/2627/SP1.csv"}}
        self.assertFalse(alfd.es_retroceso_de_temporada(data, "primera", fuentes))

    def test_permite_escribir_si_todavia_no_se_ha_detectado_2026_2027(self):
        data = {"temporada_detectada": "2025/2026"}
        fuentes = {"primera": {"url": "https://www.football-data.co.uk/mmz4281/2526/SP1.csv"}}
        self.assertFalse(alfd.es_retroceso_de_temporada(data, "primera", fuentes))


if __name__ == "__main__":
    unittest.main()
