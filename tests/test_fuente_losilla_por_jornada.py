import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import motor_prediccion_quiniela as motor


def fuente(jornada):
    return {
        "probabilidades": {
            "jornada": jornada,
            "partidos": [
                {
                    "numero": 3,
                    "local": "VALENCIA",
                    "visitante": "R.MADRID",
                    "probabilidades_signo": {"1": 7.25, "X": 11.5, "2": 81.25},
                },
            ],
        },
        "escrutinio": {"x": 1},
    }


class FuenteLosillaPorJornadaTests(unittest.TestCase):
    """Caso real 8/11/2026: primera prediccion de la J21 con Losilla aun en la
    J20; el P3 Almeria-Andorra heredo por numero el 8/11/81 del Valencia-Madrid."""

    def test_mercado_de_otra_jornada_se_ignora(self):
        f = motor.fuente_losilla_para_jornada(fuente(20), 21)
        self.assertEqual(f["probabilidades"], {})
        self.assertEqual(f["escrutinio"], {"x": 1})  # el resto de la fuente se conserva
        partido = {"num": 3, "local": "UD Almeria", "visitante": "FC Andorra"}
        self.assertEqual(motor.mercado_losilla_signos(f, partido), {"1": 0.0, "X": 0.0, "2": 0.0})

    def test_mercado_de_la_misma_jornada_se_usa(self):
        f = motor.fuente_losilla_para_jornada(fuente(21), 21)
        partido = {"num": 3, "local": "UD Almeria", "visitante": "FC Andorra"}
        self.assertEqual(motor.mercado_losilla_signos(f, partido)["2"], 81.25)

    def test_sin_jornada_en_la_fuente_o_sin_objetivo_no_se_toca(self):
        sin_jornada = {"probabilidades": {"partidos": fuente(20)["probabilidades"]["partidos"]}}
        self.assertIs(motor.fuente_losilla_para_jornada(sin_jornada, 21), sin_jornada)
        f = fuente(20)
        self.assertIs(motor.fuente_losilla_para_jornada(f, None), f)


if __name__ == "__main__":
    unittest.main()
