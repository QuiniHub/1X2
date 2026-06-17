import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import jornada_objetivo_quiniela as objetivo


def escribir_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def escribir_jornada(base, numero):
    escribir_json(
        base / f"jornada_{numero}.json",
        {
            "jornada": numero,
            "partidos": [
                {
                    "num": idx + 1,
                    "local": f"Local {idx + 1}",
                    "visitante": f"Visitante {idx + 1}",
                    "signo_oficial": "Pendiente",
                }
                for idx in range(14)
            ],
        },
    )


class JornadaObjetivoQuinielaTests(unittest.TestCase):
    def test_no_salta_a_jornada_futura_cargada(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            jornadas = tmp / "data" / "jornadas"
            for numero in (68, 70):
                escribir_jornada(jornadas, numero)

            historial = tmp / "data" / "historial_quinielas.json"
            escribir_json(
                historial,
                {
                    "jornadas": [
                        {
                            "jornada": 67,
                            "nuestra_quiniela": "1 X 2 1 X 2 1 X 2 1 X 2 1 X",
                            "resultado_oficial": "11111111111111",
                            "validada": True,
                        },
                        {
                            "jornada": 68,
                            "nuestra_quiniela": "No validada",
                            "resultado_oficial": "Pendiente",
                            "validada": False,
                        },
                    ]
                },
            )
            quinielas = tmp / "data" / "quinielas_jugadas.json"
            escribir_json(quinielas, {"jugadas": []})

            self.assertEqual(
                objetivo.jornada_objetivo_prediccion(jornadas, historial, quinielas),
                68,
            )
            resumen = objetivo.resumen_jornada_objetivo(jornadas, historial, quinielas)
            self.assertEqual(resumen["ultima_jornada_aprendida"], 67)
            self.assertEqual(resumen["jornada_objetivo"], 68)
            self.assertEqual(resumen["jornadas_futuras_cargadas"], [70])
            self.assertEqual(resumen["jornadas_intermedias_faltantes"], [69])

    def test_objetivo_es_espera_si_no_esta_cargada(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            jornadas = tmp / "data" / "jornadas"
            escribir_jornada(jornadas, 70)
            historial = tmp / "data" / "historial_quinielas.json"
            escribir_json(
                historial,
                {
                    "jornadas": [
                        {
                            "jornada": 69,
                            "signos": ["1"] * 14,
                            "validada": True,
                        }
                    ]
                },
            )
            quinielas = tmp / "data" / "quinielas_jugadas.json"
            escribir_json(quinielas, {"jugadas": []})

            resumen = objetivo.resumen_jornada_objetivo(jornadas, historial, quinielas)
            self.assertEqual(resumen["jornada_objetivo"], 70)
            self.assertTrue(resumen["jornada_objetivo_cargada"])


if __name__ == "__main__":
    unittest.main()
