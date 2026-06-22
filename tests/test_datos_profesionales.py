import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from datos_profesionales import buscar_partido, normalizar_payload


class DatosProfesionalesTests(unittest.TestCase):
    def test_normaliza_payload_profesional_completo(self):
        datos = normalizar_payload(
            {
                "temporada_objetivo": "2026/2027",
                "jornadas": {
                    "1": {
                        "partidos": [
                            {
                                "num": 1,
                                "local": "Equipo Local",
                                "visitante": "Equipo Visitante",
                                "calendario": {
                                    "fecha": "2026-08-16",
                                    "hora": "21:00",
                                    "temporada": "2026/2027",
                                    "fuente": "proveedor oficial",
                                },
                                "cuotas": {"1": 1.80, "X": 3.40, "2": 4.80, "fuente": "bookmaker"},
                                "bajas": {
                                    "local": {
                                        "lesiones": [{"jugador": "Central titular", "impacto": 2.4, "titular": True}],
                                        "sanciones": ["Mediocentro"],
                                    },
                                    "visitante": {"dudas": [{"jugador": "Delantero", "impacto": 0.8}]},
                                },
                                "alineaciones": {
                                    "local": {"titulares_probables": [f"L{i}" for i in range(11)], "confianza": 0.82},
                                    "visitante": {"titulares_probables": [f"V{i}" for i in range(10)], "dudas": ["V9"]},
                                },
                                "clasificacion": {
                                    "temporada": "2026/2027",
                                    "local": {"posicion": 4, "puntos": 18},
                                    "visitante": {"posicion": 14, "puntos": 9},
                                    "fuente": "tabla oficial",
                                },
                            }
                        ]
                    }
                },
            },
            origen="test",
        )

        partido = buscar_partido(datos, 1, {"local": "Equipo Local", "visitante": "Equipo Visitante"})

        self.assertEqual(datos["estado_global"], "operativo")
        self.assertEqual(datos["temporada_objetivo"], "2026/2027")
        self.assertEqual(datos["resumen"]["cuotas"], 1)
        self.assertEqual(datos["resumen"]["bajas_estructuradas"], 1)
        self.assertEqual(datos["resumen"]["alineaciones_probables"], 1)
        self.assertEqual(datos["resumen"]["calendario_oficial"], 1)
        self.assertEqual(datos["resumen"]["clasificacion_oficial"], 1)
        self.assertAlmostEqual(sum(partido["cuotas"]["probabilidades_implicitas"].values()), 100.0, places=1)
        self.assertGreater(partido["bajas"]["local"]["impacto_total"], partido["bajas"]["visitante"]["impacto_total"])
        self.assertTrue(partido["capas_disponibles"]["clasificacion_oficial"])


if __name__ == "__main__":
    unittest.main()
