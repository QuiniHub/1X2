import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from actualizar_resultados_directo import TZ_COMPETICION, partido_esta_programado_en_futuro


class ResultadosDirectoTests(unittest.TestCase):
    def test_partido_de_hoy_sin_hora_no_se_cierra_por_scraping(self):
        hoy = datetime.now(TZ_COMPETICION).date().isoformat()

        self.assertTrue(partido_esta_programado_en_futuro({
            "local": "Equipo A",
            "visitante": "Equipo B",
            "fecha": hoy,
            "hora": "--:--",
        }))

    def test_partido_futuro_sin_hora_no_se_cierra_por_scraping(self):
        manana = (datetime.now(TZ_COMPETICION).date() + timedelta(days=1)).isoformat()

        self.assertTrue(partido_esta_programado_en_futuro({
            "local": "Equipo A",
            "visitante": "Equipo B",
            "fecha": manana,
            "hora": "",
        }))


if __name__ == "__main__":
    unittest.main()
