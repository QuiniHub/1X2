import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from motor_prediccion_quiniela import cobertura_automatica, coste


def partido(num, probs, incertidumbre=120, sorpresa=60):
    return {
        "num": num,
        "local": f"Local {num}",
        "visitante": f"Visitante {num}",
        "probabilidades": probs,
        "incertidumbre": incertidumbre,
        "probabilidad_sorpresa": sorpresa,
    }


class MotorPrediccionTests(unittest.TestCase):
    def test_coste_elige8_es_por_apuesta(self):
        resultado = coste(dobles=2, triples=1, elige8=True)

        self.assertEqual(resultado["apuestas"], 12)
        self.assertEqual(resultado["importe_quiniela"], 9.0)
        self.assertEqual(resultado["importe_elige8"], 6.0)
        self.assertEqual(resultado["importe_total"], 15.0)

    def test_cobertura_automatica_evitar_14_fijos_en_jornada_abierta(self):
        evaluados = [
            partido(i, {"1": 35.0, "X": 34.0, "2": 31.0})
            for i in range(1, 15)
        ]

        dobles, triples, detalle = cobertura_automatica(evaluados)

        self.assertGreaterEqual(dobles, 4)
        self.assertGreaterEqual(triples, 1)
        self.assertIn("Cobertura automatica", detalle)

    def test_cobertura_automatica_respeta_boleto_sencillo_si_no_hay_riesgo(self):
        evaluados = [
            partido(i, {"1": 72.0, "X": 18.0, "2": 10.0}, incertidumbre=45, sorpresa=20)
            for i in range(1, 15)
        ]

        dobles, triples, detalle = cobertura_automatica(evaluados)

        self.assertEqual(dobles, 0)
        self.assertEqual(triples, 0)
        self.assertIn("boleto sencillo", detalle)


if __name__ == "__main__":
    unittest.main()
