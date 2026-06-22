import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import memoria_autonoma_quiniela as memoria


def escribir_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


class MemoriaAutonomaQuinielaTests(unittest.TestCase):
    def test_construye_historial_perfiles_rendimiento_y_surprise_score(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            partidos = [
                {
                    "num": 1,
                    "local": "Equipo A",
                    "visitante": "Equipo B",
                    "fecha": "2026-06-01",
                    "resultado": "0-1",
                    "signo_oficial": "2",
                },
                *[
                    {
                        "num": idx,
                        "local": f"Local {idx}",
                        "visitante": f"Visitante {idx}",
                        "fecha": "2026-06-01",
                        "resultado": "1-0",
                        "signo_oficial": "1",
                    }
                    for idx in range(2, 15)
                ],
            ]
            escribir_json(root / "data" / "jornadas" / "jornada_1.json", {"jornada": 1, "fecha": "2026-06-01", "partidos": partidos})
            escribir_json(
                root / "data" / "predicciones" / "jornada_1.json",
                {
                    "jornada": 1,
                    "prediccion_disponible": True,
                    "partidos": [
                        {
                            "num": 1,
                            "local": "Equipo A",
                            "visitante": "Equipo B",
                            "signo_final": "1",
                            "tipo": "FIJO",
                            "elige8": True,
                            "probabilidades": {"1": 72.0, "X": 18.0, "2": 10.0},
                            "incertidumbre": 42.0,
                            "probabilidad_sorpresa": 18.0,
                            "calidad_datos": "alta",
                        },
                        *[
                            {
                                "num": idx,
                                "local": f"Local {idx}",
                                "visitante": f"Visitante {idx}",
                                "signo_final": "1",
                                "tipo": "FIJO",
                                "probabilidades": {"1": 65.0, "X": 22.0, "2": 13.0},
                                "incertidumbre": 50.0,
                                "probabilidad_sorpresa": 20.0,
                                "calidad_datos": "alta",
                            }
                            for idx in range(2, 15)
                        ],
                    ],
                },
            )

            estado = memoria.actualizar_memoria_autonoma(root)

            historial = json.loads((root / "data" / "memoria_ia" / "historial_permanente.json").read_text(encoding="utf-8"))
            perfiles = json.loads((root / "data" / "memoria_ia" / "perfiles_equipos.json").read_text(encoding="utf-8"))
            rendimiento = json.loads((root / "data" / "memoria_ia" / "rendimiento_jornadas.json").read_text(encoding="utf-8"))

            self.assertEqual(estado["totales"]["partidos"], 14)
            self.assertEqual(historial["retencion"], "permanente_no_borrar")
            self.assertGreater(historial["partidos"][0]["surprise_score"], 80)
            self.assertIn("equipo a", perfiles["equipos"])
            self.assertIn("resumen_ponderado", perfiles["equipos"]["equipo a"])
            self.assertEqual(rendimiento["jornadas"]["1"]["partidos_cerrados"], 14)
            self.assertIn("ranking_elige8_confianza_real", rendimiento["jornadas"]["1"])


if __name__ == "__main__":
    unittest.main()
