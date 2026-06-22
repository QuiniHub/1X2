import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from aplicar_elige8_seguro import aplicar_elige8_seguro


def partido(num, top=62.0, sorpresa=20.0, indice=20.0):
    return {
        "num": num,
        "local": f"Local {num}",
        "visitante": f"Visitante {num}",
        "signo_final": "1",
        "signo_base": "1",
        "probabilidades": {"1": top, "X": 22.0, "2": 16.0},
        "incertidumbre": 55.0,
        "probabilidad_sorpresa": sorpresa,
        "indice_sorpresa_quinielistica": indice,
        "calidad_datos": "alta",
        "cobertura_sorpresa_sugerida": "FIJO",
    }


class Elige8ModosTests(unittest.TestCase):
    def test_bloqueo_conserva_estado_bloqueada(self):
        prediccion = {
            "estado": "bloqueada",
            "prediccion_disponible": False,
            "partidos": [partido(i) for i in range(1, 15)],
        }

        aplicar_elige8_seguro(prediccion)

        self.assertEqual(prediccion["estado"], "bloqueada")
        self.assertFalse(prediccion["publicar_prediccion"])
        self.assertTrue(prediccion["publicar_solo_boleto"])

    def test_crea_modos_conservador_y_rentable(self):
        prediccion = {
            "estado": "lista_para_publicar",
            "prediccion_disponible": True,
            "configuracion": {"elige8": True},
            "partidos": [partido(i) for i in range(1, 15)],
        }

        aplicar_elige8_seguro(prediccion)

        self.assertEqual(prediccion["configuracion"]["elige8_modo"], "conservador")
        self.assertEqual(prediccion["configuracion"]["elige8_modos_disponibles"], ["conservador", "rentable"])
        self.assertIn("conservador", prediccion["elige8_modos"]["modos"])
        self.assertIn("rentable", prediccion["elige8_modos"]["modos"])
        self.assertEqual(len(prediccion["elige8_modos"]["modos"]["conservador"]["seleccionados"]), 8)
        self.assertEqual(len(prediccion["elige8_modos"]["modos"]["rentable"]["seleccionados"]), 8)
        self.assertTrue(all("confianza_real" in item for item in prediccion["elige8_modos"]["modos"]["conservador"]["ranking"]))


if __name__ == "__main__":
    unittest.main()
