import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from actualizar_resultados_directo import (
    TZ_COMPETICION,
    buscar_resultado_final,
    inicio_partido,
    partido_ya_deberia_tener_resultado,
    partido_esta_programado_en_futuro,
)


class ResultadosDirectoTests(unittest.TestCase):
    def test_hora_cero_se_trata_como_desconocida_no_inicio_real(self):
        hoy = datetime.now(TZ_COMPETICION).date().isoformat()
        partido = {
            "local": "Equipo A",
            "visitante": "Equipo B",
            "fecha": hoy,
            "hora": "00:00",
        }

        self.assertIsNone(inicio_partido(partido))
        self.assertFalse(partido_ya_deberia_tener_resultado(partido))
        self.assertTrue(partido_esta_programado_en_futuro(partido))

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

    def test_alias_eeuu_detecta_resultado_con_puntos(self):
        texto = "Resultados quiniela jornada 67 EE.UU. - Paraguay 4 - 1 signo 1 final"

        self.assertEqual(
            buscar_resultado_final(texto, {"local": "EEUU", "visitante": "Paraguay"}),
            "4-1",
        )


if __name__ == "__main__":
    unittest.main()
