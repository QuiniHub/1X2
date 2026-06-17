import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import aplicar_memoria_mundial_prediccion as aplicar
import generar_memoria_mundial_2026 as generar


class MemoriaMundial2026Tests(unittest.TestCase):
    def test_genera_memoria_y_aplica_a_partido_con_dos_selecciones(self):
        data = {
            "resultados": [
                {"local": "Australia", "visitante": "Turquía", "resultado": "2-0", "fecha": "2026-06-13"},
                {"local": "EEUU", "visitante": "Paraguay", "resultado": "4-1", "fecha": "2026-06-12"},
            ]
        }
        memoria = generar.construir_memoria(data)
        partido = {
            "num": 1,
            "local": "EEUU",
            "visitante": "Australia",
            "probabilidades": {"1": 33.0, "X": 34.0, "2": 33.0},
            "origen_probabilidades": "fallback_posicion",
            "trazabilidad_datos": {},
        }
        actualizado = aplicar.aplicar_mundial_a_partido(partido, memoria["equipos"])
        self.assertEqual(actualizado["origen_probabilidades"], "mundial_2026_resultados_y_modelo_base")
        self.assertTrue(actualizado["memoria_mundial_2026"]["aplicado"])
        self.assertTrue(actualizado["trazabilidad_datos"]["memoria_estadistica"]["local"])
        self.assertTrue(actualizado["trazabilidad_datos"]["memoria_estadistica"]["visitante"])
        self.assertNotEqual(actualizado["probabilidades"], {"1": 33.0, "X": 34.0, "2": 33.0})

    def test_mantiene_alerta_si_falta_un_equipo(self):
        memoria = generar.construir_memoria({"resultados": [{"local": "Australia", "visitante": "Turquía", "resultado": "2-0"}]})
        partido = {
            "num": 2,
            "local": "Australia",
            "visitante": "Equipo Fantasma",
            "probabilidades": {"1": 33.0, "X": 34.0, "2": 33.0},
            "origen_probabilidades": "fallback_posicion",
            "trazabilidad_datos": {},
        }
        actualizado = aplicar.aplicar_mundial_a_partido(partido, memoria["equipos"])
        self.assertFalse(actualizado["diagnostico_calidad"]["mundial_2026"]["aplicado"])
        self.assertEqual(actualizado["calidad_datos"], "baja")


if __name__ == "__main__":
    unittest.main()
