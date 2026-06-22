import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import control_calidad_actualizacion as control


class ControlCalidadActualizacionTests(unittest.TestCase):
    def test_prediccion_bloqueada_no_alerta_como_antigua(self):
        original = control.ultima_prediccion
        try:
            control.ultima_prediccion = lambda: {
                "jornada": 69,
                "estado": "bloqueada",
                "prediccion_disponible": False,
                "publicar_prediccion": False,
                "prediccion_permitida": False,
                "partidos": [{} for _ in range(14)],
                "motivo_bloqueo": "Cierre pendiente de la jornada anterior.",
            }
            alertas = []

            resumen = control.diagnosticar_prediccion(alertas, {"jornada": 70})

            self.assertEqual(alertas, [])
            self.assertTrue(resumen["retenida_por_compuerta"])
            self.assertIn("Cierre pendiente", resumen["motivo_bloqueo"])
        finally:
            control.ultima_prediccion = original


if __name__ == "__main__":
    unittest.main()
